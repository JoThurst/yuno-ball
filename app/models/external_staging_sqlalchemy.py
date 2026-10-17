"""Source-specific external staging and row-rejection models."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Integer,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Numeric,
    func,
)

from app.database import Base
from app.models.ingestion_run_sqlalchemy import JSON_DOCUMENT, utc_now


class StatsurgeAvailabilityStagingORM(Base):
    """One parsed Stat Surge daily availability checkpoint row."""

    __tablename__ = "stg_statsurge_availability"
    __table_args__ = (
        CheckConstraint(
            "source_row_number >= 2",
            name="ck_statsurge_availability_source_row",
        ),
        CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_statsurge_availability_row_sha256",
        ),
        CheckConstraint(
            "reported_status IN "
            "('Available', 'Probable', 'Questionable', 'Doubtful', 'Out')",
            name="ck_statsurge_availability_status",
        ),
        CheckConstraint(
            "season ~ '^[0-9]{4}-[0-9]{2}$'",
            name="ck_statsurge_availability_season",
        ),
        CheckConstraint(
            "source_checkpoint = 'daily_2pm_report'",
            name="ck_statsurge_availability_checkpoint",
        ),
        CheckConstraint(
            "source_published_at IS NULL",
            name="ck_statsurge_availability_no_published_at",
        ),
        CheckConstraint(
            "source_time_precision = 'report_checkpoint'",
            name="ck_statsurge_availability_time_precision",
        ),
        CheckConstraint(
            "source_time_confidence = 'methodology_level'",
            name="ck_statsurge_availability_time_confidence",
        ),
        CheckConstraint(
            "identity_status IN ('unresolved', 'partial', 'resolved', 'conflict')",
            name="ck_statsurge_availability_identity_status",
        ),
        CheckConstraint(
            "identity_resolution_version IS NULL OR "
            "(identity_resolution_run_id IS NOT NULL AND "
            "identity_resolution_details IS NOT NULL)",
            name="ck_statsurge_availability_resolution_lineage",
        ),
        CheckConstraint(
            "cutoff_status IN ('not_evaluated', 'pregame', 'after_cutoff', 'unknown')",
            name="ck_statsurge_availability_cutoff_status",
        ),
        CheckConstraint(
            "completeness_status IN "
            "('identity_unresolved', 'partial', 'complete', 'quarantined')",
            name="ck_statsurge_availability_completeness",
        ),
        CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name="ck_statsurge_availability_validation_status",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_statsurge_availability_source_row",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_dataset_version",
            "report_date",
            "matchup_text",
            "reported_team_name",
            "reported_player_name",
            "parser_version",
            name="uq_statsurge_availability_natural_grain",
        ),
        Index(
            "idx_statsurge_availability_date_team",
            "report_date",
            "reported_team_name",
        ),
        Index(
            "idx_statsurge_availability_import_status",
            "source_import_id",
            "validation_status",
        ),
    )

    staging_row_id = Column(String(36), primary_key=True)
    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    source_row_number = Column(BigInteger, nullable=False)
    source_dataset_version = Column(String(128), nullable=False)
    source_file_name = Column(String(255), nullable=False)
    row_sha256 = Column(String(64), nullable=False)
    reported_player_name = Column(Text, nullable=False)
    reported_status = Column(String(32), nullable=False)
    reported_reason = Column(Text, nullable=False)
    reported_team_name = Column(Text, nullable=False)
    matchup_text = Column(String(32), nullable=False)
    report_date_raw = Column(String(32), nullable=False)
    report_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    source_checkpoint = Column(String(32), nullable=False)
    source_published_at = Column(DateTime(timezone=True), nullable=True)
    source_time_precision = Column(String(32), nullable=False)
    source_time_confidence = Column(String(32), nullable=False)
    resolved_player_id = Column(BigInteger, nullable=True)
    resolved_team_id = Column(BigInteger, nullable=True)
    resolved_game_id = Column(String(20), nullable=True)
    identity_status = Column(String(32), nullable=False)
    identity_resolution_version = Column(String(64), nullable=True)
    identity_resolution_run_id = Column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=True
    )
    identity_resolution_details = Column(JSON_DOCUMENT, nullable=True)
    cutoff_status = Column(String(32), nullable=False)
    completeness_status = Column(String(32), nullable=False)
    validation_status = Column(String(32), nullable=False)
    parser_version = Column(String(64), nullable=False)
    raw_values = Column(JSON_DOCUMENT, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ExternalRowRejectionORM(Base):
    """One source row quarantined before entering a staging table."""

    __tablename__ = "external_row_rejections"
    __table_args__ = (
        CheckConstraint(
            "source_row_number >= 2",
            name="ck_external_row_rejection_source_row",
        ),
        CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_row_rejection_sha256",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_external_row_rejection_source_row",
        ),
        Index(
            "idx_external_row_rejection_import_reason",
            "source_import_id",
            "reason_code",
        ),
    )

    rejection_id = Column(String(36), primary_key=True)
    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    source_file_name = Column(String(255), nullable=False)
    source_row_number = Column(BigInteger, nullable=False)
    row_sha256 = Column(String(64), nullable=False)
    reason_code = Column(String(64), nullable=False)
    reason_detail = Column(Text, nullable=True)
    raw_values = Column(JSON_DOCUMENT, nullable=False)
    parser_version = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class KaggleGameStagingORM(Base):
    """One source-shaped team perspective from the Kaggle game artifact."""

    __tablename__ = "stg_kaggle_games"
    __table_args__ = (
        CheckConstraint("source_row_number >= 2", name="ck_kaggle_games_source_row"),
        CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'", name="ck_kaggle_games_row_sha256"
        ),
        CheckConstraint("game_id ~ '^[0-9]{10}$'", name="ck_kaggle_games_game_id"),
        CheckConstraint(
            "team_id <> opponent_team_id", name="ck_kaggle_games_distinct_teams"
        ),
        CheckConstraint("wl IS NULL OR wl IN ('W', 'L')", name="ck_kaggle_games_wl"),
        CheckConstraint(
            "season ~ '^[0-9]{4}-[0-9]{2}$'", name="ck_kaggle_games_season"
        ),
        CheckConstraint(
            "season_type IN ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')",
            name="ck_kaggle_games_season_type",
        ),
        CheckConstraint(
            "date_status IN ('parsed', 'missing')", name="ck_kaggle_games_date_status"
        ),
        CheckConstraint(
            "(game_date IS NULL AND date_status = 'missing') OR "
            "(game_date IS NOT NULL AND date_status = 'parsed')",
            name="ck_kaggle_games_date_value",
        ),
        CheckConstraint(
            "result_status IN ('final', 'missing')",
            name="ck_kaggle_games_result_status",
        ),
        CheckConstraint(
            "(wl IS NULL AND result_status = 'missing') OR "
            "(wl IS NOT NULL AND result_status = 'final')",
            name="ck_kaggle_games_result_value",
        ),
        CheckConstraint(
            "promotion_eligibility IN "
            "('eligible_market_range', 'deferred_pre_2006', "
            "'excluded_incomplete_2018_19', 'excluded_unsupported_event_type', "
            "'excluded_incomplete_result')",
            name="ck_kaggle_games_promotion_eligibility",
        ),
        CheckConstraint(
            "canonical_match_status IN "
            "('not_evaluated', 'matched', 'canonical_missing', 'conflict')",
            name="ck_kaggle_games_canonical_match_status",
        ),
        CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name="ck_kaggle_games_validation_status",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_kaggle_games_source_row",
        ),
        UniqueConstraint(
            "source_import_id",
            "game_id",
            "team_id",
            "parser_version",
            name="uq_kaggle_games_natural_grain",
        ),
        Index("idx_kaggle_games_game_id", "game_id"),
        Index("idx_kaggle_games_season_type", "season", "season_type"),
        Index(
            "idx_kaggle_games_import_status",
            "source_import_id",
            "validation_status",
        ),
    )

    staging_row_id = Column(String(36), primary_key=True)
    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_run_id = Column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=False
    )
    source_row_number = Column(BigInteger, nullable=False)
    source_dataset_version = Column(String(128), nullable=False)
    source_file_name = Column(String(255), nullable=False)
    row_sha256 = Column(String(64), nullable=False)
    game_id = Column(String(20), nullable=False)
    game_date_raw = Column(String(32), nullable=True)
    game_date = Column(Date, nullable=True)
    matchup = Column(Text, nullable=False)
    team_id = Column(BigInteger, nullable=False)
    is_home = Column(Boolean, nullable=False)
    wl = Column(String(1), nullable=True)
    wins_to_date = Column(Integer, nullable=True)
    losses_to_date = Column(Integer, nullable=True)
    win_pct_to_date = Column(Numeric(8, 5), nullable=True)
    minutes = Column(Numeric(8, 2), nullable=True)
    fgm = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    fg_pct = Column(Numeric(8, 5), nullable=True)
    fg3m = Column(Integer, nullable=True)
    fg3a = Column(Integer, nullable=True)
    fg3_pct = Column(Numeric(8, 5), nullable=True)
    ftm = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)
    ft_pct = Column(Numeric(8, 5), nullable=True)
    oreb = Column(Integer, nullable=True)
    dreb = Column(Integer, nullable=True)
    reb = Column(Integer, nullable=True)
    ast = Column(Integer, nullable=True)
    stl = Column(Integer, nullable=True)
    blk = Column(Integer, nullable=True)
    tov = Column(Integer, nullable=True)
    pf = Column(Integer, nullable=True)
    pts = Column(Integer, nullable=True)
    opponent_team_id = Column(BigInteger, nullable=False)
    season_start_year = Column(Integer, nullable=False)
    season_type = Column(String(32), nullable=False)
    season = Column(String(7), nullable=False)
    date_status = Column(String(16), nullable=False)
    result_status = Column(String(16), nullable=False)
    promotion_eligibility = Column(String(40), nullable=False)
    canonical_match_status = Column(String(32), nullable=False)
    validation_status = Column(String(32), nullable=False)
    parser_version = Column(String(64), nullable=False)
    raw_values = Column(JSON_DOCUMENT, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


def _market_constraints(prefix: str, natural_name: str):
    return (
        CheckConstraint("source_row_number >= 2", name=f"ck_{prefix}_source_row"),
        CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_row_sha256"
        ),
        CheckConstraint("game_id ~ '^[0-9]{10}$'", name=f"ck_{prefix}_game_id"),
        CheckConstraint(
            "team_id <> opponent_team_id", name=f"ck_{prefix}_distinct_teams"
        ),
        CheckConstraint(
            "timing_precision = 'unknown'", name=f"ck_{prefix}_timing_precision"
        ),
        CheckConstraint(
            "snapshot_type = 'historical_static'", name=f"ck_{prefix}_snapshot_type"
        ),
        CheckConstraint(
            "canonical_match_status IN "
            "('not_evaluated', 'matched', 'canonical_missing', 'conflict')",
            name=f"ck_{prefix}_canonical_match_status",
        ),
        CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name=f"ck_{prefix}_validation_status",
        ),
        ForeignKeyConstraint(
            (
                "source_game_import_id",
                "game_id",
                "team_id",
                "source_game_parser_version",
            ),
            (
                "stg_kaggle_games.source_import_id",
                "stg_kaggle_games.game_id",
                "stg_kaggle_games.team_id",
                "stg_kaggle_games.parser_version",
            ),
            name=f"fk_{prefix}_source_game",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name=f"uq_{prefix}_source_row",
        ),
        UniqueConstraint(
            "source_import_id",
            "game_id",
            "book_id",
            "team_id",
            "opponent_team_id",
            "parser_version",
            name=natural_name,
        ),
    )


class KaggleMarketStagingMixin:
    """Columns shared by source-shaped historical market staging rows."""

    staging_row_id = Column(String(36), primary_key=True)
    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )
    # Covered by the composite source-game FK declared in _market_constraints.
    # A second single-column FK is redundant and is not present in the migration.
    source_game_import_id = Column(String(36), nullable=False)
    source_game_parser_version = Column(String(64), nullable=False)
    source_run_id = Column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=False
    )
    source_row_number = Column(BigInteger, nullable=False)
    source_dataset_version = Column(String(128), nullable=False)
    source_file_name = Column(String(255), nullable=False)
    row_sha256 = Column(String(64), nullable=False)
    game_id = Column(String(20), nullable=False)
    book_name = Column(Text, nullable=False)
    book_id = Column(BigInteger, nullable=False)
    team_id = Column(BigInteger, nullable=False)
    opponent_team_id = Column(BigInteger, nullable=False)
    timing_precision = Column(String(16), nullable=False)
    snapshot_type = Column(String(32), nullable=False)
    canonical_match_status = Column(String(32), nullable=False)
    validation_status = Column(String(32), nullable=False)
    parser_version = Column(String(64), nullable=False)
    raw_values = Column(JSON_DOCUMENT, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class KaggleMoneylineStagingORM(KaggleMarketStagingMixin, Base):
    __tablename__ = "stg_kaggle_moneylines"
    __table_args__ = (
        *_market_constraints(
            "kaggle_moneylines", "uq_kaggle_moneylines_natural_grain"
        ),
        Index("idx_kaggle_moneylines_game_book", "game_id", "book_id"),
    )

    team_price = Column(Numeric(12, 2), nullable=False)
    opponent_price = Column(Numeric(12, 2), nullable=False)


class KaggleSpreadStagingORM(KaggleMarketStagingMixin, Base):
    __tablename__ = "stg_kaggle_spreads"
    __table_args__ = (
        CheckConstraint(
            "line_pair_status IN ('inverse', 'selection_specific')",
            name="ck_kaggle_spreads_line_pair_status",
        ),
        *_market_constraints("kaggle_spreads", "uq_kaggle_spreads_natural_grain"),
        Index("idx_kaggle_spreads_game_book", "game_id", "book_id"),
    )

    team_spread = Column(Numeric(12, 2), nullable=False)
    opponent_spread = Column(Numeric(12, 2), nullable=False)
    team_price = Column(Numeric(12, 2), nullable=False)
    opponent_price = Column(Numeric(12, 2), nullable=False)
    line_pair_status = Column(String(24), nullable=False)


class KaggleTotalStagingORM(KaggleMarketStagingMixin, Base):
    __tablename__ = "stg_kaggle_totals"
    __table_args__ = (
        CheckConstraint(
            "line_pair_status IN ('same', 'selection_specific')",
            name="ck_kaggle_totals_line_pair_status",
        ),
        *_market_constraints("kaggle_totals", "uq_kaggle_totals_natural_grain"),
        Index("idx_kaggle_totals_game_book", "game_id", "book_id"),
    )

    over_total = Column(Numeric(12, 2), nullable=False)
    under_total = Column(Numeric(12, 2), nullable=False)
    over_price = Column(Numeric(12, 2), nullable=False)
    under_price = Column(Numeric(12, 2), nullable=False)
    line_pair_status = Column(String(24), nullable=False)


class ExternalMarketAnomalyORM(Base):
    """One semantically suspicious market source row retained for review."""

    __tablename__ = "external_market_anomalies"
    __table_args__ = (
        CheckConstraint(
            "source_row_number >= 2", name="ck_external_market_anomaly_source_row"
        ),
        CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_market_anomaly_sha256",
        ),
        CheckConstraint(
            "market IN ('moneyline', 'spread', 'total')",
            name="ck_external_market_anomaly_market",
        ),
        UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_external_market_anomaly_source_row",
        ),
        Index(
            "idx_external_market_anomaly_import_reason",
            "source_import_id",
            "reason_code",
        ),
    )

    anomaly_id = Column(String(36), primary_key=True)
    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_game_import_id = Column(
        String(36), ForeignKey("external_dataset_imports.import_id"), nullable=False
    )
    source_run_id = Column(
        String(36), ForeignKey("ingestion_runs.run_id"), nullable=False
    )
    source_file_name = Column(String(255), nullable=False)
    source_row_number = Column(BigInteger, nullable=False)
    row_sha256 = Column(String(64), nullable=False)
    game_id = Column(String(20), nullable=True)
    market = Column(String(16), nullable=False)
    reason_code = Column(String(64), nullable=False)
    reason_detail = Column(Text, nullable=False)
    raw_values = Column(JSON_DOCUMENT, nullable=False)
    parser_version = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
