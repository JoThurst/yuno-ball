"""Tests for truthful ingest freshness metadata."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "app" / "utils" / "freshness.py"
SPEC = importlib.util.spec_from_file_location("freshness_under_test", MODULE_PATH)
freshness = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(freshness)


class FreshnessTests(unittest.TestCase):
    def test_complete_recent_marker_exposes_source_and_run_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ingest_path = root / "last_ingest_success.json"
            validation_path = root / "last_validation.json"
            timestamp = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            ingest_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-123",
                        "timestamp": timestamp,
                        "target_date": "2026-07-15",
                        "season": "2025-26",
                        "status": "success",
                        "fetch_success": True,
                        "calc_success": True,
                        "validation_success": True,
                    }
                ),
                encoding="utf-8",
            )
            validation_path.write_text("{}", encoding="utf-8")

            with patch.object(freshness, "INGEST_MARKER", ingest_path), patch.object(
                freshness, "VALIDATION_MARKER", validation_path
            ), patch.dict(os.environ, {"INGEST_STALE_AFTER_HOURS": "1"}):
                result = freshness.get_ingest_freshness()

            self.assertEqual(result["source"], "daily_ingest")
            self.assertEqual(result["run_id"], "run-123")
            self.assertEqual(result["target_date"], "2026-07-15")
            self.assertTrue(result["is_complete"])
            self.assertFalse(result["is_stale"])

    def test_missing_marker_is_incomplete_and_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                freshness, "INGEST_MARKER", root / "missing-ingest.json"
            ), patch.object(
                freshness, "VALIDATION_MARKER", root / "missing-validation.json"
            ):
                result = freshness.get_ingest_freshness()

            self.assertFalse(result["has_marker"])
            self.assertFalse(result["is_complete"])
            self.assertTrue(result["is_stale"])
            self.assertIsNone(result["age_seconds"])

    def test_invalid_stale_threshold_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                freshness, "INGEST_MARKER", root / "missing-ingest.json"
            ), patch.object(
                freshness, "VALIDATION_MARKER", root / "missing-validation.json"
            ), patch.dict(os.environ, {"INGEST_STALE_AFTER_HOURS": "invalid"}):
                result = freshness.get_ingest_freshness()

            self.assertEqual(result["stale_after_hours"], 30)


if __name__ == "__main__":
    unittest.main()
