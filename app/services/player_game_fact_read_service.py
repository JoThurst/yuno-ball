"""Canonical-first player-game reads with non-destructive legacy fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM


def _decimal_minutes(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if ":" not in text:
        return text
    parts = [int(part) for part in text.split(":")]
    seconds = (
        parts[0] * 60 + parts[1]
        if len(parts) == 2
        else parts[0] * 3600 + parts[1] * 60 + parts[2]
    )
    return str(seconds / 60)


@dataclass(frozen=True)
class PlayerGameFactReadRow:
    player_id: int
    game_id: str
    team_id: int
    points: Optional[int]
    assists: Optional[int]
    rebounds: Optional[int]
    steals: Optional[int]
    blocks: Optional[int]
    turnovers: Optional[int]
    minutes: Optional[str]
    season: str
    season_type: Optional[str]
    game_date: Optional[datetime]
    participation_status: str
    completeness_status: str
    source_name: str

    @property
    def minutes_played(self) -> Optional[str]:
        return _decimal_minutes(self.minutes)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "game_id": self.game_id,
            "team_id": self.team_id,
            "points": self.points,
            "assists": self.assists,
            "rebounds": self.rebounds,
            "steals": self.steals,
            "blocks": self.blocks,
            "turnovers": self.turnovers,
            "minutes_played": self.minutes_played,
            "season": self.season,
            "season_type": self.season_type,
            "game_date": self.game_date,
            "participation_status": self.participation_status,
            "completeness_status": self.completeness_status,
            "source_name": self.source_name,
        }


class PlayerGameFactReadService:
    """Read canonical rows first and preserve uncovered `gamelogs` history."""

    @staticmethod
    def _canonical_rows(query) -> list[PlayerGameFactReadRow]:
        rows = query.all()
        return [
            PlayerGameFactReadRow(
                player_id=int(fact.canonical_player_id),
                game_id=str(fact.canonical_game_id),
                team_id=int(fact.canonical_team_id),
                points=fact.points,
                assists=fact.assists,
                rebounds=fact.rebounds_total,
                steals=fact.steals,
                blocks=fact.blocks,
                turnovers=fact.turnovers,
                minutes=fact.minutes,
                season=fact.season,
                season_type=fact.season_type,
                game_date=game_date,
                participation_status=fact.participation_status,
                completeness_status=fact.completeness_status,
                source_name=fact.source_name,
            )
            for fact, game_date in rows
        ]

    @staticmethod
    def _legacy_rows(query) -> list[PlayerGameFactReadRow]:
        return [
                PlayerGameFactReadRow(
                    player_id=int(row.player_id),
                    game_id=str(row.game_id),
                    team_id=int(row.team_id),
                    points=row.points,
                    assists=row.assists,
                    rebounds=row.rebounds,
                    steals=row.steals,
                    blocks=row.blocks,
                    turnovers=row.turnovers,
                    minutes=str(row.minutes_played) if row.minutes_played is not None else None,
                    season=row.season,
                    season_type=season_type,
                    game_date=game_date,
                    participation_status="played",
                    completeness_status="legacy_compatible",
                    source_name="legacy_gamelogs",
                )
            for row, game_date, season_type in query.all()
        ]

    @staticmethod
    def _legacy_query(db: Session):
        return db.query(
            GameLogORM,
            GameScheduleORM.game_date,
            GameScheduleORM.season_type,
        ).join(
            GameScheduleORM,
            (GameLogORM.game_id == GameScheduleORM.game_id)
            & (GameLogORM.team_id == GameScheduleORM.team_id),
        )

    @classmethod
    def _merge(
        cls,
        canonical: Sequence[PlayerGameFactReadRow],
        legacy: Sequence[PlayerGameFactReadRow],
        *,
        played_only: bool,
    ) -> list[PlayerGameFactReadRow]:
        selected = {
            (row.game_id, row.player_id, row.team_id): row
            for row in canonical
            if not played_only or row.participation_status == "played"
        }
        for row in legacy:
            selected.setdefault((row.game_id, row.player_id, row.team_id), row)
        return sorted(
            selected.values(),
            key=lambda row: (row.game_date or datetime.min, row.game_id),
            reverse=True,
        )

    @classmethod
    def get_by_player_and_season(
        cls,
        player_id: int,
        season: str,
        *,
        db: Session,
        played_only: bool = True,
    ) -> list[PlayerGameFactReadRow]:
        canonical = cls._canonical_rows(
            db.query(PlayerGameFactORM, GameScheduleORM.game_date)
            .join(
                GameScheduleORM,
                (PlayerGameFactORM.canonical_game_id == GameScheduleORM.game_id)
                & (PlayerGameFactORM.canonical_team_id == GameScheduleORM.team_id),
            )
            .filter(
                PlayerGameFactORM.canonical_player_id == player_id,
                PlayerGameFactORM.season == season,
            )
        )
        legacy = cls._legacy_rows(
            cls._legacy_query(db).filter(
                GameLogORM.player_id == player_id,
                GameLogORM.season == season,
            )
        )
        return cls._merge(canonical, legacy, played_only=played_only)

    @classmethod
    def get_last_n_games(
        cls,
        player_id: int,
        n: int,
        *,
        db: Session,
    ) -> list[PlayerGameFactReadRow]:
        canonical = cls._canonical_rows(
            db.query(PlayerGameFactORM, GameScheduleORM.game_date)
            .join(
                GameScheduleORM,
                (PlayerGameFactORM.canonical_game_id == GameScheduleORM.game_id)
                & (PlayerGameFactORM.canonical_team_id == GameScheduleORM.team_id),
            )
            .filter(PlayerGameFactORM.canonical_player_id == player_id)
        )
        legacy = cls._legacy_rows(
            cls._legacy_query(db).filter(GameLogORM.player_id == player_id)
        )
        return cls._merge(canonical, legacy, played_only=True)[:n]

    @classmethod
    def get_by_season(
        cls,
        season: str,
        *,
        db: Session,
        played_only: bool = True,
    ) -> list[PlayerGameFactReadRow]:
        canonical = cls._canonical_rows(
            db.query(PlayerGameFactORM, GameScheduleORM.game_date)
            .join(
                GameScheduleORM,
                (PlayerGameFactORM.canonical_game_id == GameScheduleORM.game_id)
                & (PlayerGameFactORM.canonical_team_id == GameScheduleORM.team_id),
            )
            .filter(PlayerGameFactORM.season == season)
        )
        legacy = cls._legacy_rows(
            cls._legacy_query(db).filter(GameLogORM.season == season)
        )
        return cls._merge(canonical, legacy, played_only=played_only)

    @classmethod
    def get_before_cutoff(
        cls,
        season: str,
        cutoff: datetime,
        *,
        db: Session,
    ) -> list[PlayerGameFactReadRow]:
        return [
            row
            for row in cls.get_by_season(season, db=db, played_only=True)
            if row.game_date is not None and row.game_date < cutoff
        ]

    @staticmethod
    def known_seasons(*, db: Session) -> list[str]:
        canonical = [
            season
            for (season,) in db.query(PlayerGameFactORM.season)
            .filter(PlayerGameFactORM.season.isnot(None))
            .distinct()
            .all()
        ]
        legacy = [
            season
            for (season,) in db.query(GameLogORM.season)
            .filter(GameLogORM.season.isnot(None))
            .distinct()
            .all()
        ]
        return sorted(set(canonical) | set(legacy), reverse=True)
