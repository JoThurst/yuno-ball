"""Baseline migration - existing schema

Revision ID: 78d393826e3b
Revises: 
Create Date: 2025-11-20 17:18:19.765166

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78d393826e3b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Baseline migration for existing database.
    
    This migration does nothing - it simply marks the database as being at
    this revision point. The database already has tables (users, players, teams,
    etc.) that were created using raw SQL/psycopg2.
    
    Future migrations will build on top of this baseline.
    """
    pass


def downgrade() -> None:
    """
    Downgrade does nothing - we're marking the existing state.
    """
    pass

