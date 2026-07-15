"""Versioned, append-only player analytical snapshots.

These tables are the durable Phase 2 history.  The legacy player analytical
tables remain latest-state compatibility projections and are intentionally not
used as historical model features.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Session

from app.database import Base


PLAYER_SNAPSHOT_CALCULATION_VERSION = "player-v2.1"
PLAYER_SNAPSHOT_COMPLETENESS_COMPLETE = "complete"
JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def bulk_upsert_snapshots(
    model,
    records: Iterable[Mapping],
    *,
    natural_key: Sequence[str],
    db: Session,
) -> int:
    """Idempotently publish one logical snapshot key without changing created_at."""
    values = [dict(record) for record in records]
    if not values:
        return 0

    statement = insert(model).values(values)
    protected = {"id", "created_at", *natural_key}
    update_values = {
        column.name: getattr(statement.excluded, column.name)
        for column in model.__table__.columns
        if column.name not in protected
    }
    statement = statement.on_conflict_do_update(
        index_elements=list(natural_key),
        set_=update_values,
    )
    db.execute(statement)
    db.flush()
    return len(values)


class PlayerSnapshotProvenanceMixin:
    """Shared provenance required on every durable player snapshot row."""

    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    feature_as_of = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    calculation_version = Column(String(64), nullable=False)
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    completeness_status = Column(String(16), nullable=False)
    missing_input_flags = Column(
        JSON_DOCUMENT,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class PlayerConsecutiveStreakSnapshotORM(PlayerSnapshotProvenanceMixin, Base):
    __tablename__ = "player_consecutive_streak_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "stat", "threshold", "season", "season_type",
            "feature_as_of", "calculation_version", "streak_kind",
            name="uq_player_streak_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_streak_snapshot_completeness",
        ),
        CheckConstraint(
            "streak_kind IN ('current', 'season_max')",
            name="ck_player_streak_snapshot_kind",
        ),
        Index(
            "idx_player_streak_snapshot_latest",
            "season", "season_type", "calculation_version",
            "completeness_status", "feature_as_of",
        ),
        Index("idx_player_streak_snapshot_player", "player_id", "feature_as_of"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    player_name = Column(Text, nullable=False)
    stat = Column(String(16), nullable=False)
    threshold = Column(Integer, nullable=False)
    streak_games = Column(Integer, nullable=False)
    start_game_id = Column(String, nullable=False)
    end_game_id = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False)
    streak_kind = Column(String(16), nullable=False)


class PlayerStatWindowSnapshotORM(PlayerSnapshotProvenanceMixin, Base):
    __tablename__ = "player_stat_window_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "stat", "threshold", "season", "season_type",
            "window_size", "feature_as_of", "calculation_version",
            name="uq_player_window_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_window_snapshot_completeness",
        ),
        CheckConstraint("games_hit <= games_played", name="ck_player_window_hits_lte_games"),
        Index(
            "idx_player_window_snapshot_latest",
            "season", "season_type", "calculation_version",
            "completeness_status", "feature_as_of",
        ),
        Index("idx_player_window_snapshot_player", "player_id", "feature_as_of"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    player_name = Column(Text, nullable=False)
    stat = Column(String(16), nullable=False)
    threshold = Column(Integer, nullable=False)
    window_size = Column(Integer, nullable=False)
    games_played = Column(Integer, nullable=False)
    games_hit = Column(Integer, nullable=False)
    last_game_id = Column(String, nullable=False)
    last_game_date = Column(Date, nullable=False)


class PlayerHeatIndexSnapshotORM(PlayerSnapshotProvenanceMixin, Base):
    __tablename__ = "player_heat_index_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "stat", "season", "season_type", "window_size",
            "feature_as_of", "calculation_version",
            name="uq_player_heat_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_heat_snapshot_completeness",
        ),
        Index(
            "idx_player_heat_snapshot_latest",
            "season", "season_type", "calculation_version",
            "completeness_status", "feature_as_of",
        ),
        Index("idx_player_heat_snapshot_player", "player_id", "feature_as_of"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    player_name = Column(Text, nullable=False)
    stat = Column(String(16), nullable=False)
    window_size = Column(Integer, nullable=False)
    games_played = Column(Integer, nullable=False)
    recent_games_played = Column(Integer, nullable=False)
    season_avg = Column(Float, nullable=False)
    season_std = Column(Float, nullable=False)
    recent_avg = Column(Float, nullable=False)
    z_score = Column(Float, nullable=False)
    status = Column(String(16), nullable=False)


class PlayerConsistencySnapshotORM(PlayerSnapshotProvenanceMixin, Base):
    __tablename__ = "player_consistency_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "season_type", "stat_name", "window_size",
            "feature_as_of", "calculation_version",
            name="uq_player_consistency_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_consistency_snapshot_completeness",
        ),
        Index(
            "idx_player_consistency_snapshot_latest",
            "season", "season_type", "calculation_version",
            "completeness_status", "feature_as_of",
        ),
        Index("idx_player_consistency_snapshot_player", "player_id", "feature_as_of"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    player_name = Column(Text, nullable=False)
    stat_name = Column(String(16), nullable=False)
    window_size = Column(Integer, nullable=False)
    games_played = Column(Integer, nullable=False)
    mean = Column(Float, nullable=False)
    stddev = Column(Float, nullable=False)
    cv = Column(Float, nullable=False)
    min_val = Column(Float, nullable=False)
    max_val = Column(Float, nullable=False)
    median = Column(Float, nullable=False)
    consistency_tier = Column(String(16), nullable=False)
