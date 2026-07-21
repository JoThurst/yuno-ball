"""Safety tests for bounded official injury-report filename probing."""

from datetime import date, time
import json

import scripts.backfill_official_injury_reports as backfill


def test_candidate_builder_includes_known_430pm_filename():
    candidates = backfill.build_candidates(
        start_date=date(2026, 3, 3),
        end_date=date(2026, 3, 3),
        start_time=time(16, 0),
        end_time=time(17, 0),
        interval_minutes=15,
    )

    assert len(candidates) == 5
    assert any(
        item.source_url.endswith("Injury-Report_2026-03-03_04_30PM.pdf")
        for item in candidates
    )


def test_legacy_hourly_candidates_are_deduplicated():
    candidates = backfill.build_candidates(
        start_date=date(2024, 1, 15),
        end_date=date(2024, 1, 15),
        start_time=time(16, 0),
        end_time=time(17, 0),
        interval_minutes=15,
    )

    assert [item.file_name for item in candidates] == [
        "Injury-Report_2024-01-15_04PM.pdf",
        "Injury-Report_2024-01-15_05PM.pdf",
    ]
    assert all(item.source_time_precision == "hour" for item in candidates)


def test_candidate_builder_skips_filename_era_transition_gap():
    candidates = backfill.build_candidates(
        start_date=date(2025, 12, 19),
        end_date=date(2025, 12, 19),
        start_time=time(15, 0),
        end_time=time(17, 0),
        interval_minutes=15,
    )

    assert [item.file_name for item in candidates] == [
        "Injury-Report_2025-12-19_03PM.pdf",
        "Injury-Report_2025-12-19_04PM.pdf",
        "Injury-Report_2025-12-19_05PM.pdf",
    ]


def test_dry_run_lists_candidates_without_network_or_writes(capsys):
    result = backfill.main([
        "--start-date", "2026-03-03",
        "--end-date", "2026-03-03",
        "--start-time", "16:00",
        "--end-time", "17:00",
        "--interval-minutes", "30",
        "--season", "2025-26",
        "--dry-run",
    ])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["candidate_count"] == 3
    assert output["network_access"] is False
    assert output["database_write"] is False


def test_range_over_default_seven_day_bound_fails_closed(capsys):
    result = backfill.main([
        "--start-date", "2026-03-01",
        "--end-date", "2026-03-08",
        "--season", "2025-26",
        "--dry-run",
    ])

    assert result == 1
    assert "contains 8 dates" in capsys.readouterr().err
