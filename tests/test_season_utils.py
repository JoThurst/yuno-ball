"""Unit tests for the canonical NBA season domain."""

from datetime import date, datetime
import importlib.util
from pathlib import Path
import unittest
import warnings

MODULE_PATH = Path(__file__).parents[1] / "app" / "utils" / "season_utils.py"
SPEC = importlib.util.spec_from_file_location("season_utils_under_test", MODULE_PATH)
season_utils = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(season_utils)

InvalidSeason = season_utils.InvalidSeason
active_ingestion_season = season_utils.active_ingestion_season
default_display_season = season_utils.default_display_season
format_season = season_utils.format_season
latest_known_season = season_utils.latest_known_season
next_season = season_utils.next_season
normalize_season = season_utils.normalize_season
normalize_season_type = season_utils.normalize_season_type
parse_season = season_utils.parse_season
previous_season = season_utils.previous_season
roster_season_year = season_utils.roster_season_year
season_for_date = season_utils.season_for_date
season_year_range = season_utils.season_year_range


class SeasonDomainTests(unittest.TestCase):
    def test_format_parse_and_transitions(self):
        self.assertEqual(format_season(2025), "2025-26")
        self.assertEqual(parse_season("2025-26"), (2025, 2026))
        self.assertEqual(season_year_range("2025-26"), (2025, 2026))
        self.assertEqual(previous_season("2025-26"), "2024-25")
        self.assertEqual(next_season("2025-26"), "2026-27")

    def test_rejects_noncanonical_and_mismatched_seasons(self):
        for value in ("2025", "25-26", "2025-27", "2025/26", ""):
            with self.subTest(value=value), self.assertRaises(InvalidSeason):
                normalize_season(value)

    def test_season_for_date_handles_boundary_and_year_rollover(self):
        self.assertEqual(season_for_date(date(2025, 9, 30)), "2024-25")
        self.assertEqual(season_for_date(date(2025, 10, 1)), "2025-26")
        self.assertEqual(season_for_date(datetime(2025, 12, 25, 12)), "2025-26")
        self.assertEqual(season_for_date(date(2026, 1, 1)), "2025-26")
        self.assertEqual(season_for_date(date(2026, 6, 30)), "2025-26")

    def test_playoffs_are_a_season_type_not_a_new_season(self):
        self.assertEqual(season_for_date(date(2026, 5, 15)), "2025-26")
        self.assertEqual(normalize_season_type("postseason"), "Playoffs")
        self.assertEqual(normalize_season_type("Regular"), "Regular Season")

    def test_offseason_stays_on_latest_known_until_upcoming_schedule_exists(self):
        on_date = date(2026, 7, 15)
        known = ["2024-25", "2025-26", "2025"]
        self.assertEqual(
            active_ingestion_season(on_date, known_seasons=known),
            "2025-26",
        )
        self.assertEqual(
            active_ingestion_season(
                on_date,
                known_seasons=known,
                scheduled_seasons=["2026-27"],
            ),
            "2026-27",
        )

    def test_override_and_display_policy_are_explicit(self):
        self.assertEqual(
            active_ingestion_season(date(2026, 8, 1), override="2023-24"),
            "2023-24",
        )
        self.assertEqual(
            default_display_season(
                date(2026, 8, 1),
                known_seasons=["2025-26"],
                scheduled_seasons=[],
            ),
            "2025-26",
        )

    def test_latest_known_ignores_legacy_malformed_values(self):
        self.assertEqual(
            latest_known_season(["2023-24", "2025", "2024-25"]),
            "2024-25",
        )
        self.assertIsNone(latest_known_season(["2025", "unknown"]))

    def test_roster_year_is_explicitly_legacy(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(roster_season_year("2025-26"), "2025")
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, DeprecationWarning)


if __name__ == "__main__":
    unittest.main()
