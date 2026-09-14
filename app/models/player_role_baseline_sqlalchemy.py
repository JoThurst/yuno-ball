"""Durable actual-role history and leakage-safe pregame role baselines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Session

from app.database import Base


ROLE_HISTORY_VERSION = "role-history-v1"
ROLE_BASELINE_VERSION = "role-baseline-v1"
JSON_DOCUMENT = JSONB()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def bulk_upsert_role_records(
    model,
    records: Iterable[Mapping],
    *,
    natural_key: Sequence[str],
    db: Session,
) -> int:
    """Upsert a derived role projection without changing its stable ID."""
    values = [dict(record) for record in records]
    if not values:
        return 0
    statement = insert(model).values(values)
    protected = {"id", "role_history_id", "baseline_id", "created_at", *natural_key}
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


class PlayerRoleHistoryORM(Base):
    """One derived actual-role observation at player/team/game grain."""

    __tablename__ = "player_role_history"
    __table_args__ = (
        CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_role_history_participation",
        ),
        CheckConstraint(
            "starter_status IN ('starter', 'bench', 'unknown')",
            name="ck_player_role_history_starter",
        ),
        CheckConstraint(
            "minutes_decimal IS NULL OR minutes_decimal >= 0",
            name="ck_player_role_history_minutes",
        ),
        UniqueConstraint(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "calculation_version",
            name="uq_player_role_history_grain",
        ),
        Index("idx_player_role_history_player_date", "canonical_player_id", "game_date"),
        Index("idx_player_role_history_team_date", "canonical_team_id", "game_date"),
        Index("idx_player_role_history_season", "season", "season_type"),
    )

    role_history_id = Column(String(36), primary_key=True)
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    participation_status = Column(String(16), nullable=False)
    starter_status = Column(String(16), nullable=False)
    starter_position = Column(String(8), nullable=True)
    minutes = Column(String(16), nullable=True)
    minutes_decimal = Column(Numeric(8, 2), nullable=True)
    source_name = Column(String(64), nullable=False)
    source_fact_id = Column(String(36), nullable=False)
    source_row_sha256 = Column(String(64), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    calculation_version = Column(String(64), nullable=False, default=ROLE_HISTORY_VERSION)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class PregamePlayerRoleBaselineORM(Base):
    """One leakage-safe role band for a player entering a scheduled game."""

    __tablename__ = "pregame_player_role_baselines"
    __table_args__ = (
        CheckConstraint(
            "completeness_status IN ('complete', 'partial', 'unknown', 'after_cutoff')",
            name="ck_pregame_role_baseline_completeness",
        ),
        CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low', 'none')",
            name="ck_pregame_role_baseline_confidence",
        ),
        CheckConstraint(
            "timing_policy IN ('strict_source', 'historical_game_date_proxy')",
            name="ck_pregame_role_baseline_timing_policy",
        ),
        CheckConstraint(
            "window_size > 0 AND history_games_seen >= 0 AND played_games_used >= 0",
            name="ck_pregame_role_baseline_counts",
        ),
        UniqueConstraint(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
            name="uq_pregame_role_baseline_natural_key",
        ),
        Index("idx_pregame_role_baseline_game", "canonical_game_id"),
        Index("idx_pregame_role_baseline_player", "canonical_player_id", "feature_as_of"),
        Index("idx_pregame_role_baseline_status", "season", "completeness_status"),
    )

    baseline_id = Column(String(36), primary_key=True)
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    target_game_date = Column(Date, nullable=False)
    scheduled_tipoff = Column(DateTime(timezone=True), nullable=True)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    window_size = Column(Integer, nullable=False)
    history_games_seen = Column(Integer, nullable=False)
    played_games_used = Column(Integer, nullable=False)
    start_count = Column(Integer, nullable=False)
    baseline_minutes_low = Column(Numeric(8, 2), nullable=True)
    baseline_minutes_median = Column(Numeric(8, 2), nullable=True)
    baseline_minutes_high = Column(Numeric(8, 2), nullable=True)
    latest_history_date = Column(Date, nullable=True)
    completeness_status = Column(String(16), nullable=False)
    confidence_band = Column(String(16), nullable=False)
    timing_policy = Column(String(32), nullable=False)
    feature_as_of = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=True)
    source_name = Column(String(64), nullable=False)
    calculation_version = Column(String(64), nullable=False, default=ROLE_BASELINE_VERSION)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    missing_input_flags = Column(
        JSON_DOCUMENT,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())
