"""Dry-run or apply exact identity reconciliation for official availability rows."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _date(value: str, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{option} must use YYYY-MM-DD") from exc


def _load_plan(args):
    from app.database import engine
    from app.services.official_availability_identity_service import (
        build_identity_plan,
        load_identity_inputs,
    )
    from sqlalchemy import text

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            observations, submissions, teams, players, games = load_identity_inputs(
                connection,
                season=args.season,
                start_date=args.start_date,
                end_date=args.end_date,
                resolve_player=args.resolve_player,
            )
            return build_identity_plan(
                observations,
                submissions,
                teams=teams,
                players=players,
                games=games,
                resolve_player=args.resolve_player,
            )
        finally:
            transaction.rollback()


def _payload(args, plan, *, mode: str, database_write: bool, run_id: str | None = None, written: int = 0):
    return {
        "mode": mode,
        "database_write": database_write,
        "source_fetch": False,
        "season": args.season,
        "from_date": args.start_date.isoformat(),
        "to_date": args.end_date.isoformat(),
        "resolve_player": args.resolve_player,
        "identity_resolution_version": "official-injury-identity-v1",
        "run_id": run_id,
        "observations_seen": plan.observations_seen,
        "submissions_seen": plan.submissions_seen,
        "updates_planned": len(plan.updates),
        "rows_written": written,
        "status_counts": dict(plan.status_counts),
        "game_method_counts": dict(plan.game_method_counts),
        "player_method_counts": dict(plan.player_method_counts),
    }


def _apply(args, plan):
    from app.database import engine
    from app.services.ingestion_run_service import IngestionRunTracker, PIPELINE_LOCK_NAME
    from app.services.official_availability_identity_service import (
        apply_identity_plan,
        build_identity_plan,
        load_identity_inputs,
    )

    details = {
        "scope": "bounded_official_availability_identity_reconciliation",
        "season": args.season,
        "from_date": args.start_date.isoformat(),
        "to_date": args.end_date.isoformat(),
        "resolve_player": args.resolve_player,
        "identity_resolution_version": "official-injury-identity-v1",
        "policy": "exact_normalized_team_and_report_date_matchup; no_guessing",
    }
    with IngestionRunTracker(
        run_type="official_availability_identity_reconciliation",
        source="nba_official_injury_reports",
        season=args.season,
        season_type=None,
        target_date=None,
        provider="canonical_schedule_and_team_player_dimensions",
        calculation_version="official-injury-identity-v1",
        details=details,
        lock_name=PIPELINE_LOCK_NAME,
    ) as tracker:
        with engine.begin() as connection:
            observations, submissions, teams, players, games = load_identity_inputs(
                connection,
                season=args.season,
                start_date=args.start_date,
                end_date=args.end_date,
                resolve_player=args.resolve_player,
            )
            locked_plan = build_identity_plan(
                observations,
                submissions,
                teams=teams,
                players=players,
                games=games,
                resolve_player=args.resolve_player,
            )
            written = apply_identity_plan(connection, locked_plan, run_id=tracker.run_id)
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=plan.observations_seen + plan.submissions_seen,
            rows_written=written,
            details={**details, "rows_written": written},
        )
    return _payload(args, plan, mode="apply", database_write=True, run_id=tracker.run_id, written=written)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile official availability identities using exact canonical matches")
    parser.add_argument("--season", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--resolve-player", action="store_true", help="Also populate only unique normalized player-name matches")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.utils.season_utils import normalize_season

        args.season = normalize_season(args.season)
        args.start_date = _date(args.from_date, "--from-date")
        args.end_date = _date(args.to_date, "--to-date")
        if args.end_date < args.start_date:
            raise ValueError("--to-date cannot precede --from-date")
        plan = _load_plan(args)
        output = (
            _payload(args, plan, mode="dry-run", database_write=False)
            if args.dry_run
            else _apply(args, plan)
        )
    except Exception as exc:
        print(f"Official availability identity reconciliation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
