"""Parse and atomically stage registered Kaggle historical market artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PARSER_VERSION = "kaggle-markets-v1"
GAME_PARSER_VERSION = "kaggle-games-v1"
HASH_CHUNK_BYTES = 1024 * 1024
GAME_ID_PATTERN = re.compile(r"^[0-9]{10}$")

MARKET_CONFIG = {
    "moneyline": {
        "header": (
            "game_id", "book_name", "book_id", "team_id", "a_team_id",
            "price1", "price2",
        ),
        "fields": ("price1", "price2"),
    },
    "spread": {
        "header": (
            "game_id", "book_name", "book_id", "team_id", "a_team_id",
            "spread1", "spread2", "price1", "price2",
        ),
        "fields": ("spread1", "spread2", "price1", "price2"),
    },
    "total": {
        "header": (
            "game_id", "book_name", "book_id", "team_id", "a_team_id",
            "total1", "total2", "price1", "price2",
        ),
        "fields": ("total1", "total2", "price1", "price2"),
    },
}


class KaggleMarketParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMarketArtifact:
    market: str
    file_name: str
    file_size_bytes: int
    sha256: str
    source_row_count: int
    rows: Tuple[Mapping[str, Any], ...]
    anomalies: Tuple[Mapping[str, Any], ...]
    rejections: Tuple[Mapping[str, Any], ...]
    anomaly_counts: Mapping[str, int]
    rejection_counts: Mapping[str, int]
    selection_specific_pairs: int
    distinct_games: int
    distinct_books: int

    def summary(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "source_row_count": self.source_row_count,
            "staged_row_count": len(self.rows),
            "anomaly_row_count": len(self.anomalies),
            "rejected_row_count": len(self.rejections),
            "anomaly_counts": dict(sorted(self.anomaly_counts.items())),
            "rejection_counts": dict(sorted(self.rejection_counts.items())),
            "selection_specific_pairs": self.selection_specific_pairs,
            "distinct_games": self.distinct_games,
            "distinct_books": self.distinct_books,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_hash(raw_values: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(raw_values, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _decimal(raw: str, field: str) -> Decimal:
    if not raw:
        raise ValueError(f"{field} is required")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not numeric") from exc


def _integer(raw: str, field: str) -> int:
    if not raw:
        raise ValueError(f"{field} is required")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{field} is not an integer") from exc


def _raw_values(
    row: Mapping[Optional[str], Any], header: Sequence[str]
) -> Dict[str, Any]:
    values = {field: row.get(field) for field in header}
    if row.get(None) is not None:
        values["_extra_values"] = list(row[None])
    return values


def _base_row(
    values: Mapping[str, str],
    *,
    source_row_number: int,
    row_sha256: str,
    raw_values: Mapping[str, Any],
) -> Dict[str, Any]:
    game_id = values["game_id"]
    if not GAME_ID_PATTERN.fullmatch(game_id):
        raise ValueError("game_id is not a ten-digit NBA identifier")
    team_id = _integer(values["team_id"], "team_id")
    opponent_team_id = _integer(values["a_team_id"], "a_team_id")
    if team_id == opponent_team_id:
        raise ValueError("team and opponent IDs are equal")
    return {
        "source_row_number": source_row_number,
        "row_sha256": row_sha256,
        "game_id": game_id,
        "book_name": values["book_name"],
        "book_id": _integer(values["book_id"], "book_id"),
        "team_id": team_id,
        "opponent_team_id": opponent_team_id,
        "timing_precision": "unknown",
        "snapshot_type": "historical_static",
        "canonical_match_status": "not_evaluated",
        "validation_status": "staged",
        "raw_values": dict(raw_values),
    }


def _market_values(market: str, values: Mapping[str, str]) -> Dict[str, Any]:
    if market == "moneyline":
        return {
            "team_price": _decimal(values["price1"], "price1"),
            "opponent_price": _decimal(values["price2"], "price2"),
        }
    if market == "spread":
        team_spread = _decimal(values["spread1"], "spread1")
        opponent_spread = _decimal(values["spread2"], "spread2")
        return {
            "team_spread": team_spread,
            "opponent_spread": opponent_spread,
            "team_price": _decimal(values["price1"], "price1"),
            "opponent_price": _decimal(values["price2"], "price2"),
            "line_pair_status": (
                "inverse" if team_spread == -opponent_spread else "selection_specific"
            ),
        }
    over_total = _decimal(values["total1"], "total1")
    under_total = _decimal(values["total2"], "total2")
    return {
        "over_total": over_total,
        "under_total": under_total,
        "over_price": _decimal(values["price1"], "price1"),
        "under_price": _decimal(values["price2"], "price2"),
        "line_pair_status": (
            "same" if over_total == under_total else "selection_specific"
        ),
    }


def _anomaly(market: str, row: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    if market == "moneyline" and row["team_price"] > 0 and row["opponent_price"] > 0:
        return (
            "both_moneyline_prices_positive",
            "Both team selections have positive American prices",
        )
    if market == "spread" and (
        abs(row["team_price"]) > 750 or abs(row["opponent_price"]) > 750
    ):
        return ("extreme_spread_price", "A spread price has absolute value above 750")
    if market == "total" and (
        row["over_total"] < 150
        or row["over_total"] > 260
        or row["under_total"] < 150
        or row["under_total"] > 260
    ):
        return (
            "total_outside_initial_range",
            "At least one total selection is outside the initial 150-260 range",
        )
    if market == "total" and (
        abs(row["over_price"]) > 750 or abs(row["under_price"]) > 750
    ):
        return ("extreme_total_price", "A total price has absolute value above 750")
    return None


def parse_market_artifact(
    market: str,
    raw_path: str | Path,
    *,
    encoding: str = "utf-8-sig",
) -> ParsedMarketArtifact:
    if market not in MARKET_CONFIG:
        raise KaggleMarketParseError(f"Unsupported market: {market}")
    config = MARKET_CONFIG[market]
    header = config["header"]
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise KaggleMarketParseError(f"Source file does not exist: {path}")
    before = path.stat()
    file_hash = _sha256(path)
    rows: List[Mapping[str, Any]] = []
    anomalies: List[Mapping[str, Any]] = []
    rejections: List[Mapping[str, Any]] = []
    anomaly_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()
    seen_grains = set()

    try:
        with path.open("r", encoding=encoding, newline="") as source:
            reader = csv.DictReader(source)
            actual_header = tuple(reader.fieldnames or ())
            if actual_header != header:
                raise KaggleMarketParseError(
                    f"Unexpected {market} header: {actual_header}; expected {header}"
                )
            for row_number, raw_row in enumerate(reader, start=2):
                raw_values = _raw_values(raw_row, header)
                row_sha256 = _row_hash(raw_values)
                values = {
                    field: str(raw_row.get(field) or "").strip() for field in header
                }
                try:
                    if raw_row.get(None) is not None or any(
                        raw_row.get(field) is None for field in header
                    ):
                        raise ValueError("row width does not match the header")
                    if any(not values[field] for field in header):
                        raise ValueError("one or more required fields are blank")
                    parsed = _base_row(
                        values,
                        source_row_number=row_number,
                        row_sha256=row_sha256,
                        raw_values=raw_values,
                    )
                    parsed.update(_market_values(market, values))
                    grain = (
                        parsed["game_id"], parsed["book_id"], parsed["team_id"],
                        parsed["opponent_team_id"],
                    )
                    if grain in seen_grains:
                        raise ValueError("duplicate source market natural key")
                    seen_grains.add(grain)
                except ValueError as exc:
                    reason = (
                        "duplicate_natural_key"
                        if "duplicate" in str(exc)
                        else "invalid_source_row"
                    )
                    rejection_counts[reason] += 1
                    rejections.append(
                        {
                            "source_row_number": row_number,
                            "row_sha256": row_sha256,
                            "reason_code": reason,
                            "reason_detail": str(exc),
                            "raw_values": raw_values,
                        }
                    )
                    continue

                anomaly = _anomaly(market, parsed)
                if anomaly is None:
                    rows.append(parsed)
                    continue
                reason_code, reason_detail = anomaly
                anomaly_counts[reason_code] += 1
                anomalies.append(
                    {
                        "source_row_number": row_number,
                        "row_sha256": row_sha256,
                        "game_id": parsed["game_id"],
                        "market": market,
                        "reason_code": reason_code,
                        "reason_detail": reason_detail,
                        "team_id": parsed["team_id"],
                        "opponent_team_id": parsed["opponent_team_id"],
                        "raw_values": raw_values,
                    }
                )
    except (UnicodeError, csv.Error, OSError) as exc:
        raise KaggleMarketParseError(f"Could not parse {market} CSV: {exc}") from exc

    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise KaggleMarketParseError(f"{market} file changed while being parsed")
    all_valid = [*rows, *anomalies]
    pair_status = sum(
        row.get("line_pair_status") == "selection_specific" for row in rows
    )
    return ParsedMarketArtifact(
        market=market,
        file_name=path.name,
        file_size_bytes=before.st_size,
        sha256=file_hash,
        source_row_count=len(rows) + len(anomalies) + len(rejections),
        rows=tuple(rows),
        anomalies=tuple(anomalies),
        rejections=tuple(rejections),
        anomaly_counts=dict(anomaly_counts),
        rejection_counts=dict(rejection_counts),
        selection_specific_pairs=pair_status,
        distinct_games=len({row["game_id"] for row in all_valid}),
        distinct_books=len(
            {
                row.get("book_id")
                for row in rows
            }
        ),
    )


def _apply(args: argparse.Namespace, artifacts: Mapping[str, ParsedMarketArtifact]):
    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.kaggle_market_staging_service import (
        KAGGLE_MARKET_STAGING_LOCK_NAME,
        stage_kaggle_markets,
    )

    details = {
        "game_manifest_id": args.game_manifest_id,
        "market_manifest_ids": {
            "moneyline": args.moneyline_manifest_id,
            "spread": args.spread_manifest_id,
            "total": args.totals_manifest_id,
        },
        "parser_version": PARSER_VERSION,
        "scope": "staging_only_atomic_three_market_pack",
    }
    with IngestionRunTracker(
        run_type="external_kaggle_market_staging",
        source="kaggle-uploaded-pack",
        season=None,
        target_date=None,
        provider="registered_external_artifact",
        calculation_version=PARSER_VERSION,
        details=details,
        lock_name=KAGGLE_MARKET_STAGING_LOCK_NAME,
    ) as tracker:
        result = stage_kaggle_markets(
            source_run_id=tracker.run_id,
            game_manifest_id=args.game_manifest_id,
            market_manifests={
                "moneyline": args.moneyline_manifest_id,
                "spread": args.spread_manifest_id,
                "total": args.totals_manifest_id,
            },
            artifacts=artifacts,
        )
        run_status = "partial" if result.total_anomalies or result.total_rejections else "success"
        tracker.finish(
            run_status,
            validation_status="passed",
            rows_read=result.total_source_rows,
            rows_written=result.total_inserted_rows,
            details={**details, **result.details()},
        )
    return {
        "mode": "apply",
        "run_id": tracker.run_id,
        "run_status": run_status,
        "parser_version": PARSER_VERSION,
        "markets": {market: artifact.summary() for market, artifact in artifacts.items()},
        **result.details(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically stage registered Kaggle moneyline, spread, and totals"
    )
    parser.add_argument("--game-manifest-id", required=True)
    parser.add_argument("--moneyline-manifest-id", required=True)
    parser.add_argument("--moneyline-file", required=True)
    parser.add_argument("--spread-manifest-id", required=True)
    parser.add_argument("--spread-file", required=True)
    parser.add_argument("--totals-manifest-id", required=True)
    parser.add_argument("--totals-file", required=True)
    parser.add_argument("--encoding", default="utf-8-sig")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifacts = {
            "moneyline": parse_market_artifact(
                "moneyline", args.moneyline_file, encoding=args.encoding
            ),
            "spread": parse_market_artifact(
                "spread", args.spread_file, encoding=args.encoding
            ),
            "total": parse_market_artifact(
                "total", args.totals_file, encoding=args.encoding
            ),
        }
        output = (
            {
                "mode": "dry-run",
                "database_write": False,
                "parser_version": PARSER_VERSION,
                "markets": {
                    market: artifact.summary()
                    for market, artifact in artifacts.items()
                },
            }
            if args.dry_run
            else _apply(args, artifacts)
        )
    except Exception as exc:
        print(f"Kaggle market staging failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
