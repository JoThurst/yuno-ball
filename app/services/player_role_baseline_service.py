"""Build actual-role history and pregame minutes bands from canonical facts.

This module deliberately exposes a role *band*, not a precise minutes
prediction.  Unknown starter status and missing minutes remain unknown, and
only rows available before the requested feature cutoff may enter a baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import floor
from typing import Any, Iterable, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.models.player_role_baseline_sqlalchemy import (
    ROLE_BASELINE_VERSION,
    ROLE_HISTORY_VERSION,
    PlayerRoleHistoryORM,
    PregamePlayerRoleBaselineORM,
    bulk_upsert_role_records,
)


MIN_COMPLETE_HISTORY_GAMES = 5
DEFAULT_WINDOW_SIZE = 10
ROLE_HISTORY_SOURCE = "canonical_player_game_facts"


@dataclass(frozen=True)
class RoleHistoryObservation:
    canonical_game_id: str
    canonical_player_id: int
    canonical_team_id: int
    game_date: date
    season: str
    season_type: str
    participation_status: str
    starter_status: str
    starter_position: str | None
    minutes: str | None
    minutes_decimal: float | None
    source_name: str
    source_fact_id: str
    source_row_sha256: str
    source_run_id: str
    data_available_at: datetime
    calculation_version: str = ROLE_HISTORY_VERSION


def parse_minutes(value: Any) -> float | None:
    """Parse common NBA minute formats without turning missing into zero."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 2)
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("PT"):
        hours = minutes = seconds = 0.0
        remainder = text[2:]
        if "H" in remainder:
            hours_text, remainder = remainder.split("H", 1)
            hours = float(hours_text)
        if "M" in remainder:
            minutes_text, remainder = remainder.split("M", 1)
            minutes = float(minutes_text)
        if "S" in remainder:
            seconds = float(remainder[:-1])
        return round(hours * 60 + minutes + seconds / 60, 2)
    if ":" in text:
        parts = [float(part) for part in text.split(":")]
        if len(parts) == 2:
            return round(parts[0] + parts[1] / 60, 2)
        if len(parts) == 3:
            return round(parts[0] * 60 + parts[1] + parts[2] / 60, 2)
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def build_role_history_observation(
    fact: Any,
    *,
    calculation_version: str = ROLE_HISTORY_VERSION,
) -> RoleHistoryObservation:
    """Convert one canonical fact into a named role-history observation."""
    data_available_at = _get(fact, "data_available_at")
    if data_available_at is None:
        raise ValueError("role history requires data_available_at")
    return RoleHistoryObservation(
        canonical_game_id=str(_get(fact, "canonical_game_id")),
        canonical_player_id=int(_get(fact, "canonical_player_id")),
        canonical_team_id=int(_get(fact, "canonical_team_id")),
        game_date=_as_date(_get(fact, "game_date")),
        season=str(_get(fact, "season")),
        season_type=str(_get(fact, "season_type")),
        participation_status=str(_get(fact, "participation_status")),
        starter_status=str(_get(fact, "starter_status", "unknown")),
        starter_position=_get(fact, "starter_position"),
        minutes=_get(fact, "minutes"),
        minutes_decimal=parse_minutes(_get(fact, "minutes")),
        source_name=str(_get(fact, "source_name")),
        source_fact_id=str(_get(fact, "fact_id")),
        source_row_sha256=str(_get(fact, "source_row_sha256")),
        source_run_id=str(_get(fact, "source_run_id")),
        data_available_at=_as_utc(data_available_at),
        calculation_version=calculation_version,
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _round_minutes(value: float | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_pregame_role_baseline(
    history_rows: Iterable[RoleHistoryObservation | Mapping[str, Any]],
    *,
    canonical_game_id: str,
    canonical_player_id: int,
    canonical_team_id: int,
    target_game_date: date,
    season: str,
    season_type: str,
    feature_as_of: datetime,
    scheduled_tipoff: datetime | None = None,
    source_run_id: str | None = None,
    window_size: int = DEFAULT_WINDOW_SIZE,
    min_complete_history_games: int = MIN_COMPLETE_HISTORY_GAMES,
    calculation_version: str = ROLE_BASELINE_VERSION,
    timing_policy: str = "strict_source",
    low_percentile: float = 0.25,
    high_percentile: float = 0.75,
) -> dict[str, Any]:
    """Build one pregame role band from strictly prior, available history."""
    if window_size < 1:
        raise ValueError("window_size must be positive")
    if min_complete_history_games < 1:
        raise ValueError("min_complete_history_games must be positive")
    if min_complete_history_games > window_size:
        raise ValueError("min_complete_history_games must not exceed window_size")
    if not source_run_id:
        raise ValueError("source_run_id is required for durable role baselines")
    if timing_policy not in {"strict_source", "historical_game_date_proxy"}:
        raise ValueError("timing_policy must be strict_source or historical_game_date_proxy")
    if not 0 <= low_percentile < 0.5 < high_percentile <= 1:
        raise ValueError("band percentiles must satisfy 0 <= low < 0.5 < high <= 1")
    cutoff = _as_utc(feature_as_of)
    target_date = _as_date(target_game_date)
    eligible: list[RoleHistoryObservation] = []
    for raw in history_rows:
        row = raw if isinstance(raw, RoleHistoryObservation) else build_role_history_observation(raw)
        if (
            row.canonical_player_id != canonical_player_id
            or row.canonical_team_id != canonical_team_id
            or row.season != season
            or row.season_type != season_type
            or row.canonical_game_id == canonical_game_id
            or row.game_date >= target_date
            or (
                timing_policy == "strict_source"
                and _as_utc(row.data_available_at) > cutoff
            )
        ):
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: (row.game_date, row.canonical_game_id), reverse=True)
    window = eligible[:window_size]
    usable = [row for row in window if row.participation_status == "played" and row.minutes_decimal is not None]
    usable_minutes = [float(row.minutes_decimal) for row in usable if row.minutes_decimal is not None]
    missing: list[str] = []
    if not usable_minutes:
        missing.append("no_prior_played_minutes")
    if timing_policy == "historical_game_date_proxy":
        missing.append("historical_source_time_unknown")
    if len(usable_minutes) < min_complete_history_games:
        missing.append("insufficient_prior_played_minutes")
    if not eligible:
        status = "unknown"
        confidence = "none"
    elif len(usable_minutes) < min_complete_history_games:
        status = "partial"
        confidence = "low"
    elif len(usable_minutes) < window_size:
        status = "partial"
        confidence = "medium"
    else:
        status = "complete"
        confidence = "high"
    latest = max((row.game_date for row in usable), default=None)
    source_available = (
        max((row.data_available_at for row in usable), default=None)
        if timing_policy == "strict_source"
        else None
    )
    return {
        "baseline_id": str(uuid5(
            NAMESPACE_URL,
            f"{canonical_game_id}:{canonical_player_id}:{canonical_team_id}:{window_size}:{cutoff.isoformat()}:{calculation_version}",
        )),
        "canonical_game_id": canonical_game_id,
        "canonical_player_id": canonical_player_id,
        "canonical_team_id": canonical_team_id,
        "target_game_date": target_date,
        "scheduled_tipoff": scheduled_tipoff,
        "season": season,
        "season_type": season_type,
        "window_size": window_size,
        "history_games_seen": len(window),
        "played_games_used": len(usable_minutes),
        "start_count": sum(row.starter_status == "starter" for row in usable),
        "baseline_minutes_low": _round_minutes(_percentile(usable_minutes, low_percentile) if usable_minutes else None),
        "baseline_minutes_median": _round_minutes(_percentile(usable_minutes, 0.50) if usable_minutes else None),
        "baseline_minutes_high": _round_minutes(_percentile(usable_minutes, high_percentile) if usable_minutes else None),
        "latest_history_date": latest,
        "completeness_status": status,
        "confidence_band": confidence,
        "timing_policy": timing_policy,
        "feature_as_of": cutoff,
        "data_available_at": source_available,
        "source_name": ROLE_HISTORY_SOURCE,
        "calculation_version": calculation_version,
        "source_run_id": source_run_id,
        "missing_input_flags": missing,
    }


def role_history_records_from_facts(
    facts: Iterable[Any],
    *,
    calculation_version: str = ROLE_HISTORY_VERSION,
) -> list[dict[str, Any]]:
    """Return deterministic records suitable for a bounded upsert."""
    records = []
    for fact in facts:
        observation = build_role_history_observation(
            fact,
            calculation_version=calculation_version,
        )
        records.append({
            "role_history_id": str(uuid5(
                NAMESPACE_URL,
                f"{observation.canonical_game_id}:{observation.canonical_player_id}:{observation.canonical_team_id}:{calculation_version}",
            )),
            **observation.__dict__,
        })
    return records


def publish_role_history(records: Iterable[Mapping[str, Any]], *, db: Session) -> int:
    return bulk_upsert_role_records(
        PlayerRoleHistoryORM,
        records,
        natural_key=(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "calculation_version",
        ),
        db=db,
    )


def publish_role_baselines(records: Iterable[Mapping[str, Any]], *, db: Session) -> int:
    records = [dict(record) for record in records]
    if any(record.get("timing_policy") != "strict_source" for record in records):
        raise ValueError("historical timing-proxy baselines are audit-only and cannot be published")
    return bulk_upsert_role_records(
        PregamePlayerRoleBaselineORM,
        records,
        natural_key=(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
        ),
        db=db,
    )


def build_role_history_from_db(
    db: Session,
    *,
    season: str,
    season_type: str,
    calculation_version: str = ROLE_HISTORY_VERSION,
) -> list[dict[str, Any]]:
    """Build role history from canonical facts without changing source facts."""
    facts = (
        db.query(PlayerGameFactORM)
        .filter(
            PlayerGameFactORM.season == season,
            PlayerGameFactORM.season_type == season_type,
        )
        .order_by(PlayerGameFactORM.game_date, PlayerGameFactORM.canonical_game_id)
        .all()
    )
    return role_history_records_from_facts(facts, calculation_version=calculation_version)
