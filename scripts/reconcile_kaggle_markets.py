"""Generate a read-only exact-identity reconciliation for staged markets."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MARKET_TABLES = {
    "moneyline": "stg_kaggle_moneylines",
    "spread": "stg_kaggle_spreads",
    "total": "stg_kaggle_totals",
}


class MarketReconciliationError(ValueError):
    """Raised when the registered market scope is not safely comparable."""


def _manifest(connection, import_id: str, expected_dataset: str) -> Mapping[str, Any]:
    from sqlalchemy import text

    row = connection.execute(
        text(
            """
            SELECT import_id, source_name, dataset_name, license_status,
                   commercial_use_status, validation_status
            FROM external_dataset_imports
            WHERE import_id = :import_id
            """
        ),
        {"import_id": import_id},
    ).mappings().one_or_none()
    if row is None:
        raise MarketReconciliationError(f"Unknown manifest: {import_id}")
    expected = {
        "source_name": "kaggle-uploaded-pack",
        "dataset_name": expected_dataset,
        "license_status": "approved_public",
        "commercial_use_status": "permitted",
    }
    mismatches = [key for key, value in expected.items() if row[key] != value]
    if row["validation_status"] not in {"registered", "profiled"}:
        mismatches.append("validation_status")
    if mismatches:
        raise MarketReconciliationError(
            f"Manifest {import_id} is not eligible: "
            + ", ".join(sorted(set(mismatches)))
        )
    return row


def _canonical_games(connection, game_import_id: str) -> Dict[str, Any]:
    from sqlalchemy import text

    rows = connection.execute(
        text(
            """
            WITH source_games AS (
                SELECT DISTINCT game_id, season, season_type
                FROM stg_kaggle_games
                WHERE source_import_id = :game_import_id
                  AND promotion_eligibility = 'eligible_market_range'
                  AND season_type IN ('Regular Season', 'Playoffs')
            )
            SELECT source_games.game_id,
                   source_games.season AS source_season,
                   source_games.season_type AS source_season_type,
                   count(gs.team_id) AS canonical_row_count,
                   array_agg(gs.team_id ORDER BY gs.team_id)
                       FILTER (WHERE gs.team_id IS NOT NULL) AS team_ids,
                   array_agg(gs.opponent_team_id ORDER BY gs.team_id)
                       FILTER (WHERE gs.team_id IS NOT NULL) AS opponent_team_ids,
                   array_agg(gs.season ORDER BY gs.team_id)
                       FILTER (WHERE gs.team_id IS NOT NULL) AS seasons,
                   array_agg(gs.season_type ORDER BY gs.team_id)
                       FILTER (WHERE gs.team_id IS NOT NULL) AS season_types
                   ,array_agg(gs.game_date::date ORDER BY gs.team_id)
                       FILTER (WHERE gs.team_id IS NOT NULL) AS game_dates
            FROM source_games
            LEFT JOIN game_schedule gs ON gs.game_id = source_games.game_id
            GROUP BY source_games.game_id, source_games.season,
                     source_games.season_type
            ORDER BY source_games.game_id
            """
        ),
        {"game_import_id": game_import_id},
    ).mappings().all()
    return {str(row["game_id"]): row for row in rows}


def _market_rows(
    connection,
    *,
    market: str,
    market_import_id: str,
    game_import_id: str,
):
    from sqlalchemy import text

    table = MARKET_TABLES[market]
    return connection.execute(
        text(
            f"""
            SELECT m.game_id, m.team_id, m.opponent_team_id, m.book_id,
                   m.book_name, m.source_row_number, m.parser_version,
                   m.source_game_parser_version, sg.season, sg.season_type,
                   sg.game_date, sg.is_home
            FROM {table} m
            JOIN stg_kaggle_games sg
              ON sg.source_import_id = m.source_game_import_id
             AND sg.game_id = m.game_id
             AND sg.team_id = m.team_id
             AND sg.parser_version = m.source_game_parser_version
            WHERE m.source_import_id = :market_import_id
              AND m.source_game_import_id = :game_import_id
              AND sg.promotion_eligibility = 'eligible_market_range'
              AND sg.season_type IN ('Regular Season', 'Playoffs')
            ORDER BY m.game_id, m.book_id, m.team_id
            """
        ),
        {
            "market_import_id": market_import_id,
            "game_import_id": game_import_id,
        },
    ).mappings().all()


def _markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Kaggle Market Reconciliation Report",
        "",
        "Status: generated from a read-only PostgreSQL transaction; no market or canonical rows changed",
        f"Generated (UTC): {report['generated_at']}",
        "",
        "## Technical summary",
        "",
        f"- Eligible staged market rows evaluated: {summary['rows']:,}",
        f"- Exact canonical identity matches: {summary['matched_rows']:,}",
        f"- Rows whose canonical game is missing: {summary['canonical_missing_rows']:,}",
        f"- Canonical incomplete rows: {summary['canonical_incomplete_rows']:,}",
        f"- Identity conflicts: {summary['conflict_rows']:,}",
        "",
        "Historical snapshots retain `timing_precision = unknown` and `snapshot_type = historical_static`. Identity reconciliation does not make them opening, closing, or prediction-time observations.",
        "",
        "## Coverage by market and season type",
        "",
        "| Market | Season type | Rows | Games | Matched rows | Missing rows | Conflicts |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["coverage"]:
        lines.append(
            f"| {item['market']} | {item['season_type']} | {item['rows']:,} | "
            f"{item['games']:,} | {item['matched']:,} | "
            f"{item['canonical_missing']:,} | {item['conflict']:,} |"
        )
    lines.extend(
        [
            "",
            "## Game coverage against the eligible source schedule",
            "",
            "| Market | Season type | Eligible source games | Games with market rows | Games without market rows |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in report["game_coverage"]:
        lines.append(
            f"| {item['market']} | {item['season_type']} | "
            f"{item['eligible_source_games']:,} | {item['market_games']:,} | "
            f"{item['games_without_market']:,} |"
        )
    lines.extend(
        [
            "",
            "## Coverage by source season",
            "",
            "| Market | Season | Season type | Rows | Games | Matched | Canonical missing | Conflicts |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in report["coverage_by_season"]:
        lines.append(
            f"| {item['market']} | {item['season']} | {item['season_type']} | "
            f"{item['rows']:,} | {item['games']:,} | {item['matched']:,} | "
            f"{item['canonical_missing']:,} | {item['conflict']:,} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation and next gate",
            "",
            "Playoff market identity can be promoted independently because the eligible playoff schedule set is now canonical. Regular-season market rows whose games remain absent must stay staged; they are not invalid market observations.",
            "",
            "Before promotion, approve a canonical append-only market-observation grain, retain the source manifest/run/row/parser chain, preserve selection-specific spread/total pairs, and define source precedence without overwriting either historical or future observations.",
            "",
        ]
    )
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    from sqlalchemy import text

    from app.database import engine
    from app.services.kaggle_market_reconciliation_service import (
        CanonicalMarketGameEvidence,
        MarketIdentityEvidence,
        classify_market_identity,
    )

    manifests = {
        "moneyline": (args.moneyline_manifest_id, "nba-moneyline-observations"),
        "spread": (args.spread_manifest_id, "nba-spread-observations"),
        "total": (args.totals_manifest_id, "nba-total-observations"),
    }
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            _manifest(connection, args.game_manifest_id, "nba-team-game-facts")
            for import_id, dataset in manifests.values():
                _manifest(connection, import_id, dataset)
            canonical = _canonical_games(connection, args.game_manifest_id)
            market_rows = {
                market: _market_rows(
                    connection,
                    market=market,
                    market_import_id=import_id,
                    game_import_id=args.game_manifest_id,
                )
                for market, (import_id, _) in manifests.items()
            }
        finally:
            transaction.rollback()

    overall = Counter()
    by_scope = defaultdict(Counter)
    by_season_scope = defaultdict(Counter)
    game_ids = defaultdict(set)
    season_game_ids = defaultdict(set)
    conflict_samples = []
    for market, rows in market_rows.items():
        for row in rows:
            canonical_row = canonical.get(str(row["game_id"]))
            evidence = None
            if str(row["parser_version"]) != "kaggle-markets-v1":
                raise MarketReconciliationError("Unexpected market parser version")
            if str(row["source_game_parser_version"]) != "kaggle-games-v1":
                raise MarketReconciliationError("Unexpected source-game parser version")
            if canonical_row and int(canonical_row["canonical_row_count"]) > 0:
                evidence = CanonicalMarketGameEvidence(
                    row_count=int(canonical_row["canonical_row_count"]),
                    team_ids=tuple(int(value) for value in canonical_row["team_ids"]),
                    opponent_team_ids=tuple(
                        int(value) for value in canonical_row["opponent_team_ids"]
                    ),
                    seasons=tuple(canonical_row["seasons"]),
                    season_types=tuple(canonical_row["season_types"]),
                    game_dates=tuple(canonical_row["game_dates"]),
                )
            result = classify_market_identity(
                MarketIdentityEvidence(
                    game_id=str(row["game_id"]),
                    team_id=int(row["team_id"]),
                    opponent_team_id=int(row["opponent_team_id"]),
                    season=str(row["season"]),
                    season_type=str(row["season_type"]),
                    game_date=row["game_date"],
                    is_home=bool(row["is_home"]),
                ),
                evidence,
            )
            key = (market, str(row["season_type"]))
            season_key = (market, str(row["season"]), str(row["season_type"]))
            overall[result.status] += 1
            overall["rows"] += 1
            by_scope[key][result.status] += 1
            by_scope[key]["rows"] += 1
            game_ids[key].add(str(row["game_id"]))
            by_season_scope[season_key][result.status] += 1
            by_season_scope[season_key]["rows"] += 1
            season_game_ids[season_key].add(str(row["game_id"]))
            if result.status == "conflict" and len(conflict_samples) < 20:
                conflict_samples.append(
                    {
                        "market": market,
                        "game_id": str(row["game_id"]),
                        "team_id": int(row["team_id"]),
                        "reasons": list(result.conflict_reasons),
                    }
                )

    coverage = []
    for key in sorted(by_scope):
        counts = by_scope[key]
        coverage.append(
            {
                "market": key[0],
                "season_type": key[1],
                "rows": counts["rows"],
                "games": len(game_ids[key]),
                "matched": counts["matched"],
                "canonical_missing": counts["canonical_missing"],
                "canonical_incomplete": counts["canonical_incomplete"],
                "conflict": counts["conflict"],
            }
        )
    coverage_by_season = []
    for key in sorted(by_season_scope):
        counts = by_season_scope[key]
        coverage_by_season.append(
            {
                "market": key[0],
                "season": key[1],
                "season_type": key[2],
                "rows": counts["rows"],
                "games": len(season_game_ids[key]),
                "matched": counts["matched"],
                "canonical_missing": counts["canonical_missing"],
                "canonical_incomplete": counts["canonical_incomplete"],
                "conflict": counts["conflict"],
            }
        )
    eligible_game_counts = Counter(
        str(row["source_season_type"]) for row in canonical.values()
    )
    game_coverage = []
    for market in sorted(MARKET_TABLES):
        for season_type in ("Regular Season", "Playoffs"):
            market_games = len(game_ids[(market, season_type)])
            eligible_games = eligible_game_counts[season_type]
            game_coverage.append(
                {
                    "market": market,
                    "season_type": season_type,
                    "eligible_source_games": eligible_games,
                    "market_games": market_games,
                    "games_without_market": eligible_games - market_games,
                }
            )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_write": False,
        "scope": "2006-07 through 2017-18 Regular Season and Playoffs",
        "summary": {
            "rows": overall["rows"],
            "matched_rows": overall["matched"],
            "canonical_missing_rows": overall["canonical_missing"],
            "canonical_incomplete_rows": overall["canonical_incomplete"],
            "conflict_rows": overall["conflict"],
        },
        "coverage": coverage,
        "coverage_by_season": coverage_by_season,
        "game_coverage": game_coverage,
        "conflict_samples": conflict_samples,
        "manifests": {
            "game": args.game_manifest_id,
            **{market: values[0] for market, values in manifests.items()},
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only exact identity reconciliation for Kaggle markets"
    )
    parser.add_argument("--game-manifest-id", required=True)
    parser.add_argument("--moneyline-manifest-id", required=True)
    parser.add_argument("--spread-manifest-id", required=True)
    parser.add_argument("--totals-manifest-id", required=True)
    parser.add_argument("--report")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_report(args)
        if args.report:
            output = Path(args.report).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(_markdown(report), encoding="utf-8")
            report["report_path"] = str(output)
    except Exception as exc:
        print(f"Kaggle market reconciliation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
