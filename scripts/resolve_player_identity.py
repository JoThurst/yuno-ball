"""Resolve and persist one NBA player dimension row through CommonPlayerInfo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_identity_service import (
    fetch_player_identity_record,
    upsert_player_identity_records,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-id", type=int, required=True)
    parser.add_argument("--season", default="2025-26")
    args = parser.parse_args()

    record = fetch_player_identity_record(args.player_id, season=args.season)
    with get_db_context() as db:
        counts = upsert_player_identity_records(db, [record])
        db.commit()
    print(json.dumps({"player": record.__dict__, "counts": counts}, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
