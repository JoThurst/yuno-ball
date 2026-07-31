"""Exact, versioned identity reconciliation for official injury observations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.statsurge_identity_reconciliation_service import normalize_player_name


IDENTITY_RESOLUTION_VERSION = "official-injury-identity-v1"
EASTERN = ZoneInfo("America/New_York")
MATCHUP_PATTERN = re.compile(r"^(?P<away>[A-Z]{3})@(?P<home>[A-Z]{3})$")
TEAM_ALIASES = {"laclippers": "losangelesclippers"}
PLAYER_NAME_ALIASES = {
    "nicalexanderwalker": "nickeilalexanderwalker",
    "nickalexanderwalker": "nickeilalexanderwalker",
    "thanasiantetokounmpo": "thanasisantetokounmpo",
    "brandonboston": "brandonbostonjr",
    "jimmybutleriii": "jimmybutler",
    "kentavicaldwellpope": "kentaviouscaldwellpope",
    "bubcarrington": "carltoncarrington",
    "nikoladjurisic": "nikoladjurisic",
    "shgilgeousalexander": "shaigilgeousalexander",
    "nigelhayesdavis": "nigelhayes",
    "treyjemisoniii": "treyjemison",
    "davidjonesgarcia": "davidjones",
    "jakobpoeltl": "jakobpoeltl",
    "oliviermaxenprosper": "oliviermaxenceprosper",
    "jeremiarobinsonearl": "jeremiahrobinsonearl",
    "alexsarr": "alexandresarr",
    "yanickoniederhauser": "yanickonanniederhauser",
    "hansenyang": "yanghansen",
    "adamabal": "adambal",
}
POSTPONED_GAME_MAPPINGS = {
    (date(2024, 12, 17), "MIL@OKC"): "0062400001",
    (date(2025, 1, 9), "CHA@LAL"): "0022400524",
    (date(2025, 1, 11), "CHA@LAC"): "0022400538",
    (date(2025, 1, 11), "HOU@ATL"): "0022400532",
    (date(2025, 1, 11), "SAS@LAL"): "0022400552",
    (date(2025, 1, 22), "MIL@NOP"): "0022401161",
    (date(2026, 1, 8), "MIA@CHI"): "0022500529",
    (date(2026, 1, 25), "DAL@MIL"): "0022500652",
    (date(2026, 1, 25), "DEN@MEM"): "0022500651",
}


@dataclass(frozen=True)
class CanonicalGame:
    game_id: str
    game_date: date
    season: str
    away_team_id: int
    away_abbreviation: str
    home_team_id: int
    home_abbreviation: str


@dataclass(frozen=True)
class IdentityUpdate:
    table: str
    row_id: str
    team_id: int | None
    game_id: str | None
    player_id: int | None
    details: Mapping[str, Any]


@dataclass(frozen=True)
class IdentityPlan:
    observations_seen: int
    submissions_seen: int
    updates: tuple[IdentityUpdate, ...]
    status_counts: Mapping[str, int]
    game_method_counts: Mapping[str, int]
    player_method_counts: Mapping[str, int]


def _normalize_team(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _local_schedule_date(value: datetime, precision: str) -> date:
    if precision == "date_only":
        return value.date()
    aware = value.replace(tzinfo=timezone.utc)
    return aware.astimezone(EASTERN).date()


def _team_index(rows: Iterable[Mapping[str, object]]) -> dict[str, tuple[int, ...]]:
    values: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        team_id = int(row["team_id"])
        for field in ("name", "abbreviation"):
            key = _normalize_team(row[field])
            if key:
                values[key].add(team_id)
    for alias, canonical in TEAM_ALIASES.items():
        if canonical in values:
            values[alias] = set(values[canonical])
    return {key: tuple(sorted(team_ids)) for key, team_ids in values.items()}


def _player_index(rows: Iterable[Mapping[str, object]]) -> dict[str, tuple[int, ...]]:
    values: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        values[normalize_player_name(str(row["name"]))].add(int(row["player_id"]))
    result = {key: tuple(sorted(player_ids)) for key, player_ids in values.items()}
    for source_name, canonical_name in PLAYER_NAME_ALIASES.items():
        if canonical_name in result:
            result[source_name] = result[canonical_name]
    return result


def _game_index(rows: Iterable[Mapping[str, object]]) -> dict[tuple[date, str, str], tuple[CanonicalGame, ...]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["game_id"])].append(row)
    by_key: dict[tuple[date, str, str], list[CanonicalGame]] = defaultdict(list)
    for game_id, game_rows in grouped.items():
        if len(game_rows) != 2:
            continue
        away = [row for row in game_rows if row["home_or_away"] == "A"]
        home = [row for row in game_rows if row["home_or_away"] == "H"]
        if len(away) != 1 or len(home) != 1:
            continue
        away_row, home_row = away[0], home[0]
        game = CanonicalGame(
            game_id=game_id,
            game_date=_local_schedule_date(
                away_row["game_date"], str(away_row["game_date_precision"])
            ),
            season=str(away_row["season"]),
            away_team_id=int(away_row["team_id"]),
            away_abbreviation=str(away_row["away_abbreviation"]).upper(),
            home_team_id=int(home_row["team_id"]),
            home_abbreviation=str(home_row["home_abbreviation"]).upper(),
        )
        matchup_key = (game.away_abbreviation, game.home_abbreviation)
        by_key[(game.game_date, *matchup_key)].append(game)
        raw_game_date = away_row["game_date"].date()
        if raw_game_date != game.game_date:
            by_key[(raw_game_date, *matchup_key)].append(game)
        # Legacy schedule rows stored midnight as the local calendar date,
        # while ScheduleLeagueV2 supplies midnight UTC. Retain an explicit
        # adjacent-date lookup for that representation drift; game ID/team
        # identity still remains exact and prevents guessing.
        if str(away_row["game_date_precision"]) == "exact" and getattr(
            away_row["game_date"], "time", lambda: None
        )().hour == 0:
            by_key[(game.game_date + timedelta(days=1), *matchup_key)].append(game)
    return {key: tuple(value) for key, value in by_key.items()}


def _resolve_row(
    row: Mapping[str, object],
    *,
    teams: Mapping[str, tuple[int, ...]],
    players: Mapping[str, tuple[int, ...]],
    games: Mapping[tuple[date, str, str], tuple[CanonicalGame, ...]],
    resolve_player: bool,
) -> IdentityUpdate:
    details: dict[str, Any] = {
        "identity_resolution_version": IDENTITY_RESOLUTION_VERSION,
        "conflict_reasons": [],
    }
    team_candidates = teams.get(_normalize_team(row["reported_team_name"]), ())
    team_id = team_candidates[0] if len(team_candidates) == 1 else row.get("team_id")
    details["team_method"] = "exact_normalized_name" if len(team_candidates) == 1 else "existing_or_unresolved"
    details["team_candidate_count"] = len(team_candidates)

    matchup = MATCHUP_PATTERN.fullmatch(str(row["matchup_text"] or "").strip().upper())
    game_candidates: tuple[CanonicalGame, ...] = ()
    if matchup is not None:
        postponed_game_id = POSTPONED_GAME_MAPPINGS.get(
            (row["game_date"], f"{matchup.group('away')}@{matchup.group('home')}")
        )
        if postponed_game_id:
            mapped_games = {
                game.game_id: game
                for candidates in games.values()
                for game in candidates
                if game.game_id == postponed_game_id
            }
            game_candidates = tuple(mapped_games.values())
        key = (
            row["game_date"],
            matchup.group("away"),
            matchup.group("home"),
        )
        if not game_candidates:
            game_candidates = games.get(key, ())
    game_id = game_candidates[0].game_id if len(game_candidates) == 1 else row.get("game_id")
    if len(game_candidates) == 1 and team_id is not None:
        game = game_candidates[0]
        if int(team_id) not in {game.away_team_id, game.home_team_id}:
            details["conflict_reasons"].append("reported_team_not_in_game")
            game_id = row.get("game_id")
    details["game_method"] = (
        "postponed_makeup_game"
        if (matchup is not None and (row["game_date"], str(row["matchup_text"]).strip().upper()) in POSTPONED_GAME_MAPPINGS and len(game_candidates) == 1)
        else "report_date_matchup"
        if len(game_candidates) == 1
        else "ambiguous_matchup"
        if len(game_candidates) > 1
        else "canonical_missing_or_invalid_matchup"
    )
    details["game_candidate_count"] = len(game_candidates)
    if details["game_method"] == "postponed_makeup_game":
        details["original_report_date"] = row["game_date"].isoformat()
        details["makeup_game_id"] = game_candidates[0].game_id

    player_id = row.get("player_id")
    if resolve_player:
        player_candidates = players.get(
            normalize_player_name(str(row["reported_player_name"]), source_order=True),
            (),
        )
        if len(player_candidates) == 1:
            player_id = player_candidates[0]
            details["player_method"] = "unique_normalized_name"
        else:
            details["player_method"] = "ambiguous_or_unresolved"
        details["player_candidate_count"] = len(player_candidates)
    else:
        details["player_method"] = "deferred"
        details["player_candidate_count"] = None

    if details["conflict_reasons"]:
        details["identity_status"] = "conflict"
    elif game_id is not None and team_id is not None and (not resolve_player or player_id is not None):
        details["identity_status"] = "resolved"
    else:
        details["identity_status"] = "partial"

    is_observation = row["table_name"] == "availability_observations"
    return IdentityUpdate(
        table=str(row["table_name"]),
        row_id=str(row["observation_id"] if is_observation else row["submission_id"]),
        team_id=int(team_id) if team_id is not None else None,
        game_id=str(game_id) if game_id is not None else None,
        player_id=int(player_id) if player_id is not None else None,
        details=details,
    )


def load_identity_inputs(
    connection: Connection,
    *,
    season: str,
    start_date: date,
    end_date: date,
    resolve_player: bool,
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]], dict[str, tuple[int, ...]], dict[str, tuple[int, ...]], dict[tuple[date, str, str], tuple[CanonicalGame, ...]]]:
    team_rows = connection.execute(text("SELECT team_id, name, abbreviation FROM teams")).mappings().all()
    player_rows = connection.execute(text("SELECT player_id, name FROM players")).mappings().all()
    schedule_rows = connection.execute(
        text(
            """
            SELECT gs.game_id, gs.season, gs.game_date, gs.game_date_precision,
                   gs.home_or_away, gs.team_id, gs.opponent_team_id,
                   away.abbreviation AS away_abbreviation,
                   home.abbreviation AS home_abbreviation
            FROM game_schedule gs
            JOIN teams home ON home.team_id = CASE WHEN gs.home_or_away = 'H' THEN gs.team_id ELSE gs.opponent_team_id END
            JOIN teams away ON away.team_id = CASE WHEN gs.home_or_away = 'A' THEN gs.team_id ELSE gs.opponent_team_id END
            WHERE gs.season = :season
              AND gs.season_type IN ('Regular Season', 'Play-In', 'Playoffs', 'NBA Cup')
            ORDER BY gs.game_id, gs.team_id
            """
        ),
        {"season": season},
    ).mappings().all()
    observations = connection.execute(
        text(
            """
            SELECT 'availability_observations' AS table_name, o.observation_id,
                   NULL AS submission_id, o.game_id, o.team_id, o.player_id,
                   o.game_date, o.matchup_text, o.reported_team_name,
                   o.reported_player_name, o.identity_resolution_version,
                   o.identity_resolution_details
            FROM availability_observations o
            WHERE o.game_date BETWEEN :start_date AND :end_date
              AND (o.game_id IS NULL OR o.team_id IS NULL OR (:resolve_player AND o.player_id IS NULL))
            ORDER BY o.game_date, o.observation_id
            """
        ),
        {"start_date": start_date, "end_date": end_date, "resolve_player": resolve_player},
    ).mappings().all()
    submissions = connection.execute(
        text(
            """
            SELECT 'team_report_submission_status' AS table_name, NULL AS observation_id,
                   s.submission_id, s.game_id, s.team_id, NULL AS player_id,
                   s.game_date, s.matchup_text, s.reported_team_name,
                   NULL AS reported_player_name, s.identity_resolution_version,
                   s.identity_resolution_details
            FROM team_report_submission_status s
            WHERE s.game_date BETWEEN :start_date AND :end_date
              AND (s.game_id IS NULL OR s.team_id IS NULL)
            ORDER BY s.game_date, s.submission_id
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).mappings().all()
    return (
        list(observations),
        list(submissions),
        _team_index(team_rows),
        _player_index(player_rows),
        _game_index(schedule_rows),
    )


def build_identity_plan(
    observations: Sequence[Mapping[str, object]],
    submissions: Sequence[Mapping[str, object]],
    *,
    teams: Mapping[str, tuple[int, ...]],
    players: Mapping[str, tuple[int, ...]],
    games: Mapping[tuple[date, str, str], tuple[CanonicalGame, ...]],
    resolve_player: bool,
) -> IdentityPlan:
    rows = list(observations) + list(submissions)
    updates = tuple(
        _resolve_row(
            row,
            teams=teams,
            players=players,
            games=games,
            resolve_player=resolve_player,
        )
        for row in rows
    )
    status_counts: dict[str, int] = defaultdict(int)
    game_methods: dict[str, int] = defaultdict(int)
    player_methods: dict[str, int] = defaultdict(int)
    for update in updates:
        status_counts[str(update.details["identity_status"])] += 1
        game_methods[str(update.details["game_method"])] += 1
        player_methods[str(update.details["player_method"])] += 1
    return IdentityPlan(
        observations_seen=len(observations),
        submissions_seen=len(submissions),
        updates=updates,
        status_counts=dict(status_counts),
        game_method_counts=dict(game_methods),
        player_method_counts=dict(player_methods),
    )


def apply_identity_plan(
    connection: Connection,
    plan: IdentityPlan,
    *,
    run_id: str,
) -> int:
    updates = [
        {
            "row_id": update.row_id,
            "team_id": update.team_id,
            "game_id": update.game_id,
            "player_id": update.player_id,
            "version": IDENTITY_RESOLUTION_VERSION,
            "run_id": run_id,
            "details": dict(update.details),
        }
        for update in plan.updates
    ]
    written = 0
    for table in ("availability_observations", "team_report_submission_status"):
        table_updates = [row for row, update in zip(updates, plan.updates) if update.table == table]
        if not table_updates:
            continue
        id_column = "observation_id" if table == "availability_observations" else "submission_id"
        player_clause = ", player_id = :player_id" if table == "availability_observations" else ""
        result = connection.execute(
            text(
                f"""
                UPDATE {table}
                SET team_id = :team_id,
                    game_id = :game_id
                    {player_clause},
                    identity_resolution_version = :version,
                    identity_resolution_run_id = :run_id,
                    identity_resolution_details = CAST(:details AS jsonb)
                WHERE {id_column} = :row_id
                """
            ),
            [
                {
                    **row,
                    "details": __import__("json").dumps(row["details"], sort_keys=True),
                }
                for row in table_updates
            ],
        )
        written += int(result.rowcount or 0)
    if written != len(updates):
        raise ValueError(f"Identity update count {written} did not match plan {len(updates)}")
    return written
