"""Add enhanced streak tables (consecutive streaks and stat windows)

Revision ID: add_enhanced_streaks
Revises: 3236dd43e25a
Create Date: 2025-11-24 16:20:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_enhanced_streaks'
down_revision = '3236dd43e25a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create player_consecutive_streaks table
    op.create_table(
        'player_consecutive_streaks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.Text(), nullable=False),
        sa.Column('stat', sa.Text(), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('streak_games', sa.Integer(), nullable=False),
        sa.Column('start_game_id', sa.BigInteger(), nullable=False),
        sa.Column('end_game_id', sa.BigInteger(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('streak_kind', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'stat', 'threshold', 'season', 'streak_kind', name='player_consecutive_streaks_unique')
    )
    
    # Create indexes for player_consecutive_streaks
    op.create_index('idx_consecutive_streaks_player_id', 'player_consecutive_streaks', ['player_id'])
    op.create_index('idx_consecutive_streaks_season', 'player_consecutive_streaks', ['season'])
    op.create_index('idx_consecutive_streaks_stat', 'player_consecutive_streaks', ['stat'])
    op.create_index('idx_consecutive_streaks_active', 'player_consecutive_streaks', ['is_active'])
    op.create_index('idx_consecutive_streaks_kind', 'player_consecutive_streaks', ['streak_kind'])
    
    # Create player_stat_windows table
    op.create_table(
        'player_stat_windows',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.Text(), nullable=False),
        sa.Column('stat', sa.Text(), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('window_size', sa.Integer(), nullable=False),
        sa.Column('games_played', sa.Integer(), nullable=False),
        sa.Column('games_hit', sa.Integer(), nullable=False),
        sa.Column('last_game_id', sa.BigInteger(), nullable=False),
        sa.Column('last_game_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'stat', 'threshold', 'season', 'window_size', name='player_stat_windows_unique')
    )
    
    # Create indexes for player_stat_windows
    op.create_index('idx_stat_windows_player_id', 'player_stat_windows', ['player_id'])
    op.create_index('idx_stat_windows_season', 'player_stat_windows', ['season'])
    op.create_index('idx_stat_windows_stat', 'player_stat_windows', ['stat'])
    op.create_index('idx_stat_windows_window_size', 'player_stat_windows', ['window_size'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_stat_windows_window_size', table_name='player_stat_windows')
    op.drop_index('idx_stat_windows_stat', table_name='player_stat_windows')
    op.drop_index('idx_stat_windows_season', table_name='player_stat_windows')
    op.drop_index('idx_stat_windows_player_id', table_name='player_stat_windows')
    
    op.drop_index('idx_consecutive_streaks_kind', table_name='player_consecutive_streaks')
    op.drop_index('idx_consecutive_streaks_active', table_name='player_consecutive_streaks')
    op.drop_index('idx_consecutive_streaks_stat', table_name='player_consecutive_streaks')
    op.drop_index('idx_consecutive_streaks_season', table_name='player_consecutive_streaks')
    op.drop_index('idx_consecutive_streaks_player_id', table_name='player_consecutive_streaks')
    
    # Drop tables
    op.drop_table('player_stat_windows')
    op.drop_table('player_consecutive_streaks')

