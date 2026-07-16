"""Deterministic identity reconciliation for staged Stat Surge checkpoints."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import json
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
import unicodedata

from sqlalchemy import text
from sqlalchemy.engine import Connection


IDENTITY_RESOLUTION_VERSION = "statsurge-identity-v1"
EXPECTED_IMPORT_IDENTITY = {
    "source_name": "stat-surge",
    "dataset_name": "nba-injury-daily-checkpoints",
    "license_status": "approved_public",
    "commercial_use_status": "permitted",
}
TEAM_NAME_ALIASES = {"LA Clippers": "Los Angeles Clippers"}
MATCHUP_PATTERN = re.compile(r"^(?P<away>[A-Z]{3})@(?P<home>[A-Z]{3})$")


@dataclass(frozen=True)
class CanonicalGameIdentity:
    game_id: str
    game_date: date
    season: str
    away_team_id: int
    away_abbreviation: str
    home_team_id: int
    home_abbreviation: str


@dataclass(frozen=True)
class StatsurgeIdentityResult:
    resolved_player_id: Optional[int]
    resolved_team_id: Optional[int]
    resolved_game_id: Optional[str]
    identity_status: str
    completeness_status: str
    cutoff_status: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class StatsurgeIdentityPlan:
    source_rows: int
    results: Tuple[Tuple[str, StatsurgeIdentityResult], ...]
    status_counts: Mapping[str, int]
    player_method_counts: Mapping[str, int]
    game_method_counts: Mapping[str, int]
    team_method_counts: Mapping[str, int]
    season_counts: Mapping[str, Mapping[str, int]]
    unresolved_player_counts: Mapping[str, int]


def normalize_player_name(value: str, *, source_order: bool = False) -> str:
    """Normalize order, accents, punctuation, and spacing without fuzzy aliases."""
    raw = str(value or "").strip()
    if source_order and "," in raw:
        last, first = raw.split(",", 1)
        raw = f"{first.strip()} {last.strip()}"
    normalized = unicodedata.normalize("NFKD", raw).casefold()
    return "".join(
        character
        for character in normalized
        if character.isalnum() and not unicodedata.combining(character)
    )


def resolve_statsurge_identity(
    *,
    reported_player_name: str,
    reported_team_name: str,
    matchup_text: str,
    report_date: date,
    season: str,
    teams_by_name: Mapping[str, Tuple[int, ...]],
    players_by_name: Mapping[str, Tuple[int, ...]],
    games_by_key: Mapping[Tuple[date, str, str], Tuple[CanonicalGameIdentity, ...]],
) -> StatsurgeIdentityResult:
    """Resolve one row using exact, auditable candidates only."""
    conflict_reasons = []
    canonical_team_name = TEAM_NAME_ALIASES.get(
        reported_team_name, reported_team_name
    )
    team_candidates = teams_by_name.get(canonical_team_name, ())
    if len(team_candidates) == 1:
        team_id = team_candidates[0]
        team_method = "explicit_alias" if canonical_team_name != reported_team_name else "exact_name"
    else:
        team_id = None
        team_method = "ambiguous" if len(team_candidates) > 1 else "unresolved"
        if len(team_candidates) > 1:
            conflict_reasons.append("ambiguous_team")

    player_key = normalize_player_name(reported_player_name, source_order=True)
    player_candidates = players_by_name.get(player_key, ())
    if len(player_candidates) == 1:
        player_id = player_candidates[0]
        player_method = "unique_normalized_name"
    else:
        player_id = None
        player_method = "ambiguous" if len(player_candidates) > 1 else "unresolved"
        if len(player_candidates) > 1:
            conflict_reasons.append("ambiguous_player")

    matchup = MATCHUP_PATTERN.fullmatch(str(matchup_text or "").strip())
    game_id = None
    game_method = "invalid_matchup"
    game_candidates: Tuple[CanonicalGameIdentity, ...] = ()
    if matchup is None:
        conflict_reasons.append("invalid_matchup")
    else:
        away = matchup.group("away")
        home = matchup.group("home")
        same_day = games_by_key.get((report_date, away, home), ())
        next_day = games_by_key.get((report_date + timedelta(days=1), away, home), ())
        if len(same_day) == 1:
            game_candidates = same_day
            game_method = "report_date"
        elif len(same_day) > 1:
            game_candidates = same_day
            game_method = "ambiguous_report_date"
            conflict_reasons.append("ambiguous_game")
        elif len(next_day) == 1:
            game_candidates = next_day
            game_method = "report_date_plus_one"
        elif len(next_day) > 1:
            game_candidates = next_day
            game_method = "ambiguous_report_date_plus_one"
            conflict_reasons.append("ambiguous_game")
        else:
            game_method = "canonical_missing"

    if len(game_candidates) == 1:
        game = game_candidates[0]
        if game.season != season:
            conflict_reasons.append("game_season")
        elif team_id is not None and team_id not in {
            game.away_team_id,
            game.home_team_id,
        }:
            conflict_reasons.append("reported_team_not_in_game")
        else:
            game_id = game.game_id

    resolved_count = sum(
        value is not None for value in (player_id, team_id, game_id)
    )
    if conflict_reasons:
        identity_status = "conflict"
        completeness_status = "quarantined"
    elif resolved_count == 3:
        identity_status = "resolved"
        # Identity is complete, but exact source timing is not.
        completeness_status = "partial"
    elif resolved_count:
        identity_status = "partial"
        completeness_status = "identity_unresolved"
    else:
        identity_status = "unresolved"
        completeness_status = "identity_unresolved"

    return StatsurgeIdentityResult(
        resolved_player_id=player_id,
        resolved_team_id=team_id,
        resolved_game_id=game_id,
        identity_status=identity_status,
        completeness_status=completeness_status,
        cutoff_status="unknown",
        details={
            "team_method": team_method,
            "team_candidate_count": len(team_candidates),
            "player_method": player_method,
            "player_candidate_count": len(player_candidates),
            "game_method": game_method,
            "game_candidate_count": len(game_candidates),
            "conflict_reasons": sorted(set(conflict_reasons)),
            "cutoff_reason": "source_checkpoint_methodology_only_and_game_date_only",
        },
    )


def _validate_manifest(connection: Connection, source_import_id: str) -> None:
    row = connection.execute(
        text(
            """
            SELECT source_name, dataset_name, license_status,
                   commercial_use_status, validation_status
            FROM external_dataset_imports
            WHERE import_id = :source_import_id
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().one_or_none()
    if row is None:
        raise ValueError(f"Unknown Stat Surge manifest: {source_import_id}")
    mismatches = [
        key for key, value in EXPECTED_IMPORT_IDENTITY.items() if row[key] != value
    ]
    if row["validation_status"] not in {"registered", "profiled"}:
        mismatches.append("validation_status")
    if mismatches:
        raise ValueError(
            "Manifest is not eligible for identity reconciliation: "
            + ", ".join(sorted(set(mismatches)))
        )


def build_statsurge_identity_plan(
    connection: Connection,
    *,
    source_import_id: str,
) -> StatsurgeIdentityPlan:
    """Build the complete deterministic identity plan from durable DB facts."""
    _validate_manifest(connection, source_import_id)
    teams = connection.execute(
        text("SELECT team_id, name, abbreviation FROM teams ORDER BY team_id")
    ).mappings().all()
    players = connection.execute(
        text("SELECT player_id, name FROM players ORDER BY player_id")
    ).mappings().all()
    games = connection.execute(
        text(
            """
            SELECT gs.game_id, min(gs.game_date)::date AS game_date,
                   min(gs.season) AS season,
                   max(gs.team_id) FILTER (WHERE gs.home_or_away = 'A') AS away_team_id,
                   max(t.abbreviation) FILTER (WHERE gs.home_or_away = 'A') AS away_abbreviation,
                   max(gs.team_id) FILTER (WHERE gs.home_or_away = 'H') AS home_team_id,
                   max(t.abbreviation) FILTER (WHERE gs.home_or_away = 'H') AS home_abbreviation
            FROM game_schedule gs
            JOIN teams t ON t.team_id = gs.team_id
            WHERE gs.game_date::date BETWEEN DATE '2021-10-19' AND DATE '2024-06-18'
            GROUP BY gs.game_id
            HAVING count(*) = 2
               AND count(*) FILTER (WHERE gs.home_or_away = 'A') = 1
               AND count(*) FILTER (WHERE gs.home_or_away = 'H') = 1
            ORDER BY gs.game_id
            """
        )
    ).mappings().all()
    source_rows = connection.execute(
        text(
            """
            SELECT staging_row_id, reported_player_name, reported_team_name,
                   matchup_text, report_date, season
            FROM stg_statsurge_availability
            WHERE source_import_id = :source_import_id
              AND parser_version = 'statsurge-availability-v1'
            ORDER BY source_row_number
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().all()
    if not source_rows:
        raise ValueError("Manifest has no staged Stat Surge rows")

    teams_by_name: Dict[str, list[int]] = defaultdict(list)
    for row in teams:
        teams_by_name[str(row["name"])].append(int(row["team_id"]))
    players_by_name: Dict[str, list[int]] = defaultdict(list)
    for row in players:
        players_by_name[normalize_player_name(str(row["name"]))].append(
            int(row["player_id"])
        )
    games_by_key: Dict[
        Tuple[date, str, str], list[CanonicalGameIdentity]
    ] = defaultdict(list)
    for row in games:
        game = CanonicalGameIdentity(
            game_id=str(row["game_id"]),
            game_date=row["game_date"],
            season=str(row["season"]),
            away_team_id=int(row["away_team_id"]),
            away_abbreviation=str(row["away_abbreviation"]),
            home_team_id=int(row["home_team_id"]),
            home_abbreviation=str(row["home_abbreviation"]),
        )
        games_by_key[
            (game.game_date, game.away_abbreviation, game.home_abbreviation)
        ].append(game)

    frozen_teams_by_name = {
        key: tuple(value) for key, value in teams_by_name.items()
    }
    frozen_players_by_name = {
        key: tuple(value) for key, value in players_by_name.items()
    }
    frozen_games_by_key = {
        key: tuple(value) for key, value in games_by_key.items()
    }

    results = []
    statuses = Counter()
    player_methods = Counter()
    game_methods = Counter()
    team_methods = Counter()
    seasons: Dict[str, Counter] = defaultdict(Counter)
    unresolved_players = Counter()
    for row in source_rows:
        result = resolve_statsurge_identity(
            reported_player_name=str(row["reported_player_name"]),
            reported_team_name=str(row["reported_team_name"]),
            matchup_text=str(row["matchup_text"]),
            report_date=row["report_date"],
            season=str(row["season"]),
            teams_by_name=frozen_teams_by_name,
            players_by_name=frozen_players_by_name,
            games_by_key=frozen_games_by_key,
        )
        results.append((str(row["staging_row_id"]), result))
        statuses[result.identity_status] += 1
        player_methods[str(result.details["player_method"])] += 1
        game_methods[str(result.details["game_method"])] += 1
        team_methods[str(result.details["team_method"])] += 1
        season_counts = seasons[str(row["season"])]
        season_counts["rows"] += 1
        season_counts[result.identity_status] += 1
        if result.resolved_player_id is not None:
            season_counts["player_resolved"] += 1
        if result.resolved_game_id is not None:
            season_counts["game_resolved"] += 1
        if result.resolved_player_id is None:
            unresolved_players[str(row["reported_player_name"])] += 1

    return StatsurgeIdentityPlan(
        source_rows=len(source_rows),
        results=tuple(results),
        status_counts=dict(statuses),
        player_method_counts=dict(player_methods),
        game_method_counts=dict(game_methods),
        team_method_counts=dict(team_methods),
        season_counts={key: dict(value) for key, value in sorted(seasons.items())},
        unresolved_player_counts=dict(
            sorted(unresolved_players.items(), key=lambda item: (-item[1], item[0]))
        ),
    )


def apply_statsurge_identity_plan(
    connection: Connection,
    *,
    source_import_id: str,
    source_run_id: str,
) -> Tuple[StatsurgeIdentityPlan, int]:
    """Persist changed reconciliation outcomes without rewriting source values."""
    plan = build_statsurge_identity_plan(
        connection, source_import_id=source_import_id
    )
    current_rows = connection.execute(
        text(
            """
            SELECT staging_row_id, resolved_player_id, resolved_team_id,
                   resolved_game_id, identity_status, completeness_status,
                   cutoff_status, identity_resolution_version,
                   identity_resolution_details
            FROM stg_statsurge_availability
            WHERE source_import_id = :source_import_id
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().all()
    current = {str(row["staging_row_id"]): row for row in current_rows}
    updates = []
    for staging_row_id, result in plan.results:
        row = current[staging_row_id]
        expected = {
            "resolved_player_id": result.resolved_player_id,
            "resolved_team_id": result.resolved_team_id,
            "resolved_game_id": result.resolved_game_id,
            "identity_status": result.identity_status,
            "completeness_status": result.completeness_status,
            "cutoff_status": result.cutoff_status,
            "identity_resolution_version": IDENTITY_RESOLUTION_VERSION,
            "identity_resolution_details": dict(result.details),
        }
        if all(row[key] == value for key, value in expected.items()):
            continue
        updates.append(
            {
                "staging_row_id": staging_row_id,
                "source_run_id": source_run_id,
                **{
                    **expected,
                    "identity_resolution_details": json.dumps(
                        expected["identity_resolution_details"],
                        sort_keys=True,
                    ),
                },
            }
        )
    if updates:
        result = connection.execute(
            text(
                """
                UPDATE stg_statsurge_availability
                SET resolved_player_id = :resolved_player_id,
                    resolved_team_id = :resolved_team_id,
                    resolved_game_id = :resolved_game_id,
                    identity_status = :identity_status,
                    completeness_status = :completeness_status,
                    cutoff_status = :cutoff_status,
                    identity_resolution_version = :identity_resolution_version,
                    identity_resolution_run_id = :source_run_id,
                    identity_resolution_details = CAST(:identity_resolution_details AS jsonb)
                WHERE staging_row_id = :staging_row_id
                """
            ),
            updates,
        )
        written = int(result.rowcount or 0)
    else:
        written = 0
    if written != len(updates):
        raise ValueError("Identity update count does not match the plan")
    return plan, written
