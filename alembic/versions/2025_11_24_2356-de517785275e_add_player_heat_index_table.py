"""add_player_heat_index_table

Revision ID: de517785275e
Revises: e44bdbe004a8
Create Date: 2025-11-24 23:56:32.887183

This migration creates the player_heat_index table for storing heat index
calculations (hot & cold detection) based on Z-scores comparing recent form
to season averages.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'de517785275e'
down_revision = 'e44bdbe004a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create player_heat_index table
    op.create_table(
        'player_heat_index',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.Text(), nullable=False),
        sa.Column('stat', sa.Text(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('window_size', sa.Integer(), nullable=False),
        sa.Column('season_avg', sa.Float(), nullable=False),
        sa.Column('season_std', sa.Float(), nullable=False),
        sa.Column('recent_avg', sa.Float(), nullable=False),
        sa.Column('z_score', sa.Float(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'stat', 'season', 'window_size', name='player_heat_index_unique')
    )
    
    # Create indexes
    op.create_index('idx_heat_index_player_id', 'player_heat_index', ['player_id'])
    op.create_index('idx_heat_index_season', 'player_heat_index', ['season'])
    op.create_index('idx_heat_index_stat', 'player_heat_index', ['stat'])
    op.create_index('idx_heat_index_status', 'player_heat_index', ['status'])
    op.create_index('idx_heat_index_z_score', 'player_heat_index', ['z_score'])
    op.create_index('idx_heat_index_window_size', 'player_heat_index', ['window_size'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_heat_index_window_size', table_name='player_heat_index')
    op.drop_index('idx_heat_index_z_score', table_name='player_heat_index')
    op.drop_index('idx_heat_index_status', table_name='player_heat_index')
    op.drop_index('idx_heat_index_stat', table_name='player_heat_index')
    op.drop_index('idx_heat_index_season', table_name='player_heat_index')
    op.drop_index('idx_heat_index_player_id', table_name='player_heat_index')
    
    # Drop table
    op.drop_table('player_heat_index')
