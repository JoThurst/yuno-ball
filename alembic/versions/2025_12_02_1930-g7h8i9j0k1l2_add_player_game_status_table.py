"""Add player_game_status table

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2025-12-02 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f6g7h8i9j0k1'
branch_labels = None
depends_on = None


def upgrade():
    """Create player_game_status table for injury tracking."""
    op.create_table(
        'player_game_status',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.String(20), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('not_playing_reason', sa.String(50), nullable=True),
        sa.Column('not_playing_description', sa.Text(), nullable=True),
        sa.Column('played', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('player_name', sa.Text(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'player_id', name='player_game_status_unique')
    )
    
    # Create indexes
    op.create_index('idx_player_game_status_game_id', 'player_game_status', ['game_id'])
    op.create_index('idx_player_game_status_player_id', 'player_game_status', ['player_id'])
    op.create_index('idx_player_game_status_team_id', 'player_game_status', ['team_id'])
    op.create_index('idx_player_game_status_game_date', 'player_game_status', ['game_date'])
    op.create_index('idx_player_game_status_season', 'player_game_status', ['season'])
    op.create_index('idx_player_game_status_reason', 'player_game_status', ['not_playing_reason'])


def downgrade():
    """Drop player_game_status table."""
    op.drop_index('idx_player_game_status_reason', table_name='player_game_status')
    op.drop_index('idx_player_game_status_season', table_name='player_game_status')
    op.drop_index('idx_player_game_status_game_date', table_name='player_game_status')
    op.drop_index('idx_player_game_status_team_id', table_name='player_game_status')
    op.drop_index('idx_player_game_status_player_id', table_name='player_game_status')
    op.drop_index('idx_player_game_status_game_id', table_name='player_game_status')
    op.drop_table('player_game_status')

