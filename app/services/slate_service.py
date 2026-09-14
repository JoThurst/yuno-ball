"""Shared builders for Fan Daily and Betting Daily slate pages.

Extracts query logic used by scripts/todays_games_report.py and
scripts/todays_teams_report.py into structured dicts for Jinja templates.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
from app.models.player_stat_window_sqlalchemy import PlayerStatWindowORM
from app.models.player_consistency_sqlalchemy import PlayerConsistencyORM
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.team_daily_flags_sqlalchemy import TeamDailyFlagsORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.market_observation_sqlalchemy import (
    MarketObservationHeaderORM,
    MarketObservationSelectionORM,
)
from app.models.player_analytics_snapshot_sqlalchemy import (
    PLAYER_SNAPSHOT_CALCULATION_VERSION,
    PlayerConsecutiveStreakSnapshotORM,
    PlayerConsistencySnapshotORM,
    PlayerHeatIndexSnapshotORM,
    PlayerStatWindowSnapshotORM,
)
from app.models.team_analytics_snapshot_sqlalchemy import (
    TEAM_SNAPSHOT_CALCULATION_VERSION,
    TEAM_SNAPSHOT_COMPLETENESS_COMPLETE,
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.services.player_snapshot_service import (
    complete_snapshot_history_exists,
    feature_cutoff_for_slate,
    load_complete_snapshot_at_cutoff,
    load_latest_complete_snapshot,
)
from app.services.official_availability_slate_service import (
    build_slate_official_availability,
    non_available_observations,
)
from app.utils.season_utils import get_current_season, roster_season_year, season_for_date
from app.utils.id_utils import normalize_nba_game_id
from app.utils.freshness import get_ingest_freshness

logger = logging.getLogger(__name__)


def normalize_game_id(game_id) -> str:
    """Compatibility name for the central NBA game-ID normalizer."""

    return normalize_nba_game_id(game_id)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def heat_status_from_zscore(z_score: float) -> str:
    if z_score >= 1.0:
        return "on_fire"
    if z_score >= 0.65:
        return "heating_up"
    if z_score >= -0.64:
        return "average"
    if z_score >= -1.0:
        return "cooling_off"
    return "ice_cold"


def _pair_games(raw_games: List[dict]) -> List[dict]:
    """Collapse home/away schedule rows into one matchup per game_id."""
    by_id: Dict[str, List[dict]] = defaultdict(list)
    for g in raw_games:
        by_id[normalize_game_id(g["game_id"])].append(g)

    matchups = []
    for game_id, rows in by_id.items():
        home = next((r for r in rows if r.get("home_or_away") == "H"), None)
        away = next((r for r in rows if r.get("home_or_away") == "A"), None)
        # Fallback: treat first as home if location missing
        if home is None and rows:
            home = rows[0]
        if away is None and len(rows) > 1:
            away = rows[1]
        if home is None:
            continue

        game_date = home.get("game_date")
        if isinstance(game_date, str):
            try:
                game_date = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            except ValueError:
                game_date = None
        game_date_precision = home.get("game_date_precision")

        matchups.append({
            "game_id": game_id,
            "game_date": game_date,
            "game_time": (
                game_date.strftime("%I:%M %p")
                if isinstance(game_date, datetime)
                and game_date_precision != "date_only"
                else None
            ),
            "game_date_precision": game_date_precision,
            "home_team_id": home.get("team_id"),
            "away_team_id": (
                away.get("team_id") if away else home.get("opponent_team_id")
            ),
            "home_name": home.get("team_name"),
            "away_name": (
                away.get("team_name") if away else home.get("opponent_name")
            ),
            "home_abbr": home.get("team_abbreviation"),
            "away_abbr": (
                away.get("team_abbreviation")
                if away
                else home.get("opponent_abbreviation")
            ),
            "result_home": home.get("result"),
        })

    matchups.sort(key=lambda m: m.get("game_date") or datetime.min)
    return matchups


def _load_roster_players(db, team_ids: Set[int], season: str) -> Dict[int, dict]:
    players: Dict[int, dict] = {}
    for team_id in team_ids:
        roster = RosterORM.get_by_team_and_season(team_id, season, db=db)
        if not roster:
            # Read-only compatibility until every environment has applied the
            # Phase 4 roster-season migration.
            roster = RosterORM.get_by_team_and_season(
                team_id,
                roster_season_year(season),
                db=db,
            )
        team = TeamORM.get_by_id(team_id, db=db)
        team_name = team.name if team else f"Team {team_id}"
        team_abbr = team.abbreviation if team else ""
        for entry in roster:
            players[entry.player_id] = {
                "player_id": entry.player_id,
                "player_name": entry.player_name,
                "team_id": team_id,
                "team_name": team_name,
                "team_abbr": team_abbr,
                "position": entry.position,
                "number": entry.player_number,
            }
    return players


def _serialize_streak(s: ConsecutiveStreakORM) -> dict:
    return {
        "player_id": s.player_id,
        "player_name": s.player_name,
        "stat": s.stat,
        "threshold": s.threshold,
        "streak_games": s.streak_games,
        "streak_kind": s.streak_kind,
        "is_active": s.is_active,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
    }


def _serialize_heat(h: PlayerHeatIndexORM) -> dict:
    return {
        "player_id": h.player_id,
        "player_name": h.player_name,
        "stat": h.stat,
        "window_size": h.window_size,
        "z_score": round(h.z_score, 2) if h.z_score is not None else None,
        "recent_avg": round(h.recent_avg, 2) if h.recent_avg is not None else None,
        "season_avg": round(h.season_avg, 2) if h.season_avg is not None else None,
        "status": heat_status_from_zscore(h.z_score or 0),
    }


def _serialize_window(w: PlayerStatWindowORM) -> dict:
    hit_rate = (w.games_hit / w.games_played) if w.games_played else 0
    return {
        "player_id": w.player_id,
        "player_name": w.player_name,
        "stat": w.stat,
        "threshold": w.threshold,
        "games_hit": w.games_hit,
        "games_played": w.games_played,
        "window_size": w.window_size,
        "hit_rate": round(hit_rate * 100, 1),
        "last_game_date": w.last_game_date.isoformat() if w.last_game_date else None,
    }


def _serialize_consistency(c: PlayerConsistencyORM) -> dict:
    return {
        "player_id": c.player_id,
        "stat_name": c.stat_name,
        "mean": round(c.mean, 1) if c.mean is not None else None,
        "stddev": round(c.stddev, 1) if c.stddev is not None else None,
        "cv": round(c.cv, 2) if c.cv is not None else None,
        "consistency_tier": c.consistency_tier,
    }


def _serialize_schedule(sf: TeamScheduleFactorsORM) -> dict:
    return {
        "team_id": sf.team_id,
        "game_id": normalize_game_id(sf.game_id),
        "days_rest": sf.days_rest,
        "is_b2b": sf.is_b2b,
        "is_3_in_4": getattr(sf, "is_3_in_4", False),
        "is_4_in_5": getattr(sf, "is_4_in_5", False),
        "is_5_in_7": getattr(sf, "is_5_in_7", False),
        "rest_edge": sf.rest_edge,
        "rest_diff": sf.rest_diff,
        "opponent_days_rest": sf.opponent_days_rest,
    }


def _serialize_environment(env: Any) -> dict:
    tags = env.tags or []
    return {
        "game_id": normalize_game_id(env.game_id),
        "pace_projection": round(env.pace_projection, 1) if env.pace_projection else None,
        "scoring_env_index": round(env.scoring_env_index, 1) if env.scoring_env_index else None,
        "three_env_index": round(env.three_env_index, 1) if env.three_env_index else None,
        "chaos_index": round(env.chaos_index, 1) if env.chaos_index else None,
        "home_off_rtg_lastn": round(env.home_off_rtg_lastn, 1) if env.home_off_rtg_lastn else None,
        "away_off_rtg_lastn": round(env.away_off_rtg_lastn, 1) if env.away_off_rtg_lastn else None,
        "home_def_rtg_lastn": round(env.home_def_rtg_lastn, 1) if env.home_def_rtg_lastn else None,
        "away_def_rtg_lastn": round(env.away_def_rtg_lastn, 1) if env.away_def_rtg_lastn else None,
        "tags": tags,
        "three_point_fest": bool(
            getattr(env, "three_point_fest", "three_point_fest" in tags)
        ),
        "paint_battle": bool(getattr(env, "paint_battle", "paint_battle" in tags)),
        "glass_war": bool(getattr(env, "glass_war", "glass_war" in tags)),
        "whistle_heavy": bool(
            getattr(env, "whistle_heavy", "whistle_heavy" in tags)
        ),
        "feature_as_of": (
            env.feature_as_of.isoformat()
            if getattr(env, "feature_as_of", None)
            else None
        ),
        "calculation_version": getattr(env, "calculation_version", None),
        "completeness": getattr(env, "completeness_status", "legacy_unversioned"),
        "pace_label": (
            "fast" if env.pace_projection and env.pace_projection > 102
            else "slow" if env.pace_projection and env.pace_projection < 96
            else "average"
        ),
        "scoring_label": (
            "high" if env.scoring_env_index and env.scoring_env_index > 105
            else "low" if env.scoring_env_index and env.scoring_env_index < 95
            else "average"
        ),
    }


def _serialize_odds(odds_list: List[GameOddsORM]) -> dict:
    if not odds_list:
        return {}
    # Prefer first US book with spread
    primary = odds_list[0]
    for o in odds_list:
        if o.home_spread is not None:
            primary = o
            break
    return {
        "sportsbook": primary.sportsbook_name,
        "home_ml": primary.home_ml_odds,
        "away_ml": primary.away_ml_odds,
        "spread": primary.home_spread,
        "home_spread": primary.home_spread,
        "away_spread": primary.away_spread,
        "home_ml_trend": primary.home_ml_trend,
        "away_ml_trend": primary.away_ml_trend,
        "books_count": len(odds_list),
    }


def _serialize_market_observations(
    headers: List[MarketObservationHeaderORM],
    selections_by_observation: Dict[str, List[MarketObservationSelectionORM]],
) -> Dict[str, dict]:
    """Return latest complete forward market pairs for the public daily view."""
    grouped: Dict[tuple[str, str, str], List[MarketObservationHeaderORM]] = defaultdict(list)
    for header in headers:
        grouped[
            (
                normalize_game_id(header.canonical_game_id),
                str(header.sportsbook_id),
                str(header.market_type),
            )
        ].append(header)

    by_game: Dict[str, dict] = {}
    for (game_id, sportsbook_id, market_type), candidates in grouped.items():
        latest = max(
            candidates,
            key=lambda row: (row.observed_at or row.data_available_at, row.created_at),
        )
        selections = selections_by_observation.get(str(latest.observation_id), [])
        if not selections:
            continue
        entry = by_game.setdefault(
            game_id,
            {
                "source": "nba_live_odds",
                "status": "available",
                "completeness": "complete_pair_observed",
                "observations_total": 0,
                "books_count": 0,
                "sportsbooks": set(),
                "markets": [],
            },
        )
        entry["observations_total"] += len(candidates)
        entry["sportsbooks"].add(sportsbook_id)
        entry["markets"].append(
            {
                "market_type": market_type,
                "sportsbook_id": sportsbook_id,
                "sportsbook_name": latest.sportsbook_name,
                "observed_at": _iso(latest.observed_at or latest.data_available_at),
                "data_available_at": _iso(latest.data_available_at),
                "selections": [
                    {
                        "selection_key": selection.selection_key,
                        "selection_label": selection.selection_label,
                        "line_value": (
                            float(selection.line_value)
                            if selection.line_value is not None else None
                        ),
                        "price_american": selection.price_american,
                    }
                    for selection in selections
                ],
            }
        )

    for value in by_game.values():
        value["sportsbooks"] = sorted(value["sportsbooks"])
        value["books_count"] = len(value["sportsbooks"])
        value["markets"].sort(key=lambda item: (item["market_type"], item["sportsbook_id"]))
    return by_game


def _player_callouts_for_team(
    team_id: int,
    players: Dict[int, dict],
    streaks_by_player: Dict[int, list],
    heat_by_player: Dict[int, list],
    windows_by_player: Dict[int, list],
    consistency_by_player: Dict[int, list],
    injuries_by_player: Dict[int, list],
    limit: int = 5,
) -> List[dict]:
    """Top notable players on a team for slate cards."""
    team_players = [p for p in players.values() if p["team_id"] == team_id]
    scored = []
    for p in team_players:
        pid = p["player_id"]
        heats = heat_by_player.get(pid, [])
        notable_heat = [
            h for h in heats
            if h["status"] in ("on_fire", "heating_up", "ice_cold", "cooling_off")
            and h.get("window_size") in (3, 5, 10)
        ]
        active_streaks = [
            s for s in streaks_by_player.get(pid, [])
            if s.get("is_active") and s.get("streak_games", 0) >= 3
        ]
        hot_windows = [
            w for w in windows_by_player.get(pid, [])
            if w.get("hit_rate", 0) >= 70 and w.get("window_size") == 10
        ]
        score = (
            len(active_streaks) * 10
            + sum(abs(h.get("z_score") or 0) for h in notable_heat[:3])
            + len(hot_windows) * 2
        )
        if score <= 0 and not injuries_by_player.get(pid):
            continue
        cons = consistency_by_player.get(pid, [])
        overall_tier = "mixed"
        if cons:
            volatile = sum(1 for c in cons if c.get("consistency_tier") == "volatile")
            steady = sum(1 for c in cons if c.get("consistency_tier") == "steady")
            if steady > volatile + 1:
                overall_tier = "steady"
            elif volatile > steady + 1:
                overall_tier = "volatile"

        scored.append({
            **p,
            "score": score,
            "heat": sorted(notable_heat, key=lambda h: abs(h.get("z_score") or 0), reverse=True)[:3],
            "streaks": active_streaks[:3],
            "windows": hot_windows[:3],
            "consistency_tier": overall_tier,
            "injuries": injuries_by_player.get(pid, [])[:2],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def build_slate_context(
    target_date: Optional[date] = None,
    season: Optional[str] = None,
    include_odds: bool = True,
    include_injuries: bool = True,
    player_limit_per_team: int = 5,
) -> Dict[str, Any]:
    """Build full slate context for Fan or Betting daily pages.

    ``include_injuries`` remains a compatibility parameter, but postgame
    ``player_game_status`` rows are intentionally not rendered as pregame
    injury callouts. Official report observations must supply that payload.
    """
    target_date = target_date or date.today()
    # Derive season from the slate date so historical pages (e.g. 2025-03-03)
    # query the correct season tables instead of "current" offseason season.
    season = season or season_for_date(target_date)
    freshness = get_ingest_freshness()

    with get_db_context() as db:
        raw_games = GameScheduleORM.get_by_date(target_date, db=db)
        matchups = _pair_games(raw_games)
        availability_by_game = (
            build_slate_official_availability(matchups, db=db)
            if include_injuries and matchups
            else {}
        )

        team_ids: Set[int] = set()
        for m in matchups:
            if m.get("home_team_id"):
                team_ids.add(m["home_team_id"])
            if m.get("away_team_id"):
                team_ids.add(m["away_team_id"])

        players = _load_roster_players(db, team_ids, season) if team_ids else {}
        player_ids = list(players.keys())

        requested_cutoff = feature_cutoff_for_slate(target_date)
        matchup_game_ids = [m["game_id"] for m in matchups]
        id_variants = set(matchup_game_ids)
        for gid in matchup_game_ids:
            if gid.isdigit():
                id_variants.add(str(int(gid)))
                id_variants.add(gid.zfill(10))

        # Historical team/game payloads are served only from complete versioned
        # snapshots that were available at the requested pregame cutoff.
        team_snapshot_rows = []
        environment_snapshot_rows = []
        if id_variants:
            team_snapshot_rows = (
                db.query(TeamGameFeatureSnapshotORM)
                .filter(
                    TeamGameFeatureSnapshotORM.game_id.in_(list(id_variants)),
                    TeamGameFeatureSnapshotORM.season == season,
                    TeamGameFeatureSnapshotORM.window_size == 10,
                    TeamGameFeatureSnapshotORM.calculation_version
                    == TEAM_SNAPSHOT_CALCULATION_VERSION,
                    TeamGameFeatureSnapshotORM.completeness_status
                    == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE,
                    TeamGameFeatureSnapshotORM.feature_as_of <= requested_cutoff,
                    TeamGameFeatureSnapshotORM.data_available_at <= requested_cutoff,
                )
                .order_by(TeamGameFeatureSnapshotORM.feature_as_of.desc())
                .all()
            )
            environment_snapshot_rows = (
                db.query(GameEnvironmentSnapshotORM)
                .filter(
                    GameEnvironmentSnapshotORM.game_id.in_(list(id_variants)),
                    GameEnvironmentSnapshotORM.season == season,
                    GameEnvironmentSnapshotORM.window_size == 10,
                    GameEnvironmentSnapshotORM.calculation_version
                    == TEAM_SNAPSHOT_CALCULATION_VERSION,
                    GameEnvironmentSnapshotORM.completeness_status
                    == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE,
                    GameEnvironmentSnapshotORM.feature_as_of <= requested_cutoff,
                    GameEnvironmentSnapshotORM.data_available_at <= requested_cutoff,
                )
                .order_by(GameEnvironmentSnapshotORM.feature_as_of.desc())
                .all()
            )

        metrics_by_team: Dict[int, Any] = {}
        metrics_by_game_team: Dict[tuple, Any] = {}
        for row in team_snapshot_rows:
            key = (normalize_game_id(row.game_id), row.team_id)
            if key not in metrics_by_game_team:
                metrics_by_game_team[key] = row
                metrics_by_team[row.team_id] = row
        team_metrics_rows = list(metrics_by_team.values())

        flags_by_team: Dict[int, list] = defaultdict(list)
        for row in team_metrics_rows:
            flags_by_team[row.team_id].extend(row.flags or [])

        env_by_game: Dict[str, dict] = {}
        for row in environment_snapshot_rows:
            key = normalize_game_id(row.game_id)
            if key not in env_by_game:
                env_by_game[key] = _serialize_environment(row)

        team_snapshot_fallback = False
        if target_date == date.today() and not team_snapshot_rows:
            # Compatibility is limited to today's slate when Phase 3 has not
            # published any usable row. Historical requests never fall forward.
            team_metrics_rows = (
                db.query(TeamDailyMetricsORM)
                .filter(
                    TeamDailyMetricsORM.season == season,
                    TeamDailyMetricsORM.window_size == 10,
                )
                .order_by(
                    TeamDailyMetricsORM.team_id,
                    TeamDailyMetricsORM.stat_date.desc(),
                )
                .distinct(TeamDailyMetricsORM.team_id)
                .all()
            )
            metrics_by_team = {row.team_id: row for row in team_metrics_rows}
            flags_all = (
                db.query(TeamDailyFlagsORM)
                .filter(TeamDailyFlagsORM.season == season)
                .order_by(TeamDailyFlagsORM.stat_date.desc())
                .all()
            )
            seen_flag = set()
            for row in flags_all:
                key = (row.team_id, row.flag_type)
                if key not in seen_flag:
                    seen_flag.add(key)
                    flags_by_team[row.team_id].append(
                        {"flag_type": row.flag_type, "severity": row.severity}
                    )
            team_snapshot_fallback = True

        if target_date == date.today() and not environment_snapshot_rows:
            envs = (
                db.query(GameEnvironmentDailyORM)
                .filter(
                    GameEnvironmentDailyORM.game_date == target_date,
                    GameEnvironmentDailyORM.season == season,
                )
                .all()
            )
            env_by_game = {
                normalize_game_id(row.game_id): _serialize_environment(row)
                for row in envs
            }
            team_snapshot_fallback = True

        team_snapshot_meta = {
            "source": (
                "legacy_latest" if team_snapshot_fallback else "versioned_snapshot"
            ),
            "requested_cutoff": requested_cutoff.isoformat(),
            "calculation_version": (
                None if team_snapshot_fallback else TEAM_SNAPSHOT_CALCULATION_VERSION
            ),
            "complete_team_rows": len(team_snapshot_rows),
            "expected_team_rows": len(matchups) * 2,
            "complete_environment_rows": len(environment_snapshot_rows),
            "expected_environment_rows": len(matchups),
            "completeness": (
                "legacy_unversioned"
                if team_snapshot_fallback
                else "complete"
                if len(team_snapshot_rows) == len(matchups) * 2
                and len(environment_snapshot_rows) == len(matchups)
                else "partial_or_missing"
            ),
            "fallback_used": team_snapshot_fallback,
        }

        # Schedule factors may be stored on UTC calendar dates that differ from
        # EST slate dates — join by game_id from today's matchups.
        schedule_by_game: Dict[str, Dict[int, dict]] = defaultdict(dict)
        if matchup_game_ids:
            schedule_factors = (
                db.query(TeamScheduleFactorsORM)
                .filter(TeamScheduleFactorsORM.game_id.in_(list(id_variants)))
                .all()
            )
            for sf in schedule_factors:
                schedule_by_game[normalize_game_id(sf.game_id)][sf.team_id] = (
                    _serialize_schedule(sf)
                )

        odds_by_game: Dict[str, dict] = {}
        market_observations_by_game: Dict[str, dict] = {}
        if include_odds:
            try:
                odds_rows = GameOddsORM.get_by_date(
                    target_date, country_code="US", db=db
                )
                grouped: Dict[str, list] = defaultdict(list)
                for o in odds_rows:
                    grouped[normalize_game_id(o.game_id)].append(o)
                odds_by_game = {
                    gid: _serialize_odds(olist) for gid, olist in grouped.items()
                }
            except Exception as exc:
                logger.warning(f"Odds load failed: {exc}")
            try:
                market_headers = (
                    db.query(MarketObservationHeaderORM)
                    .filter(
                        MarketObservationHeaderORM.game_date == target_date,
                        MarketObservationHeaderORM.snapshot_type == "forward",
                        MarketObservationHeaderORM.canonical_game_id.in_(
                            matchup_game_ids or ["__none__"]
                        ),
                    )
                    .all()
                )
                observation_ids = [row.observation_id for row in market_headers]
                market_selections = (
                    db.query(MarketObservationSelectionORM)
                    .filter(
                        MarketObservationSelectionORM.observation_id.in_(
                            observation_ids or ["__none__"]
                        )
                    )
                    .all()
                )
                selections_by_observation: Dict[str, List[MarketObservationSelectionORM]] = defaultdict(list)
                for selection in market_selections:
                    selections_by_observation[str(selection.observation_id)].append(selection)
                market_observations_by_game = _serialize_market_observations(
                    market_headers, selections_by_observation
                )
            except Exception as exc:
                logger.warning(f"Canonical market observation load failed: {exc}")

        # Player insights
        streaks_by_player: Dict[int, list] = defaultdict(list)
        heat_by_player: Dict[int, list] = defaultdict(list)
        windows_by_player: Dict[int, list] = defaultdict(list)
        consistency_by_player: Dict[int, list] = defaultdict(list)
        injuries_by_player: Dict[int, list] = defaultdict(list)
        player_snapshot_meta = {
            "source": "legacy_latest",
            "feature_as_of": None,
            "calculation_version": None,
            "source_run_id": None,
            "completeness": "legacy_unversioned",
            "fallback_used": True,
        }

        if player_ids:
            requested_cutoff = feature_cutoff_for_slate(target_date)
            anchor = load_latest_complete_snapshot(
                db,
                PlayerStatWindowSnapshotORM,
                season=season,
                requested_cutoff=requested_cutoff,
                player_ids=player_ids,
            )
            if anchor.feature_as_of is not None:
                streak_result = load_complete_snapshot_at_cutoff(
                    db,
                    PlayerConsecutiveStreakSnapshotORM,
                    season=season,
                    feature_as_of=anchor.feature_as_of,
                    player_ids=player_ids,
                )
                heat_result = load_complete_snapshot_at_cutoff(
                    db,
                    PlayerHeatIndexSnapshotORM,
                    season=season,
                    feature_as_of=anchor.feature_as_of,
                    player_ids=player_ids,
                )
                consistency_result = load_complete_snapshot_at_cutoff(
                    db,
                    PlayerConsistencySnapshotORM,
                    season=season,
                    feature_as_of=anchor.feature_as_of,
                    player_ids=player_ids,
                )
                streaks = [row for row in streak_result.rows if row.streak_games >= 3]
                heats = heat_result.rows
                windows = anchor.rows
                cons_rows = [row for row in consistency_result.rows if row.window_size == 0]
                source_row = next(iter(anchor.rows), None)
                player_snapshot_meta = {
                    "source": "versioned_snapshot",
                    "feature_as_of": anchor.feature_as_of.isoformat(),
                    "calculation_version": PLAYER_SNAPSHOT_CALCULATION_VERSION,
                    "source_run_id": getattr(source_row, "source_run_id", None),
                    "completeness": "complete",
                    "fallback_used": False,
                }
            else:
                if complete_snapshot_history_exists(db, season=season):
                    # v2 exists for the season but nothing is eligible at the
                    # requested historical cutoff. Return an honest missing
                    # state; a legacy fallback here would leak future games.
                    streaks = heats = windows = cons_rows = ()
                    player_snapshot_meta = {
                        "source": "versioned_snapshot",
                        "feature_as_of": None,
                        "calculation_version": PLAYER_SNAPSHOT_CALCULATION_VERSION,
                        "source_run_id": None,
                        "completeness": "missing_at_requested_cutoff",
                        "fallback_used": False,
                    }
                elif target_date == date.today():
                    streaks = (
                        db.query(ConsecutiveStreakORM)
                        .filter(
                            ConsecutiveStreakORM.player_id.in_(player_ids),
                            ConsecutiveStreakORM.season == season,
                            ConsecutiveStreakORM.streak_games >= 3,
                        )
                        .all()
                    )
                    heats = (
                        db.query(PlayerHeatIndexORM)
                        .filter(
                            PlayerHeatIndexORM.player_id.in_(player_ids),
                            PlayerHeatIndexORM.season == season,
                        )
                        .all()
                    )
                    windows = (
                        db.query(PlayerStatWindowORM)
                        .filter(
                            PlayerStatWindowORM.player_id.in_(player_ids),
                            PlayerStatWindowORM.season == season,
                        )
                        .all()
                    )
                    cons_rows = (
                        db.query(PlayerConsistencyORM)
                        .filter(
                            PlayerConsistencyORM.player_id.in_(player_ids),
                            PlayerConsistencyORM.season == season,
                            PlayerConsistencyORM.window_size == 0,
                        )
                        .all()
                    )
                else:
                    streaks = heats = windows = cons_rows = ()
                    player_snapshot_meta = {
                        "source": "versioned_snapshot",
                        "feature_as_of": None,
                        "calculation_version": PLAYER_SNAPSHOT_CALCULATION_VERSION,
                        "source_run_id": None,
                        "completeness": "missing_at_requested_cutoff",
                        "fallback_used": False,
                    }
            for s in streaks:
                streaks_by_player[s.player_id].append(_serialize_streak(s))

            for h in heats:
                heat_by_player[h.player_id].append(_serialize_heat(h))

            for w in windows:
                ser = _serialize_window(w)
                if ser["hit_rate"] > 0:
                    windows_by_player[w.player_id].append(ser)

            for c in cons_rows:
                consistency_by_player[c.player_id].append(_serialize_consistency(c))

            # Do not use PlayerGameStatusORM for pregame injury callouts. It is
            # postgame Live BoxScore data, has no report publication timestamp,
            # and a prior-game absence is not evidence of today's availability.

        for availability in availability_by_game.values():
            for observation in availability.get("observations", []):
                player_id = observation.get("player_id")
                status = observation.get("status")
                if player_id is None or status not in {
                    "Probable",
                    "Questionable",
                    "Doubtful",
                    "Out",
                }:
                    continue
                injuries_by_player[player_id].append(
                    {
                        "status": status,
                        "reason": (
                            observation.get("reason_detail")
                            or observation.get("reason_category")
                            or observation.get("raw_reason")
                        ),
                        "as_of": availability.get("as_of"),
                        "source": availability.get("source"),
                        "completeness": availability.get("completeness"),
                    }
                )

        # Assemble matchup cards
        slate_games = []
        for m in matchups:
            gid = m["game_id"]
            home_id = m["home_team_id"]
            away_id = m["away_team_id"]
            home_metrics = metrics_by_game_team.get((gid, home_id)) or metrics_by_team.get(home_id)
            away_metrics = metrics_by_game_team.get((gid, away_id)) or metrics_by_team.get(away_id)

            slate_games.append({
                **m,
                "availability": availability_by_game.get(
                    gid,
                    {
                        "as_of": None,
                        "source": "nba_official_injury_reports",
                        "completeness": "unknown",
                        "unknown_reason": "no_scheduled_tipoff",
                        "observations": [],
                        "unresolved_observation_count": 0,
                    },
                ),
                "home_availability": non_available_observations(
                    availability_by_game.get(gid, {}),
                    team_id=home_id,
                ),
                "away_availability": non_available_observations(
                    availability_by_game.get(gid, {}),
                    team_id=away_id,
                ),
                "environment": env_by_game.get(gid),
                "home_schedule": schedule_by_game.get(gid, {}).get(home_id),
                "away_schedule": schedule_by_game.get(gid, {}).get(away_id),
                "odds": odds_by_game.get(gid) if include_odds else None,
                "observed_markets": market_observations_by_game.get(gid),
                "home_flags": flags_by_team.get(home_id, [])[:5],
                "away_flags": flags_by_team.get(away_id, [])[:5],
                "home_net_delta": (
                    round(home_metrics.net_rtg_delta, 1)
                    if home_metrics and home_metrics.net_rtg_delta is not None
                    else None
                ),
                "away_net_delta": (
                    round(away_metrics.net_rtg_delta, 1)
                    if away_metrics and away_metrics.net_rtg_delta is not None
                    else None
                ),
                "home_players": _player_callouts_for_team(
                    home_id, players, streaks_by_player, heat_by_player,
                    windows_by_player, consistency_by_player, injuries_by_player,
                    limit=player_limit_per_team,
                ),
                "away_players": _player_callouts_for_team(
                    away_id, players, streaks_by_player, heat_by_player,
                    windows_by_player, consistency_by_player, injuries_by_player,
                    limit=player_limit_per_team,
                ),
            })

        # Headlines
        improvers = sorted(
            [m for m in team_metrics_rows if m.net_rtg_delta is not None],
            key=lambda m: m.net_rtg_delta,
            reverse=True,
        )[:3]
        decliners = sorted(
            [m for m in team_metrics_rows if m.net_rtg_delta is not None],
            key=lambda m: m.net_rtg_delta,
        )[:3]
        high_scoring = sorted(
            [g for g in slate_games if g.get("environment") and g["environment"].get("scoring_env_index")],
            key=lambda g: g["environment"]["scoring_env_index"],
            reverse=True,
        )[:3]
        fast_pace = sorted(
            [g for g in slate_games if g.get("environment") and g["environment"].get("pace_projection")],
            key=lambda g: g["environment"]["pace_projection"],
            reverse=True,
        )[:3]

        # League-wide hot/cold for fan page strip
        hot_players = []
        cold_players = []
        for pid, heats in heat_by_player.items():
            best = max(heats, key=lambda h: h.get("z_score") or -99, default=None)
            worst = min(heats, key=lambda h: h.get("z_score") or 99, default=None)
            info = players.get(pid, {})
            if best and (best.get("z_score") or 0) >= 0.65:
                hot_players.append({**info, **best})
            if worst and (worst.get("z_score") or 0) <= -0.65:
                cold_players.append({**info, **worst})
        hot_players.sort(key=lambda x: x.get("z_score") or 0, reverse=True)
        cold_players.sort(key=lambda x: x.get("z_score") or 0)

        headlines = {
            "improvers": [
                {
                    "team_name": next(
                        (
                            game["home_name"]
                            if game["home_team_id"] == m.team_id
                            else game["away_name"]
                            for game in matchups
                            if m.team_id in {game["home_team_id"], game["away_team_id"]}
                        ),
                        f"Team {m.team_id}",
                    ),
                    "delta": round(m.net_rtg_delta, 1),
                }
                for m in improvers
            ],
            "decliners": [
                {
                    "team_name": next(
                        (
                            game["home_name"]
                            if game["home_team_id"] == m.team_id
                            else game["away_name"]
                            for game in matchups
                            if m.team_id in {game["home_team_id"], game["away_team_id"]}
                        ),
                        f"Team {m.team_id}",
                    ),
                    "delta": round(m.net_rtg_delta, 1),
                }
                for m in decliners
            ],
            "high_scoring": [
                {
                    "label": f"{g['home_abbr']}-{g['away_abbr']}",
                    "index": g["environment"]["scoring_env_index"],
                }
                for g in high_scoring
            ],
            "fast_pace": [
                {
                    "label": f"{g['home_abbr']}-{g['away_abbr']}",
                    "pace": g["environment"]["pace_projection"],
                }
                for g in fast_pace
            ],
        }

    return {
        "target_date": target_date,
        "target_date_display": target_date.strftime("%A, %B %d, %Y"),
        "season": season,
        "games": slate_games,
        "game_count": len(slate_games),
        "headlines": headlines,
        "hot_players": hot_players[:12],
        "cold_players": cold_players[:12],
        "freshness": freshness,
        "player_snapshot": player_snapshot_meta,
        "team_snapshot": team_snapshot_meta,
        "has_games": len(slate_games) > 0,
    }


def get_fan_daily_data(
    target_date: Optional[date] = None,
    season: Optional[str] = None,
) -> Dict[str, Any]:
    """Fan Daily: no odds framing; injuries kept light."""
    ctx = build_slate_context(
        target_date=target_date,
        season=season,
        include_odds=False,
        include_injuries=True,
        player_limit_per_team=4,
    )
    ctx["page_mode"] = "fan"
    return ctx


def get_betting_daily_data(
    target_date: Optional[date] = None,
    season: Optional[str] = None,
) -> Dict[str, Any]:
    """Betting Daily: odds, edges, denser player prop context."""
    ctx = build_slate_context(
        target_date=target_date,
        season=season,
        include_odds=True,
        include_injuries=True,
        player_limit_per_team=6,
    )
    ctx["page_mode"] = "betting"
    return ctx
