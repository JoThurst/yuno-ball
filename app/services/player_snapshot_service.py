"""Leakage-safe calculation and lookup for durable player snapshots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import statistics
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.player_analytics_snapshot_sqlalchemy import (
    PLAYER_SNAPSHOT_CALCULATION_VERSION,
    PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
    PlayerConsecutiveStreakSnapshotORM,
    PlayerConsistencySnapshotORM,
    PlayerHeatIndexSnapshotORM,
    PlayerStatWindowSnapshotORM,
    bulk_upsert_snapshots,
)
from app.utils.season_utils import normalize_season, normalize_season_type


EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
SNAPSHOT_PUBLISH_HOUR_ET = 10
SOURCE_AVAILABILITY_LAG = timedelta(hours=6)

STREAK_STATS = ("PTS", "REB", "AST", "STL", "BLK", "PRA")
HEAT_STATS = ("PTS", "REB", "AST", "PRA")
CONSISTENCY_STATS = ("pts", "reb", "ast", "pra", "stl", "blk", "tov")
WINDOW_SIZES = (5, 10)
HEAT_WINDOW_SIZES = (3, 5, 10)
CONSISTENCY_WINDOW_SIZES = (0, 10)
MIN_CONSISTENCY_GAMES = 5

THRESHOLDS: Mapping[str, Sequence[int]] = {
    "PTS": (10, 15, 20, 25, 30),
    "REB": (4, 6, 8, 10, 12),
    "AST": (2, 4, 6, 8, 10),
    "STL": (1, 2, 3, 4),
    "BLK": (1, 2, 3, 4),
    "PRA": (20, 25, 30, 35, 40),
}

SEASON_TYPE_GAME_ID_PREFIX = {
    "Pre Season": "1",
    "Regular Season": "2",
    "All-Star": "3",
    "Playoffs": "4",
}


@dataclass(frozen=True)
class PlayerGameFact:
    player_id: int
    player_name: str
    game_id: str
    team_id: int
    game_time: datetime
    points: Optional[int]
    rebounds: Optional[int]
    assists: Optional[int]
    steals: Optional[int]
    blocks: Optional[int]
    turnovers: Optional[int]

    @property
    def game_date(self) -> date:
        return _aware_utc(self.game_time).astimezone(EASTERN).date()


@dataclass(frozen=True)
class SnapshotPublicationContext:
    season: str
    season_type: str
    target_date: date
    feature_as_of: datetime
    calculation_version: str
    source_run_id: str


@dataclass(frozen=True)
class SnapshotReadResult:
    rows: Sequence[object]
    feature_as_of: Optional[datetime]
    calculation_version: str


def feature_cutoff_for_slate(target_date: date) -> datetime:
    """Canonical snapshot time: 10:00 ET before the target slate begins."""
    local_cutoff = datetime.combine(
        target_date,
        time(hour=SNAPSHOT_PUBLISH_HOUR_ET),
        tzinfo=EASTERN,
    )
    return local_cutoff.astimezone(UTC)


def build_snapshot_context(
    *,
    season: str,
    target_date: date,
    source_run_id: str,
    season_type: str = "Regular Season",
    calculation_version: str = PLAYER_SNAPSHOT_CALCULATION_VERSION,
) -> SnapshotPublicationContext:
    if not source_run_id:
        raise ValueError("source_run_id is required for durable snapshot publication")
    if not calculation_version:
        raise ValueError("calculation_version is required")
    return SnapshotPublicationContext(
        season=normalize_season(season),
        season_type=normalize_season_type(season_type),
        target_date=target_date,
        feature_as_of=feature_cutoff_for_slate(target_date),
        calculation_version=calculation_version,
        source_run_id=source_run_id,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _game_id_matches_season_type(game_id: str, season_type: str) -> bool:
    normalized = str(game_id).lstrip("0")
    expected = SEASON_TYPE_GAME_ID_PREFIX[season_type]
    return normalized.startswith(expected)


def _stat_value(game: PlayerGameFact, stat: str) -> Optional[float]:
    field = {
        "PTS": "points",
        "REB": "rebounds",
        "AST": "assists",
        "STL": "steals",
        "BLK": "blocks",
        "TOV": "turnovers",
    }.get(stat.upper())
    if stat.upper() == "PRA":
        components = (game.points, game.rebounds, game.assists)
        if any(value is None for value in components):
            return None
        return float(sum(components))
    if field is None:
        return None
    value = getattr(game, field)
    return float(value) if value is not None else None


def _provenance(
    context: SnapshotPublicationContext,
    data_available_at: datetime,
) -> dict:
    return {
        "season": context.season,
        "season_type": context.season_type,
        "feature_as_of": context.feature_as_of,
        "data_available_at": data_available_at,
        "calculation_version": context.calculation_version,
        "source_run_id": context.source_run_id,
        "completeness_status": PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
        "missing_input_flags": {},
    }


def _fetch_game_facts(
    db: Session,
    context: SnapshotPublicationContext,
) -> List[PlayerGameFact]:
    """Read only source facts strictly before the target slate calendar date."""
    rows = (
        db.query(
            GameLogORM.player_id,
            PlayerORM.name.label("player_name"),
            GameLogORM.game_id,
            GameLogORM.team_id,
            GameScheduleORM.game_date,
            GameLogORM.points,
            GameLogORM.rebounds,
            GameLogORM.assists,
            GameLogORM.steals,
            GameLogORM.blocks,
            GameLogORM.turnovers,
        )
        .join(
            GameScheduleORM,
            (GameLogORM.game_id == GameScheduleORM.game_id)
            & (GameLogORM.team_id == GameScheduleORM.team_id),
        )
        .join(PlayerORM, PlayerORM.player_id == GameLogORM.player_id)
        .filter(
            GameLogORM.season == context.season,
            GameScheduleORM.season == context.season,
            GameScheduleORM.result.in_(("W", "L")),
            GameScheduleORM.game_date < context.feature_as_of.replace(tzinfo=None),
            text(
                "DATE((game_schedule.game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') < :snapshot_target_date"
            ).bindparams(snapshot_target_date=context.target_date),
        )
        .order_by(
            GameLogORM.player_id,
            GameScheduleORM.game_date,
            GameLogORM.game_id,
        )
        .all()
    )
    return [
        PlayerGameFact(
            player_id=row.player_id,
            player_name=row.player_name,
            game_id=str(row.game_id),
            team_id=row.team_id,
            game_time=row.game_date,
            points=row.points,
            rebounds=row.rebounds,
            assists=row.assists,
            steals=row.steals,
            blocks=row.blocks,
            turnovers=row.turnovers,
        )
        for row in rows
        if _game_id_matches_season_type(row.game_id, context.season_type)
    ]


def _target_slate_exists(db: Session, context: SnapshotPublicationContext) -> bool:
    rows = (
        db.query(GameScheduleORM.game_id)
        .filter(
            GameScheduleORM.season == context.season,
            text(
                "DATE((game_schedule.game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') = :snapshot_target_date"
            ).bindparams(snapshot_target_date=context.target_date),
        )
        .distinct()
        .all()
    )
    return any(
        _game_id_matches_season_type(row.game_id, context.season_type)
        for row in rows
    )


def calculate_snapshot_records(
    facts: Iterable[PlayerGameFact],
    context: SnapshotPublicationContext,
) -> Dict[str, List[dict]]:
    """Pure calculation layer used by the writer and preservation tests."""
    ordered_facts = sorted(
        facts,
        key=lambda game: (game.player_id, _aware_utc(game.game_time), game.game_id),
    )
    if not ordered_facts:
        return {"streaks": [], "windows": [], "heat": [], "consistency": []}

    latest_source_time = max(_aware_utc(game.game_time) for game in ordered_facts)
    data_available_at = latest_source_time + SOURCE_AVAILABILITY_LAG
    if data_available_at > context.feature_as_of:
        raise ValueError(
            "Input availability rule exceeds feature_as_of; choose a later snapshot cutoff"
        )
    provenance = _provenance(context, data_available_at)

    by_player: Dict[int, List[PlayerGameFact]] = defaultdict(list)
    for game in ordered_facts:
        by_player[game.player_id].append(game)

    results: Dict[str, List[dict]] = {
        "streaks": [],
        "windows": [],
        "heat": [],
        "consistency": [],
    }
    for games in by_player.values():
        _calculate_streaks_and_windows(games, provenance, results)
        _calculate_heat(games, provenance, results)
        _calculate_consistency(games, provenance, results)
    return results


def _calculate_streaks_and_windows(
    games: Sequence[PlayerGameFact],
    provenance: Mapping,
    results: Dict[str, List[dict]],
) -> None:
    player = games[0]
    for stat in STREAK_STATS:
        values = [_stat_value(game, stat) for game in games]
        # A missing basketball value is unknown, not zero.  Do not publish a
        # complete record for this player/stat if any source game is incomplete.
        if any(value is None for value in values):
            continue

        for threshold in THRESHOLDS[stat]:
            current_length = 0
            for value in reversed(values):
                if value >= threshold:
                    current_length += 1
                else:
                    break
            if current_length:
                streak_games = games[-current_length:]
                results["streaks"].append({
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "stat": stat,
                    "threshold": threshold,
                    "streak_games": current_length,
                    "start_game_id": streak_games[0].game_id,
                    "end_game_id": streak_games[-1].game_id,
                    "start_date": streak_games[0].game_date,
                    "end_date": streak_games[-1].game_date,
                    "is_active": True,
                    "streak_kind": "current",
                    **provenance,
                })

            best_start = best_end = None
            best_length = run_start = run_length = 0
            for index, value in enumerate(values):
                if value >= threshold:
                    if run_length == 0:
                        run_start = index
                    run_length += 1
                    if run_length > best_length:
                        best_length = run_length
                        best_start = run_start
                        best_end = index
                else:
                    run_length = 0
            if best_length:
                results["streaks"].append({
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "stat": stat,
                    "threshold": threshold,
                    "streak_games": best_length,
                    "start_game_id": games[best_start].game_id,
                    "end_game_id": games[best_end].game_id,
                    "start_date": games[best_start].game_date,
                    "end_date": games[best_end].game_date,
                    "is_active": False,
                    "streak_kind": "season_max",
                    **provenance,
                })

            for window_size in WINDOW_SIZES:
                window_games = games[-window_size:]
                window_values = values[-window_size:]
                results["windows"].append({
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "stat": stat,
                    "threshold": threshold,
                    "window_size": window_size,
                    "games_played": len(window_games),
                    "games_hit": sum(value >= threshold for value in window_values),
                    "last_game_id": games[-1].game_id,
                    "last_game_date": games[-1].game_date,
                    **provenance,
                })


def _calculate_heat(
    games: Sequence[PlayerGameFact],
    provenance: Mapping,
    results: Dict[str, List[dict]],
) -> None:
    player = games[0]
    for stat in HEAT_STATS:
        values = [_stat_value(game, stat) for game in games]
        if len(values) < 3 or any(value is None for value in values):
            continue
        season_avg = statistics.mean(values)
        season_std = statistics.stdev(values)
        if season_std == 0:
            continue
        for window_size in HEAT_WINDOW_SIZES:
            recent_values = values[-window_size:]
            recent_avg = statistics.mean(recent_values)
            z_score = (recent_avg - season_avg) / season_std
            status = (
                "on_fire" if z_score >= 1.0
                else "ice_cold" if z_score <= -1.0
                else "normal"
            )
            results["heat"].append({
                "player_id": player.player_id,
                "player_name": player.player_name,
                "stat": stat,
                "window_size": window_size,
                "games_played": len(values),
                "recent_games_played": len(recent_values),
                "season_avg": round(season_avg, 2),
                "season_std": round(season_std, 2),
                "recent_avg": round(recent_avg, 2),
                "z_score": round(z_score, 3),
                "status": status,
                **provenance,
            })


def _calculate_consistency(
    games: Sequence[PlayerGameFact],
    provenance: Mapping,
    results: Dict[str, List[dict]],
) -> None:
    player = games[0]
    for stat_name in CONSISTENCY_STATS:
        values = [_stat_value(game, stat_name.upper()) for game in games]
        if any(value is None for value in values):
            continue
        for window_size in CONSISTENCY_WINDOW_SIZES:
            selected = values if window_size == 0 else values[-window_size:]
            if len(selected) < MIN_CONSISTENCY_GAMES:
                continue
            mean = statistics.mean(selected)
            stddev = statistics.stdev(selected)
            cv = stddev / mean if mean > 0 else 0.0
            tier = "steady" if cv < 0.35 else "volatile" if cv > 0.55 else "average"
            results["consistency"].append({
                "player_id": player.player_id,
                "player_name": player.player_name,
                "stat_name": stat_name,
                "window_size": window_size,
                "games_played": len(selected),
                "mean": round(mean, 2),
                "stddev": round(stddev, 2),
                "cv": round(cv, 4),
                "min_val": round(min(selected), 2),
                "max_val": round(max(selected), 2),
                "median": round(statistics.median(selected), 2),
                "consistency_tier": tier,
                **provenance,
            })


def publish_player_snapshots(
    context: SnapshotPublicationContext,
    *,
    db: Optional[Session] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Calculate and atomically upsert all four player snapshot families."""
    if db is None:
        with get_db_context() as session:
            return publish_player_snapshots(context, db=session, dry_run=dry_run)

    if not _target_slate_exists(db, context):
        return {"streaks": 0, "windows": 0, "heat": 0, "consistency": 0}

    records = calculate_snapshot_records(_fetch_game_facts(db, context), context)
    counts = {name: len(values) for name, values in records.items()}
    if dry_run:
        return counts

    bulk_upsert_snapshots(
        PlayerConsecutiveStreakSnapshotORM,
        records["streaks"],
        natural_key=(
            "player_id", "stat", "threshold", "season", "season_type",
            "feature_as_of", "calculation_version", "streak_kind",
        ),
        db=db,
    )
    bulk_upsert_snapshots(
        PlayerStatWindowSnapshotORM,
        records["windows"],
        natural_key=(
            "player_id", "stat", "threshold", "season", "season_type",
            "window_size", "feature_as_of", "calculation_version",
        ),
        db=db,
    )
    bulk_upsert_snapshots(
        PlayerHeatIndexSnapshotORM,
        records["heat"],
        natural_key=(
            "player_id", "stat", "season", "season_type", "window_size",
            "feature_as_of", "calculation_version",
        ),
        db=db,
    )
    bulk_upsert_snapshots(
        PlayerConsistencySnapshotORM,
        records["consistency"],
        natural_key=(
            "player_id", "season", "season_type", "stat_name", "window_size",
            "feature_as_of", "calculation_version",
        ),
        db=db,
    )
    return counts


def load_latest_complete_snapshot(
    db: Session,
    model,
    *,
    season: str,
    requested_cutoff: datetime,
    player_ids: Optional[Sequence[int]] = None,
    season_type: str = "Regular Season",
    calculation_version: str = PLAYER_SNAPSHOT_CALCULATION_VERSION,
) -> SnapshotReadResult:
    """Load one exact latest-valid cutoff; never fall forward or mix versions."""
    season = normalize_season(season)
    season_type = normalize_season_type(season_type)
    cutoff = (
        db.query(func.max(model.feature_as_of))
        .filter(
            model.season == season,
            model.season_type == season_type,
            model.calculation_version == calculation_version,
            model.completeness_status == PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
            model.feature_as_of <= requested_cutoff,
            model.data_available_at <= requested_cutoff,
        )
        .scalar()
    )
    if cutoff is None:
        return SnapshotReadResult((), None, calculation_version)

    query = db.query(model).filter(
        model.season == season,
        model.season_type == season_type,
        model.calculation_version == calculation_version,
        model.completeness_status == PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
        model.feature_as_of == cutoff,
    )
    if player_ids is not None:
        if not player_ids:
            return SnapshotReadResult((), cutoff, calculation_version)
        query = query.filter(model.player_id.in_(player_ids))
    return SnapshotReadResult(tuple(query.all()), cutoff, calculation_version)


def load_complete_snapshot_at_cutoff(
    db: Session,
    model,
    *,
    season: str,
    feature_as_of: datetime,
    player_ids: Optional[Sequence[int]] = None,
    season_type: str = "Regular Season",
    calculation_version: str = PLAYER_SNAPSHOT_CALCULATION_VERSION,
) -> SnapshotReadResult:
    """Load rows at one anchor cutoff so a payload never mixes slate versions."""
    query = db.query(model).filter(
        model.season == normalize_season(season),
        model.season_type == normalize_season_type(season_type),
        model.calculation_version == calculation_version,
        model.completeness_status == PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
        model.feature_as_of == feature_as_of,
        model.data_available_at <= feature_as_of,
    )
    if player_ids is not None:
        if not player_ids:
            return SnapshotReadResult((), feature_as_of, calculation_version)
        query = query.filter(model.player_id.in_(player_ids))
    return SnapshotReadResult(tuple(query.all()), feature_as_of, calculation_version)


def complete_snapshot_history_exists(
    db: Session,
    *,
    season: str,
    season_type: str = "Regular Season",
    calculation_version: str = PLAYER_SNAPSHOT_CALCULATION_VERSION,
) -> bool:
    """Return whether v2 history exists, even if none is eligible for a request."""
    return (
        db.query(PlayerStatWindowSnapshotORM.id)
        .filter(
            PlayerStatWindowSnapshotORM.season == normalize_season(season),
            PlayerStatWindowSnapshotORM.season_type == normalize_season_type(season_type),
            PlayerStatWindowSnapshotORM.calculation_version == calculation_version,
            PlayerStatWindowSnapshotORM.completeness_status
            == PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE,
        )
        .first()
        is not None
    )
