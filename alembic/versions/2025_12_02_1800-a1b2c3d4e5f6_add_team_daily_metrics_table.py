"""add_team_daily_metrics_table

Revision ID: a1b2c3d4e5f6
Revises: de517785275e
Create Date: 2025-12-02 18:00:00.000000

This migration creates the team_daily_metrics table for storing team performance
metrics comparing season-to-date statistics with recent form (last N games).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'de517785275e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create team_daily_metrics table
    op.create_table(
        'team_daily_metrics',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('team_name', sa.Text(), nullable=False),
        sa.Column('window_size', sa.Integer(), nullable=False, server_default='10'),
        
        # Season stats
        sa.Column('off_rtg_season', sa.Float(), nullable=True),
        sa.Column('def_rtg_season', sa.Float(), nullable=True),
        sa.Column('net_rtg_season', sa.Float(), nullable=True),
        sa.Column('pace_season', sa.Float(), nullable=True),
        sa.Column('efg_season', sa.Float(), nullable=True),
        sa.Column('tov_pct_season', sa.Float(), nullable=True),
        sa.Column('orb_pct_season', sa.Float(), nullable=True),
        sa.Column('ftr_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_3pt_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_paint_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_mid_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_ft_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_fb_season', sa.Float(), nullable=True),
        sa.Column('pct_pts_off_tov_season', sa.Float(), nullable=True),
        sa.Column('sec_chance_pts_per100_season', sa.Float(), nullable=True),
        sa.Column('fb_pts_per100_season', sa.Float(), nullable=True),
        sa.Column('paint_pts_per100_season', sa.Float(), nullable=True),
        sa.Column('opp_sec_chance_pts_per100_season', sa.Float(), nullable=True),
        sa.Column('opp_fb_pts_per100_season', sa.Float(), nullable=True),
        sa.Column('opp_paint_pts_per100_season', sa.Float(), nullable=True),
        
        # Last N stats
        sa.Column('off_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('def_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('net_rtg_lastn', sa.Float(), nullable=True),
        sa.Column('pace_lastn', sa.Float(), nullable=True),
        sa.Column('efg_lastn', sa.Float(), nullable=True),
        sa.Column('tov_pct_lastn', sa.Float(), nullable=True),
        sa.Column('orb_pct_lastn', sa.Float(), nullable=True),
        sa.Column('ftr_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_3pt_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_paint_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_mid_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_ft_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_fb_lastn', sa.Float(), nullable=True),
        sa.Column('pct_pts_off_tov_lastn', sa.Float(), nullable=True),
        sa.Column('sec_chance_pts_per100_lastn', sa.Float(), nullable=True),
        sa.Column('fb_pts_per100_lastn', sa.Float(), nullable=True),
        sa.Column('paint_pts_per100_lastn', sa.Float(), nullable=True),
        sa.Column('opp_sec_chance_pts_per100_lastn', sa.Float(), nullable=True),
        sa.Column('opp_fb_pts_per100_lastn', sa.Float(), nullable=True),
        sa.Column('opp_paint_pts_per100_lastn', sa.Float(), nullable=True),
        
        # Deltas
        sa.Column('off_rtg_delta', sa.Float(), nullable=True),
        sa.Column('def_rtg_delta', sa.Float(), nullable=True),
        sa.Column('net_rtg_delta', sa.Float(), nullable=True),
        sa.Column('pace_delta', sa.Float(), nullable=True),
        sa.Column('efg_delta', sa.Float(), nullable=True),
        sa.Column('tov_pct_delta', sa.Float(), nullable=True),
        sa.Column('orb_pct_delta', sa.Float(), nullable=True),
        sa.Column('ftr_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_3pt_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_paint_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_mid_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_ft_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_fb_delta', sa.Float(), nullable=True),
        sa.Column('pct_pts_off_tov_delta', sa.Float(), nullable=True),
        sa.Column('sec_chance_pts_per100_delta', sa.Float(), nullable=True),
        sa.Column('fb_pts_per100_delta', sa.Float(), nullable=True),
        sa.Column('paint_pts_per100_delta', sa.Float(), nullable=True),
        sa.Column('opp_sec_chance_pts_per100_delta', sa.Float(), nullable=True),
        sa.Column('opp_fb_pts_per100_delta', sa.Float(), nullable=True),
        sa.Column('opp_paint_pts_per100_delta', sa.Float(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.UniqueConstraint('stat_date', 'team_id', 'window_size', name='team_daily_metrics_unique')
    )
    
    # Create indexes
    op.create_index('idx_team_daily_metrics_team_id', 'team_daily_metrics', ['team_id'])
    op.create_index('idx_team_daily_metrics_season', 'team_daily_metrics', ['season'])
    op.create_index('idx_team_daily_metrics_stat_date', 'team_daily_metrics', ['stat_date'])
    op.create_index('idx_team_daily_metrics_window_size', 'team_daily_metrics', ['window_size'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_team_daily_metrics_window_size', table_name='team_daily_metrics')
    op.drop_index('idx_team_daily_metrics_stat_date', table_name='team_daily_metrics')
    op.drop_index('idx_team_daily_metrics_season', table_name='team_daily_metrics')
    op.drop_index('idx_team_daily_metrics_team_id', table_name='team_daily_metrics')
    
    # Drop table
    op.drop_table('team_daily_metrics')

