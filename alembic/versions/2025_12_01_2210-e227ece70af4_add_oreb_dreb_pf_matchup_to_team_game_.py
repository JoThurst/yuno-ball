"""add_oreb_dreb_pf_matchup_to_team_game_stats

Revision ID: e227ece70af4
Revises: c3d4e5f6g7h8
Create Date: 2025-12-01 22:10:07.701175

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e227ece70af4'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing columns from NBA API team game log to team_game_stats table."""
    # Add rebound breakdown columns
    op.add_column('team_game_stats', 
                  sa.Column('oreb', sa.Integer(), nullable=True, comment='Offensive Rebounds'))
    op.add_column('team_game_stats', 
                  sa.Column('dreb', sa.Integer(), nullable=True, comment='Defensive Rebounds'))
    
    # Add fouls column
    op.add_column('team_game_stats', 
                  sa.Column('pf', sa.Integer(), nullable=True, comment='Personal Fouls'))
    
    # Add game result columns
    op.add_column('team_game_stats', 
                  sa.Column('matchup', sa.String(50), nullable=True, comment='Matchup string (e.g., LAL @ BOS)'))
    op.add_column('team_game_stats', 
                  sa.Column('wl', sa.String(1), nullable=True, comment='Win/Loss (W or L)'))
    op.add_column('team_game_stats', 
                  sa.Column('w', sa.Integer(), nullable=True, comment='Season wins after this game'))
    op.add_column('team_game_stats', 
                  sa.Column('l', sa.Integer(), nullable=True, comment='Season losses after this game'))
    op.add_column('team_game_stats', 
                  sa.Column('w_pct', sa.Float(), nullable=True, comment='Win percentage after this game'))
    
    # Remove plus_minus column (always NULL in data)
    op.drop_column('team_game_stats', 'plus_minus')
    
    # Create indexes for commonly queried columns
    op.create_index('idx_team_game_stats_oreb', 'team_game_stats', ['oreb'])
    op.create_index('idx_team_game_stats_dreb', 'team_game_stats', ['dreb'])
    op.create_index('idx_team_game_stats_wl', 'team_game_stats', ['wl'])


def downgrade() -> None:
    """Remove the added columns and restore plus_minus."""
    # Drop indexes
    op.drop_index('idx_team_game_stats_wl', table_name='team_game_stats')
    op.drop_index('idx_team_game_stats_dreb', table_name='team_game_stats')
    op.drop_index('idx_team_game_stats_oreb', table_name='team_game_stats')
    
    # Restore plus_minus column
    op.add_column('team_game_stats', 
                  sa.Column('plus_minus', sa.Float(), nullable=True))
    
    # Remove game result columns
    op.drop_column('team_game_stats', 'w_pct')
    op.drop_column('team_game_stats', 'l')
    op.drop_column('team_game_stats', 'w')
    op.drop_column('team_game_stats', 'wl')
    op.drop_column('team_game_stats', 'matchup')
    
    # Remove fouls column
    op.drop_column('team_game_stats', 'pf')
    
    # Remove rebound breakdown columns
    op.drop_column('team_game_stats', 'dreb')
    op.drop_column('team_game_stats', 'oreb')

