"""Read-only official availability assembly for dated slate payloads."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from app.services.availability_observation_service import (
    get_cutoff_aware_availability,
)
from app.services.official_availability_serving_service import (
    build_official_availability_payload,
)
from app.utils.id_utils import normalize_nba_game_id


UTC = timezone.utc
NON_AVAILABLE_STATUSES = frozenset(
    {"Probable", "Questionable", "Doubtful", "Out"}
)


def _aware_utc(value: datetime) -> datetime:
    """Schedule timestamps are stored as UTC-naive values in legacy rows."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _observation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    game_date = row.get("game_date")
    if isinstance(game_date, str):
        game_date = date.fromisoformat(game_date)
    return {
        "observation_id": row["observation_id"],
        "game_date": game_date,
        "matchup_text": row.get("matchup"),
        "player_id": row.get("player_id"),
        "reported_player_name": row.get("reported_player_name"),
        "team_id": row.get("team_id"),
        "game_id": row.get("game_id"),
        "status": row.get("status"),
        "reason_category": row.get("reason_category"),
        "reason_detail": row.get("reason_detail"),
        "raw_reason": row.get("raw_reason"),
        "source_url": row.get("source_url"),
    }


def build_game_official_availability(
    game_id: str,
    *,
    scheduled_tipoff: datetime,
    db: Session,
) -> dict[str, Any]:
    """Build one game payload using the canonical scheduled-tipoff cutoff."""
    canonical_game_id = normalize_nba_game_id(game_id)
    cutoff = _aware_utc(scheduled_tipoff)
    result = get_cutoff_aware_availability(
        canonical_game_id,
        cutoff=cutoff,
        db=db,
    )
    rows = [_observation_row(row) for row in result.get("observations", [])]
    report_as_of = result.get("as_of")
    as_of = (
        datetime.fromisoformat(report_as_of.replace("Z", "+00:00"))
        if report_as_of
        else cutoff
    )
    payload = build_official_availability_payload(
        rows,
        as_of=as_of,
        source=result.get("source") or "nba_official_injury_reports",
    ).to_dict()
    unresolved_count = sum(
        1 for observation in payload["observations"]
        if observation["identity_status"] == "unresolved"
    )
    submission_statuses = result.get("team_submission_statuses", [])
    if not payload["observations"]:
        payload["unknown_reason"] = (
            "team_submission_only" if submission_statuses else result.get(
                "missing_reason", "no_official_observation_before_cutoff"
            )
        )
    payload.update(
        {
            "game_id": canonical_game_id,
            "cutoff": cutoff.isoformat(),
            "stale": bool(result.get("stale", False)),
            "freshness_status": result.get("freshness_status", "unknown"),
            "latest_report": result.get("latest_report"),
            "team_submission_statuses": submission_statuses,
            "unresolved_observation_count": unresolved_count,
        }
    )
    return payload


def build_slate_official_availability(
    matchups: Sequence[Mapping[str, Any]],
    *,
    db: Session,
) -> dict[str, dict[str, Any]]:
    """Build official availability keyed only by canonical scheduled game ID."""
    payloads: dict[str, dict[str, Any]] = {}
    for matchup in matchups:
        game_id = normalize_nba_game_id(matchup["game_id"])
        scheduled_tipoff = matchup.get("game_date")
        if not isinstance(scheduled_tipoff, datetime):
            continue
        payloads[game_id] = build_game_official_availability(
            game_id,
            scheduled_tipoff=scheduled_tipoff,
            db=db,
        )
    return payloads


def non_available_observations(
    payload: Mapping[str, Any],
    *,
    team_id: int,
) -> list[dict[str, Any]]:
    """Return only status rows suitable for a player-facing availability callout."""
    return [
        observation
        for observation in payload.get("observations", [])
        if observation.get("team_id") == team_id
        and observation.get("status") in NON_AVAILABLE_STATUSES
    ]
