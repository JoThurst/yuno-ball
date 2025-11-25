"""fix_players_available_seasons_column_to_array

Revision ID: e44bdbe004a8
Revises: add_enhanced_streaks
Create Date: 2025-11-24 22:29:13.408374

This migration ensures the available_seasons column is TEXT[] (PostgreSQL array)
and converts existing TEXT (comma-separated string) data to array format.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e44bdbe004a8'
down_revision = 'add_enhanced_streaks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Drop the GIN index if it exists (it uses gin_trgm_ops which doesn't work with arrays)
    # We'll recreate it with the proper operator class for arrays
    op.execute("""
        DROP INDEX IF EXISTS idx_players_seasons;
    """)
    
    # Step 2: Clean up corrupted data and convert valid strings to arrays
    # Corrupted data like "-,0,2,2,2,2025-26,4,5" should be cleared (set to NULL)
    # Valid season strings like "2015-16,2016-17,2017-18" should be converted to arrays
    op.execute("""
        DO $$
        BEGIN
            -- Only process if column is TEXT type
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'players' 
                AND column_name = 'available_seasons' 
                AND data_type = 'text'
            ) THEN
                -- Clear corrupted data (contains non-season patterns like single digits, dashes alone, etc.)
                UPDATE players 
                SET available_seasons = NULL
                WHERE available_seasons IS NOT NULL 
                AND (
                    -- Contains patterns that indicate corruption
                    available_seasons::text ~ '[^0-9,\-]'  -- Contains invalid characters
                    OR available_seasons::text ~ '^[^0-9]'  -- Starts with non-digit
                    OR available_seasons::text ~ '[^0-9]$'  -- Ends with non-digit
                    OR available_seasons::text ~ ',\s*[^0-9]'  -- Comma followed by non-digit
                    OR available_seasons::text ~ '[^0-9]\s*,'  -- Non-digit followed by comma
                    OR available_seasons::text !~ '^[0-9]{4}-[0-9]{2}'  -- Doesn't start with season pattern
                );
                
                -- Convert valid season strings to arrays
                -- Valid format: "2015-16,2016-17,2017-18" or single "2015-16"
                UPDATE players 
                SET available_seasons = string_to_array(available_seasons::text, ',')
                WHERE available_seasons IS NOT NULL 
                AND available_seasons::text ~ '^[0-9]{4}-[0-9]{2}(,[0-9]{4}-[0-9]{2})*$';
            END IF;
        END $$;
    """)
    
    # Step 3: Ensure column type is TEXT[]
    # If it's currently TEXT, alter it to TEXT[]
    op.execute("""
        DO $$
        BEGIN
            -- Check if column is TEXT and convert to TEXT[]
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'players' 
                AND column_name = 'available_seasons' 
                AND data_type = 'text'
            ) THEN
                -- Convert TEXT to TEXT[]
                ALTER TABLE players 
                ALTER COLUMN available_seasons TYPE text[] 
                USING string_to_array(available_seasons, ',');
            END IF;
        END $$;
    """)
    
    # Step 4: Recreate the GIN index with the proper operator class for arrays
    # GIN indexes on arrays use the default operator class, not gin_trgm_ops
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_players_seasons 
        ON players USING gin(available_seasons);
    """)


def downgrade() -> None:
    # Step 1: Drop the GIN index
    op.execute("""
        DROP INDEX IF EXISTS idx_players_seasons;
    """)
    
    # Step 2: Convert TEXT[] back to TEXT (comma-separated string)
    op.execute("""
        ALTER TABLE players 
        ALTER COLUMN available_seasons TYPE text 
        USING array_to_string(available_seasons, ',');
    """)
    
    # Step 3: Recreate the GIN index with gin_trgm_ops for TEXT
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_players_seasons 
        ON players USING gin(available_seasons gin_trgm_ops);
    """)

