"""Dry-run or apply deterministic Stat Surge staging identity resolution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _payload(plan) -> dict:
    return {
        "source_rows": plan.source_rows,
        "identity_status_counts": dict(plan.status_counts),
        "player_method_counts": dict(plan.player_method_counts),
        "game_method_counts": dict(plan.game_method_counts),
        "team_method_counts": dict(plan.team_method_counts),
        "season_counts": dict(plan.season_counts),
        "unresolved_player_counts": dict(plan.unresolved_player_counts),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Stat Surge Identity Reconciliation Report",
        "",
        f"Status: {report['mode']} identity reconciliation evidence",
        "",
        "## Technical summary",
        "",
        f"- Source rows: {report['source_rows']:,}",
        f"- Fully identity-resolved: {report['identity_status_counts'].get('resolved', 0):,}",
        f"- Partially resolved: {report['identity_status_counts'].get('partial', 0):,}",
        f"- Conflicts: {report['identity_status_counts'].get('conflict', 0):,}",
        f"- Database rows changed: {report.get('rows_written', 0):,}",
        "",
        "All rows retain `cutoff_status = unknown`: the source supplies a methodology-level daily 2 p.m. checkpoint but no exact publication timestamp, and matched schedules are date-only. Identity resolution does not make these strict pregame features.",
        "",
        "## Coverage by season",
        "",
        "| Season | Rows | Resolved | Partial | Player resolved | Game resolved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for season, values in report["season_counts"].items():
        lines.append(
            f"| {season} | {values.get('rows', 0):,} | "
            f"{values.get('resolved', 0):,} | {values.get('partial', 0):,} | "
            f"{values.get('player_resolved', 0):,} | "
            f"{values.get('game_resolved', 0):,} |"
        )
    lines.extend(
        [
            "",
            "## Unresolved player names",
            "",
            "| Reported player | Rows |",
            "|---|---:|",
        ]
    )
    for name, count in report["unresolved_player_counts"].items():
        lines.append(f"| {name} | {count:,} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Resolution uses exact team names plus one reviewed franchise alias, strict matchup/date team pairs, and a unique punctuation-insensitive player-name key. No fuzzy or probabilistic player match is accepted. Unresolved names and cancelled/postponed games remain staged and queryable; no canonical availability rows or public behavior are created.",
            "",
        ]
    )
    return "\n".join(lines)


def _dry_run(source_import_id: str):
    from sqlalchemy import text

    from app.database import engine
    from app.services.statsurge_identity_reconciliation_service import (
        build_statsurge_identity_plan,
    )

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            plan = build_statsurge_identity_plan(
                connection, source_import_id=source_import_id
            )
        finally:
            transaction.rollback()
    return {"mode": "dry-run", "database_write": False, **_payload(plan)}


def _apply(source_import_id: str):
    from app.database import engine
    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.statsurge_availability_staging_service import (
        STATSURGE_STAGING_LOCK_NAME,
    )
    from app.services.statsurge_identity_reconciliation_service import (
        IDENTITY_RESOLUTION_VERSION,
        apply_statsurge_identity_plan,
    )

    details = {
        "source_import_id": source_import_id,
        "scope": "staging_identity_and_cutoff_classification_only",
        "identity_resolution_version": IDENTITY_RESOLUTION_VERSION,
    }
    with IngestionRunTracker(
        run_type="external_statsurge_identity_reconciliation",
        source="statsurge",
        season=None,
        target_date=None,
        provider="registered_external_artifact",
        calculation_version=IDENTITY_RESOLUTION_VERSION,
        details=details,
        lock_name=STATSURGE_STAGING_LOCK_NAME,
    ) as tracker:
        with engine.begin() as connection:
            plan, rows_written = apply_statsurge_identity_plan(
                connection,
                source_import_id=source_import_id,
                source_run_id=tracker.run_id,
            )
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=plan.source_rows,
            rows_written=rows_written,
            details={**details, **_payload(plan), "rows_written": rows_written},
        )
    return {
        "mode": "apply",
        "database_write": True,
        "run_id": tracker.run_id,
        "rows_written": rows_written,
        **_payload(plan),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile Stat Surge player/team/game identities"
    )
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--report")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = (
            _dry_run(args.manifest_id)
            if args.dry_run
            else _apply(args.manifest_id)
        )
        if args.report:
            path = Path(args.report).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_markdown(output), encoding="utf-8")
            output["report_path"] = str(path)
    except Exception as exc:
        print(f"Stat Surge identity reconciliation failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
