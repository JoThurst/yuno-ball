"""Read-only reconciliation of staged Kaggle games against Yuno schedules."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PLAYER_GAME_HEADER = (
    "season_id", "player_id", "player_name", "team_id", "team_abbreviation",
    "team_name", "game_id", "game_date", "matchup", "wl", "min", "fgm",
    "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
    "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "pts",
    "plus_minus", "season_type", "season_year", "season",
)
GAME_PARSER_VERSION = "kaggle-games-v1"
HASH_CHUNK_BYTES = 1024 * 1024


class ReconciliationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_and_canonical_rows(connection, game_manifest_id: str):
    from sqlalchemy import text

    return connection.execute(
        text(
            """
            WITH source_games AS (
                SELECT
                    game_id,
                    min(season) AS season,
                    min(season_type) AS season_type,
                    min(game_date) AS game_date,
                    array_agg(team_id ORDER BY team_id) AS team_ids,
                    array_agg(opponent_team_id ORDER BY team_id) AS opponent_team_ids,
                    array_agg(is_home ORDER BY team_id) AS home_flags,
                    array_agg(wl ORDER BY team_id) AS results,
                    array_agg(pts ORDER BY team_id) AS points
                FROM stg_kaggle_games
                WHERE source_import_id = :game_manifest_id
                  AND parser_version = :parser_version
                  AND promotion_eligibility = 'eligible_market_range'
                GROUP BY game_id
            ),
            canonical_games AS (
                SELECT
                    gs.game_id,
                    count(*) AS row_count,
                    array_agg(gs.team_id::bigint ORDER BY gs.team_id) AS team_ids,
                    array_agg(gs.opponent_team_id::bigint ORDER BY gs.team_id)
                        AS opponent_team_ids,
                    array_agg(gs.season ORDER BY gs.team_id) AS seasons,
                    array_agg(gs.game_date::date ORDER BY gs.team_id) AS game_dates,
                    array_agg(gs.home_or_away ORDER BY gs.team_id) AS home_or_away,
                    array_agg(gs.result ORDER BY gs.team_id) AS results
                FROM game_schedule gs
                WHERE gs.game_id IN (SELECT game_id FROM source_games)
                GROUP BY gs.game_id
            )
            SELECT
                s.*,
                c.row_count AS canonical_row_count,
                c.team_ids AS canonical_team_ids,
                c.opponent_team_ids AS canonical_opponent_team_ids,
                c.seasons AS canonical_seasons,
                c.game_dates AS canonical_game_dates,
                c.home_or_away AS canonical_home_or_away,
                c.results AS canonical_results
            FROM source_games s
            LEFT JOIN canonical_games c USING (game_id)
            ORDER BY s.season, s.season_type, s.game_id
            """
        ),
        {"game_manifest_id": game_manifest_id, "parser_version": GAME_PARSER_VERSION},
    ).mappings().all()


def _manifest(connection, import_id: str) -> Mapping[str, Any]:
    from sqlalchemy import text

    row = connection.execute(
        text(
            """
            SELECT import_id, source_name, dataset_name, dataset_version,
                   file_name, file_size_bytes, sha256, source_row_count,
                   license_status, commercial_use_status, validation_status
            FROM external_dataset_imports
            WHERE import_id = :import_id
            """
        ),
        {"import_id": import_id},
    ).mappings().one_or_none()
    if row is None:
        raise ReconciliationError(f"Unknown external manifest: {import_id}")
    return row


def _team_coverage(connection, game_manifest_id: str) -> Dict[str, Any]:
    from sqlalchemy import text

    row = connection.execute(
        text(
            """
            WITH source_teams AS (
                SELECT DISTINCT team_id
                FROM stg_kaggle_games
                WHERE source_import_id = :game_manifest_id
                  AND promotion_eligibility = 'eligible_market_range'
                UNION
                SELECT DISTINCT opponent_team_id
                FROM stg_kaggle_games
                WHERE source_import_id = :game_manifest_id
                  AND promotion_eligibility = 'eligible_market_range'
            )
            SELECT count(*) AS source_team_ids,
                   count(*) FILTER (WHERE t.team_id IS NOT NULL) AS yuno_team_ids,
                   array_agg(source_teams.team_id ORDER BY source_teams.team_id)
                       FILTER (WHERE t.team_id IS NULL) AS missing_team_ids
            FROM source_teams
            LEFT JOIN teams t USING (team_id)
            """
        ),
        {"game_manifest_id": game_manifest_id},
    ).mappings().one()
    return {
        "source_team_ids": int(row["source_team_ids"]),
        "yuno_team_ids": int(row["yuno_team_ids"]),
        "missing_team_ids": list(row["missing_team_ids"] or []),
    }


def _parse_player_game_dates(path: Path, target_ids: set[str]):
    evidence = defaultdict(
        lambda: {"rows": 0, "dates": set(), "seasons": set(), "types": set(), "teams": set()}
    )
    total_rows = 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if tuple(reader.fieldnames or ()) != PLAYER_GAME_HEADER:
                raise ReconciliationError("Unexpected player-game CSV header")
            for row in reader:
                total_rows += 1
                game_id = str(row.get("game_id") or "").strip()
                if game_id not in target_ids:
                    continue
                item = evidence[game_id]
                item["rows"] += 1
                raw_date = str(row.get("game_date") or "").strip()
                if raw_date:
                    try:
                        item["dates"].add(date.fromisoformat(raw_date))
                    except ValueError as exc:
                        raise ReconciliationError(
                            f"Invalid player-game date for {game_id}: {raw_date}"
                        ) from exc
                item["seasons"].add(str(row.get("season") or "").strip())
                item["types"].add(str(row.get("season_type") or "").strip())
                raw_team = str(row.get("team_id") or "").strip()
                if raw_team:
                    item["teams"].add(int(raw_team))
    except (UnicodeError, csv.Error, OSError) as exc:
        raise ReconciliationError(f"Could not parse player-game CSV: {exc}") from exc
    return total_rows, evidence


def _markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Kaggle Game Reconciliation Report",
        "",
        "Status: generated read-only evidence; no canonical rows changed",
        f"Generated (UTC): {report['generated_at']}",
        "",
        "## Decision summary",
        "",
        f"- Source games evaluated: {summary['source_games']:,}",
        f"- Exact canonical matches: {summary['matched']:,}",
        f"- Canonical missing: {summary['canonical_missing']:,}",
        f"- Canonical incomplete: {summary['canonical_incomplete']:,}",
        f"- Conflicts: {summary['conflict']:,}",
        f"- Missing source dates: {report['date_repairs']['target_games']:,}",
        f"- Unique player-game date repairs: {report['date_repairs']['unique_repair']:,}",
        "",
        "## Canonical prerequisites",
        "",
    ]
    lines.extend(f"- {value}" for value in report["canonical_prerequisites"])
    lines.extend(["", "## Status by season type", "", "| Season type | Matched | Missing | Incomplete | Conflict |", "|---|---:|---:|---:|---:|"])
    for season_type, values in sorted(report["by_season_type"].items()):
        lines.append(
            f"| {season_type} | {values.get('matched', 0):,} | "
            f"{values.get('canonical_missing', 0):,} | "
            f"{values.get('canonical_incomplete', 0):,} | "
            f"{values.get('conflict', 0):,} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Missing Yuno games remain valid staged external evidence. The next write phase must add explicit season-type and source lineage to the canonical schedule contract, then backfill only exact-ID, reciprocal-team, final games with known or uniquely repaired dates.",
            "",
            "Playoff absence is a canonical coverage gap, not a reason to discard the staged game or its market observations.",
            "",
        ]
    )
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    from sqlalchemy import text
    from app.database import engine
    from app.services.kaggle_game_reconciliation_service import (
        CanonicalGameEvidence,
        PlayerGameDateEvidence,
        SourceGameEvidence,
        classify_date_repair,
        classify_game,
    )

    player_path = Path(args.player_game_file).expanduser().resolve()
    if not player_path.is_file():
        raise ReconciliationError(f"Player-game source file not found: {player_path}")
    player_hash = _sha256(player_path)

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            game_manifest = _manifest(connection, args.game_manifest_id)
            player_manifest = _manifest(connection, args.player_game_manifest_id)
            if game_manifest["dataset_name"] != "nba-team-game-facts":
                raise ReconciliationError("Game manifest dataset is not nba-team-game-facts")
            expected_player = {
                "source_name": "kaggle-uploaded-pack",
                "dataset_name": "nba-player-game-facts",
                "file_name": player_path.name,
                "sha256": player_hash,
                "file_size_bytes": player_path.stat().st_size,
                "license_status": "approved_public",
                "commercial_use_status": "permitted",
            }
            mismatches = [
                field
                for field, expected in expected_player.items()
                if player_manifest[field] != expected
            ]
            if mismatches:
                raise ReconciliationError(
                    "Player-game manifest mismatch: " + ", ".join(mismatches)
                )
            raw_rows = _source_and_canonical_rows(connection, args.game_manifest_id)
            team_coverage = _team_coverage(connection, args.game_manifest_id)
        finally:
            transaction.rollback()

    source_games = {}
    classifications = {}
    by_season_type = defaultdict(Counter)
    by_season = defaultdict(Counter)
    conflict_samples = []
    missing_samples = []
    for row in raw_rows:
        source = SourceGameEvidence(
            game_id=row["game_id"],
            season=row["season"],
            season_type=row["season_type"],
            game_date=row["game_date"],
            team_ids=tuple(int(value) for value in row["team_ids"]),
            opponent_team_ids=tuple(
                int(value) for value in row["opponent_team_ids"]
            ),
            home_flags=tuple(bool(value) for value in row["home_flags"]),
            results=tuple(row["results"]),
            points=tuple(row["points"]),
        )
        canonical = None
        if row["canonical_row_count"] is not None:
            canonical = CanonicalGameEvidence(
                row_count=int(row["canonical_row_count"]),
                team_ids=tuple(int(value) for value in row["canonical_team_ids"]),
                opponent_team_ids=tuple(
                    int(value) for value in row["canonical_opponent_team_ids"]
                ),
                seasons=tuple(row["canonical_seasons"]),
                game_dates=tuple(row["canonical_game_dates"]),
                home_or_away=tuple(row["canonical_home_or_away"]),
                results=tuple(row["canonical_results"]),
            )
        result = classify_game(source, canonical)
        source_games[source.game_id] = source
        classifications[source.game_id] = result
        by_season_type[source.season_type][result.status] += 1
        by_season[source.season][result.status] += 1
        sample = {
            "game_id": source.game_id,
            "season": source.season,
            "season_type": source.season_type,
            "game_date": source.game_date.isoformat() if source.game_date else None,
            "team_ids": list(source.team_ids),
        }
        if result.status == "conflict" and len(conflict_samples) < 20:
            conflict_samples.append(
                {**sample, "reasons": list(result.conflict_reasons)}
            )
        if result.status == "canonical_missing" and len(missing_samples) < 20:
            missing_samples.append(sample)

    missing_date_ids = {
        game_id for game_id, source in source_games.items() if source.game_date is None
    }
    total_player_rows, raw_player_evidence = _parse_player_game_dates(
        player_path, missing_date_ids
    )
    if total_player_rows != player_manifest["source_row_count"]:
        raise ReconciliationError(
            "Player-game parsed row count does not match its manifest"
        )

    date_statuses = Counter()
    date_samples = defaultdict(list)
    for game_id in sorted(missing_date_ids):
        raw = raw_player_evidence.get(game_id)
        evidence = None
        if raw is not None:
            evidence = PlayerGameDateEvidence(
                row_count=int(raw["rows"]),
                dates=tuple(sorted(raw["dates"])),
                seasons=tuple(sorted(raw["seasons"])),
                season_types=tuple(sorted(raw["types"])),
                team_ids=tuple(sorted(raw["teams"])),
            )
        repair = classify_date_repair(source_games[game_id], evidence)
        date_statuses[repair.status] += 1
        if len(date_samples[repair.status]) < 20:
            date_samples[repair.status].append(
                {
                    "game_id": game_id,
                    "season": source_games[game_id].season,
                    "season_type": source_games[game_id].season_type,
                    "proposed_date": (
                        repair.proposed_date.isoformat()
                        if repair.proposed_date
                        else None
                    ),
                    "reasons": list(repair.conflict_reasons),
                }
            )

    overall = Counter(value.status for value in classifications.values())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_write": False,
        "scope": "2006-07 through 2017-18 regular season and playoffs",
        "game_manifest_id": args.game_manifest_id,
        "player_game_manifest_id": args.player_game_manifest_id,
        "player_game_sha256": player_hash,
        "summary": {
            "source_games": len(source_games),
            "matched": overall["matched"],
            "canonical_missing": overall["canonical_missing"],
            "canonical_incomplete": overall["canonical_incomplete"],
            "conflict": overall["conflict"],
        },
        "by_season_type": {
            key: dict(value) for key, value in sorted(by_season_type.items())
        },
        "by_season": {key: dict(value) for key, value in sorted(by_season.items())},
        "team_coverage": team_coverage,
        "date_repairs": {
            "target_games": len(missing_date_ids),
            **dict(date_statuses),
            "samples": dict(date_samples),
        },
        "canonical_prerequisites": [
            "game_schedule needs explicit season_type before playoff backfill",
            "canonical rows need source_import_id and source_run_id lineage",
            "backfill must insert two reciprocal rows per exact NBA game_id",
            "only final Regular Season/Playoffs rows with known or uniquely repaired dates are eligible",
        ],
        "conflict_samples": conflict_samples,
        "canonical_missing_samples": missing_samples,
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only staged Kaggle game reconciliation"
    )
    parser.add_argument("--game-manifest-id", required=True)
    parser.add_argument("--player-game-manifest-id", required=True)
    parser.add_argument("--player-game-file", required=True)
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
        print(f"Kaggle game reconciliation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
