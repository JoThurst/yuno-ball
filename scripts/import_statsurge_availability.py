"""Parse and stage the registered Stat Surge daily availability archive.

The command never promotes rows into canonical or user-facing tables. Dry-run
mode uses only the Python standard library and does not open the database.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEADER = ("PLAYER", "STATUS", "REASON", "TEAM", "GAME", "DATE")
ALLOWED_STATUSES = {"Available", "Probable", "Questionable", "Doubtful", "Out"}
MATCHUP_PATTERN = re.compile(r"^[A-Z0-9]{2,3}@[A-Z0-9]{2,3}$")
PARSER_VERSION = "statsurge-availability-v1"
HASH_CHUNK_BYTES = 1024 * 1024


class StatsurgeParseError(ValueError):
    """Raised when the artifact itself cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedStatsurgeArtifact:
    """Complete in-memory partition of one bounded Stat Surge CSV."""

    file_name: str
    file_size_bytes: int
    sha256: str
    source_row_count: int
    rows: Tuple[Mapping[str, Any], ...]
    rejections: Tuple[Mapping[str, Any], ...]
    status_counts: Mapping[str, int]
    rejection_counts: Mapping[str, int]
    first_report_date: Optional[date]
    last_report_date: Optional[date]

    def summary(self) -> Dict[str, Any]:
        return {
            "parser_version": PARSER_VERSION,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "source_row_count": self.source_row_count,
            "staged_row_count": len(self.rows),
            "rejected_row_count": len(self.rejections),
            "status_counts": dict(sorted(self.status_counts.items())),
            "rejection_counts": dict(sorted(self.rejection_counts.items())),
            "first_report_date": (
                self.first_report_date.isoformat() if self.first_report_date else None
            ),
            "last_report_date": (
                self.last_report_date.isoformat() if self.last_report_date else None
            ),
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_values(row: Mapping[Optional[str], Any]) -> Dict[str, Any]:
    values = {field: row.get(field) for field in EXPECTED_HEADER}
    extra = row.get(None)
    if extra is not None:
        values["_extra_values"] = list(extra)
    return values


def _row_sha256(raw_values: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        raw_values,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _season_for_date(report_date: date) -> str:
    start_year = report_date.year if report_date.month >= 7 else report_date.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _rejection(
    *,
    source_row_number: int,
    raw_values: Mapping[str, Any],
    row_sha256: str,
    reason_code: str,
    reason_detail: str,
) -> Dict[str, Any]:
    return {
        "source_row_number": source_row_number,
        "row_sha256": row_sha256,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "raw_values": dict(raw_values),
    }


def parse_statsurge_artifact(
    raw_path: str | Path,
    *,
    encoding: str = "utf-8-sig",
) -> ParsedStatsurgeArtifact:
    """Hash, parse, validate, and fully partition one source artifact."""
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise StatsurgeParseError(f"Source file does not exist: {path}")
    before = path.stat()
    file_sha256 = _sha256(path)
    rows: List[Mapping[str, Any]] = []
    rejections: List[Mapping[str, Any]] = []
    seen_natural_keys = set()
    status_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()
    parsed_dates: List[date] = []

    try:
        with path.open("r", encoding=encoding, newline="") as source:
            reader = csv.DictReader(source)
            header = tuple(reader.fieldnames or ())
            if header != EXPECTED_HEADER:
                raise StatsurgeParseError(
                    f"Unexpected CSV header: {header}; expected {EXPECTED_HEADER}"
                )
            for logical_index, raw_row in enumerate(reader, start=2):
                raw_values = _raw_values(raw_row)
                row_hash = _row_sha256(raw_values)
                values = {
                    field: str(raw_row.get(field) or "").strip()
                    for field in EXPECTED_HEADER
                }

                reason_code = None
                reason_detail = None
                if raw_row.get(None) is not None or any(
                    raw_row.get(field) is None for field in EXPECTED_HEADER
                ):
                    reason_code = "malformed_row_width"
                    reason_detail = "CSV row width does not match the six-column header"
                elif any(not values[field] for field in EXPECTED_HEADER):
                    reason_code = "missing_required_value"
                    reason_detail = "One or more required source fields are blank"
                elif values["STATUS"] not in ALLOWED_STATUSES:
                    reason_code = "invalid_status"
                    reason_detail = f"Unsupported status: {values['STATUS']}"
                elif not MATCHUP_PATTERN.fullmatch(values["GAME"]):
                    reason_code = "invalid_matchup"
                    reason_detail = f"Unsupported matchup text: {values['GAME']}"

                report_date = None
                if reason_code is None:
                    try:
                        report_date = datetime.strptime(
                            values["DATE"], "%m/%d/%Y"
                        ).date()
                    except ValueError:
                        reason_code = "invalid_report_date"
                        reason_detail = f"Unsupported report date: {values['DATE']}"

                if reason_code is None:
                    natural_key = (
                        report_date,
                        values["GAME"].casefold(),
                        values["TEAM"].casefold(),
                        values["PLAYER"].casefold(),
                    )
                    if natural_key in seen_natural_keys:
                        reason_code = "duplicate_natural_key"
                        reason_detail = "A prior row has the same date/matchup/team/player grain"
                    else:
                        seen_natural_keys.add(natural_key)

                if reason_code is not None:
                    rejection_counts[reason_code] += 1
                    rejections.append(
                        _rejection(
                            source_row_number=logical_index,
                            raw_values=raw_values,
                            row_sha256=row_hash,
                            reason_code=reason_code,
                            reason_detail=reason_detail or reason_code,
                        )
                    )
                    continue

                assert report_date is not None
                status_counts[values["STATUS"]] += 1
                parsed_dates.append(report_date)
                rows.append(
                    {
                        "source_row_number": logical_index,
                        "row_sha256": row_hash,
                        "reported_player_name": values["PLAYER"],
                        "reported_status": values["STATUS"],
                        "reported_reason": values["REASON"],
                        "reported_team_name": values["TEAM"],
                        "matchup_text": values["GAME"],
                        "report_date_raw": values["DATE"],
                        "report_date": report_date,
                        "season": _season_for_date(report_date),
                        "source_checkpoint": "daily_2pm_report",
                        "source_published_at": None,
                        "source_time_precision": "report_checkpoint",
                        "source_time_confidence": "methodology_level",
                        "resolved_player_id": None,
                        "resolved_team_id": None,
                        "resolved_game_id": None,
                        "identity_status": "unresolved",
                        "cutoff_status": "not_evaluated",
                        "completeness_status": "identity_unresolved",
                        "validation_status": "staged",
                        "raw_values": raw_values,
                    }
                )
    except (UnicodeError, csv.Error, OSError) as exc:
        raise StatsurgeParseError(f"Could not parse Stat Surge CSV: {exc}") from exc

    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise StatsurgeParseError("Source file changed while it was being parsed")
    return ParsedStatsurgeArtifact(
        file_name=path.name,
        file_size_bytes=before.st_size,
        sha256=file_sha256,
        source_row_count=len(rows) + len(rejections),
        rows=tuple(rows),
        rejections=tuple(rejections),
        status_counts=dict(status_counts),
        rejection_counts=dict(rejection_counts),
        first_report_date=min(parsed_dates) if parsed_dates else None,
        last_report_date=max(parsed_dates) if parsed_dates else None,
    )


def _apply(
    args: argparse.Namespace,
    parsed: ParsedStatsurgeArtifact,
) -> Dict[str, Any]:
    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.statsurge_availability_staging_service import (
        STATSURGE_STAGING_LOCK_NAME,
        stage_statsurge_availability,
    )

    run_details = {
        "source_import_id": args.manifest_id,
        "file_name": parsed.file_name,
        "sha256": parsed.sha256,
        "parser_version": PARSER_VERSION,
        "scope": "staging_only",
    }
    with IngestionRunTracker(
        run_type="external_statsurge_staging",
        source="stat-surge",
        season=None,
        target_date=None,
        provider="registered_external_artifact",
        calculation_version=PARSER_VERSION,
        details=run_details,
        lock_name=STATSURGE_STAGING_LOCK_NAME,
    ) as tracker:
        result = stage_statsurge_availability(
            source_import_id=args.manifest_id,
            source_run_id=tracker.run_id,
            file_name=parsed.file_name,
            file_sha256=parsed.sha256,
            source_row_count=parsed.source_row_count,
            rows=parsed.rows,
            rejections=parsed.rejections,
        )
        run_status = "success" if result.rejected_rows == 0 else "partial"
        tracker.finish(
            run_status,
            validation_status="passed",
            rows_read=result.source_rows,
            rows_written=(
                result.inserted_staged_rows + result.inserted_rejected_rows
            ),
            details={
                **run_details,
                "staged_rows": result.staged_rows,
                "rejected_rows": result.rejected_rows,
                "inserted_staged_rows": result.inserted_staged_rows,
                "inserted_rejected_rows": result.inserted_rejected_rows,
            },
        )
    return {
        "mode": "apply",
        "run_id": tracker.run_id,
        "run_status": run_status,
        "manifest_id": args.manifest_id,
        **parsed.summary(),
        "inserted_staged_rows": result.inserted_staged_rows,
        "inserted_rejected_rows": result.inserted_rejected_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage one registered Stat Surge availability artifact"
    )
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--encoding", default="utf-8-sig")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        parsed = parse_statsurge_artifact(args.file, encoding=args.encoding)
        if args.dry_run:
            output = {
                "mode": "dry-run",
                "database_write": False,
                "manifest_id": args.manifest_id,
                **parsed.summary(),
            }
        else:
            output = _apply(args, parsed)
    except Exception as exc:
        print(f"Stat Surge staging failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
