"""Bounded repair planning for legacy TeamGameLog projections.

The 2024-25 ``team_game_stats`` rows predate the current TeamGameLog field
mapping. This service refreshes only the missing rebound/result fields after
validating the source rows against the durable game identity already present
in the database.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

from nba_api.stats.endpoints import teamgamelog
from sqlalchemy.orm import Session

from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.utils.fetch.team_fetcher import TeamFetcher
from app.utils.id_utils import normalize_nba_game_id
from app.utils.season_utils import normalize_season


REPAIR_FIELDS = ("oreb", "dreb", "wl", "w", "l", "w_pct")
SOURCE_FIELDS = ("OREB", "DREB", "WL", "W", "L", "W_PCT")


@dataclass(frozen=True)
class RepairSourceRow:
    game_id: str
    game_date: date
    pts: Optional[int]
    reb: Optional[int]
    oreb: Optional[int]
    dreb: Optional[int]
    wl: Optional[str]
    w: Optional[int]
    l: Optional[int]
    w_pct: Optional[float]


@dataclass(frozen=True)
class RepairPlan:
    season: str
    rows_read: int
    candidate_rows: int
    teams_fetched: int
    source_rows: int
    validated_rows: int
    rows_to_update: int
    field_updates: int
    identity_corrections: int
    errors: tuple[str, ...]
    updates: tuple[dict[str, Any], ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.validated_rows == self.candidate_rows

    def summary(self) -> dict[str, Any]:
        return {
            "season": self.season,
            "rows_read": self.rows_read,
            "candidate_rows": self.candidate_rows,
            "teams_fetched": self.teams_fetched,
            "source_rows": self.source_rows,
            "validated_rows": self.validated_rows,
            "rows_to_update": self.rows_to_update,
            "field_updates": self.field_updates,
            "identity_corrections": self.identity_corrections,
            "errors": list(self.errors),
            "valid": self.valid,
        }


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%b %d, %Y").date()


def parse_team_game_log(response: Mapping[str, Any]) -> dict[str, RepairSourceRow]:
    """Parse one TeamGameLog response using named headers only."""
    result_sets = response.get("resultSets") or []
    if not result_sets:
        raise ValueError("TeamGameLog response did not contain resultSets")
    dataset = result_sets[0]
    headers = dataset.get("headers") or []
    rows = dataset.get("rowSet") or []
    required = {"Game_ID", "GAME_DATE", "PTS", "REB", *SOURCE_FIELDS}
    missing = sorted(required.difference(headers))
    if missing:
        raise ValueError(f"TeamGameLog response missing headers: {missing}")

    parsed: dict[str, RepairSourceRow] = {}
    for raw_row in rows:
        row = dict(zip(headers, raw_row))
        game_id = normalize_nba_game_id(row["Game_ID"])
        if game_id in parsed:
            raise ValueError(f"duplicate TeamGameLog game_id={game_id}")
        parsed[game_id] = RepairSourceRow(
            game_id=game_id,
            game_date=_as_date(row["GAME_DATE"]),
            pts=_as_int(row["PTS"]),
            reb=_as_int(row["REB"]),
            oreb=_as_int(row["OREB"]),
            dreb=_as_int(row["DREB"]),
            wl=str(row["WL"]).strip() if row["WL"] is not None else None,
            w=_as_int(row["W"]),
            l=_as_int(row["L"]),
            w_pct=_as_float(row["W_PCT"]),
        )
    return parsed


def _source_payload(fetcher: TeamFetcher, *, team_id: int, season: str) -> dict[str, RepairSourceRow]:
    endpoint = fetcher.create_endpoint(
        teamgamelog.TeamGameLog,
        season=season,
        team_id=team_id,
        season_type_all_star="Regular Season",
        league_id_nullable="00",
        timeout=45,
    )
    return parse_team_game_log(endpoint.get_dict())


def build_repair_plan(
    db: Session,
    *,
    season: str,
    fetcher: Optional[TeamFetcher] = None,
) -> RepairPlan:
    """Fetch and validate all missing-field candidates without writing rows."""
    season = normalize_season(season)
    rows = (
        db.query(TeamGameStatsORM)
        .filter(TeamGameStatsORM.season == season)
        .order_by(TeamGameStatsORM.game_date, TeamGameStatsORM.game_id, TeamGameStatsORM.team_id)
        .all()
    )
    candidates = [row for row in rows if any(getattr(row, field) is None for field in REPAIR_FIELDS)]
    schedule_rows = (
        db.query(GameScheduleORM)
        .filter(GameScheduleORM.season == season)
        .filter(GameScheduleORM.game_id.in_({str(row.game_id) for row in rows}))
        .all()
    )
    schedule_by_key = {(str(row.game_id), row.team_id): row for row in schedule_rows}
    team_ids = sorted({row.team_id for row in candidates})
    source_by_team: dict[int, dict[str, RepairSourceRow]] = {}
    errors: list[str] = []
    fetcher = fetcher or TeamFetcher()
    for team_id in team_ids:
        try:
            source_by_team[team_id] = _source_payload(fetcher, team_id=team_id, season=season)
        except Exception as exc:  # keep the plan fail-closed and reviewable
            errors.append(f"team {team_id}: source fetch failed: {type(exc).__name__}: {exc}")

    rows_by_game: dict[str, list[TeamGameStatsORM]] = defaultdict(list)
    for row in rows:
        rows_by_game[str(row.game_id)].append(row)

    updates: list[dict[str, Any]] = []
    validated = 0
    for row in candidates:
        game_id = str(row.game_id)
        source = source_by_team.get(row.team_id, {}).get(game_id)
        if source is None:
            errors.append(f"{game_id}/{row.team_id}: source row missing")
            continue
        if source.game_date != row.game_date:
            errors.append(
                f"{game_id}/{row.team_id}: date mismatch db={row.game_date} source={source.game_date}"
            )
            continue
        if source.pts != row.pts or source.reb != row.reb:
            errors.append(
                f"{game_id}/{row.team_id}: points/rebounds mismatch "
                f"db=({row.pts},{row.reb}) source=({source.pts},{source.reb})"
            )
            continue
        schedule_row = schedule_by_key.get((game_id, row.team_id))
        if schedule_row is None or schedule_row.opponent_team_id == row.team_id:
            errors.append(f"{game_id}/{row.team_id}: schedule identity is not valid")
            continue
        expected_opponent_id = schedule_row.opponent_team_id
        if source.wl not in {"W", "L"} or source.oreb is None or source.dreb is None or source.w is None or source.l is None or source.w_pct is None:
            errors.append(f"{game_id}/{row.team_id}: source repair fields incomplete")
            continue

        pair = rows_by_game[game_id]
        if len(pair) != 2 or {item.team_id for item in pair} != {row.team_id, expected_opponent_id}:
            errors.append(f"{game_id}/{row.team_id}: durable team pair is not exactly reciprocal")
            continue
        expected_by_team = {item.team_id: schedule_by_key.get((game_id, item.team_id)) for item in pair}
        if any(
            item_schedule is None
            or item_schedule.opponent_team_id != (expected_opponent_id if team_id == row.team_id else row.team_id)
            for team_id, item_schedule in expected_by_team.items()
        ):
            errors.append(f"{game_id}/{row.team_id}: schedule opponent identity is not reciprocal")
            continue

        updates.append(
            {
                "game_id": game_id,
                "team_id": row.team_id,
                "opponent_team_id": expected_opponent_id,
                "identity_correction": row.opponent_team_id != expected_opponent_id,
                "oreb": source.oreb,
                "dreb": source.dreb,
                "wl": source.wl,
                "w": source.w,
                "l": source.l,
                "w_pct": source.w_pct,
            }
        )
        validated += 1

    # Validate each game has one source-side winner and one source-side loser.
    for game_id, pair in rows_by_game.items():
        if not any(item in candidates for item in pair):
            continue
        results = {
            update["wl"]
            for update in updates
            if update["game_id"] == game_id
        }
        if results != {"W", "L"}:
            errors.append(f"{game_id}: repaired pair does not resolve to one W and one L")

    return RepairPlan(
        season=season,
        rows_read=len(rows),
        candidate_rows=len(candidates),
        teams_fetched=len(source_by_team),
        source_rows=sum(len(rows) for rows in source_by_team.values()),
        validated_rows=validated,
        rows_to_update=len(updates),
        field_updates=sum(sum(getattr(row, field) is None for field in REPAIR_FIELDS) for row in candidates),
        identity_corrections=sum(update["identity_correction"] for update in updates),
        errors=tuple(errors),
        updates=tuple(updates),
    )


def apply_repair_plan(db: Session, plan: RepairPlan) -> int:
    """Apply a validated plan in the caller's transaction."""
    if not plan.valid:
        raise ValueError(f"refusing invalid repair plan: {plan.summary()}")
    written = 0
    for update in plan.updates:
        row = db.get(TeamGameStatsORM, (update["game_id"], update["team_id"]))
        if row is None:
            raise ValueError(f"repair target disappeared: {update['game_id']}/{update['team_id']}")
        row.opponent_team_id = update["opponent_team_id"]
        for field in REPAIR_FIELDS:
            if getattr(row, field) is None:
                setattr(row, field, update[field])
        written += 1
    db.flush()
    return written
