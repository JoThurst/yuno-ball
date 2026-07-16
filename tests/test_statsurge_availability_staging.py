"""Contract tests for Stat Surge source parsing and staging eligibility."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import uuid

import pytest

from scripts.import_statsurge_availability import (
    StatsurgeParseError,
    main,
    parse_statsurge_artifact,
)
from app.services.statsurge_availability_staging_service import (
    _manifest_for_staging,
    stage_statsurge_availability,
)


HEADER = "PLAYER,STATUS,REASON,TEAM,GAME,DATE\n"


def test_parser_preserves_source_fields_and_checkpoint_semantics(tmp_path):
    source = tmp_path / "injuries.csv"
    source.write_text(
        HEADER
        + '"Irving, Kyrie",Out,Not With Team,Brooklyn Nets,BKN@MIL,10/19/2021\n'
        + '"Green, Test",Questionable,Rest,Boston Celtics,BOS@NYK,01/02/2022\n',
        encoding="utf-8",
    )

    parsed = parse_statsurge_artifact(source)

    assert parsed.source_row_count == 2
    assert len(parsed.rows) == 2
    assert parsed.rejections == ()
    assert parsed.rows[0]["source_row_number"] == 2
    assert parsed.rows[0]["reported_player_name"] == "Irving, Kyrie"
    assert parsed.rows[0]["season"] == "2021-22"
    assert parsed.rows[0]["source_published_at"] is None
    assert parsed.rows[0]["source_time_precision"] == "report_checkpoint"
    assert parsed.rows[0]["identity_status"] == "unresolved"
    assert parsed.status_counts == {"Out": 1, "Questionable": 1}


def test_parser_quarantines_bad_rows_and_duplicate_natural_keys(tmp_path):
    source = tmp_path / "injuries.csv"
    source.write_text(
        HEADER
        + "Player One,Out,Rest,Team One,AAA@BBB,10/19/2021\n"
        + "Player One,Out,Rest,Team One,AAA@BBB,10/19/2021\n"
        + "Player Two,Maybe,Rest,Team Two,AAA@BBB,10/19/2021\n"
        + "Player Three,Out,Rest,Team Three,AAA@BBB,bad-date\n"
        + "Player Four,Out,Rest,Team Four,not-a-game,10/19/2021\n"
        + "Player Five,Out,,Team Five,AAA@BBB,10/19/2021\n"
        + "Player Six,Out,Rest,Team Six,AAA@BBB,10/19/2021,extra\n",
        encoding="utf-8",
    )

    parsed = parse_statsurge_artifact(source)

    assert parsed.source_row_count == 7
    assert len(parsed.rows) == 1
    assert len(parsed.rejections) == 6
    assert parsed.rejection_counts == {
        "duplicate_natural_key": 1,
        "invalid_status": 1,
        "invalid_report_date": 1,
        "invalid_matchup": 1,
        "missing_required_value": 1,
        "malformed_row_width": 1,
    }
    assert {row["source_row_number"] for row in parsed.rejections} == set(
        range(3, 9)
    )


def test_parser_rejects_header_drift(tmp_path):
    source = tmp_path / "injuries.csv"
    source.write_text("PLAYER,STATUS,TEAM\nTest,Out,Team\n", encoding="utf-8")

    with pytest.raises(StatsurgeParseError, match="Unexpected CSV header"):
        parse_statsurge_artifact(source)


def test_dry_run_does_not_open_database(tmp_path, capsys):
    source = tmp_path / "injuries.csv"
    source.write_text(
        HEADER + "Player One,Out,Rest,Team One,AAA@BBB,10/19/2021\n",
        encoding="utf-8",
    )

    result = main(
        [
            "--manifest-id",
            str(uuid.uuid4()),
            "--file",
            str(source),
            "--dry-run",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["database_write"] is False
    assert output["staged_row_count"] == 1


def _eligible_manifest():
    manifest = MagicMock()
    manifest.source_name = "stat-surge"
    manifest.dataset_name = "nba-injury-daily-checkpoints"
    manifest.file_name = "injuries.csv"
    manifest.sha256 = "a" * 64
    manifest.source_row_count = 1
    manifest.license_status = "approved_public"
    manifest.commercial_use_status = "permitted"
    manifest.validation_status = "registered"
    return manifest


def test_manifest_gate_requires_hash_and_approved_use():
    session = MagicMock()
    manifest = _eligible_manifest()
    session.get.return_value = manifest

    assert (
        _manifest_for_staging(
            session,
            source_import_id=str(uuid.uuid4()),
            file_name="injuries.csv",
            file_sha256="a" * 64,
            source_row_count=1,
        )
        is manifest
    )

    manifest.license_status = "needs_review"
    with pytest.raises(ValueError, match="license_status"):
        _manifest_for_staging(
            session,
            source_import_id=str(uuid.uuid4()),
            file_name="injuries.csv",
            file_sha256="a" * 64,
            source_row_count=1,
        )


def test_staging_rejects_overlapping_source_partitions_before_database_access():
    source_import_id = str(uuid.uuid4())
    source_run_id = str(uuid.uuid4())
    row = {"source_row_number": 2, "row_sha256": "a" * 64}
    rejection = {
        "source_row_number": 2,
        "row_sha256": "a" * 64,
        "reason_code": "fixture",
        "reason_detail": "fixture",
        "raw_values": {},
    }

    with pytest.raises(ValueError, match="both staged and rejected"):
        stage_statsurge_availability(
            source_import_id=source_import_id,
            source_run_id=source_run_id,
            file_name="injuries.csv",
            file_sha256="a" * 64,
            source_row_count=2,
            rows=[row],
            rejections=[rejection],
            db=MagicMock(),
        )
