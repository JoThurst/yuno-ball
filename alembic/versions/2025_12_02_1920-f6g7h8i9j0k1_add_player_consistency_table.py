"""Add player_consistency table

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2025-12-02 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6g7h8i9j0k1'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade():
    """Create player_consistency table for volatility/consistency metrics."""
    op.create_table(
        'player_consistency',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.Text(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('stat_name', sa.Text(), nullable=False),
        sa.Column('window_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('games_played', sa.Integer(), nullable=False),
        sa.Column('mean', sa.Float(), nullable=False),
        sa.Column('stddev', sa.Float(), nullable=False),
        sa.Column('cv', sa.Float(), nullable=False),
        sa.Column('min_val', sa.Float(), nullable=True),
        sa.Column('max_val', sa.Float(), nullable=True),
        sa.Column('median', sa.Float(), nullable=True),
        sa.Column('consistency_tier', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'season', 'stat_name', 'window_size', name='player_consistency_unique')
    )
    
    # Create indexes
    op.create_index('idx_player_consistency_player_id', 'player_consistency', ['player_id'])
    op.create_index('idx_player_consistency_season', 'player_consistency', ['season'])
    op.create_index('idx_player_consistency_stat_name', 'player_consistency', ['stat_name'])
    op.create_index('idx_player_consistency_cv', 'player_consistency', ['cv'])
    op.create_index('idx_player_consistency_tier', 'player_consistency', ['consistency_tier'])


def downgrade():
    """Drop player_consistency table."""
    op.drop_index('idx_player_consistency_tier', table_name='player_consistency')
    op.drop_index('idx_player_consistency_cv', table_name='player_consistency')
    op.drop_index('idx_player_consistency_stat_name', table_name='player_consistency')
    op.drop_index('idx_player_consistency_season', table_name='player_consistency')
    op.drop_index('idx_player_consistency_player_id', table_name='player_consistency')
    op.drop_table('player_consistency')

