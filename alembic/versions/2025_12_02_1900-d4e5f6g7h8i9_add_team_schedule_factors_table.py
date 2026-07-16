"""add_team_schedule_factors_table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-12-02 19:00:00.000000

This migration creates the team_schedule_factors table for storing per-team
per-game schedule factors (days rest, B2B, 3-in-4, rest edge, etc.).

Schedule factors are calculated per team per game - one team can be on a B2B
while the other is on 3 days rest.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'e227ece70af4'  # Chain from add_oreb_dreb_pf_matchup_to_team_game_stats
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create team_schedule_factors table
    op.create_table(
        'team_schedule_factors',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        
        # Identifiers
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('opponent_id', sa.Integer(), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        
        # Schedule Factors - This Team
        sa.Column('days_rest', sa.Integer(), nullable=True),
        sa.Column('is_b2b', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_3_in_4', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_4_in_5', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_5_in_7', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('games_last_4', sa.Integer(), nullable=True),
        sa.Column('games_last_7', sa.Integer(), nullable=True),
        
        # Comparative Factors
        sa.Column('opponent_days_rest', sa.Integer(), nullable=True),
        sa.Column('rest_edge', sa.Text(), nullable=True),  # 'advantage' | 'even' | 'disadvantage'
        sa.Column('rest_diff', sa.Integer(), nullable=True),  # days_rest - opponent_days_rest
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.ForeignKeyConstraint(['opponent_id'], ['teams.team_id']),
        # Note: game_id FK would require game_schedule to have game_id as PK, which it doesn't
        # game_schedule has composite PK (game_id, team_id), so we skip the FK here
        sa.UniqueConstraint('game_id', 'team_id', name='team_schedule_factors_unique')
    )
    
    # Create indexes
    op.create_index('idx_team_schedule_factors_team_id', 'team_schedule_factors', ['team_id'])
    op.create_index('idx_team_schedule_factors_game_date', 'team_schedule_factors', ['game_date'])
    op.create_index('idx_team_schedule_factors_season', 'team_schedule_factors', ['season'])
    op.create_index('idx_team_schedule_factors_is_b2b', 'team_schedule_factors', ['is_b2b'])
    op.create_index('idx_team_schedule_factors_rest_edge', 'team_schedule_factors', ['rest_edge'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_team_schedule_factors_rest_edge', table_name='team_schedule_factors')
    op.drop_index('idx_team_schedule_factors_is_b2b', table_name='team_schedule_factors')
    op.drop_index('idx_team_schedule_factors_season', table_name='team_schedule_factors')
    op.drop_index('idx_team_schedule_factors_game_date', table_name='team_schedule_factors')
    op.drop_index('idx_team_schedule_factors_team_id', table_name='team_schedule_factors')
    
    # Drop table
    op.drop_table('team_schedule_factors')

