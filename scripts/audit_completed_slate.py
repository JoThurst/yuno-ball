"""Read-only completed-slate collection audit with a nonzero failure exit code."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import SessionLocal
from app.services.completed_slate_audit_service import build_completed_slate_audit
from app.utils.season_utils import normalize_season


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, help="Canonical YYYY-YY season")
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--expected-games", required=True, type=int,
                        help="Independently verified scheduled game count for a completed slate")
    args = parser.parse_args()
    season = normalize_season(args.season)
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        report = build_completed_slate_audit(
            db, season=season, target_date=args.date, expected_games=args.expected_games,
        )
        db.rollback()
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
