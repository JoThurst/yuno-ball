"""Add immutable player-game content revisions and promotion ledgers."""

from alembic import op
import sqlalchemy as sa


revision = "j6k7l8m9n0p1"
down_revision = "i5j6k7l8m9n0"
branch_labels = None
depends_on = None

REVISION_CHECKS = {
    "player_game_fact_revisions": (
        "ck_player_game_fact_revision_response_sha256",
        "ck_player_game_fact_revision_availability_basis",
    ),
    "player_game_advanced_fact_revisions": (
        "ck_player_game_advanced_revision_response_sha256",
        "ck_player_game_advanced_revision_availability_basis",
    ),
}


def _create_promotion_table(
    table: str,
    unique_name: str,
    revision_table: str,
    *,
    index_name: str,
    reason_name: str,
    distinct_name: str,
) -> None:
    op.create_table(
        table,
        sa.Column("promotion_id", sa.String(36), primary_key=True),
        sa.Column("promotion_key", sa.String(64), nullable=False),
        sa.Column("canonical_game_id", sa.String(32), nullable=False),
        sa.Column("canonical_player_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_team_id", sa.Integer(), nullable=False),
        sa.Column("previous_revision_id", sa.String(36), sa.ForeignKey(f"{revision_table}.revision_id"), nullable=True),
        sa.Column("selected_revision_id", sa.String(36), sa.ForeignKey(f"{revision_table}.revision_id"), nullable=False),
        sa.Column("source_run_id", sa.String(36), sa.ForeignKey("ingestion_runs.run_id"), nullable=False),
        sa.Column("publication_key", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("promotion_key", name=unique_name),
        sa.CheckConstraint(
            "reason IN ('initial', 'correction', 'reversion', 'baseline_backfill')",
            name=reason_name,
        ),
        sa.CheckConstraint(
            "previous_revision_id IS NULL OR previous_revision_id <> selected_revision_id",
            name=distinct_name,
        ),
    )
    op.create_index(
        index_name,
        table,
        ["canonical_game_id", "canonical_player_id", "canonical_team_id", "selected_at"],
    )


def upgrade() -> None:
    for table, (response_check, availability_check) in REVISION_CHECKS.items():
        op.add_column(table, sa.Column("source_response_sha256", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("data_available_at_basis", sa.String(32), nullable=False, server_default="legacy_unspecified"))
        op.create_check_constraint(response_check, table,
                                   "source_response_sha256 IS NULL OR source_response_sha256 ~ '^[0-9a-f]{64}$'")
        op.create_check_constraint(availability_check, table,
                                   "data_available_at_basis IN ('provider_published', 'retrieved_proxy', 'legacy_unspecified')")
        if table == "player_game_fact_revisions":
            op.drop_constraint("uq_player_game_fact_revision_source_row", table, type_="unique")
            op.create_unique_constraint("uq_player_game_fact_revision_content", table,
                                        ["source_name", "source_row_key", "parser_version", "source_row_sha256"])
        else:
            op.drop_constraint("uq_player_game_advanced_revision_source_row", table, type_="unique")
            op.create_unique_constraint("uq_player_game_advanced_revision_content", table,
                                        ["source_name", "source_row_key", "parser_version", "source_row_sha256"])

    _create_promotion_table(
        "player_game_fact_promotions",
        "uq_player_game_fact_promotion_key",
        "player_game_fact_revisions",
        index_name="idx_player_game_fact_promotion_grain",
        reason_name="ck_player_game_fact_promotion_reason",
        distinct_name="ck_player_game_fact_promotion_distinct_revisions",
    )
    _create_promotion_table(
        "player_game_advanced_fact_promotions",
        "uq_player_game_advanced_promotion_key",
        "player_game_advanced_fact_revisions",
        index_name="idx_player_game_advanced_promotion_grain",
        reason_name="ck_player_game_advanced_promotion_reason",
        distinct_name="ck_player_game_advanced_promotion_distinct_revisions",
    )

    # Existing selected rows become explicit baselines; no prior correction history is invented.
    op.execute(sa.text("""
        INSERT INTO player_game_fact_promotions
          (promotion_id, promotion_key, canonical_game_id, canonical_player_id, canonical_team_id,
           previous_revision_id, selected_revision_id, source_run_id, publication_key, reason, selected_at)
        SELECT fact.fact_id,
               md5('baseline:traditional:' || fact.fact_id) ||
                 md5('baseline:traditional:2:' || fact.fact_id),
               fact.canonical_game_id,
               fact.canonical_player_id, fact.canonical_team_id, NULL, fact.revision_id,
               fact.source_run_id, 'baseline:' || fact.fact_id, 'baseline_backfill', fact.selected_at
        FROM player_game_facts AS fact
    """))
    op.execute(sa.text("""
        INSERT INTO player_game_advanced_fact_promotions
          (promotion_id, promotion_key, canonical_game_id, canonical_player_id, canonical_team_id,
           previous_revision_id, selected_revision_id, source_run_id, publication_key, reason, selected_at)
        SELECT fact.fact_id,
               md5('baseline:advanced:' || fact.fact_id) ||
                 md5('baseline:advanced:2:' || fact.fact_id),
               fact.canonical_game_id,
               fact.canonical_player_id, fact.canonical_team_id, NULL, fact.revision_id,
               fact.source_run_id, 'baseline:' || fact.fact_id, 'baseline_backfill', fact.selected_at
        FROM player_game_advanced_facts AS fact
    """))
    op.execute(sa.text("""
        UPDATE player_game_fact_revisions
        SET source_response_sha256 = raw_payload->>'response_sha256'
        WHERE raw_payload->>'response_sha256' ~ '^[0-9a-f]{64}$'
    """))
    op.execute(sa.text("""
        UPDATE player_game_advanced_fact_revisions
        SET source_response_sha256 = raw_payload->>'response_sha256'
        WHERE raw_payload->>'response_sha256' ~ '^[0-9a-f]{64}$'
    """))
    op.execute(sa.text("""
        CREATE FUNCTION reject_player_game_promotion_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'player-game promotion history is append-only'; END;
        $$ LANGUAGE plpgsql
    """))
    for table in ("player_game_fact_promotions", "player_game_advanced_fact_promotions"):
        op.execute(sa.text(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_player_game_promotion_mutation()"))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS player_game_advanced_fact_promotions_immutable ON player_game_advanced_fact_promotions"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS player_game_fact_promotions_immutable ON player_game_fact_promotions"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS reject_player_game_promotion_mutation()"))
    op.drop_index("idx_player_game_advanced_promotion_grain", table_name="player_game_advanced_fact_promotions")
    op.drop_table("player_game_advanced_fact_promotions")
    op.drop_index("idx_player_game_fact_promotion_grain", table_name="player_game_fact_promotions")
    op.drop_table("player_game_fact_promotions")
    for table, unique_name, content_name in (
        ("player_game_fact_revisions", "uq_player_game_fact_revision_source_row", "uq_player_game_fact_revision_content"),
        ("player_game_advanced_fact_revisions", "uq_player_game_advanced_revision_source_row", "uq_player_game_advanced_revision_content"),
    ):
        op.drop_constraint(content_name, table, type_="unique")
        op.create_unique_constraint(unique_name, table, ["source_name", "source_row_key", "parser_version"])
        response_check, availability_check = REVISION_CHECKS[table]
        op.drop_constraint(availability_check, table, type_="check")
        op.drop_constraint(response_check, table, type_="check")
        op.drop_column(table, "data_available_at_basis")
        op.drop_column(table, "source_response_sha256")
