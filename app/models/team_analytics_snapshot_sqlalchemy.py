"""Versioned, leakage-safe team and game analytical snapshots.

The legacy team daily tables remain current-state compatibility projections.
These Phase 3 tables are authoritative for historical pregame analysis.
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
    ForeignKeyConstraint,
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


TEAM_SNAPSHOT_CALCULATION_VERSION = "team-v2.1"
TEAM_SNAPSHOT_COMPLETENESS_COMPLETE = "complete"
TEAM_SNAPSHOT_COMPLETENESS_PARTIAL = "partial"
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
    """Idempotently publish one snapshot key without changing created_at."""
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


class TeamSnapshotProvenanceMixin:
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    feature_as_of = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=True)
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


class TeamGameFeatureSnapshotORM(TeamSnapshotProvenanceMixin, Base):
    """One pregame team-perspective feature record for a scheduled game."""

    __tablename__ = "team_game_feature_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_team_feature_snapshot_schedule",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "game_id",
            "team_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
            name="uq_team_feature_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_team_feature_snapshot_completeness",
        ),
        CheckConstraint(
            "window_games_played <= season_games_played",
            name="ck_team_feature_snapshot_window_lte_season",
        ),
        CheckConstraint(
            "season_games_used <= season_games_played AND "
            "window_games_used <= window_games_played",
            name="ck_team_feature_snapshot_used_lte_played",
        ),
        Index(
            "idx_team_feature_snapshot_latest",
            "season",
            "season_type",
            "calculation_version",
            "completeness_status",
            "feature_as_of",
        ),
        Index(
            "idx_team_feature_snapshot_team",
            "team_id",
            "feature_as_of",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(String(20), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    opponent_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    scheduled_tipoff = Column(DateTime(timezone=True), nullable=False)
    is_home = Column(Boolean, nullable=False)
    window_size = Column(Integer, nullable=False)

    source_latest_game_id = Column(String(20), nullable=True)
    source_latest_game_date = Column(Date, nullable=True)
    season_games_played = Column(Integer, nullable=False)
    season_games_used = Column(Integer, nullable=False)
    window_games_played = Column(Integer, nullable=False)
    window_games_used = Column(Integer, nullable=False)

    off_rtg_season = Column(Float, nullable=True)
    def_rtg_season = Column(Float, nullable=True)
    net_rtg_season = Column(Float, nullable=True)
    pace_season = Column(Float, nullable=True)
    efg_season = Column(Float, nullable=True)
    tov_pct_season = Column(Float, nullable=True)
    orb_pct_season = Column(Float, nullable=True)
    ftr_season = Column(Float, nullable=True)
    pct_pts_3pt_season = Column(Float, nullable=True)

    off_rtg_lastn = Column(Float, nullable=True)
    def_rtg_lastn = Column(Float, nullable=True)
    net_rtg_lastn = Column(Float, nullable=True)
    pace_lastn = Column(Float, nullable=True)
    efg_lastn = Column(Float, nullable=True)
    tov_pct_lastn = Column(Float, nullable=True)
    orb_pct_lastn = Column(Float, nullable=True)
    ftr_lastn = Column(Float, nullable=True)
    pct_pts_3pt_lastn = Column(Float, nullable=True)

    off_rtg_delta = Column(Float, nullable=True)
    def_rtg_delta = Column(Float, nullable=True)
    net_rtg_delta = Column(Float, nullable=True)
    pace_delta = Column(Float, nullable=True)
    efg_delta = Column(Float, nullable=True)
    tov_pct_delta = Column(Float, nullable=True)
    orb_pct_delta = Column(Float, nullable=True)
    ftr_delta = Column(Float, nullable=True)
    pct_pts_3pt_delta = Column(Float, nullable=True)

    sos_net_season = Column(Float, nullable=True)
    sos_net_lastn = Column(Float, nullable=True)
    sos_net_delta = Column(Float, nullable=True)

    days_rest = Column(Integer, nullable=True)
    is_b2b = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_3_in_4 = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_4_in_5 = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_5_in_7 = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    games_last_4_days = Column(Integer, nullable=False, default=0, server_default=text("0"))
    games_last_7_days = Column(Integer, nullable=False, default=0, server_default=text("0"))

    flags = Column(
        JSON_DOCUMENT,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )


class GameEnvironmentSnapshotORM(TeamSnapshotProvenanceMixin, Base):
    """One game-level environment derived from the paired team snapshots."""

    __tablename__ = "game_environment_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "home_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_game_environment_snapshot_home_schedule",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["game_id", "away_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_game_environment_snapshot_away_schedule",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "game_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
            name="uq_game_environment_snapshot_natural_key",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_game_environment_snapshot_completeness",
        ),
        Index(
            "idx_game_environment_snapshot_latest",
            "season",
            "season_type",
            "calculation_version",
            "completeness_status",
            "feature_as_of",
        ),
        Index("idx_game_environment_snapshot_date", "game_date", "feature_as_of"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(String(20), nullable=False)
    game_date = Column(Date, nullable=False)
    scheduled_tipoff = Column(DateTime(timezone=True), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    window_size = Column(Integer, nullable=False)

    home_off_rtg_lastn = Column(Float, nullable=True)
    home_def_rtg_lastn = Column(Float, nullable=True)
    home_pace_lastn = Column(Float, nullable=True)
    away_off_rtg_lastn = Column(Float, nullable=True)
    away_def_rtg_lastn = Column(Float, nullable=True)
    away_pace_lastn = Column(Float, nullable=True)
    pace_projection = Column(Float, nullable=True)
    scoring_env_index = Column(Float, nullable=True)
    three_env_index = Column(Float, nullable=True)
    chaos_index = Column(Float, nullable=True)
    pace_up_for_home = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    pace_up_for_away = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    tags = Column(
        JSON_DOCUMENT,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
