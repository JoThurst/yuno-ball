"""
Cross-validate NBA daily data in the database against NBA sources.

Critical checks fail the process (exit 1). Warning checks are reported but
do not fail (useful in offseason when odds/injuries are sparse).

Usage:
    python scripts/validate_daily_data.py
    python scripts/validate_daily_data.py --season 2025-26
    python scripts/validate_daily_data.py --date 2026-03-03
    python scripts/validate_daily_data.py --offline   # DB-only checks (no CDN)
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.absolute()
project_root_str = str(project_root)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

from dotenv import load_dotenv
load_dotenv()

import os
import logging
import requests
from sqlalchemy import func

from db_config import init_db

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
init_db(DATABASE_URL)

# Ensure app package is importable as a proper package (same pattern as daily_fetch)
import app  # noqa: F401
from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
from app.models.player_analytics_snapshot_sqlalchemy import (
    PLAYER_SNAPSHOT_CALCULATION_VERSION,
    PlayerConsecutiveStreakSnapshotORM,
    PlayerConsistencySnapshotORM,
    PlayerHeatIndexSnapshotORM,
    PlayerStatWindowSnapshotORM,
)
from app.models.team_analytics_snapshot_sqlalchemy import (
    TEAM_SNAPSHOT_CALCULATION_VERSION,
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.services.player_snapshot_service import feature_cutoff_for_slate
from app.services.schedule_result_reconciliation_service import (
    build_schedule_result_plan,
    load_schedule_result_sources,
)
from app.utils.season_utils import get_current_season

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("validate_daily_data")

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

# Severity
CRITICAL = "critical"
WARNING = "warning"


class CheckResult:
    def __init__(self, name: str, severity: str, passed: bool, message: str, details: Any = None):
        self.name = name
        self.severity = severity
        self.passed = passed
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "severity": self.severity,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


def _parse_cdn_final_games(payload: dict, target_date: date) -> Dict[str, dict]:
    """Map game_id -> {home_score, away_score, status} for games on target_date (EST)."""
    import pytz
    eastern = pytz.timezone("America/New_York")
    games = {}

    for game_date_block in payload.get("gameDates", []):
        for game in game_date_block.get("games", []):
            raw = game.get("gameDateTimeUTC")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                local_date = dt.astimezone(eastern).date()
            except (ValueError, TypeError):
                continue
            if local_date != target_date:
                continue
            game_id = str(game.get("gameId"))
            games[game_id] = {
                "status": game.get("gameStatus"),
                "home_score": game.get("homeTeam", {}).get("score"),
                "away_score": game.get("awayTeam", {}).get("score"),
                "home_team_id": game.get("homeTeam", {}).get("teamId"),
                "away_team_id": game.get("awayTeam", {}).get("teamId"),
            }
    return games


def check_schedule_completeness(
    db, season: str, target_date: date, offline: bool
) -> CheckResult:
    """Compare DB schedule for target_date vs CDN (or presence-only if offline)."""
    db_games = GameScheduleORM.get_by_date(target_date, db=db)
    db_game_ids = {str(g["game_id"]) for g in db_games}

    if offline:
        # Offseason: empty slate is OK
        if not db_game_ids:
            return CheckResult(
                "schedule_completeness",
                CRITICAL,
                True,
                f"No DB games on {target_date} (offline mode — OK if offseason)",
                {"db_count": 0},
            )
        return CheckResult(
            "schedule_completeness",
            CRITICAL,
            True,
            f"DB has {len(db_game_ids)} unique games on {target_date} (offline)",
            {"db_count": len(db_game_ids)},
        )

    try:
        resp = requests.get(NBA_SCHEDULE_CDN_URL, timeout=30)
        resp.raise_for_status()
        payload = resp.json().get("leagueSchedule", {})
        cdn_games = _parse_cdn_final_games(payload, target_date)
    except Exception as exc:
        return CheckResult(
            "schedule_completeness",
            WARNING,
            False,
            f"Could not reach NBA CDN for schedule check: {exc}",
        )

    if not cdn_games and not db_game_ids:
        return CheckResult(
            "schedule_completeness",
            CRITICAL,
            True,
            f"No games on {target_date} in CDN or DB (offseason / rest day)",
            {"cdn_count": 0, "db_count": 0},
        )

    missing_in_db = set(cdn_games) - db_game_ids
    extra_in_db = db_game_ids - set(cdn_games)

    # Each game has 2 DB rows (home/away); compare unique IDs
    passed = len(missing_in_db) == 0
    msg = (
        f"CDN={len(cdn_games)} DB={len(db_game_ids)} "
        f"missing_in_db={len(missing_in_db)} extra_in_db={len(extra_in_db)}"
    )
    return CheckResult(
        "schedule_completeness",
        CRITICAL,
        passed,
        msg,
        {
            "missing_in_db": sorted(missing_in_db)[:20],
            "extra_in_db": sorted(extra_in_db)[:20],
        },
    )


def check_schedule_result_consistency(
    db, season: str, target_date: date
) -> CheckResult:
    """Fail when local final team-game facts can repair null schedule results."""
    schedule_rows, team_game_rows = load_schedule_result_sources(
        db,
        season=season,
        from_date=target_date,
        to_date=target_date,
    )
    source_game_ids = {row.game_id for row in team_game_rows}
    if not source_game_ids:
        return CheckResult(
            "schedule_result_consistency",
            CRITICAL,
            True,
            f"No final team-game sources on {target_date}; result reconciliation skipped",
            {"source_games": 0},
        )

    source_schedule_rows = [
        row for row in schedule_rows if row.game_id in source_game_ids
    ]
    plan = build_schedule_result_plan(source_schedule_rows, team_game_rows)
    passed = plan.eligible_games == 0 and len(plan.issues) == 0
    return CheckResult(
        "schedule_result_consistency",
        CRITICAL,
        passed,
        (
            f"Team-game source games={len(source_game_ids)}; "
            f"schedule games needing reconciliation={plan.eligible_games}; "
            f"blocked source pairs={len(plan.issues)}"
        ),
        {
            "eligible_game_ids": sorted({row.game_id for row in plan.updates})[:25],
            "issues": [
                {"game_id": issue.game_id, "reason": issue.reason}
                for issue in plan.issues[:25]
            ],
        },
    )


def check_final_scores(db, season: str, lookback_days: int = 7) -> CheckResult:
    """Completed games in last N days should have W/L and matching home/away results."""
    cutoff = datetime.now() - timedelta(days=lookback_days)
    rows = (
        db.query(GameScheduleORM)
        .filter(
            GameScheduleORM.season == season,
            GameScheduleORM.game_date >= cutoff,
            GameScheduleORM.result.isnot(None),
        )
        .all()
    )

    by_game: Dict[str, List[GameScheduleORM]] = defaultdict(list)
    for row in rows:
        by_game[str(row.game_id)].append(row)

    mismatches = []
    for game_id, entries in by_game.items():
        if len(entries) < 2:
            mismatches.append({"game_id": game_id, "issue": "fewer_than_2_rows"})
            continue
        results = {e.result for e in entries}
        if results != {"W", "L"}:
            mismatches.append({
                "game_id": game_id,
                "issue": f"results={sorted(results)}",
            })

    passed = len(mismatches) == 0
    return CheckResult(
        "final_scores_wl",
        CRITICAL,
        passed,
        f"Checked {len(by_game)} completed games; {len(mismatches)} mismatches",
        {"mismatches": mismatches[:25]},
    )


def check_gamelog_orphans(db, season: str) -> CheckResult:
    """Gamelogs should reference known teams and schedule games."""
    total_logs = db.query(GameLogORM).filter(GameLogORM.season == season).count()
    valid_team_ids = {t.team_id for t in TeamORM.get_all(db)}

    orphan_team_q = db.query(GameLogORM.game_id).filter(GameLogORM.season == season)
    if valid_team_ids:
        orphan_team_q = orphan_team_q.filter(~GameLogORM.team_id.in_(valid_team_ids))
    orphan_team_rows = orphan_team_q.distinct().limit(25).all()

    schedule_game_ids = db.query(GameScheduleORM.game_id).distinct()
    orphan_game_rows = (
        db.query(GameLogORM.game_id)
        .filter(
            GameLogORM.season == season,
            ~GameLogORM.game_id.in_(schedule_game_ids),
        )
        .distinct()
        .limit(25)
        .all()
    )

    orphan_teams = [str(r[0]) for r in orphan_team_rows]
    orphan_games = [str(r[0]) for r in orphan_game_rows]
    passed = len(orphan_teams) == 0 and len(orphan_games) == 0

    return CheckResult(
        "gamelog_orphans",
        CRITICAL,
        passed,
        f"Season {season}: {total_logs} logs; "
        f"orphan_team_samples={len(orphan_teams)} orphan_game_samples={len(orphan_games)}",
        {"orphan_team_samples": orphan_teams, "orphan_game_samples": orphan_games},
    )


def check_gamelog_stat_ranges(db, season: str) -> CheckResult:
    """Flag impossible box-score values."""
    bad = (
        db.query(GameLogORM)
        .filter(
            GameLogORM.season == season,
            (
                (GameLogORM.points < 0)
                | (GameLogORM.points > 100)
                | (GameLogORM.rebounds < 0)
                | (GameLogORM.rebounds > 55)
                | (GameLogORM.assists < 0)
                | (GameLogORM.assists > 40)
            ),
        )
        .limit(25)
        .all()
    )
    passed = len(bad) == 0
    return CheckResult(
        "gamelog_stat_ranges",
        CRITICAL,
        passed,
        f"Found {len(bad)} out-of-range gamelog rows",
        {
            "samples": [
                {
                    "player_id": g.player_id,
                    "game_id": g.game_id,
                    "pts": g.points,
                    "reb": g.rebounds,
                    "ast": g.assists,
                }
                for g in bad
            ]
        },
    )


def check_roster_gamelog_coverage(db, season: str) -> CheckResult:
    """Active roster players should generally have some gamelogs (warning in early season)."""
    rosters = db.query(RosterORM).filter(RosterORM.season == season).all()
    if not rosters:
        roster_year = season.split("-", 1)[0]
        # Read-only compatibility until the Phase 4 migration is applied.
        rosters = db.query(RosterORM).filter(RosterORM.season == roster_year).all()
    else:
        roster_year = season.split("-", 1)[0]

    if not rosters:
        return CheckResult(
            "roster_gamelog_coverage",
            WARNING,
            False,
            f"No roster rows for season={season} / year={roster_year}",
        )

    player_ids = {r.player_id for r in rosters}
    players_with_logs = {
        pid
        for (pid,) in db.query(GameLogORM.player_id)
        .filter(GameLogORM.season == season, GameLogORM.player_id.in_(player_ids))
        .distinct()
        .all()
    }
    missing = player_ids - players_with_logs
    coverage = (len(players_with_logs) / len(player_ids)) if player_ids else 0.0
    # Warning only — early season / injured players often have 0 logs
    passed = coverage >= 0.5
    return CheckResult(
        "roster_gamelog_coverage",
        WARNING,
        passed,
        f"Coverage {coverage:.0%} ({len(players_with_logs)}/{len(player_ids)}); "
        f"missing={len(missing)}",
        {"missing_sample": sorted(missing)[:30]},
    )


def check_derived_freshness(db, season: str, as_of: date) -> List[CheckResult]:
    """Derived tables should have data for the season / recent dates."""
    results = []

    heat_count = (
        db.query(PlayerHeatIndexORM)
        .filter(PlayerHeatIndexORM.season == season)
        .count()
    )
    results.append(
        CheckResult(
            "heat_index_present",
            WARNING,
            heat_count > 0,
            f"player_heat_index rows for {season}: {heat_count}",
        )
    )

    streak_count = (
        db.query(ConsecutiveStreakORM)
        .filter(ConsecutiveStreakORM.season == season)
        .count()
    )
    results.append(
        CheckResult(
            "consecutive_streaks_present",
            WARNING,
            streak_count > 0,
            f"player_consecutive_streaks rows for {season}: {streak_count}",
        )
    )

    env_count = (
        db.query(GameEnvironmentDailyORM)
        .filter(GameEnvironmentDailyORM.game_date == as_of)
        .count()
    )
    # Also accept yesterday if today has no games
    if env_count == 0:
        env_count = (
            db.query(GameEnvironmentDailyORM)
            .filter(GameEnvironmentDailyORM.game_date == as_of - timedelta(days=1))
            .count()
        )
        label = f"{as_of} or prior day"
    else:
        label = str(as_of)

    results.append(
        CheckResult(
            "game_environment_freshness",
            WARNING,
            env_count > 0,
            f"game_environment_daily rows for {label}: {env_count}",
        )
    )
    return results


def check_player_snapshot_integrity(db, season: str, as_of: date) -> CheckResult:
    """Verify that the latest reader anchor is complete and internally eligible."""
    requested_cutoff = feature_cutoff_for_slate(as_of)
    target_regular_games = {
        str(game["game_id"])
        for game in GameScheduleORM.get_by_date(as_of, db=db)
        if str(game["game_id"]).lstrip("0").startswith("2")
    }
    if not target_regular_games:
        unexpected = (
            db.query(PlayerStatWindowSnapshotORM)
            .filter(
                PlayerStatWindowSnapshotORM.season == season,
                PlayerStatWindowSnapshotORM.season_type == "Regular Season",
                PlayerStatWindowSnapshotORM.calculation_version
                == PLAYER_SNAPSHOT_CALCULATION_VERSION,
                PlayerStatWindowSnapshotORM.feature_as_of == requested_cutoff,
            )
            .count()
        )
        return CheckResult(
            "player_snapshot_integrity",
            WARNING,
            unexpected == 0,
            f"No Regular Season slate on {as_of}; exact-cutoff snapshot rows={unexpected}",
        )

    anchor = (
        db.query(func.max(PlayerStatWindowSnapshotORM.feature_as_of))
        .filter(
            PlayerStatWindowSnapshotORM.season == season,
            PlayerStatWindowSnapshotORM.season_type == "Regular Season",
            PlayerStatWindowSnapshotORM.calculation_version
            == PLAYER_SNAPSHOT_CALCULATION_VERSION,
            PlayerStatWindowSnapshotORM.completeness_status == "complete",
            PlayerStatWindowSnapshotORM.feature_as_of <= requested_cutoff,
            PlayerStatWindowSnapshotORM.data_available_at <= requested_cutoff,
        )
        .scalar()
    )
    if anchor is None:
        return CheckResult(
            "player_snapshot_integrity",
            WARNING,
            False,
            f"No complete {PLAYER_SNAPSHOT_CALCULATION_VERSION} snapshot at or before {requested_cutoff.isoformat()}",
        )

    models = {
        "streaks": PlayerConsecutiveStreakSnapshotORM,
        "windows": PlayerStatWindowSnapshotORM,
        "heat": PlayerHeatIndexSnapshotORM,
        "consistency": PlayerConsistencySnapshotORM,
    }
    counts = {}
    invalid_availability = 0
    for name, model in models.items():
        base = db.query(model).filter(
            model.season == season,
            model.season_type == "Regular Season",
            model.calculation_version == PLAYER_SNAPSHOT_CALCULATION_VERSION,
            model.feature_as_of == anchor,
            model.completeness_status == "complete",
        )
        counts[name] = base.count()
        invalid_availability += base.filter(model.data_available_at > model.feature_as_of).count()

    passed = counts["windows"] > 0 and invalid_availability == 0
    return CheckResult(
        "player_snapshot_integrity",
        WARNING,
        passed,
        f"cutoff={anchor.isoformat()} counts={counts} invalid_availability={invalid_availability}",
        {"feature_as_of": anchor, "counts": counts},
    )


def check_team_snapshot_integrity(db, season: str, as_of: date) -> CheckResult:
    """Verify exact-cutoff team/game grains and pregame availability."""
    cutoff = feature_cutoff_for_slate(as_of)
    target_games = {
        str(game["game_id"])
        for game in GameScheduleORM.get_by_date(as_of, db=db)
        if str(game["game_id"]).lstrip("0").startswith("2")
    }
    team_query = db.query(TeamGameFeatureSnapshotORM).filter(
        TeamGameFeatureSnapshotORM.season == season,
        TeamGameFeatureSnapshotORM.season_type == "Regular Season",
        TeamGameFeatureSnapshotORM.calculation_version
        == TEAM_SNAPSHOT_CALCULATION_VERSION,
        TeamGameFeatureSnapshotORM.feature_as_of == cutoff,
    )
    environment_query = db.query(GameEnvironmentSnapshotORM).filter(
        GameEnvironmentSnapshotORM.season == season,
        GameEnvironmentSnapshotORM.season_type == "Regular Season",
        GameEnvironmentSnapshotORM.calculation_version
        == TEAM_SNAPSHOT_CALCULATION_VERSION,
        GameEnvironmentSnapshotORM.feature_as_of == cutoff,
    )
    if not target_games:
        unexpected = team_query.count() + environment_query.count()
        return CheckResult(
            "team_snapshot_integrity",
            WARNING,
            unexpected == 0,
            f"No Regular Season slate on {as_of}; exact-cutoff rows={unexpected}",
        )

    team_count = team_query.count()
    environment_count = environment_query.count()
    invalid_availability = team_query.filter(
        TeamGameFeatureSnapshotORM.data_available_at
        > TeamGameFeatureSnapshotORM.feature_as_of
    ).count()
    invalid_source_date = team_query.filter(
        TeamGameFeatureSnapshotORM.source_latest_game_date >= as_of
    ).count()
    invalid_pregame_cutoff = team_query.filter(
        TeamGameFeatureSnapshotORM.scheduled_tipoff
        <= TeamGameFeatureSnapshotORM.feature_as_of
    ).count()
    passed = (
        team_count == len(target_games) * 2
        and environment_count == len(target_games)
        and invalid_availability == 0
        and invalid_source_date == 0
        and invalid_pregame_cutoff == 0
    )
    details = {
        "games": len(target_games),
        "team_features": team_count,
        "game_environments": environment_count,
        "invalid_availability": invalid_availability,
        "invalid_source_date": invalid_source_date,
        "invalid_pregame_cutoff": invalid_pregame_cutoff,
    }
    return CheckResult(
        "team_snapshot_integrity",
        WARNING,
        passed,
        f"cutoff={cutoff.isoformat()} counts={details}",
        details,
    )


def check_odds_coverage(db, season: str, target_date: date) -> CheckResult:
    db_games = GameScheduleORM.get_by_date(target_date, db=db)
    game_ids = list({str(g["game_id"]) for g in db_games})
    if not game_ids:
        return CheckResult(
            "odds_coverage",
            WARNING,
            True,
            f"No games on {target_date} — odds check skipped",
        )

    odds_game_ids = {
        str(gid)
        for (gid,) in db.query(GameOddsORM.game_id)
        .filter(GameOddsORM.game_id.in_(game_ids))
        .distinct()
        .all()
    }
    coverage = len(odds_game_ids) / len(game_ids)
    return CheckResult(
        "odds_coverage",
        WARNING,
        coverage >= 0.5,
        f"Odds for {len(odds_game_ids)}/{len(game_ids)} games on {target_date} "
        f"({coverage:.0%})",
        {"missing": sorted(set(game_ids) - odds_game_ids)[:20]},
    )


def check_injury_coverage(db, season: str, lookback_days: int = 14) -> CheckResult:
    cutoff = date.today() - timedelta(days=lookback_days)
    status_count = (
        db.query(PlayerGameStatusORM)
        .filter(
            PlayerGameStatusORM.season == season,
            PlayerGameStatusORM.game_date >= cutoff,
        )
        .count()
    )
    completed = (
        db.query(GameScheduleORM.game_id)
        .filter(
            GameScheduleORM.season == season,
            GameScheduleORM.result.isnot(None),
            GameScheduleORM.game_date >= datetime.combine(cutoff, datetime.min.time()),
        )
        .distinct()
        .count()
    )
    # Sparse injury data is common; warn if we have completed games but zero status
    passed = status_count > 0 or completed == 0
    return CheckResult(
        "injury_coverage",
        WARNING,
        passed,
        f"player_game_status rows in last {lookback_days}d: {status_count} "
        f"(completed games: {completed})",
    )


def run_validation(
    season: str,
    target_date: date,
    offline: bool = False,
) -> Tuple[List[CheckResult], bool]:
    results: List[CheckResult] = []

    with get_db_context() as db:
        results.append(check_schedule_completeness(db, season, target_date, offline))
        results.append(check_schedule_result_consistency(db, season, target_date))
        results.append(check_final_scores(db, season))
        results.append(check_gamelog_orphans(db, season))
        results.append(check_gamelog_stat_ranges(db, season))
        results.append(check_roster_gamelog_coverage(db, season))
        results.extend(check_derived_freshness(db, season, target_date))
        results.append(check_player_snapshot_integrity(db, season, target_date))
        results.append(check_team_snapshot_integrity(db, season, target_date))
        results.append(check_odds_coverage(db, season, target_date))
        results.append(check_injury_coverage(db, season))

    critical_failed = any(
        (not r.passed) and r.severity == CRITICAL for r in results
    )
    return results, not critical_failed


def print_report(results: List[CheckResult], season: str, target_date: date) -> None:
    print("=" * 70)
    print(f"DAILY DATA VALIDATION — season={season} date={target_date}")
    print("=" * 70)
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] ({r.severity:8}) {r.name}: {r.message}")
        if not r.passed and r.details:
            detail_str = json.dumps(r.details, default=str)
            if len(detail_str) > 300:
                detail_str = detail_str[:300] + "..."
            print(f"           details: {detail_str}")
    print("=" * 70)
    crit_fail = sum(1 for r in results if not r.passed and r.severity == CRITICAL)
    warn_fail = sum(1 for r in results if not r.passed and r.severity == WARNING)
    print(f"Critical failures: {crit_fail} | Warning failures: {warn_fail}")
    print("=" * 70)


def parse_args():
    parser = argparse.ArgumentParser(description="Validate NBA daily data accuracy")
    parser.add_argument("--season", type=str, default=None)
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip CDN/API comparisons; DB-only checks",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional path to write JSON report",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    season = args.season or get_current_season()
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    results, ok = run_validation(season, target_date, offline=args.offline)
    print_report(results, season, target_date)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "season": season,
                    "date": str(target_date),
                    "ok": ok,
                    "checks": [r.to_dict() for r in results],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        logger.info(f"Wrote JSON report to {out_path}")

    # Also write under data/ for automation
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "last_validation.json").write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "season": season,
                "date": str(target_date),
                "ok": ok,
                "checks": [r.to_dict() for r in results],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
