"""add_team_daily_flags_table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-02 18:10:00.000000

This migration creates the team_daily_flags table for storing qualitative
flags/tags for teams based on their performance trends.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create team_daily_flags table
    op.create_table(
        'team_daily_flags',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('team_name', sa.Text(), nullable=False),
        sa.Column('flag_type', sa.Text(), nullable=False),
        sa.Column('severity', sa.Float(), nullable=True),
        sa.Column('details_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.UniqueConstraint('stat_date', 'team_id', 'flag_type', name='team_daily_flags_unique')
    )
    
    # Create indexes
    op.create_index('idx_team_daily_flags_team_id', 'team_daily_flags', ['team_id'])
    op.create_index('idx_team_daily_flags_season', 'team_daily_flags', ['season'])
    op.create_index('idx_team_daily_flags_stat_date', 'team_daily_flags', ['stat_date'])
    op.create_index('idx_team_daily_flags_flag_type', 'team_daily_flags', ['flag_type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_team_daily_flags_flag_type', table_name='team_daily_flags')
    op.drop_index('idx_team_daily_flags_stat_date', table_name='team_daily_flags')
    op.drop_index('idx_team_daily_flags_season', table_name='team_daily_flags')
    op.drop_index('idx_team_daily_flags_team_id', table_name='team_daily_flags')
    
    # Drop table
    op.drop_table('team_daily_flags')

