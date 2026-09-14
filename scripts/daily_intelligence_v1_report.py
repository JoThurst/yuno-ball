"""Print a read-only Daily Intelligence V1 package as JSON.

Examples:
    python scripts/daily_intelligence_v1_report.py --date 2025-03-03 --season 2024-25
    python scripts/daily_intelligence_v1_report.py  # current centrally-derived date/season
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app.services.daily_intelligence_service import build_daily_intelligence_v1  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", dest="target_date", help="Target slate date (YYYY-MM-DD).")
    parser.add_argument("--season", help="Optional season override, e.g. 2024-25.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target_date = None
    if args.target_date:
        try:
            target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit("--date must use YYYY-MM-DD") from exc
    package = build_daily_intelligence_v1(target_date=target_date, season=args.season)
    print(json.dumps(package.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
