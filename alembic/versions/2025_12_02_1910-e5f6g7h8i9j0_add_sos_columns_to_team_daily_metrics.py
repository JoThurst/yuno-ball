"""add_sos_columns_to_team_daily_metrics

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2025-12-02 19:10:00.000000

This migration adds Strength of Schedule (SoS) columns to the team_daily_metrics table.
SoS is based on average opponent NetRtg - higher = faced tougher opponents.

Columns added:
- sos_net_season: Average opponent NetRtg for all games
- sos_net_last10: Average opponent NetRtg for last 10 games
- sos_net_delta: last10 - season (positive = harder recent schedule)
- sos_off_season: Average opponent OffRtg for all games
- sos_def_season: Average opponent DefRtg for all games
- sos_off_last10: Average opponent OffRtg for last 10 games
- sos_def_last10: Average opponent DefRtg for last 10 games
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Strength of Schedule columns to team_daily_metrics
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_net_season', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_net_last10', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_net_delta', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_off_season', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_def_season', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_off_last10', sa.Float(), nullable=True))
    op.add_column('team_daily_metrics', 
                  sa.Column('sos_def_last10', sa.Float(), nullable=True))


def downgrade() -> None:
    # Remove Strength of Schedule columns
    op.drop_column('team_daily_metrics', 'sos_def_last10')
    op.drop_column('team_daily_metrics', 'sos_off_last10')
    op.drop_column('team_daily_metrics', 'sos_def_season')
    op.drop_column('team_daily_metrics', 'sos_off_season')
    op.drop_column('team_daily_metrics', 'sos_net_delta')
    op.drop_column('team_daily_metrics', 'sos_net_last10')
    op.drop_column('team_daily_metrics', 'sos_net_season')

