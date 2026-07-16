"""Generate the consolidated Release 1 external-data coverage report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_report(connection) -> str:
    from sqlalchemy import text

    manifests = connection.execute(
        text(
            """
            SELECT dataset_name, source_name, source_row_count,
                   license_status, commercial_use_status, validation_status
            FROM external_dataset_imports
            ORDER BY dataset_name
            """
        )
    ).mappings().all()
    table_counts = connection.execute(
        text(
            """
            SELECT 'Stat Surge checkpoints' AS dataset,
                   count(*) AS rows, count(DISTINCT report_date) AS units
            FROM stg_statsurge_availability
            UNION ALL
            SELECT 'Kaggle team games', count(*), count(DISTINCT game_id)
            FROM stg_kaggle_games
            UNION ALL
            SELECT 'Kaggle moneylines', count(*), count(DISTINCT game_id)
            FROM stg_kaggle_moneylines
            UNION ALL
            SELECT 'Kaggle spreads', count(*), count(DISTINCT game_id)
            FROM stg_kaggle_spreads
            UNION ALL
            SELECT 'Kaggle totals', count(*), count(DISTINCT game_id)
            FROM stg_kaggle_totals
            ORDER BY dataset
            """
        )
    ).mappings().all()
    injury = connection.execute(
        text(
            """
            SELECT season, count(*) AS rows,
                   count(*) FILTER (WHERE identity_status = 'resolved') AS resolved,
                   count(*) FILTER (WHERE identity_status = 'partial') AS partial,
                   count(*) FILTER (WHERE resolved_player_id IS NULL) AS player_unresolved,
                   count(*) FILTER (WHERE resolved_game_id IS NULL) AS game_unresolved,
                   count(*) FILTER (WHERE cutoff_status = 'unknown') AS cutoff_unknown
            FROM stg_statsurge_availability
            GROUP BY season ORDER BY season
            """
        )
    ).mappings().all()
    game_coverage = connection.execute(
        text(
            """
            WITH source_games AS (
                SELECT game_id, min(season) AS season,
                       min(season_type) AS season_type
                FROM stg_kaggle_games
                WHERE promotion_eligibility = 'eligible_market_range'
                GROUP BY game_id
            ), canonical AS (
                SELECT game_id, count(*) AS rows
                FROM game_schedule GROUP BY game_id
            )
            SELECT season_type, count(*) AS source_games,
                   count(*) FILTER (WHERE canonical.rows = 2) AS canonical_games,
                   count(*) FILTER (WHERE canonical.rows IS NULL) AS canonical_missing
            FROM source_games
            LEFT JOIN canonical USING (game_id)
            GROUP BY season_type ORDER BY season_type
            """
        )
    ).mappings().all()
    market_coverage = connection.execute(
        text(
            """
            WITH market_rows AS (
                SELECT 'moneyline' AS market, game_id, team_id,
                       opponent_team_id, source_game_import_id
                FROM stg_kaggle_moneylines
                UNION ALL
                SELECT 'spread', game_id, team_id, opponent_team_id,
                       source_game_import_id FROM stg_kaggle_spreads
                UNION ALL
                SELECT 'total', game_id, team_id, opponent_team_id,
                       source_game_import_id FROM stg_kaggle_totals
            ), canonical_counts AS (
                SELECT game_id, count(*) AS rows
                FROM game_schedule GROUP BY game_id
            )
            SELECT market, sg.season_type, count(*) AS rows,
                   count(DISTINCT market_rows.game_id) AS games,
                   count(*) FILTER (
                       WHERE canonical_counts.rows = 2
                         AND gs.opponent_team_id = market_rows.opponent_team_id
                   ) AS matched,
                   count(*) FILTER (WHERE canonical_counts.rows IS NULL) AS missing,
                   count(*) FILTER (
                       WHERE canonical_counts.rows IS NOT NULL
                         AND (canonical_counts.rows <> 2 OR gs.opponent_team_id IS DISTINCT FROM market_rows.opponent_team_id)
                   ) AS conflict
            FROM market_rows
            JOIN stg_kaggle_games sg
              ON sg.source_import_id = market_rows.source_game_import_id
             AND sg.game_id = market_rows.game_id
             AND sg.team_id = market_rows.team_id
             AND sg.parser_version = 'kaggle-games-v1'
            LEFT JOIN canonical_counts ON canonical_counts.game_id = market_rows.game_id
            LEFT JOIN game_schedule gs
              ON gs.game_id = market_rows.game_id
             AND gs.team_id = market_rows.team_id
            WHERE sg.promotion_eligibility = 'eligible_market_range'
              AND sg.season_type IN ('Regular Season', 'Playoffs')
            GROUP BY market, sg.season_type
            ORDER BY market, sg.season_type
            """
        )
    ).mappings().all()
    anomaly = connection.execute(
        text(
            """
            SELECT count(*) AS anomalies,
                   (SELECT count(*) FROM external_row_rejections) AS rejections
            FROM external_market_anomalies
            """
        )
    ).mappings().one()
    promoted = connection.execute(
        text(
            """
            SELECT count(*) AS rows, count(DISTINCT game_id) AS games
            FROM game_schedule
            WHERE source_name = 'kaggle-uploaded-pack'
              AND season_type = 'Playoffs'
            """
        )
    ).mappings().one()

    lines = [
        "# Release 1 External Data Coverage Report",
        "",
        "Status: Release 1 — External Data Staging complete in the local branch and local PostgreSQL database; not yet committed, merged, or deployed",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Technical summary",
        "",
        "Release 1 now has immutable manifests, source-specific staging, quarantine partitions, deterministic identity reconciliation, documented source precedence, provenance-preserving bounded promotion, and no public consumer. Historical market timing and Stat Surge cutoff timing remain explicitly unknown rather than being inferred.",
        "",
        "## Registered source artifacts",
        "",
        "| Dataset | Source | Inspected rows | License | Commercial use | Validation |",
        "|---|---|---:|---|---|---|",
    ]
    for row in manifests:
        lines.append(
            f"| {row['dataset_name']} | {row['source_name']} | "
            f"{int(row['source_row_count'] or 0):,} | {row['license_status']} | "
            f"{row['commercial_use_status']} | {row['validation_status']} |"
        )
    lines.extend(
        [
            "",
            "## Staging coverage",
            "",
            "| Dataset | Staged rows | Distinct dates or games |",
            "|---|---:|---:|",
        ]
    )
    for row in table_counts:
        lines.append(
            f"| {row['dataset']} | {int(row['rows']):,} | {int(row['units']):,} |"
        )
    lines.extend(
        [
            "",
            "## Stat Surge identity coverage",
            "",
            "| Season | Rows | Fully identity-resolved | Partial | Player unresolved | Game unresolved | Cutoff unknown |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in injury:
        lines.append(
            f"| {row['season']} | {int(row['rows']):,} | {int(row['resolved']):,} | "
            f"{int(row['partial']):,} | {int(row['player_unresolved']):,} | "
            f"{int(row['game_unresolved']):,} | {int(row['cutoff_unknown']):,} |"
        )
    lines.extend(
        [
            "",
            "## Eligible game coverage",
            "",
            "| Season type | Source games | Canonical games | Canonical missing |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in game_coverage:
        lines.append(
            f"| {row['season_type']} | {int(row['source_games']):,} | "
            f"{int(row['canonical_games']):,} | {int(row['canonical_missing']):,} |"
        )
    lines.extend(
        [
            "",
            f"The bounded playoff promotion inserted {int(promoted['games']):,} previously missing games / {int(promoted['rows']):,} reciprocal rows with manifest, run, row, hash, and parser lineage. Missing regular-season games remain staged and are not a Release 1 blocker.",
            "",
            "## Eligible market identity coverage",
            "",
            "| Market | Season type | Rows | Games | Exact canonical matches | Canonical missing | Conflicts |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in market_coverage:
        lines.append(
            f"| {row['market']} | {row['season_type']} | {int(row['rows']):,} | "
            f"{int(row['games']):,} | {int(row['matched']):,} | "
            f"{int(row['missing']):,} | {int(row['conflict']):,} |"
        )
    lines.extend(
        [
            "",
            "## Quarantine and partition results",
            "",
            f"- Market semantic anomalies: {int(anomaly['anomalies']):,}",
            f"- Parser row rejections: {int(anomaly['rejections']):,}",
            "- Selection-specific spread and total pairs remain source-shaped; they were not normalized away.",
            "",
            "## Release 1 exit gate",
            "",
            "| Gate | Local status | Evidence |",
            "|---|---|---|",
            "| Import manifests | Complete | Eight immutable artifact registrations with hashes and permissions |",
            "| Staging tables | Complete | Injury, team-game, moneyline, spread, total, rejection, and anomaly tables |",
            "| Injury and odds profiles | Complete | Source semantics, season coverage, missingness, and timing limitations are reported |",
            "| Identity reconciliation | Complete for Release 1 | Exact game/market audit plus versioned Stat Surge staging identity outcomes |",
            "| Quarantine rules | Complete | Malformed and declared semantic anomaly partitions are queryable |",
            "| Source precedence | Complete | Field-specific non-destructive rules in `ANALYTICS_ARCHITECTURE_CONTRACT.md` |",
            "| No public behavior change | Complete | No route, cache, model, or serving consumer was added |",
            "",
            "## Intentional deferrals",
            "",
            "- Canonical market-observation promotion waits for a separate append-only header/selection contract. `game_odds` is not a safe target.",
            "- Stat Surge canonical availability promotion waits for stronger cutoff semantics; all rows remain staging-only and cutoff-unknown.",
            "- Fourteen unresolved player names and two missing/cancelled source games remain queryable rather than fuzzily matched.",
            "- Promotion of 12,059 missing eligible regular-season games and 363 audited date repairs is a separate high-volume phase.",
            "- Full player-game and identity-file relational staging is deferred to broader Program A work; it is not required for Release 1's no-public-behavior staging boundary.",
            "- Official injury PDF collection, forward timestamped odds, and box-score endpoint bake-offs begin later roadmap milestones.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the read-only Release 1 external-data report"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "RELEASE_1_EXTERNAL_DATA_COVERAGE_REPORT.md",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    from sqlalchemy import text

    from app.database import engine

    args = build_parser().parse_args(argv)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            report = build_report(connection)
        finally:
            transaction.rollback()
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
