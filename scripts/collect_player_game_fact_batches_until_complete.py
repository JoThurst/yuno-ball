"""Run C7 pending batches sequentially until the coverage gate is complete."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_game_fact_coverage_service import (
    build_player_game_fact_coverage_report,
)


RUNNER = Path(__file__).with_name("collect_player_game_fact_batch.py")


def _pending_count(season: str, season_type: str, max_games: int) -> int:
    with get_db_context() as db:
        report = build_player_game_fact_coverage_report(
            db,
            season=season,
            season_type=season_type,
            max_batch_size=max_games,
        )
    return len(report["traditional_backfill_batches"])


def _run(command: list[str], label: str) -> dict:
    print(f"\n=== {label} ===", flush=True)
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="", flush=True)
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
    try:
        # Application startup logging may precede the runner's JSON payload.
        payload_start = completed.stdout.find("{")
        if payload_start < 0:
            raise ValueError("no JSON object found")
        payload, _ = json.JSONDecoder().raw_decode(completed.stdout[payload_start:])
        return payload
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} did not return valid JSON") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run, apply, and replay every pending C7 batch sequentially."
    )
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--max-games", type=int, default=25)
    parser.add_argument(
        "--max-batches",
        type=int,
        help="optional safety cap; omit to continue until no pending batches remain",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0,
        help="optional pause between completed batches for proxy/rate-limit control",
    )
    parser.add_argument(
        "--preflight-dry-run",
        action="store_true",
        help="run one full dry-run before the first apply; not repeated per batch",
    )
    args = parser.parse_args()
    if not 1 <= args.max_games <= 25:
        parser.error("--max-games must be between 1 and 25")
    if args.max_batches is not None and args.max_batches < 1:
        parser.error("--max-batches must be positive")
    if args.pause_seconds < 0:
        parser.error("--pause-seconds cannot be negative")

    common = [
        sys.executable,
        str(RUNNER),
        "--season",
        args.season,
        "--season-type",
        args.season_type,
        "--max-games",
        str(args.max_games),
    ]
    completed_batches = 0
    while True:
        pending = _pending_count(args.season, args.season_type, args.max_games)
        if pending == 0:
            print(f"C7 coverage complete after {completed_batches} batch(es).")
            return 0
        if args.max_batches is not None and completed_batches >= args.max_batches:
            print(
                f"Stopped at safety cap after {completed_batches} batch(es); "
                f"{pending} pending batch(es) remain."
            )
            return 0

        if args.preflight_dry_run and completed_batches == 0:
            _run(
                [*common, "--batch", "1", "--dry-run"],
                "Preflight: first pending batch dry-run",
            )
        applied = _run(
            [*common, "--batch", "1", "--apply"],
            f"Batch {completed_batches + 1}: apply",
        )
        run_id = applied.get("run_id")
        if not run_id:
            raise RuntimeError("Apply result did not contain a replayable run_id")
        replay = _run(
            [
                *common,
                "--replay-run-id",
                str(run_id),
                "--apply",
            ],
            f"Batch {completed_batches + 1}: database-only no-op replay",
        )
        completed_batches += 1
        print(
            f"Batch {completed_batches} complete; replay writes: "
            f"Traditional={replay.get('traditional_counts', {}).get('facts_created', 0) + replay.get('traditional_counts', {}).get('facts_updated', 0) + replay.get('traditional_counts', {}).get('revisions_created', 0)}, "
            f"Advanced={replay.get('advanced_counts', {}).get('facts_created', 0) + replay.get('advanced_counts', {}).get('facts_updated', 0) + replay.get('advanced_counts', {}).get('revisions_created', 0)}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
