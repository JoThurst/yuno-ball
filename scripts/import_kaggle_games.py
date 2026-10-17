"""Parse and stage the registered Kaggle team-game artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import date
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

EXPECTED_HEADER = (
    "game_id", "game_date", "matchup", "team_id", "is_home", "wl", "w", "l",
    "w_pct", "min", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct",
    "ftm", "fta", "ft_pct", "oreb", "dreb", "reb", "ast", "stl", "blk",
    "tov", "pf", "pts", "a_team_id", "season_year", "season_type", "season",
)
GAME_ID_PATTERN = re.compile(r"^[0-9]{10}$")
SEASON_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}$")
ALLOWED_SEASON_TYPES = {"Regular Season", "Playoffs", "Pre Season", "All Star"}
OPTIONAL_INTEGER_FIELDS = (
    "w", "l", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb",
    "reb", "ast", "stl", "blk", "tov", "pf", "pts",
)
OPTIONAL_DECIMAL_FIELDS = ("w_pct", "min", "fg_pct", "fg3_pct", "ft_pct")
PARSER_VERSION = "kaggle-games-v1"
HASH_CHUNK_BYTES = 1024 * 1024


class KaggleGameParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedKaggleGames:
    file_name: str
    file_size_bytes: int
    sha256: str
    source_row_count: int
    rows: Tuple[Mapping[str, Any], ...]
    rejections: Tuple[Mapping[str, Any], ...]
    season_type_counts: Mapping[str, int]
    eligibility_counts: Mapping[str, int]
    rejection_counts: Mapping[str, int]
    missing_date_rows: int
    distinct_games: int

    def summary(self) -> Dict[str, Any]:
        return {
            "parser_version": PARSER_VERSION,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "source_row_count": self.source_row_count,
            "staged_row_count": len(self.rows),
            "rejected_row_count": len(self.rejections),
            "distinct_games": self.distinct_games,
            "missing_date_rows": self.missing_date_rows,
            "season_type_counts": dict(sorted(self.season_type_counts.items())),
            "promotion_eligibility_counts": dict(
                sorted(self.eligibility_counts.items())
            ),
            "rejection_counts": dict(sorted(self.rejection_counts.items())),
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_values(row: Mapping[Optional[str], Any]) -> Dict[str, Any]:
    values = {field: row.get(field) for field in EXPECTED_HEADER}
    if row.get(None) is not None:
        values["_extra_values"] = list(row[None])
    return values


def _row_hash(raw_values: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(raw_values, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _integer(raw: str, field: str, *, required: bool = False) -> Optional[int]:
    if not raw:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{field} is not an integer") from exc


def _decimal(raw: str, field: str) -> Optional[Decimal]:
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not numeric") from exc


def _eligibility(season: str, season_type: str, wl: Optional[str]) -> str:
    if season >= "2018-19":
        return "excluded_incomplete_2018_19"
    if season_type not in {"Regular Season", "Playoffs"}:
        return "excluded_unsupported_event_type"
    if wl is None:
        return "excluded_incomplete_result"
    if "2006-07" <= season <= "2017-18":
        return "eligible_market_range"
    return "deferred_pre_2006"


def _rejection(
    row_number: int,
    row_hash: str,
    raw_values: Mapping[str, Any],
    reason_code: str,
    detail: str,
) -> Dict[str, Any]:
    return {
        "source_row_number": row_number,
        "row_sha256": row_hash,
        "reason_code": reason_code,
        "reason_detail": detail,
        "raw_values": dict(raw_values),
    }


def _pair_error(pair: Sequence[Mapping[str, Any]]) -> Optional[str]:
    if len(pair) != 2:
        return "game does not have exactly two valid team perspectives"
    first, second = pair
    if not (
        first["team_id"] == second["opponent_team_id"]
        and first["opponent_team_id"] == second["team_id"]
    ):
        return "team/opponent IDs are not reciprocal"
    if {first["is_home"], second["is_home"]} != {True, False}:
        return "game does not contain one home and one away row"
    results = {first["wl"], second["wl"]}
    if results not in ({"W", "L"}, {None}):
        return "paired result values are neither W/L nor both missing"
    for field in ("game_date", "season", "season_start_year", "season_type"):
        if first[field] != second[field]:
            return f"paired rows disagree on {field}"
    return None


def parse_kaggle_games(
    raw_path: str | Path,
    *,
    encoding: str = "utf-8-sig",
) -> ParsedKaggleGames:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise KaggleGameParseError(f"Source file does not exist: {path}")
    before = path.stat()
    file_hash = _sha256(path)
    candidate_rows: List[Mapping[str, Any]] = []
    rejections: List[Mapping[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    seen_grains = set()

    try:
        with path.open("r", encoding=encoding, newline="") as source:
            reader = csv.DictReader(source)
            header = tuple(reader.fieldnames or ())
            if header != EXPECTED_HEADER:
                raise KaggleGameParseError(
                    f"Unexpected CSV header: {header}; expected {EXPECTED_HEADER}"
                )
            for row_number, raw_row in enumerate(reader, start=2):
                raw_values = _raw_values(raw_row)
                row_hash = _row_hash(raw_values)
                values = {
                    field: str(raw_row.get(field) or "").strip()
                    for field in EXPECTED_HEADER
                }
                try:
                    if raw_row.get(None) is not None or any(
                        raw_row.get(field) is None for field in EXPECTED_HEADER
                    ):
                        raise ValueError("row width does not match the header")
                    required = (
                        "game_id", "matchup", "team_id", "is_home",
                        "a_team_id", "season_year", "season_type", "season",
                    )
                    if any(not values[field] for field in required):
                        raise ValueError("one or more required fields are blank")
                    if not GAME_ID_PATTERN.fullmatch(values["game_id"]):
                        raise ValueError("game_id is not a ten-digit NBA identifier")
                    team_id = _integer(values["team_id"], "team_id", required=True)
                    opponent_id = _integer(
                        values["a_team_id"], "a_team_id", required=True
                    )
                    if team_id == opponent_id:
                        raise ValueError("team and opponent IDs are equal")
                    if values["is_home"] not in {"t", "f"}:
                        raise ValueError("is_home is not t or f")
                    wl = values["wl"] or None
                    if wl not in {None, "W", "L"}:
                        raise ValueError("wl is not blank, W, or L")
                    if values["season_type"] not in ALLOWED_SEASON_TYPES:
                        raise ValueError("season_type is unsupported")
                    if not SEASON_PATTERN.fullmatch(values["season"]):
                        raise ValueError("season is not canonical YYYY-YY")
                    season_start_year = _integer(
                        values["season_year"], "season_year", required=True
                    )
                    if season_start_year != int(values["season"][:4]):
                        raise ValueError("season_year disagrees with season")
                    game_date = None
                    if values["game_date"]:
                        try:
                            game_date = date.fromisoformat(values["game_date"])
                        except ValueError as exc:
                            raise ValueError("game_date is not ISO YYYY-MM-DD") from exc
                    integer_values = {
                        field: _integer(values[field], field)
                        for field in OPTIONAL_INTEGER_FIELDS
                    }
                    decimal_values = {
                        field: _decimal(values[field], field)
                        for field in OPTIONAL_DECIMAL_FIELDS
                    }
                    grain = (values["game_id"], team_id)
                    if grain in seen_grains:
                        raise ValueError("duplicate game/team natural key")
                    seen_grains.add(grain)
                except ValueError as exc:
                    reason = "invalid_source_row"
                    if "duplicate" in str(exc):
                        reason = "duplicate_natural_key"
                    rejection_counts[reason] += 1
                    rejections.append(
                        _rejection(row_number, row_hash, raw_values, reason, str(exc))
                    )
                    continue

                candidate_rows.append(
                    {
                        "source_row_number": row_number,
                        "row_sha256": row_hash,
                        "game_id": values["game_id"],
                        "game_date_raw": values["game_date"] or None,
                        "game_date": game_date,
                        "matchup": values["matchup"],
                        "team_id": team_id,
                        "is_home": values["is_home"] == "t",
                        "wl": wl,
                        "wins_to_date": integer_values["w"],
                        "losses_to_date": integer_values["l"],
                        "win_pct_to_date": decimal_values["w_pct"],
                        "minutes": decimal_values["min"],
                        "fgm": integer_values["fgm"],
                        "fga": integer_values["fga"],
                        "fg_pct": decimal_values["fg_pct"],
                        "fg3m": integer_values["fg3m"],
                        "fg3a": integer_values["fg3a"],
                        "fg3_pct": decimal_values["fg3_pct"],
                        "ftm": integer_values["ftm"],
                        "fta": integer_values["fta"],
                        "ft_pct": decimal_values["ft_pct"],
                        "oreb": integer_values["oreb"],
                        "dreb": integer_values["dreb"],
                        "reb": integer_values["reb"],
                        "ast": integer_values["ast"],
                        "stl": integer_values["stl"],
                        "blk": integer_values["blk"],
                        "tov": integer_values["tov"],
                        "pf": integer_values["pf"],
                        "pts": integer_values["pts"],
                        "opponent_team_id": opponent_id,
                        "season_start_year": season_start_year,
                        "season_type": values["season_type"],
                        "season": values["season"],
                        "date_status": "parsed" if game_date else "missing",
                        "result_status": "final" if wl else "missing",
                        "promotion_eligibility": _eligibility(
                            values["season"], values["season_type"], wl
                        ),
                        "canonical_match_status": "not_evaluated",
                        "validation_status": "staged",
                        "raw_values": raw_values,
                    }
                )
    except (UnicodeError, csv.Error, OSError) as exc:
        raise KaggleGameParseError(f"Could not parse Kaggle game CSV: {exc}") from exc

    by_game: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_game[str(row["game_id"])].append(row)
    invalid_game_ids = {
        game_id: error
        for game_id, pair in by_game.items()
        if (error := _pair_error(pair)) is not None
    }
    rows: List[Mapping[str, Any]] = []
    for row in candidate_rows:
        error = invalid_game_ids.get(str(row["game_id"]))
        if error is None:
            rows.append(row)
            continue
        rejection_counts["invalid_game_pair"] += 1
        rejections.append(
            _rejection(
                int(row["source_row_number"]),
                str(row["row_sha256"]),
                row["raw_values"],
                "invalid_game_pair",
                error,
            )
        )

    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise KaggleGameParseError("Source file changed while it was being parsed")
    season_type_counts = Counter(str(row["season_type"]) for row in rows)
    eligibility_counts = Counter(str(row["promotion_eligibility"]) for row in rows)
    return ParsedKaggleGames(
        file_name=path.name,
        file_size_bytes=before.st_size,
        sha256=file_hash,
        source_row_count=len(rows) + len(rejections),
        rows=tuple(rows),
        rejections=tuple(rejections),
        season_type_counts=dict(season_type_counts),
        eligibility_counts=dict(eligibility_counts),
        rejection_counts=dict(rejection_counts),
        missing_date_rows=sum(row["game_date"] is None for row in rows),
        distinct_games=len({row["game_id"] for row in rows}),
    )


def _apply(args: argparse.Namespace, parsed: ParsedKaggleGames) -> Dict[str, Any]:
    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.kaggle_game_staging_service import (
        KAGGLE_GAME_STAGING_LOCK_NAME,
        stage_kaggle_games,
    )

    details = {
        "source_import_id": args.manifest_id,
        "file_name": parsed.file_name,
        "sha256": parsed.sha256,
        "parser_version": PARSER_VERSION,
        "scope": "staging_only",
    }
    with IngestionRunTracker(
        run_type="external_kaggle_game_staging",
        source="kaggle-uploaded-pack",
        season=None,
        target_date=None,
        provider="registered_external_artifact",
        calculation_version=PARSER_VERSION,
        details=details,
        lock_name=KAGGLE_GAME_STAGING_LOCK_NAME,
    ) as tracker:
        result = stage_kaggle_games(
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
            rows_written=result.inserted_staged_rows + result.inserted_rejected_rows,
            details={
                **details,
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
    parser = argparse.ArgumentParser(description="Stage registered Kaggle game rows")
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
        parsed = parse_kaggle_games(args.file, encoding=args.encoding)
        output = (
            {
                "mode": "dry-run",
                "database_write": False,
                "manifest_id": args.manifest_id,
                **parsed.summary(),
            }
            if args.dry_run
            else _apply(args, parsed)
        )
    except Exception as exc:
        print(f"Kaggle game staging failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
