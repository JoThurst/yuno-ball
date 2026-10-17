"""Persistence and cutoff-aware serving for official availability observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from app.models.availability_observation_sqlalchemy import (
    AvailabilityObservationORM,
    TeamReportSubmissionStatusORM,
)
from app.models.availability_report_document_sqlalchemy import (
    AvailabilityReportDocumentORM,
)
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.team_sqlalchemy import TeamORM
from app.utils.parse.official_injury_report_parser import (
    EASTERN,
    PARSER_VERSION,
    OfficialInjuryReportParseResult,
    ParsedAvailabilityObservation,
    ParsedTeamSubmissionStatus,
    parse_official_injury_report_pdf,
)


UTC = timezone.utc
MAX_ERROR_SUMMARY = 500
_TEAM_NAME_ALIASES = {
    "laclippers": "losangelesclippers",
    "lalakers": "losangeleslakers",
}


class AvailabilityObservationConflict(ValueError):
    """Raised when one parser version produces conflicting source rows."""


@dataclass(frozen=True)
class AvailabilityParsePersistenceResult:
    document_id: str
    parser_version: str
    parse_status: str
    observations_seen: int
    observations_created: int
    team_submission_statuses_seen: int
    team_submission_statuses_created: int

    @property
    def rows_written(self) -> int:
        return self.observations_created + self.team_submission_statuses_created


def mark_report_document_parse_failed(
    document: AvailabilityReportDocumentORM,
    error: BaseException,
    *,
    db: Session,
    parser_version: str = PARSER_VERSION,
) -> None:
    """Retain a bounded parse failure without fabricating source observations."""
    document.parser_version = parser_version
    document.parse_status = "failed"
    document.parse_error_summary = str(error)[:MAX_ERROR_SUMMARY] or type(error).__name__


def _aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return value.astimezone(UTC)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _row_key(values: Iterable[object]) -> str:
    payload = json.dumps(
        [value.isoformat() if hasattr(value, "isoformat") else value for value in values],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _team_index(db: Session) -> Dict[str, int]:
    index: Dict[str, int] = {}
    for team in db.query(TeamORM).all():
        for value in (team.name, team.abbreviation):
            if not value:
                continue
            normalized = _normalize_text(value)
            if normalized and normalized not in index:
                index[normalized] = team.team_id
            elif normalized and index.get(normalized) != team.team_id:
                index.pop(normalized, None)
    for alias, canonical in _TEAM_NAME_ALIASES.items():
        if canonical in index:
            index[alias] = index[canonical]
    return index


def _resolve_team_and_game(
    db: Session,
    *,
    reported_team_name: str,
    game_date: date,
    matchup: str,
    teams: Dict[str, int],
) -> Tuple[Optional[int], Optional[str]]:
    team_id = teams.get(_normalize_text(reported_team_name))
    if team_id is None:
        return None, None

    matchup_parts = matchup.split("@")
    opponent_id = None
    if len(matchup_parts) == 2:
        matchup_team_ids = [teams.get(_normalize_text(part)) for part in matchup_parts]
        if team_id in matchup_team_ids:
            opponent_ids = [value for value in matchup_team_ids if value and value != team_id]
            opponent_id = opponent_ids[0] if len(opponent_ids) == 1 else None

    # The source game date is Eastern while the schedule stores a mixture of
    # exact UTC timestamps and UTC-midnight date-only values. Search the two
    # UTC calendar dates that can contain one Eastern report date, then use the
    # matchup to avoid selecting another same-day game.
    day_start = datetime.combine(game_date, time.min, tzinfo=UTC)
    day_end = datetime.combine(
        game_date + timedelta(days=2),
        time.min,
        tzinfo=UTC,
    )
    schedules = (
        db.query(GameScheduleORM)
        .filter(
            GameScheduleORM.team_id == team_id,
            GameScheduleORM.game_date >= day_start.replace(tzinfo=None),
            GameScheduleORM.game_date < day_end.replace(tzinfo=None),
        )
        .all()
    )
    if opponent_id is not None:
        schedules = [
            schedule
            for schedule in schedules
            if schedule.opponent_team_id == opponent_id
        ]
    game_ids = sorted({schedule.game_id for schedule in schedules})
    return team_id, game_ids[0] if len(game_ids) == 1 else None


def _metadata(
    document: AvailabilityReportDocumentORM,
    parser_version: str,
    *,
    report_published_at: Optional[datetime] = None,
) -> dict:
    return {
        "report_document_id": document.document_id,
        "source_name": document.source_name,
        "source_url": document.source_url,
        "raw_sha256": document.raw_sha256,
        "report_published_at": _aware_utc(
            report_published_at
            or getattr(document, "printed_report_published_at", None)
            or document.report_published_at,
            "report_published_at",
        ),
        "source_time_precision": document.source_time_precision,
        "parser_version": parser_version,
    }


def _observation_values(
    document: AvailabilityReportDocumentORM,
    parsed: ParsedAvailabilityObservation,
    *,
    parser_version: str,
    team_id: Optional[int],
    game_id: Optional[str],
    report_published_at: Optional[datetime] = None,
) -> dict:
    return {
        **_metadata(
            document,
            parser_version,
            report_published_at=report_published_at,
        ),
        "observation_id": str(uuid.uuid4()),
        "source_row_key": _row_key(
            (
                parsed.game_date,
                parsed.game_time_text,
                parsed.matchup,
                parsed.reported_team_name,
                parsed.reported_player_name,
            )
        ),
        "game_id": game_id,
        "game_date": parsed.game_date,
        "reported_game_time_text": parsed.game_time_text,
        "scheduled_tipoff": None,
        "matchup_text": parsed.matchup,
        "team_id": team_id,
        "player_id": None,
        "reported_team_name": parsed.reported_team_name,
        "reported_player_name": parsed.reported_player_name,
        "status": parsed.current_status,
        "raw_reason": parsed.raw_reason,
        "reason_category": parsed.reason_category,
        "reason_detail": parsed.reason_detail,
    }


def _submission_values(
    document: AvailabilityReportDocumentORM,
    parsed: ParsedTeamSubmissionStatus,
    *,
    parser_version: str,
    team_id: Optional[int],
    game_id: Optional[str],
    report_published_at: Optional[datetime] = None,
) -> dict:
    return {
        **_metadata(
            document,
            parser_version,
            report_published_at=report_published_at,
        ),
        "submission_id": str(uuid.uuid4()),
        "source_row_key": _row_key(
            (
                parsed.game_date,
                parsed.game_time_text,
                parsed.matchup,
                parsed.reported_team_name,
            )
        ),
        "game_id": game_id,
        "game_date": parsed.game_date,
        "reported_game_time_text": parsed.game_time_text,
        "scheduled_tipoff": None,
        "matchup_text": parsed.matchup,
        "team_id": team_id,
        "reported_team_name": parsed.reported_team_name,
        "submission_status": parsed.submission_status,
        "raw_text": parsed.raw_text,
    }


def _assert_same(existing, values: dict, identity_fields: Sequence[str]) -> None:
    for field, value in values.items():
        if field in identity_fields or field in {
            "created_at",
            "observation_id",
            "submission_id",
            "team_id",
            "game_id",
            "player_id",
        }:
            continue
        current = getattr(existing, field)
        if isinstance(current, datetime) and isinstance(value, datetime):
            current = _aware_utc(current, field)
            value = _aware_utc(value, field)
        if current != value:
            raise AvailabilityObservationConflict(
                f"Existing parsed row conflicts on {field}: {getattr(existing, field)!r} != {value!r}"
            )


def persist_parsed_report_document(
    document: AvailabilityReportDocumentORM,
    parsed: OfficialInjuryReportParseResult,
    *,
    db: Session,
    parser_version: str = PARSER_VERSION,
) -> AvailabilityParsePersistenceResult:
    """Persist one parser revision idempotently and update document parse state."""
    parsed_published_at = _aware_utc(
        parsed.report_published_at,
        "parsed.report_published_at",
    )
    filename_published_at = _aware_utc(
        document.report_published_at,
        "document.report_published_at",
    )
    existing_printed = getattr(document, "printed_report_published_at", None)
    if existing_printed is not None and parsed_published_at != _aware_utc(
        existing_printed,
        "document.printed_report_published_at",
    ):
        raise AvailabilityObservationConflict(
            f"Parsed printed timestamp conflicts with document {document.document_id}"
        )
    if parsed_published_at < filename_published_at:
        raise AvailabilityObservationConflict(
            f"Parsed timestamp precedes filename timestamp for document {document.document_id}"
        )
    document.printed_report_published_at = parsed_published_at

    teams = _team_index(db)
    observations_created = 0
    submissions_created = 0

    for parsed_observation in parsed.observations:
        team_id, game_id = _resolve_team_and_game(
            db,
            reported_team_name=parsed_observation.reported_team_name,
            game_date=parsed_observation.game_date,
            matchup=parsed_observation.matchup,
            teams=teams,
        )
        values = _observation_values(
            document,
            parsed_observation,
            parser_version=parser_version,
            team_id=team_id,
            game_id=game_id,
            report_published_at=parsed_published_at,
        )
        existing = (
            db.query(AvailabilityObservationORM)
            .filter_by(
                report_document_id=document.document_id,
                parser_version=parser_version,
                source_row_key=values["source_row_key"],
            )
            .one_or_none()
        )
        if existing is None:
            db.add(AvailabilityObservationORM(**values))
            observations_created += 1
        else:
            _assert_same(
                existing,
                values,
                ("report_document_id", "parser_version", "source_row_key"),
            )
            for field in ("team_id", "game_id", "player_id"):
                if values[field] is not None and getattr(existing, field) != values[field]:
                    setattr(existing, field, values[field])

    for parsed_submission in parsed.team_submission_statuses:
        team_id, game_id = _resolve_team_and_game(
            db,
            reported_team_name=parsed_submission.reported_team_name,
            game_date=parsed_submission.game_date,
            matchup=parsed_submission.matchup,
            teams=teams,
        )
        values = _submission_values(
            document,
            parsed_submission,
            parser_version=parser_version,
            team_id=team_id,
            game_id=game_id,
            report_published_at=parsed_published_at,
        )
        existing = (
            db.query(TeamReportSubmissionStatusORM)
            .filter_by(
                report_document_id=document.document_id,
                parser_version=parser_version,
                source_row_key=values["source_row_key"],
            )
            .one_or_none()
        )
        if existing is None:
            db.add(TeamReportSubmissionStatusORM(**values))
            submissions_created += 1
        else:
            _assert_same(
                existing,
                values,
                ("report_document_id", "parser_version", "source_row_key"),
            )
            for field in ("team_id", "game_id"):
                if values[field] is not None and getattr(existing, field) != values[field]:
                    setattr(existing, field, values[field])

    document.parser_version = parser_version
    document.parse_status = parsed.parse_status
    document.parse_error_summary = (
        parsed.parse_error_summary[:MAX_ERROR_SUMMARY]
        if parsed.parse_error_summary
        else None
    )
    if parsed.parse_status == "partial":
        document.completeness_status = "partial"

    return AvailabilityParsePersistenceResult(
        document_id=document.document_id,
        parser_version=parser_version,
        parse_status=parsed.parse_status,
        observations_seen=len(parsed.observations),
        observations_created=observations_created,
        team_submission_statuses_seen=len(parsed.team_submission_statuses),
        team_submission_statuses_created=submissions_created,
    )


def parse_and_persist_report_document(
    document_id: str,
    *,
    db: Session,
    parser_version: str = PARSER_VERSION,
) -> AvailabilityParsePersistenceResult:
    """Parse one archived immutable PDF and persist its source observations."""
    document = (
        db.query(AvailabilityReportDocumentORM)
        .filter_by(document_id=document_id)
        .one_or_none()
    )
    if document is None:
        raise ValueError(f"Unknown availability report document: {document_id}")
    path = Path(document.raw_storage_locator)
    if not path.is_file():
        raise FileNotFoundError(f"Archived report is not readable: {path}")
    parsed = parse_official_injury_report_pdf(path)
    return persist_parsed_report_document(
        document,
        parsed,
        db=db,
        parser_version=parser_version,
    )


def _freshness_payload(
    report_published_at: datetime,
    cutoff: datetime,
    freshness_threshold: Optional[timedelta],
) -> dict:
    age_seconds = max(
        0,
        int((_aware_utc(cutoff, "cutoff") - _aware_utc(
            report_published_at,
            "report_published_at",
        )).total_seconds()),
    )
    if freshness_threshold is None:
        freshness_status = "not_evaluated"
        stale = False
    else:
        if freshness_threshold.total_seconds() < 0:
            raise ValueError("freshness_threshold cannot be negative")
        stale = age_seconds > freshness_threshold.total_seconds()
        freshness_status = "stale" if stale else "fresh"
    return {
        "freshness_seconds": age_seconds,
        "freshness_minutes": round(age_seconds / 60, 1),
        "freshness_status": freshness_status,
        "stale": stale,
    }


def get_cutoff_aware_availability(
    game_id: str,
    *,
    cutoff: datetime,
    db: Session,
    freshness_threshold: Optional[timedelta] = None,
) -> dict:
    """Return the latest official report strictly before a target-game cutoff."""
    cutoff_utc = _aware_utc(cutoff, "cutoff")
    observation_query = (
        db.query(AvailabilityObservationORM)
        .filter(AvailabilityObservationORM.game_id == game_id)
        .filter(
            AvailabilityObservationORM.report_document_id
            == AvailabilityReportDocumentORM.document_id
        )
    )
    observation_exists = (
        observation_query.exists()
        if hasattr(observation_query, "exists")
        else false()
    )
    submission_query = (
        db.query(TeamReportSubmissionStatusORM)
        .filter(TeamReportSubmissionStatusORM.game_id == game_id)
        .filter(
            TeamReportSubmissionStatusORM.report_document_id
            == AvailabilityReportDocumentORM.document_id
        )
    )
    submission_exists = (
        submission_query.exists()
        if hasattr(submission_query, "exists")
        else false()
    )
    published_at = func.coalesce(
        AvailabilityReportDocumentORM.printed_report_published_at,
        AvailabilityReportDocumentORM.report_published_at,
    )
    document_query = (
        db.query(AvailabilityReportDocumentORM)
        .filter(published_at < cutoff_utc)
        .filter(or_(observation_exists, submission_exists))
        .order_by(
            published_at.desc(),
            AvailabilityReportDocumentORM.created_at.desc(),
            AvailabilityReportDocumentORM.document_id.desc(),
        )
    )
    document = document_query.first() if hasattr(document_query, "first") else None

    base = {
        "game_id": game_id,
        "cutoff": cutoff_utc.isoformat(),
        "as_of": None,
        "source": None,
        "completeness": "unknown",
        "stale": False,
        "freshness_status": "unknown",
        "observations": [],
        "team_submission_statuses": [],
        "latest_report": None,
    }
    if document is None:
        base["availability_state"] = "unknown"
        base["missing_reason"] = "no_official_report_before_cutoff"
        return base

    report_published_at = _aware_utc(
        getattr(document, "printed_report_published_at", None)
        or document.report_published_at,
        "document.report_published_at",
    )
    freshness = _freshness_payload(
        report_published_at,
        cutoff_utc,
        freshness_threshold,
    )
    observations = (
        db.query(AvailabilityObservationORM)
        .filter(
            AvailabilityObservationORM.report_document_id == document.document_id,
            AvailabilityObservationORM.game_id == game_id,
            AvailabilityObservationORM.parser_version == document.parser_version,
        )
        .order_by(
            AvailabilityObservationORM.reported_team_name,
            AvailabilityObservationORM.reported_player_name,
        )
        .all()
    )
    submissions = (
        db.query(TeamReportSubmissionStatusORM)
        .filter(
            TeamReportSubmissionStatusORM.report_document_id == document.document_id,
            TeamReportSubmissionStatusORM.game_id == game_id,
            TeamReportSubmissionStatusORM.parser_version == document.parser_version,
        )
        .order_by(TeamReportSubmissionStatusORM.reported_team_name)
        .all()
    )
    return {
        **base,
        "availability_state": "reported",
        "as_of": report_published_at.isoformat(),
        "source": document.source_name,
        "completeness": document.completeness_status,
        **freshness,
        "latest_report": {
            "document_id": document.document_id,
            "report_published_at": report_published_at.isoformat(),
            "source_time_precision": document.source_time_precision,
            "source_url": document.source_url,
            "raw_sha256": document.raw_sha256,
            "parser_version": document.parser_version,
            "parse_status": document.parse_status,
        },
        "observations": [observation.to_dict() for observation in observations],
        "team_submission_statuses": [
            submission.to_dict() for submission in submissions
        ],
    }
