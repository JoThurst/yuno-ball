"""Add game_odds table

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2025-12-02 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    """Create game_odds table for betting line storage."""
    op.create_table(
        'game_odds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.String(20), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('home_team_id', sa.Integer(), nullable=False),
        sa.Column('away_team_id', sa.Integer(), nullable=False),
        sa.Column('sportsbook_id', sa.String(50), nullable=False),
        sa.Column('sportsbook_name', sa.Text(), nullable=True),
        sa.Column('country_code', sa.String(10), nullable=True),
        sa.Column('sportsbook_url', sa.Text(), nullable=True),
        # Moneyline
        sa.Column('home_ml_odds', sa.Float(), nullable=True),
        sa.Column('away_ml_odds', sa.Float(), nullable=True),
        sa.Column('home_ml_opening', sa.Float(), nullable=True),
        sa.Column('away_ml_opening', sa.Float(), nullable=True),
        sa.Column('home_ml_trend', sa.String(10), nullable=True),
        sa.Column('away_ml_trend', sa.String(10), nullable=True),
        # Spread
        sa.Column('home_spread', sa.Float(), nullable=True),
        sa.Column('away_spread', sa.Float(), nullable=True),
        sa.Column('home_spread_opening', sa.Float(), nullable=True),
        sa.Column('away_spread_opening', sa.Float(), nullable=True),
        sa.Column('spread_home_odds', sa.Float(), nullable=True),
        sa.Column('spread_away_odds', sa.Float(), nullable=True),
        # Raw data
        sa.Column('raw_data', JSONB(), nullable=True),
        # Timestamps
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['home_team_id'], ['teams.team_id'], ),
        sa.ForeignKeyConstraint(['away_team_id'], ['teams.team_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'sportsbook_id', name='game_odds_unique')
    )
    
    # Create indexes
    op.create_index('idx_game_odds_game_id', 'game_odds', ['game_id'])
    op.create_index('idx_game_odds_game_date', 'game_odds', ['game_date'])
    op.create_index('idx_game_odds_season', 'game_odds', ['season'])
    op.create_index('idx_game_odds_sportsbook', 'game_odds', ['sportsbook_id'])


def downgrade():
    """Drop game_odds table."""
    op.drop_index('idx_game_odds_sportsbook', table_name='game_odds')
    op.drop_index('idx_game_odds_season', table_name='game_odds')
    op.drop_index('idx_game_odds_game_date', table_name='game_odds')
    op.drop_index('idx_game_odds_game_id', table_name='game_odds')
    op.drop_table('game_odds')

