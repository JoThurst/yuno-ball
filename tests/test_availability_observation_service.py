"""Unit contracts for official observation persistence and serving metadata."""

from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch
import uuid

from app.models.availability_report_document_sqlalchemy import (
    AvailabilityReportDocumentORM,
)
from app.services.availability_observation_service import (
    _observation_values,
    get_cutoff_aware_availability,
)
from app.utils.parse.official_injury_report_parser import (
    ParsedAvailabilityObservation,
)


def _document():
    return AvailabilityReportDocumentORM(
        document_id=str(uuid.uuid4()),
        source_name="official_nba",
        source_url="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-03-03_11_30AM.pdf",
        report_published_at=datetime(2026, 3, 3, 16, 30, tzinfo=timezone.utc),
        report_date=date(2026, 3, 3),
        source_time_precision="minute",
        retrieved_at=datetime(2026, 3, 3, 17, tzinfo=timezone.utc),
        raw_sha256="a" * 64,
        file_name="Injury-Report_2026-03-03_11_30AM.pdf",
        file_size_bytes=100,
        media_type="application/pdf",
        raw_storage_locator="C:/archive/report.pdf",
        collector_version="official-injury-documents-v1",
        completeness_status="complete",
        parser_version=None,
        parse_status="not_parsed",
        parse_error_summary=None,
        source_run_id=str(uuid.uuid4()),
    )


def test_observation_preserves_source_time_without_inventing_a_tipoff():
    parsed = ParsedAvailabilityObservation(
        game_date=date(2026, 3, 3),
        game_time=datetime.strptime("07:00", "%H:%M").time(),
        game_time_text="07:00 (ET)",
        matchup="DAL@CHA",
        reported_team_name="Dallas Mavericks",
        reported_player_name="Bagley III, Marvin",
        current_status="Out",
        raw_reason="Injury/Illness - Neck; Sprain",
        reason_category="Injury/Illness",
        reason_detail="Neck; Sprain",
    )

    values = _observation_values(
        _document(),
        parsed,
        parser_version="official-injury-report-layout-v1",
        team_id=None,
        game_id=None,
    )

    assert values["reported_game_time_text"] == "07:00 (ET)"
    assert values["scheduled_tipoff"] is None
    assert values["source_url"].startswith("https://ak-static.cms.nba.com/")
    assert values["raw_sha256"] == "a" * 64
    assert values["player_id"] is None


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def exists(self):
        return object()

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _EmptyDB:
    def query(self, *args, **kwargs):
        return _EmptyQuery()


def test_cutoff_serving_never_turns_missing_report_into_healthy():
    with patch(
        "app.services.availability_observation_service.or_",
        return_value=object(),
    ):
        payload = get_cutoff_aware_availability(
            "0022500883",
            cutoff=datetime(2026, 3, 3, 18, tzinfo=timezone.utc),
            db=_EmptyDB(),
            freshness_threshold=timedelta(hours=4),
        )

    assert payload["availability_state"] == "unknown"
    assert payload["missing_reason"] == "no_official_report_before_cutoff"
    assert payload["observations"] == []
