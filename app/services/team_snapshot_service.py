"""Leakage-safe calculation and lookup for durable team/game snapshots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_analytics_snapshot_sqlalchemy import (
    TEAM_SNAPSHOT_CALCULATION_VERSION,
    TEAM_SNAPSHOT_COMPLETENESS_COMPLETE,
    TEAM_SNAPSHOT_COMPLETENESS_PARTIAL,
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
    bulk_upsert_snapshots,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.utils.season_utils import normalize_season, normalize_season_type


EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
SNAPSHOT_PUBLISH_HOUR_ET = 10
SOURCE_AVAILABILITY_LAG = timedelta(hours=6)
DEFAULT_WINDOW_SIZE = 10

SEASON_TYPE_GAME_ID_PREFIX = {
    "Pre Season": "1",
    "Regular Season": "2",
    "All-Star": "3",
    "Playoffs": "4",
}

METRIC_NAMES = (
    "off_rtg",
    "def_rtg",
    "net_rtg",
    "pace",
    "efg",
    "tov_pct",
    "orb_pct",
    "ftr",
    "pct_pts_3pt",
)

FLAG_THRESHOLDS: Mapping[str, Tuple[str, float, str]] = {
    "offense_rising": ("off_rtg_delta", 5.0, "positive"),
    "offense_falling": ("off_rtg_delta", -5.0, "negative"),
    "defense_improving": ("def_rtg_delta", -4.0, "negative"),
    "defense_declining": ("def_rtg_delta", 5.0, "positive"),
    "pace_up": ("pace_delta", 4.0, "positive"),
    "pace_down": ("pace_delta", -4.0, "negative"),
    "shooting_hot": ("efg_delta", 0.03, "positive"),
    "shooting_cold": ("efg_delta", -0.03, "negative"),
    "turnover_prone": ("tov_pct_delta", 0.02, "positive"),
    "ball_secure": ("tov_pct_delta", -0.03, "negative"),
    "three_point_heavy": ("pct_pts_3pt_delta", 0.05, "positive"),
}


@dataclass(frozen=True)
class TeamSnapshotPublicationContext:
    season: str
    season_type: str
    target_date: date
    feature_as_of: datetime
    calculation_version: str
    source_run_id: str


@dataclass(frozen=True)
class SlateTeam:
    game_id: str
    team_id: int
    opponent_team_id: int
    scheduled_tipoff: datetime
    is_home: bool


@dataclass(frozen=True)
class TeamGameFact:
    game_id: str
    team_id: int
    opponent_team_id: int
    game_time: datetime
    fg: Optional[int]
    fga: Optional[int]
    fg3: Optional[int]
    fta: Optional[int]
    oreb: Optional[int]
    dreb: Optional[int]
    tov: Optional[int]
    pts: Optional[int]

    @property
    def game_date(self) -> date:
        return _aware_utc(self.game_time).astimezone(EASTERN).date()


@dataclass(frozen=True)
class TeamSnapshotReadResult:
    rows: Sequence[object]
    feature_as_of: Optional[datetime]
    calculation_version: str


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def feature_cutoff_for_slate(target_date: date) -> datetime:
    local_cutoff = datetime.combine(
        target_date,
        time(hour=SNAPSHOT_PUBLISH_HOUR_ET),
        tzinfo=EASTERN,
    )
    return local_cutoff.astimezone(UTC)


def build_team_snapshot_context(
    *,
    season: str,
    target_date: date,
    source_run_id: str,
    season_type: str = "Regular Season",
    calculation_version: str = TEAM_SNAPSHOT_CALCULATION_VERSION,
) -> TeamSnapshotPublicationContext:
    if not source_run_id:
        raise ValueError("source_run_id is required for durable snapshot publication")
    if not calculation_version:
        raise ValueError("calculation_version is required")
    return TeamSnapshotPublicationContext(
        season=normalize_season(season),
        season_type=normalize_season_type(season_type),
        target_date=target_date,
        feature_as_of=feature_cutoff_for_slate(target_date),
        calculation_version=calculation_version,
        source_run_id=source_run_id,
    )


def _game_id_matches_season_type(game_id: str, season_type: str) -> bool:
    normalized = str(game_id).lstrip("0")
    return normalized.startswith(SEASON_TYPE_GAME_ID_PREFIX[season_type])


def _fetch_slate_teams(
    db: Session,
    context: TeamSnapshotPublicationContext,
) -> List[SlateTeam]:
    rows = (
        db.query(GameScheduleORM)
        .filter(
            GameScheduleORM.season == context.season,
            text(
                "DATE((game_schedule.game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') = :team_snapshot_target_date"
            ).bindparams(team_snapshot_target_date=context.target_date),
        )
        .order_by(GameScheduleORM.game_date, GameScheduleORM.game_id, GameScheduleORM.team_id)
        .all()
    )
    return [
        SlateTeam(
            game_id=str(row.game_id),
            team_id=row.team_id,
            opponent_team_id=row.opponent_team_id,
            scheduled_tipoff=_aware_utc(row.game_date),
            is_home=row.home_or_away == "H",
        )
        for row in rows
        if _game_id_matches_season_type(row.game_id, context.season_type)
    ]


def _fetch_team_game_facts(
    db: Session,
    context: TeamSnapshotPublicationContext,
) -> List[TeamGameFact]:
    rows = (
        db.query(
            TeamGameStatsORM.game_id,
            TeamGameStatsORM.team_id,
            TeamGameStatsORM.opponent_team_id,
            GameScheduleORM.game_date,
            TeamGameStatsORM.fg,
            TeamGameStatsORM.fga,
            TeamGameStatsORM.fg3,
            TeamGameStatsORM.fta,
            TeamGameStatsORM.oreb,
            TeamGameStatsORM.dreb,
            TeamGameStatsORM.tov,
            TeamGameStatsORM.pts,
        )
        .join(
            GameScheduleORM,
            (TeamGameStatsORM.game_id == GameScheduleORM.game_id)
            & (TeamGameStatsORM.team_id == GameScheduleORM.team_id),
        )
        .filter(
            TeamGameStatsORM.season == context.season,
            GameScheduleORM.season == context.season,
            GameScheduleORM.result.in_(("W", "L")),
            GameScheduleORM.game_date < context.feature_as_of.replace(tzinfo=None),
            text(
                "DATE((game_schedule.game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') < :team_snapshot_target_date"
            ).bindparams(team_snapshot_target_date=context.target_date),
        )
        .order_by(GameScheduleORM.game_date, TeamGameStatsORM.game_id, TeamGameStatsORM.team_id)
        .all()
    )
    return [
        TeamGameFact(
            game_id=str(row.game_id),
            team_id=row.team_id,
            opponent_team_id=row.opponent_team_id,
            game_time=_aware_utc(row.game_date),
            fg=row.fg,
            fga=row.fga,
            fg3=row.fg3,
            fta=row.fta,
            oreb=row.oreb,
            dreb=row.dreb,
            tov=row.tov,
            pts=row.pts,
        )
        for row in rows
        if _game_id_matches_season_type(row.game_id, context.season_type)
    ]


def _required_missing(fact: TeamGameFact, opponent: Optional[TeamGameFact]) -> List[str]:
    missing = []
    if opponent is None:
        return ["opponent_pair"]
    team_fields = ("fg", "fga", "fg3", "fta", "oreb", "tov", "pts")
    opponent_fields = ("fga", "fta", "oreb", "dreb", "tov", "pts")
    for field in team_fields:
        if getattr(fact, field) is None:
            missing.append(f"team.{field}")
    for field in opponent_fields:
        if getattr(opponent, field) is None:
            missing.append(f"opponent.{field}")
    if opponent.team_id != fact.opponent_team_id or opponent.opponent_team_id != fact.team_id:
        missing.append("opponent_pair_reciprocity")
    return missing


def _aggregate_metrics(
    games: Sequence[TeamGameFact],
    pair_lookup: Mapping[Tuple[str, int], TeamGameFact],
) -> Tuple[Dict[str, Optional[float]], int, Dict[str, List[str]]]:
    usable: List[Tuple[TeamGameFact, TeamGameFact]] = []
    excluded: Dict[str, List[str]] = {}
    for fact in games:
        opponent = pair_lookup.get((fact.game_id, fact.opponent_team_id))
        missing = _required_missing(fact, opponent)
        if missing:
            excluded[fact.game_id] = missing
            continue
        usable.append((fact, opponent))

    empty = {name: None for name in METRIC_NAMES}
    if not usable:
        return empty, 0, excluded

    total_fg = sum(fact.fg for fact, _ in usable)
    total_fga = sum(fact.fga for fact, _ in usable)
    total_fg3 = sum(fact.fg3 for fact, _ in usable)
    total_fta = sum(fact.fta for fact, _ in usable)
    total_oreb = sum(fact.oreb for fact, _ in usable)
    total_tov = sum(fact.tov for fact, _ in usable)
    total_pts = sum(fact.pts for fact, _ in usable)
    total_opp_dreb = sum(opponent.dreb for _, opponent in usable)
    total_opp_pts = sum(opponent.pts for _, opponent in usable)

    possessions = sum(
        fact.fga + 0.44 * fact.fta - fact.oreb + fact.tov
        for fact, _ in usable
    )
    opponent_possessions = sum(
        opponent.fga + 0.44 * opponent.fta - opponent.oreb + opponent.tov
        for _, opponent in usable
    )
    games_used = len(usable)
    off_rtg = total_pts / possessions * 100 if possessions > 0 else None
    def_rtg = total_opp_pts / opponent_possessions * 100 if opponent_possessions > 0 else None
    net_rtg = off_rtg - def_rtg if off_rtg is not None and def_rtg is not None else None
    metrics = {
        "off_rtg": off_rtg,
        "def_rtg": def_rtg,
        "net_rtg": net_rtg,
        "pace": possessions / games_used if games_used else None,
        "efg": (total_fg + 0.5 * total_fg3) / total_fga if total_fga > 0 else None,
        "tov_pct": (
            total_tov / (total_fga + 0.44 * total_fta + total_tov)
            if total_fga + 0.44 * total_fta + total_tov > 0
            else None
        ),
        "orb_pct": (
            total_oreb / (total_oreb + total_opp_dreb)
            if total_oreb + total_opp_dreb > 0
            else None
        ),
        "ftr": total_fta / total_fga if total_fga > 0 else None,
        "pct_pts_3pt": total_fg3 * 3 / total_pts if total_pts > 0 else None,
    }
    return (
        {key: round(value, 4) if value is not None else None for key, value in metrics.items()},
        games_used,
        excluded,
    )


def _delta_metrics(
    season_metrics: Mapping[str, Optional[float]],
    recent_metrics: Mapping[str, Optional[float]],
) -> Dict[str, Optional[float]]:
    deltas = {}
    for name in METRIC_NAMES:
        season_value = season_metrics.get(name)
        recent_value = recent_metrics.get(name)
        deltas[f"{name}_delta"] = (
            round(recent_value - season_value, 4)
            if season_value is not None and recent_value is not None
            else None
        )
    return deltas


def _flags(deltas: Mapping[str, Optional[float]]) -> List[dict]:
    flags = []
    for flag_type, (metric, threshold, direction) in FLAG_THRESHOLDS.items():
        value = deltas.get(metric)
        if value is None:
            continue
        triggered = value >= threshold if direction == "positive" else value <= threshold
        if triggered:
            flags.append(
                {
                    "flag_type": flag_type,
                    "metric": metric,
                    "delta": round(value, 4),
                    "threshold": threshold,
                }
            )
    return flags


def _schedule_factors(games: Sequence[TeamGameFact], target_date: date) -> dict:
    prior_dates = sorted({game.game_date for game in games if game.game_date < target_date})
    days_rest = (target_date - prior_dates[-1]).days - 1 if prior_dates else None
    games_last_4 = sum(target_date - timedelta(days=3) <= value < target_date for value in prior_dates)
    games_last_5 = sum(target_date - timedelta(days=4) <= value < target_date for value in prior_dates)
    games_last_7 = sum(target_date - timedelta(days=6) <= value < target_date for value in prior_dates)
    return {
        "days_rest": days_rest,
        "is_b2b": days_rest == 0,
        "is_3_in_4": games_last_4 >= 2,
        "is_4_in_5": games_last_5 >= 3,
        "is_5_in_7": games_last_7 >= 4,
        "games_last_4_days": games_last_4,
        "games_last_7_days": games_last_7,
    }


def _opponent_net_ratings(
    facts_by_team: Mapping[int, Sequence[TeamGameFact]],
    pair_lookup: Mapping[Tuple[str, int], TeamGameFact],
) -> Dict[int, Optional[float]]:
    result = {}
    for team_id, games in facts_by_team.items():
        metrics, _, _ = _aggregate_metrics(games, pair_lookup)
        result[team_id] = metrics["net_rtg"]
    return result


def _average_opponent_rating(
    games: Sequence[TeamGameFact],
    ratings: Mapping[int, Optional[float]],
) -> Optional[float]:
    values = [ratings.get(game.opponent_team_id) for game in games]
    usable = [value for value in values if value is not None]
    return round(sum(usable) / len(usable), 4) if usable else None


def build_team_feature_records(
    context: TeamSnapshotPublicationContext,
    slate_teams: Sequence[SlateTeam],
    facts: Sequence[TeamGameFact],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    team_id: Optional[int] = None,
) -> List[dict]:
    """Build team records while defensively reapplying the pre-cutoff rule."""
    safe_facts = [
        fact
        for fact in facts
        if _aware_utc(fact.game_time) < context.feature_as_of
        and fact.game_date < context.target_date
        and _game_id_matches_season_type(fact.game_id, context.season_type)
    ]
    facts_by_team: Dict[int, List[TeamGameFact]] = defaultdict(list)
    for fact in safe_facts:
        facts_by_team[fact.team_id].append(fact)
    for team_games in facts_by_team.values():
        team_games.sort(key=lambda game: (_aware_utc(game.game_time), game.game_id))

    pair_lookup = {(fact.game_id, fact.team_id): fact for fact in safe_facts}
    opponent_ratings = _opponent_net_ratings(facts_by_team, pair_lookup)
    records = []
    for slate in slate_teams:
        if team_id is not None and slate.team_id != team_id:
            continue
        if slate.scheduled_tipoff <= context.feature_as_of:
            raise ValueError(
                f"Feature cutoff {context.feature_as_of.isoformat()} is not pregame for {slate.game_id}"
            )
        team_games = facts_by_team.get(slate.team_id, [])
        recent_games = team_games[-window_size:]
        season_metrics, season_used, season_excluded = _aggregate_metrics(team_games, pair_lookup)
        recent_metrics, recent_used, recent_excluded = _aggregate_metrics(recent_games, pair_lookup)
        deltas = _delta_metrics(season_metrics, recent_metrics)
        sos_season = _average_opponent_rating(team_games, opponent_ratings)
        sos_recent = _average_opponent_rating(recent_games, opponent_ratings)
        missing_flags = {}
        if len(recent_games) < window_size:
            missing_flags["insufficient_window_games"] = {
                "required": window_size,
                "available": len(recent_games),
            }
        if season_excluded:
            missing_flags["excluded_season_games"] = season_excluded
        if recent_excluded:
            missing_flags["excluded_window_games"] = recent_excluded
        if not team_games:
            missing_flags["no_prior_games"] = True

        completeness = (
            TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
            if len(recent_games) >= window_size
            and season_used == len(team_games)
            and recent_used == len(recent_games)
            else TEAM_SNAPSHOT_COMPLETENESS_PARTIAL
        )
        used_games = [
            game
            for game in team_games
            if game.game_id not in season_excluded
        ]
        latest = used_games[-1] if used_games else None
        data_available_at = (
            max(_aware_utc(game.game_time) + SOURCE_AVAILABILITY_LAG for game in used_games)
            if used_games
            else None
        )
        record = {
            "game_id": slate.game_id,
            "team_id": slate.team_id,
            "opponent_team_id": slate.opponent_team_id,
            "game_date": context.target_date,
            "scheduled_tipoff": slate.scheduled_tipoff,
            "is_home": slate.is_home,
            "window_size": window_size,
            "season": context.season,
            "season_type": context.season_type,
            "feature_as_of": context.feature_as_of,
            "data_available_at": data_available_at,
            "calculation_version": context.calculation_version,
            "source_run_id": context.source_run_id,
            "completeness_status": completeness,
            "missing_input_flags": missing_flags,
            "source_latest_game_id": latest.game_id if latest else None,
            "source_latest_game_date": latest.game_date if latest else None,
            "season_games_played": len(team_games),
            "season_games_used": season_used,
            "window_games_played": len(recent_games),
            "window_games_used": recent_used,
            "sos_net_season": sos_season,
            "sos_net_lastn": sos_recent,
            "sos_net_delta": (
                round(sos_recent - sos_season, 4)
                if sos_season is not None and sos_recent is not None
                else None
            ),
            "flags": _flags(deltas),
            **_schedule_factors(team_games, context.target_date),
        }
        for name in METRIC_NAMES:
            record[f"{name}_season"] = season_metrics[name]
            record[f"{name}_lastn"] = recent_metrics[name]
            record[f"{name}_delta"] = deltas[f"{name}_delta"]
        records.append(record)
    return records


def _pace_projection(home_pace: float, away_pace: float) -> float:
    average = (home_pace + away_pace) / 2
    return round(0.7 * average + 0.3 * max(home_pace, away_pace), 2)


def build_game_environment_records(
    context: TeamSnapshotPublicationContext,
    team_records: Sequence[Mapping],
) -> List[dict]:
    grouped: Dict[str, List[Mapping]] = defaultdict(list)
    for record in team_records:
        grouped[str(record["game_id"])].append(record)

    environments = []
    for game_id, paired in grouped.items():
        if len(paired) != 2:
            continue
        home = next((row for row in paired if row["is_home"]), None)
        away = next((row for row in paired if not row["is_home"]), None)
        if home is None or away is None:
            continue
        required = (
            "off_rtg_lastn",
            "def_rtg_lastn",
            "pace_lastn",
            "tov_pct_lastn",
        )
        missing = {
            side: [field for field in required if row.get(field) is None]
            for side, row in (("home", home), ("away", away))
        }
        missing = {key: value for key, value in missing.items() if value}
        complete = (
            not missing
            and home["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
            and away["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
        )
        pace = scoring = three = chaos = None
        tags: List[str] = []
        if not missing:
            pace = _pace_projection(home["pace_lastn"], away["pace_lastn"])
            home_expected = (home["off_rtg_lastn"] + away["def_rtg_lastn"]) / 2
            away_expected = (away["off_rtg_lastn"] + home["def_rtg_lastn"]) / 2
            scoring = round((((home_expected + away_expected) / 2) * (pace / 99.0) / 115.0) * 100, 2)
            if home.get("pct_pts_3pt_lastn") is not None and away.get("pct_pts_3pt_lastn") is not None:
                three = round(
                    (((home["pct_pts_3pt_lastn"] + away["pct_pts_3pt_lastn"]) / 2) / 0.35) * 100,
                    2,
                )
            average_tov = (home["tov_pct_lastn"] + away["tov_pct_lastn"]) / 2
            chaos = round((pace / 99.0) * 50 + (average_tov / 0.14) * 50, 2)
            if pace > 105:
                tags.append("fast_pace")
            elif pace < 94:
                tags.append("slow_pace")
            if scoring > 108:
                tags.append("high_scoring")
            elif scoring < 92:
                tags.append("defensive_battle")
            if three is not None and three > 110:
                tags.append("three_point_fest")
            if chaos > 115:
                tags.append("chaotic")

        missing_flags = dict(missing)
        if not complete and not missing_flags:
            missing_flags["partial_team_snapshots"] = True
        data_times = [value for value in (home.get("data_available_at"), away.get("data_available_at")) if value]
        environments.append(
            {
                "game_id": game_id,
                "game_date": context.target_date,
                "scheduled_tipoff": home["scheduled_tipoff"],
                "home_team_id": home["team_id"],
                "away_team_id": away["team_id"],
                "window_size": home["window_size"],
                "season": context.season,
                "season_type": context.season_type,
                "feature_as_of": context.feature_as_of,
                "data_available_at": max(data_times) if data_times else None,
                "calculation_version": context.calculation_version,
                "source_run_id": context.source_run_id,
                "completeness_status": (
                    TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
                    if complete
                    else TEAM_SNAPSHOT_COMPLETENESS_PARTIAL
                ),
                "missing_input_flags": missing_flags,
                "home_off_rtg_lastn": home.get("off_rtg_lastn"),
                "home_def_rtg_lastn": home.get("def_rtg_lastn"),
                "home_pace_lastn": home.get("pace_lastn"),
                "away_off_rtg_lastn": away.get("off_rtg_lastn"),
                "away_def_rtg_lastn": away.get("def_rtg_lastn"),
                "away_pace_lastn": away.get("pace_lastn"),
                "pace_projection": pace,
                "scoring_env_index": scoring,
                "three_env_index": three,
                "chaos_index": chaos,
                "pace_up_for_home": bool(
                    home.get("pace_delta") is not None and home["pace_delta"] >= 2
                ),
                "pace_up_for_away": bool(
                    away.get("pace_delta") is not None and away["pace_delta"] >= 2
                ),
                "tags": tags,
            }
        )
    return environments


def _build_records(
    db: Session,
    context: TeamSnapshotPublicationContext,
    *,
    window_size: int,
    team_id: Optional[int],
) -> Tuple[List[dict], List[dict]]:
    slate_teams = _fetch_slate_teams(db, context)
    facts = _fetch_team_game_facts(db, context)
    team_records = build_team_feature_records(
        context,
        slate_teams,
        facts,
        window_size=window_size,
        team_id=team_id,
    )
    environment_records = build_game_environment_records(context, team_records)
    return team_records, environment_records


def publish_team_game_snapshots(
    context: TeamSnapshotPublicationContext,
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    team_id: Optional[int] = None,
    dry_run: bool = False,
    db: Optional[Session] = None,
) -> Dict[str, int]:
    """Atomically publish team features and paired game environments."""
    if window_size < 1:
        raise ValueError("window_size must be positive")

    def _publish(session: Session) -> Dict[str, int]:
        team_records, environment_records = _build_records(
            session,
            context,
            window_size=window_size,
            team_id=team_id,
        )
        counts = {
            "team_features": len(team_records),
            "game_environments": len(environment_records),
        }
        if dry_run:
            return counts
        bulk_upsert_snapshots(
            TeamGameFeatureSnapshotORM,
            team_records,
            natural_key=(
                "game_id",
                "team_id",
                "window_size",
                "feature_as_of",
                "calculation_version",
            ),
            db=session,
        )
        bulk_upsert_snapshots(
            GameEnvironmentSnapshotORM,
            environment_records,
            natural_key=(
                "game_id",
                "window_size",
                "feature_as_of",
                "calculation_version",
            ),
            db=session,
        )
        return counts

    if db is not None:
        return _publish(db)
    with get_db_context() as session:
        return _publish(session)


def latest_team_feature_snapshot(
    *,
    game_id: str,
    team_id: int,
    requested_cutoff: datetime,
    calculation_version: str = TEAM_SNAPSHOT_CALCULATION_VERSION,
    include_partial: bool = False,
    db: Session,
) -> TeamSnapshotReadResult:
    query = db.query(TeamGameFeatureSnapshotORM).filter(
        TeamGameFeatureSnapshotORM.game_id == str(game_id),
        TeamGameFeatureSnapshotORM.team_id == team_id,
        TeamGameFeatureSnapshotORM.calculation_version == calculation_version,
        TeamGameFeatureSnapshotORM.feature_as_of <= _aware_utc(requested_cutoff),
        TeamGameFeatureSnapshotORM.data_available_at <= _aware_utc(requested_cutoff),
    )
    if not include_partial:
        query = query.filter(
            TeamGameFeatureSnapshotORM.completeness_status
            == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
        )
    row = query.order_by(TeamGameFeatureSnapshotORM.feature_as_of.desc()).first()
    return TeamSnapshotReadResult(
        rows=[row] if row else [],
        feature_as_of=row.feature_as_of if row else None,
        calculation_version=calculation_version,
    )


def latest_game_environment_snapshot(
    *,
    game_id: str,
    requested_cutoff: datetime,
    calculation_version: str = TEAM_SNAPSHOT_CALCULATION_VERSION,
    include_partial: bool = False,
    db: Session,
) -> TeamSnapshotReadResult:
    query = db.query(GameEnvironmentSnapshotORM).filter(
        GameEnvironmentSnapshotORM.game_id == str(game_id),
        GameEnvironmentSnapshotORM.calculation_version == calculation_version,
        GameEnvironmentSnapshotORM.feature_as_of <= _aware_utc(requested_cutoff),
        GameEnvironmentSnapshotORM.data_available_at <= _aware_utc(requested_cutoff),
    )
    if not include_partial:
        query = query.filter(
            GameEnvironmentSnapshotORM.completeness_status
            == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
        )
    row = query.order_by(GameEnvironmentSnapshotORM.feature_as_of.desc()).first()
    return TeamSnapshotReadResult(
        rows=[row] if row else [],
        feature_as_of=row.feature_as_of if row else None,
        calculation_version=calculation_version,
    )
