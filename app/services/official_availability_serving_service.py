"""Read-only serving contract for official availability observations.

This module defines the payload boundary only. Routes and slate calculations
must supply an explicit publication cutoff and remain separate consumers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class OfficialAvailabilityObservation:
    observation_id: str
    report_date: date
    matchup_text: str | None
    player_id: int | None
    player_name: str | None
    team_id: int | None
    game_id: str | None
    status: str | None
    reason_category: str | None
    reason_detail: str | None
    raw_reason: str | None
    source_url: str | None
    identity_status: str


@dataclass(frozen=True)
class OfficialAvailabilityPayload:
    as_of: datetime
    source: str
    completeness: str
    unknown_reason: str | None
    observations: tuple[OfficialAvailabilityObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "source": self.source,
            "completeness": self.completeness,
            "unknown_reason": self.unknown_reason,
            "observations": [
                {
                    **asdict(observation),
                    "report_date": observation.report_date.isoformat(),
                }
                for observation in self.observations
            ],
        }


def build_official_availability_payload(
    rows: Sequence[Mapping[str, object]],
    *,
    as_of: datetime,
    source: str = "nba_official_injury_reports",
) -> OfficialAvailabilityPayload:
    """Build a freshness- and completeness-aware payload from prefiltered rows.

    Callers are responsible for filtering source publication timestamps to the
    requested ``as_of`` cutoff. This function never infers health from absence.
    """
    observations = tuple(
        OfficialAvailabilityObservation(
            observation_id=str(row["observation_id"]),
            report_date=row["game_date"],
            matchup_text=str(row["matchup_text"]) if row.get("matchup_text") else None,
            player_id=int(row["player_id"]) if row.get("player_id") is not None else None,
            player_name=str(row["reported_player_name"])
            if row.get("reported_player_name")
            else None,
            team_id=int(row["team_id"]) if row.get("team_id") is not None else None,
            game_id=str(row["game_id"]) if row.get("game_id") else None,
            status=str(row["status"]) if row.get("status") else None,
            reason_category=str(row["reason_category"])
            if row.get("reason_category")
            else None,
            reason_detail=str(row["reason_detail"])
            if row.get("reason_detail")
            else None,
            raw_reason=str(row["raw_reason"])
            if row.get("raw_reason")
            else None,
            source_url=str(row["source_url"]) if row.get("source_url") else None,
            identity_status=(
                "resolved"
                if row.get("player_id") is not None and row.get("team_id") is not None and row.get("game_id")
                else "unresolved"
            ),
        )
        for row in rows
    )
    if not observations:
        completeness, unknown_reason = "unknown", "no_official_observation"
    elif any(observation.identity_status == "unresolved" for observation in observations):
        completeness, unknown_reason = "partial", "identity_unresolved"
    else:
        completeness, unknown_reason = "complete", None
    return OfficialAvailabilityPayload(
        as_of=as_of,
        source=source,
        completeness=completeness,
        unknown_reason=unknown_reason,
        observations=observations,
    )
