"""Versioned traditional player-game facts and canonical selected facts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.ingestion_run_sqlalchemy import utc_now
# Register the referenced table whenever canonical facts are imported.
from app.models.player_game_starter_evidence_sqlalchemy import PlayerGameStarterEvidenceORM  # noqa: F401


TRADITIONAL_FACT_COLUMNS = (
    "minutes",
    "field_goals_made",
    "field_goals_attempted",
    "field_goals_percentage",
    "three_pointers_made",
    "three_pointers_attempted",
    "three_pointers_percentage",
    "free_throws_made",
    "free_throws_attempted",
    "free_throws_percentage",
    "rebounds_offensive",
    "rebounds_defensive",
    "rebounds_total",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fouls_personal",
    "points",
    "plus_minus_points",
)

ADVANCED_FACT_COLUMNS = (
    "minutes",
    "estimated_offensive_rating",
    "offensive_rating",
    "estimated_defensive_rating",
    "defensive_rating",
    "estimated_net_rating",
    "net_rating",
    "assist_percentage",
    "assist_to_turnover",
    "assist_ratio",
    "offensive_rebound_percentage",
    "defensive_rebound_percentage",
    "rebound_percentage",
    "turnover_ratio",
    "effective_field_goal_percentage",
    "true_shooting_percentage",
    "usage_percentage",
    "estimated_usage_percentage",
    "estimated_pace",
    "pace",
    "pace_per_40",
    "possessions",
    "pie",
)


class PlayerGameFactRevisionORM(Base):
    """One immutable source row for one traditional player-game fact."""

    __tablename__ = "player_game_fact_revisions"
    __table_args__ = (
        CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_fact_revision_sha256",
        ),
        CheckConstraint(
            "source_response_sha256 IS NULL OR source_response_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_fact_revision_response_sha256",
        ),
        CheckConstraint(
            "data_available_at_basis IN ('provider_published', 'retrieved_proxy', 'legacy_unspecified')",
            name="ck_player_game_fact_revision_availability_basis",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_game_fact_revision_completeness",
        ),
        CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_game_fact_revision_participation",
        ),
        CheckConstraint(
            "starter_status IN ('starter', 'bench', 'unknown')",
            name="ck_player_game_fact_revision_starter",
        ),
        UniqueConstraint(
            "source_name",
            "source_row_key",
            "parser_version",
            "source_row_sha256",
            name="uq_player_game_fact_revision_content",
        ),
        Index("idx_player_game_fact_revision_game", "canonical_game_id"),
        Index("idx_player_game_fact_revision_player", "canonical_player_id"),
        Index("idx_player_game_fact_revision_run", "source_run_id"),
        Index("idx_player_game_fact_revision_date", "game_date"),
    )

    revision_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_row_key = Column(String(255), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_game_id = Column(String(32), nullable=False)
    source_player_id = Column(BigInteger, nullable=False)
    source_team_id = Column(Integer, nullable=False)
    canonical_game_id = Column(String(32), nullable=True)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=True)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    source_row_sha256 = Column(String(64), nullable=False)
    source_response_sha256 = Column(String(64), nullable=True)
    data_available_at_basis = Column(
        String(32),
        nullable=False,
        default="legacy_unspecified",
        server_default="legacy_unspecified",
    )
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    completeness_status = Column(String(16), nullable=False)
    participation_status = Column(String(16), nullable=False)
    starter_status = Column(String(16), nullable=False, default="unknown", server_default="unknown")

    minutes = Column(String(16), nullable=True)
    field_goals_made = Column(Integer, nullable=True)
    field_goals_attempted = Column(Integer, nullable=True)
    field_goals_percentage = Column(Numeric(8, 6), nullable=True)
    three_pointers_made = Column(Integer, nullable=True)
    three_pointers_attempted = Column(Integer, nullable=True)
    three_pointers_percentage = Column(Numeric(8, 6), nullable=True)
    free_throws_made = Column(Integer, nullable=True)
    free_throws_attempted = Column(Integer, nullable=True)
    free_throws_percentage = Column(Numeric(8, 6), nullable=True)
    rebounds_offensive = Column(Integer, nullable=True)
    rebounds_defensive = Column(Integer, nullable=True)
    rebounds_total = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    steals = Column(Integer, nullable=True)
    blocks = Column(Integer, nullable=True)
    turnovers = Column(Integer, nullable=True)
    fouls_personal = Column(Integer, nullable=True)
    points = Column(Integer, nullable=True)
    plus_minus_points = Column(Integer, nullable=True)

    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class PlayerGameFactORM(Base):
    """Canonical selected traditional fact for one player-team-game grain."""

    __tablename__ = "player_game_facts"
    __table_args__ = (
        CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_game_fact_participation",
        ),
        CheckConstraint(
            "starter_status IN ('starter', 'bench', 'unknown')",
            name="ck_player_game_fact_starter",
        ),
        ForeignKeyConstraint(
            ["canonical_game_id", "canonical_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_player_game_fact_schedule",
        ),
        UniqueConstraint(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            name="uq_player_game_fact_canonical_grain",
        ),
        Index("idx_player_game_fact_player_date", "canonical_player_id", "game_date"),
        Index("idx_player_game_fact_game", "canonical_game_id"),
        Index("idx_player_game_fact_starter_evidence", "starter_evidence_id"),
    )

    fact_id = Column(String(36), primary_key=True)
    revision_id = Column(
        String(36),
        ForeignKey("player_game_fact_revisions.revision_id"),
        nullable=False,
    )
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    completeness_status = Column(String(16), nullable=False)
    participation_status = Column(String(16), nullable=False)
    starter_status = Column(String(16), nullable=False)
    starter_position = Column(String(8), nullable=True)
    starter_evidence_id = Column(
        String(36),
        ForeignKey("player_game_starter_evidence.evidence_id"),
        nullable=True,
    )

    minutes = Column(String(16), nullable=True)
    field_goals_made = Column(Integer, nullable=True)
    field_goals_attempted = Column(Integer, nullable=True)
    field_goals_percentage = Column(Numeric(8, 6), nullable=True)
    three_pointers_made = Column(Integer, nullable=True)
    three_pointers_attempted = Column(Integer, nullable=True)
    three_pointers_percentage = Column(Numeric(8, 6), nullable=True)
    free_throws_made = Column(Integer, nullable=True)
    free_throws_attempted = Column(Integer, nullable=True)
    free_throws_percentage = Column(Numeric(8, 6), nullable=True)
    rebounds_offensive = Column(Integer, nullable=True)
    rebounds_defensive = Column(Integer, nullable=True)
    rebounds_total = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    steals = Column(Integer, nullable=True)
    blocks = Column(Integer, nullable=True)
    turnovers = Column(Integer, nullable=True)
    fouls_personal = Column(Integer, nullable=True)
    points = Column(Integer, nullable=True)
    plus_minus_points = Column(Integer, nullable=True)

    source_name = Column(String(64), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_row_sha256 = Column(String(64), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    selected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class PlayerGameFactPromotionORM(Base):
    """Append-only selection history for one traditional canonical grain."""

    __tablename__ = "player_game_fact_promotions"
    __table_args__ = (
        UniqueConstraint("promotion_key", name="uq_player_game_fact_promotion_key"),
        CheckConstraint(
            "reason IN ('initial', 'correction', 'reversion', 'baseline_backfill')",
            name="ck_player_game_fact_promotion_reason",
        ),
        CheckConstraint(
            "previous_revision_id IS NULL OR previous_revision_id <> selected_revision_id",
            name="ck_player_game_fact_promotion_distinct_revisions",
        ),
        Index(
            "idx_player_game_fact_promotion_grain",
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "selected_at",
        ),
    )
    promotion_id = Column(String(36), primary_key=True)
    promotion_key = Column(String(64), nullable=False)
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, nullable=False)
    canonical_team_id = Column(Integer, nullable=False)
    previous_revision_id = Column(String(36), ForeignKey("player_game_fact_revisions.revision_id"), nullable=True)
    selected_revision_id = Column(String(36), ForeignKey("player_game_fact_revisions.revision_id"), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    publication_key = Column(String(128), nullable=False)
    reason = Column(String(24), nullable=False)
    selected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def fact_values_from_revision(revision: PlayerGameFactRevisionORM) -> Dict[str, Any]:
    """Return the traditional fact fields copied into the canonical projection."""
    return {field: getattr(revision, field) for field in TRADITIONAL_FACT_COLUMNS}


class PlayerGameAdvancedFactRevisionORM(Base):
    """One immutable Advanced V3 source row."""

    __tablename__ = "player_game_advanced_fact_revisions"
    __table_args__ = (
        CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_advanced_revision_sha256",
        ),
        CheckConstraint(
            "source_response_sha256 IS NULL OR source_response_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_advanced_revision_response_sha256",
        ),
        CheckConstraint(
            "data_available_at_basis IN ('provider_published', 'retrieved_proxy', 'legacy_unspecified')",
            name="ck_player_game_advanced_revision_availability_basis",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_game_advanced_revision_completeness",
        ),
        CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_game_advanced_revision_participation",
        ),
        UniqueConstraint(
            "source_name",
            "source_row_key",
            "parser_version",
            "source_row_sha256",
            name="uq_player_game_advanced_revision_content",
        ),
        Index("idx_player_game_advanced_revision_game", "canonical_game_id"),
        Index("idx_player_game_advanced_revision_player", "canonical_player_id"),
        Index("idx_player_game_advanced_revision_run", "source_run_id"),
    )

    revision_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_row_key = Column(String(255), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_game_id = Column(String(32), nullable=False)
    source_player_id = Column(BigInteger, nullable=False)
    source_team_id = Column(Integer, nullable=False)
    canonical_game_id = Column(String(32), nullable=True)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=True)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    source_row_sha256 = Column(String(64), nullable=False)
    source_response_sha256 = Column(String(64), nullable=True)
    data_available_at_basis = Column(
        String(32),
        nullable=False,
        default="legacy_unspecified",
        server_default="legacy_unspecified",
    )
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    completeness_status = Column(String(16), nullable=False)
    participation_status = Column(String(16), nullable=False)
    minutes = Column(String(16), nullable=True)
    estimated_offensive_rating = Column(Numeric(12, 6), nullable=True)
    offensive_rating = Column(Numeric(12, 6), nullable=True)
    estimated_defensive_rating = Column(Numeric(12, 6), nullable=True)
    defensive_rating = Column(Numeric(12, 6), nullable=True)
    estimated_net_rating = Column(Numeric(12, 6), nullable=True)
    net_rating = Column(Numeric(12, 6), nullable=True)
    assist_percentage = Column(Numeric(12, 6), nullable=True)
    assist_to_turnover = Column(Numeric(12, 6), nullable=True)
    assist_ratio = Column(Numeric(12, 6), nullable=True)
    offensive_rebound_percentage = Column(Numeric(12, 6), nullable=True)
    defensive_rebound_percentage = Column(Numeric(12, 6), nullable=True)
    rebound_percentage = Column(Numeric(12, 6), nullable=True)
    turnover_ratio = Column(Numeric(12, 6), nullable=True)
    effective_field_goal_percentage = Column(Numeric(12, 6), nullable=True)
    true_shooting_percentage = Column(Numeric(12, 6), nullable=True)
    usage_percentage = Column(Numeric(12, 6), nullable=True)
    estimated_usage_percentage = Column(Numeric(12, 6), nullable=True)
    estimated_pace = Column(Numeric(12, 6), nullable=True)
    pace = Column(Numeric(12, 6), nullable=True)
    pace_per_40 = Column(Numeric(12, 6), nullable=True)
    possessions = Column(Numeric(12, 6), nullable=True)
    pie = Column(Numeric(12, 6), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class PlayerGameAdvancedFactORM(Base):
    """Selected canonical Advanced V3 fact."""

    __tablename__ = "player_game_advanced_facts"
    __table_args__ = (
        CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_game_advanced_fact_participation",
        ),
        ForeignKeyConstraint(
            ["canonical_game_id", "canonical_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_player_game_advanced_fact_schedule",
        ),
        UniqueConstraint(
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            name="uq_player_game_advanced_fact_canonical_grain",
        ),
        Index("idx_player_game_advanced_fact_player_date", "canonical_player_id", "game_date"),
        Index("idx_player_game_advanced_fact_game", "canonical_game_id"),
    )

    fact_id = Column(String(36), primary_key=True)
    revision_id = Column(
        String(36),
        ForeignKey("player_game_advanced_fact_revisions.revision_id"),
        nullable=False,
    )
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=False)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    completeness_status = Column(String(16), nullable=False)
    participation_status = Column(String(16), nullable=False)
    minutes = Column(String(16), nullable=True)
    estimated_offensive_rating = Column(Numeric(12, 6), nullable=True)
    offensive_rating = Column(Numeric(12, 6), nullable=True)
    estimated_defensive_rating = Column(Numeric(12, 6), nullable=True)
    defensive_rating = Column(Numeric(12, 6), nullable=True)
    estimated_net_rating = Column(Numeric(12, 6), nullable=True)
    net_rating = Column(Numeric(12, 6), nullable=True)
    assist_percentage = Column(Numeric(12, 6), nullable=True)
    assist_to_turnover = Column(Numeric(12, 6), nullable=True)
    assist_ratio = Column(Numeric(12, 6), nullable=True)
    offensive_rebound_percentage = Column(Numeric(12, 6), nullable=True)
    defensive_rebound_percentage = Column(Numeric(12, 6), nullable=True)
    rebound_percentage = Column(Numeric(12, 6), nullable=True)
    turnover_ratio = Column(Numeric(12, 6), nullable=True)
    effective_field_goal_percentage = Column(Numeric(12, 6), nullable=True)
    true_shooting_percentage = Column(Numeric(12, 6), nullable=True)
    usage_percentage = Column(Numeric(12, 6), nullable=True)
    estimated_usage_percentage = Column(Numeric(12, 6), nullable=True)
    estimated_pace = Column(Numeric(12, 6), nullable=True)
    pace = Column(Numeric(12, 6), nullable=True)
    pace_per_40 = Column(Numeric(12, 6), nullable=True)
    possessions = Column(Numeric(12, 6), nullable=True)
    pie = Column(Numeric(12, 6), nullable=True)
    source_name = Column(String(64), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_row_sha256 = Column(String(64), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    selected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())


class PlayerGameAdvancedFactPromotionORM(Base):
    """Append-only selection history for one Advanced canonical grain."""

    __tablename__ = "player_game_advanced_fact_promotions"
    __table_args__ = (
        UniqueConstraint("promotion_key", name="uq_player_game_advanced_promotion_key"),
        CheckConstraint(
            "reason IN ('initial', 'correction', 'reversion', 'baseline_backfill')",
            name="ck_player_game_advanced_promotion_reason",
        ),
        CheckConstraint(
            "previous_revision_id IS NULL OR previous_revision_id <> selected_revision_id",
            name="ck_player_game_advanced_promotion_distinct_revisions",
        ),
        Index(
            "idx_player_game_advanced_promotion_grain",
            "canonical_game_id",
            "canonical_player_id",
            "canonical_team_id",
            "selected_at",
        ),
    )
    promotion_id = Column(String(36), primary_key=True)
    promotion_key = Column(String(64), nullable=False)
    canonical_game_id = Column(String(32), nullable=False)
    canonical_player_id = Column(BigInteger, nullable=False)
    canonical_team_id = Column(Integer, nullable=False)
    previous_revision_id = Column(String(36), ForeignKey("player_game_advanced_fact_revisions.revision_id"), nullable=True)
    selected_revision_id = Column(String(36), ForeignKey("player_game_advanced_fact_revisions.revision_id"), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    publication_key = Column(String(128), nullable=False)
    reason = Column(String(24), nullable=False)
    selected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def advanced_fact_values_from_revision(
    revision: PlayerGameAdvancedFactRevisionORM,
) -> Dict[str, Any]:
    return {field: getattr(revision, field) for field in ADVANCED_FACT_COLUMNS}
