"""add_game_environment_daily_table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-12-02 18:20:00.000000

This migration creates the game_environment_daily table for storing game
matchup environment analysis by combining metrics from both teams.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create game_environment_daily table
    op.create_table(
        'game_environment_daily',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('game_id', sa.BigInteger(), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('home_team_id', sa.Integer(), nullable=False),
        sa.Column('away_team_id', sa.Integer(), nullable=False),
        
        # Home team recent form
        sa.Column('home_off_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('home_def_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('home_pace_lastn', sa.Float(), nullable=True),
        
        # Away team recent form
        sa.Column('away_off_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('away_def_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('away_pace_lastn', sa.Float(), nullable=True),
        
        # Environment indices
        sa.Column('pace_projection', sa.Float(), nullable=True),
        sa.Column('scoring_env_index', sa.Float(), nullable=True),
        sa.Column('three_env_index', sa.Float(), nullable=True),
        sa.Column('reb_env_index', sa.Float(), nullable=True),
        sa.Column('ft_env_index', sa.Float(), nullable=True),
        sa.Column('chaos_index', sa.Float(), nullable=True),
        
        # Boolean flags
        sa.Column('pace_up_for_home', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('pace_up_for_away', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('three_point_fest', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('paint_battle', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('glass_war', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('whistle_heavy', sa.Boolean(), nullable=True, server_default='false'),
        
        # Additional data
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('details_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['home_team_id'], ['teams.team_id']),
        sa.ForeignKeyConstraint(['away_team_id'], ['teams.team_id']),
        sa.UniqueConstraint('game_id', 'game_date', name='game_environment_daily_unique')
    )
    
    # Create indexes
    op.create_index('idx_game_environment_game_id', 'game_environment_daily', ['game_id'])
    op.create_index('idx_game_environment_game_date', 'game_environment_daily', ['game_date'])
    op.create_index('idx_game_environment_season', 'game_environment_daily', ['season'])
    op.create_index('idx_game_environment_home_team', 'game_environment_daily', ['home_team_id'])
    op.create_index('idx_game_environment_away_team', 'game_environment_daily', ['away_team_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_game_environment_away_team', table_name='game_environment_daily')
    op.drop_index('idx_game_environment_home_team', table_name='game_environment_daily')
    op.drop_index('idx_game_environment_season', table_name='game_environment_daily')
    op.drop_index('idx_game_environment_game_date', table_name='game_environment_daily')
    op.drop_index('idx_game_environment_game_id', table_name='game_environment_daily')
    
    # Drop table
    op.drop_table('game_environment_daily')

