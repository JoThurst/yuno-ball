import os
import sys
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
import pandas as pd

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    handlers=[
        logging.FileHandler('database_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseCleaner:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("Database URL not provided and DATABASE_URL environment variable not set")
        
        self.conn = None
        self.cur = None
        self.table_schemas = {}
        self.current_season = self._get_current_season()
        logger.info(f"DatabaseCleaner initialized (Current Season: {self.current_season})")

    def _get_current_season(self):
        """Determine current NBA season based on date"""
        now = datetime.now()
        year = now.year
        # NBA season spans two years, new season typically starts in October
        if now.month < 10:  # Before October
            return f"{year-1}-{str(year)[2:]}"
        return f"{year}-{str(year+1)[2:]}"

    def get_seasons_to_keep(self, num_seasons=10):
        """Get list of recent seasons to keep"""
        current_year = int(self.current_season.split('-')[0])
        seasons = []
        for i in range(num_seasons):
            year = current_year - i
            seasons.append(f"{year}-{str(year+1)[2:]}")
        return seasons

    def connect(self):
        """Establish database connection"""
        try:
            logger.info("Attempting to connect to database...")
            self.conn = psycopg2.connect(self.db_url)
            self.cur = self.conn.cursor()
            logger.info("Successfully connected to database")
            self._load_table_schemas()
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def _load_table_schemas(self):
        """Load table schemas to validate column names"""
        try:
            tables = [
                'players', 'statistics', 'game_schedule', 
                'team_game_stats', 'gamelogs', 
                'leaguedashplayerstats', 'player_streaks',
                'league_dash_team_stats'  # Added missing tables
            ]
            
            logger.info(f"Loading schemas for tables: {', '.join(tables)}")
            
            for table in tables:
                # Get column information for each table
                self.cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                """, (table,))
                
                columns = {row[0]: row[1] for row in self.cur.fetchall()}
                if columns:
                    self.table_schemas[table] = columns
                    logger.info(f"✓ Table {table} schema loaded with {len(columns)} columns: {list(columns.keys())}")
                else:
                    logger.warning(f"⚠ Table {table} not found in database")
            
        except Exception as e:
            logger.error(f"Error loading table schemas: {e}")
            raise

    def _validate_columns(self, table_name, columns):
        """Validate that columns exist in table schema"""
        if table_name not in self.table_schemas:
            logger.error(f"Table {table_name} schema not loaded")
            raise ValueError(f"Table {table_name} schema not loaded")
            
        invalid_columns = [col for col in columns if col not in self.table_schemas[table_name]]
        if invalid_columns:
            logger.error(f"Invalid columns for table {table_name}: {invalid_columns}")
            raise ValueError(f"Invalid columns for table {table_name}: {invalid_columns}")
        
        logger.debug(f"Validated columns for {table_name}: {columns}")
        return True

    def disconnect(self):
        """Close database connection"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def remove_duplicates(self, table_name, unique_columns):
        """Remove duplicate records based on specified columns"""
        try:
            logger.info(f"Checking for duplicates in {table_name} based on columns: {unique_columns}")
            
            # Validate columns exist
            self._validate_columns(table_name, unique_columns)
            
            # First, count potential duplicates
            count_query = sql.SQL("""
                SELECT COUNT(*) - COUNT(DISTINCT ({unique_cols}))
                FROM {table_name}
            """).format(
                table_name=sql.Identifier(table_name),
                unique_cols=sql.SQL(', ').join(map(sql.Identifier, unique_columns))
            )
            
            self.cur.execute(count_query)
            potential_dupes = self.cur.fetchone()[0]
            logger.info(f"Found {potential_dupes} potential duplicate records in {table_name}")
            
            if potential_dupes == 0:
                logger.info(f"✓ No duplicates found in {table_name}")
                return 0
            
            # Create temporary table with row numbers for each group of duplicates
            dedup_query = sql.SQL("""
                DELETE FROM {table_name} t1 
                USING (
                    SELECT MIN(ctid) as min_ctid, {unique_cols}
                    FROM {table_name}
                    GROUP BY {unique_cols}
                    HAVING COUNT(*) > 1
                ) t2
                WHERE t1.{first_unique_col} = t2.{first_unique_col}
                AND t1.ctid != t2.min_ctid
            """).format(
                table_name=sql.Identifier(table_name),
                unique_cols=sql.SQL(', ').join(map(sql.Identifier, unique_columns)),
                first_unique_col=sql.Identifier(unique_columns[0])
            )
            
            self.cur.execute(dedup_query)
            deleted_count = self.cur.rowcount
            self.conn.commit()
            logger.info(f"✓ Removed {deleted_count} duplicate records from {table_name}")
            return deleted_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error removing duplicates from {table_name}: {e}")
            raise

    def standardize_player_names(self):
        """Standardize player names across all tables"""
        try:
            logger.info("Starting player name standardization...")
            
            # Validate required columns exist
            self._validate_columns('players', ['name'])
            
            # First, count how many names need standardization
            count_query = """
                SELECT COUNT(*) 
                FROM players 
                WHERE name != initcap(name)
            """
            self.cur.execute(count_query)
            needs_update = self.cur.fetchone()[0]
            logger.info(f"Found {needs_update} player names that need standardization")
            
            # Update players table
            update_query = """
                UPDATE players
                SET name = initcap(name)
                WHERE name != initcap(name)
            """
            self.cur.execute(update_query)
            updated_count = self.cur.rowcount
            logger.info(f"✓ Standardized {updated_count} names in players table")
            
            # Update leaguedashplayerstats table if it exists
            if 'leaguedashplayerstats' in self.table_schemas:
                count_query = """
                    SELECT COUNT(*) 
                    FROM leaguedashplayerstats 
                    WHERE player_name != initcap(player_name)
                """
                self.cur.execute(count_query)
                needs_update = self.cur.fetchone()[0]
                logger.info(f"Found {needs_update} player names that need standardization in leaguedashplayerstats")
                
                update_query = """
                    UPDATE leaguedashplayerstats
                    SET player_name = initcap(player_name)
                    WHERE player_name != initcap(player_name)
                """
                self.cur.execute(update_query)
                league_updated = self.cur.rowcount
                updated_count += league_updated
                logger.info(f"✓ Standardized {league_updated} names in leaguedashplayerstats table")
            
            self.conn.commit()
            logger.info(f"✓ Total player names standardized: {updated_count}")
            return updated_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error standardizing player names: {e}")
            raise

    def handle_null_values(self, table_name, column_rules):
        """Handle NULL or invalid values based on specified rules"""
        try:
            logger.info(f"Checking NULL values in {table_name} for columns: {list(column_rules.keys())}")
            
            # Validate columns exist
            self._validate_columns(table_name, column_rules.keys())
            
            # First, count NULL values for each column
            for column in column_rules.keys():
                count_query = sql.SQL("""
                    SELECT COUNT(*) 
                    FROM {table} 
                    WHERE {column} IS NULL
                """).format(
                    table=sql.Identifier(table_name),
                    column=sql.Identifier(column)
                )
                self.cur.execute(count_query)
                null_count = self.cur.fetchone()[0]
                logger.info(f"Found {null_count} NULL values in {table_name}.{column}")
            
            updates = []
            for column, rule in column_rules.items():
                if rule['action'] == 'set_default':
                    update_query = sql.SQL("""
                        UPDATE {table}
                        SET {column} = {value}
                        WHERE {column} IS NULL
                    """).format(
                        table=sql.Identifier(table_name),
                        column=sql.Identifier(column),
                        value=sql.Literal(rule['value'])
                    )
                    self.cur.execute(update_query)
                    updates.append((column, self.cur.rowcount))
            
            self.conn.commit()
            for column, count in updates:
                logger.info(f"✓ Updated {count} NULL values in {table_name}.{column} to default value")
            return updates
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error handling NULL values in {table_name}: {e}")
            raise

    def remove_outdated_seasons(self, table_name, seasons_to_keep):
        """Remove data from seasons not in the keep list"""
        try:
            logger.info(f"Checking for outdated seasons in {table_name}")
            logger.info(f"Keeping seasons: {seasons_to_keep}")
            
            # Handle different season column names
            season_column = 'season_year' if table_name == 'statistics' else 'season'
            
            # First, get all distinct seasons in the table
            season_query = sql.SQL("""
                SELECT DISTINCT {season_col}
                FROM {table}
                ORDER BY {season_col} DESC
            """).format(
                table=sql.Identifier(table_name),
                season_col=sql.Identifier(season_column)
            )
            
            self.cur.execute(season_query)
            all_seasons = [row[0] for row in self.cur.fetchall()]
            
            if not all_seasons:
                logger.info(f"✓ No seasons found in {table_name}")
                return 0
                
            logger.info(f"Found seasons in {table_name}: {all_seasons}")
            seasons_to_remove = [s for s in all_seasons if s not in seasons_to_keep]
            
            if not seasons_to_remove:
                logger.info(f"✓ No outdated seasons to remove from {table_name}")
                return 0
            
            logger.info(f"Will remove seasons from {table_name}: {seasons_to_remove}")
            
            # Count records to be deleted
            count_query = sql.SQL("""
                SELECT COUNT(*) 
                FROM {table}
                WHERE {season_col} = ANY(%s)
            """).format(
                table=sql.Identifier(table_name),
                season_col=sql.Identifier(season_column)
            )
            
            self.cur.execute(count_query, (seasons_to_remove,))
            to_delete = self.cur.fetchone()[0]
            
            if to_delete == 0:
                logger.info(f"✓ No records to remove from {table_name}")
                return 0
            
            logger.info(f"Found {to_delete} records to remove from {table_name}")
            
            # Delete outdated seasons
            delete_query = sql.SQL("""
                DELETE FROM {table}
                WHERE {season_col} = ANY(%s)
            """).format(
                table=sql.Identifier(table_name),
                season_col=sql.Identifier(season_column)
            )
            
            self.cur.execute(delete_query, (seasons_to_remove,))
            deleted_count = self.cur.rowcount
            self.conn.commit()
            logger.info(f"✓ Removed {deleted_count} records from {table_name} for seasons: {seasons_to_remove}")
            return deleted_count
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error removing outdated seasons from {table_name}: {e}")
            raise

    def optimize_indexes(self):
        """Manage and optimize database indexes"""
        try:
            logger.info("Starting database index optimization...")
            
            # Define indexes for each table
            index_definitions = {
                'players': [
                    ('player_id_idx', 'player_id'),
                    ('player_name_idx', 'name')
                ],
                'statistics': [
                    ('stats_player_season_idx', 'player_id, season_year'),
                    ('stats_season_idx', 'season_year')
                ],
                'game_schedule': [
                    ('schedule_game_id_idx', 'game_id'),
                    ('schedule_team_id_idx', 'team_id'),
                    ('schedule_date_idx', 'game_date'),
                    ('schedule_season_idx', 'season')
                ],
                'team_game_stats': [
                    ('team_stats_game_team_idx', 'game_id, team_id'),
                    ('team_stats_date_idx', 'game_date'),
                    ('team_stats_season_idx', 'season')
                ],
                'gamelogs': [
                    ('gamelogs_player_game_idx', 'player_id, game_id'),
                    ('gamelogs_game_idx', 'game_id'),
                    ('gamelogs_season_idx', 'season')
                ],
                'leaguedashplayerstats': [
                    ('leaguedash_player_season_idx', 'player_id, season'),
                    ('leaguedash_season_idx', 'season'),
                    ('leaguedash_team_idx', 'team_id')
                ],
                'player_streaks': [
                    ('streaks_player_stat_idx', 'player_id, stat, season'),
                    ('streaks_season_idx', 'season')
                ],
                'league_dash_team_stats': [
                    ('team_dash_composite_idx', 'team_id, season, season_type'),
                    ('team_dash_season_idx', 'season')
                ]
            }

            for table, indexes in index_definitions.items():
                if table in self.table_schemas:
                    logger.info(f"Optimizing indexes for table: {table}")
                    
                    # Get existing indexes
                    self.cur.execute("""
                        SELECT indexname, indexdef 
                        FROM pg_indexes 
                        WHERE tablename = %s
                    """, (table,))
                    existing_indexes = {row[0]: row[1] for row in self.cur.fetchall()}
                    
                    # Create or update needed indexes
                    for index_name, columns in indexes:
                        if index_name not in existing_indexes:
                            try:
                                create_idx_query = sql.SQL("""
                                    CREATE INDEX IF NOT EXISTS {} ON {} ({})
                                """).format(
                                    sql.Identifier(index_name),
                                    sql.Identifier(table),
                                    sql.SQL(columns)
                                )
                                self.cur.execute(create_idx_query)
                                logger.info(f"✓ Created index {index_name} on {table}")
                            except Exception as e:
                                logger.error(f"Failed to create index {index_name} on {table}: {e}")
                    
                    # ANALYZE table to update statistics
                    try:
                        analyze_query = sql.SQL("ANALYZE {}").format(sql.Identifier(table))
                        self.cur.execute(analyze_query)
                        logger.info(f"✓ Analyzed table {table}")
                    except Exception as e:
                        logger.error(f"Failed to analyze table {table}: {e}")
            
            self.conn.commit()
            logger.info("✓ Database index optimization completed")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error optimizing indexes: {e}")
            raise

    def cleanup_all(self):
        """Run all cleanup procedures"""
        try:
            logger.info("Starting comprehensive database cleanup...")
            self.connect()
            
            # Get actual table schemas first
            logger.info("\n=== Checking Database Schema ===")
            for table in self.table_schemas:
                logger.info(f"Table {table} columns: {list(self.table_schemas[table].keys())}")
            
            # Remove duplicates from main tables with validated column names
            logger.info("\n=== Removing Duplicate Records ===")
            tables_unique_cols = {
                'players': ['player_id'],
                'statistics': ['player_id', 'season_year'],  # Composite unique key
                'game_schedule': ['game_id', 'team_id'],  # Composite primary key
                'team_game_stats': ['game_id', 'team_id'],  # Composite primary key
                'gamelogs': ['player_id', 'game_id'],  # Composite primary key
                'leaguedashplayerstats': ['player_id', 'season'],  # Composite primary key
                'player_streaks': ['player_id', 'stat', 'season', 'threshold'],  # Composite unique key
                'league_dash_team_stats': ['team_id', 'season', 'season_type']  # Composite primary key
            }
            
            for table, unique_cols in tables_unique_cols.items():
                if table in self.table_schemas:
                    try:
                        self.remove_duplicates(table, unique_cols)
                    except Exception as e:
                        logger.error(f"Failed to remove duplicates from {table}: {e}")
                        # Continue with other tables instead of failing completely
                        continue
                else:
                    logger.warning(f"⚠ Skipping {table} - table not found in database")
            
            # Standardize player names in both players and leaguedashplayerstats tables
            logger.info("\n=== Standardizing Player Names ===")
            if 'players' in self.table_schemas:
                try:
                    self.standardize_player_names()
                except Exception as e:
                    logger.error(f"Failed to standardize player names: {e}")
            
            # Handle NULL values with validated columns
            logger.info("\n=== Handling NULL Values ===")
            null_value_rules = {
                'statistics': {
                    'points': {'action': 'set_default', 'value': 0},
                    'rebounds': {'action': 'set_default', 'value': 0},
                    'assists': {'action': 'set_default', 'value': 0},
                    'blocks': {'action': 'set_default', 'value': 0},
                    'steals': {'action': 'set_default', 'value': 0}
                },
                'gamelogs': {
                    'points': {'action': 'set_default', 'value': 0},
                    'assists': {'action': 'set_default', 'value': 0},
                    'rebounds': {'action': 'set_default', 'value': 0},
                    'steals': {'action': 'set_default', 'value': 0},
                    'blocks': {'action': 'set_default', 'value': 0},
                    'turnovers': {'action': 'set_default', 'value': 0},
                    'minutes_played': {'action': 'set_default', 'value': '00:00'}
                },
                'leaguedashplayerstats': {
                    'min': {'action': 'set_default', 'value': 0.0},     # Minutes as double precision
                    'pts': {'action': 'set_default', 'value': 0.0},    # Stats are stored as numeric
                    'reb': {'action': 'set_default', 'value': 0.0},
                    'ast': {'action': 'set_default', 'value': 0.0},
                    'stl': {'action': 'set_default', 'value': 0.0},
                    'blk': {'action': 'set_default', 'value': 0.0},
                    'tov': {'action': 'set_default', 'value': 0.0},
                    'fgm': {'action': 'set_default', 'value': 0.0},
                    'fga': {'action': 'set_default', 'value': 0.0},
                    'fg_pct': {'action': 'set_default', 'value': 0.0},
                    'fg3m': {'action': 'set_default', 'value': 0.0},
                    'fg3a': {'action': 'set_default', 'value': 0.0},
                    'fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'ftm': {'action': 'set_default', 'value': 0.0},
                    'fta': {'action': 'set_default', 'value': 0.0},
                    'ft_pct': {'action': 'set_default', 'value': 0.0},
                    'oreb': {'action': 'set_default', 'value': 0.0},
                    'dreb': {'action': 'set_default', 'value': 0.0},
                    'plus_minus': {'action': 'set_default', 'value': 0.0},
                    'nba_fantasy_pts': {'action': 'set_default', 'value': 0.0},
                    'wnba_fantasy_pts': {'action': 'set_default', 'value': 0.0},
                    'dd2': {'action': 'set_default', 'value': 0},      # Double-doubles count
                    'td3': {'action': 'set_default', 'value': 0},      # Triple-doubles count
                    'gp': {'action': 'set_default', 'value': 0},       # Games played
                    'w': {'action': 'set_default', 'value': 0},        # Wins
                    'l': {'action': 'set_default', 'value': 0},        # Losses
                    'w_pct': {'action': 'set_default', 'value': 0.0}   # Win percentage
                },
                'team_game_stats': {
                    'fg': {'action': 'set_default', 'value': 0},
                    'fga': {'action': 'set_default', 'value': 0},
                    'fg_pct': {'action': 'set_default', 'value': 0.0},
                    'fg3': {'action': 'set_default', 'value': 0},
                    'fg3a': {'action': 'set_default', 'value': 0},
                    'fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'ft': {'action': 'set_default', 'value': 0},
                    'fta': {'action': 'set_default', 'value': 0},
                    'ft_pct': {'action': 'set_default', 'value': 0.0},
                    'reb': {'action': 'set_default', 'value': 0},
                    'ast': {'action': 'set_default', 'value': 0},
                    'stl': {'action': 'set_default', 'value': 0},
                    'blk': {'action': 'set_default', 'value': 0},
                    'tov': {'action': 'set_default', 'value': 0},
                    'pts': {'action': 'set_default', 'value': 0},
                    'plus_minus': {'action': 'set_default', 'value': 0.0}
                },
                'player_streaks': {
                    'streak_games': {'action': 'set_default', 'value': 0},
                    'threshold': {'action': 'set_default', 'value': 0}
                },
                'league_dash_team_stats': {
                    # Base Stats - Totals
                    'base_totals_gp': {'action': 'set_default', 'value': 0},
                    'base_totals_w': {'action': 'set_default', 'value': 0},
                    'base_totals_l': {'action': 'set_default', 'value': 0},
                    'base_totals_w_pct': {'action': 'set_default', 'value': 0.0},
                    'base_totals_min': {'action': 'set_default', 'value': 0.0},
                    'base_totals_fgm': {'action': 'set_default', 'value': 0},
                    'base_totals_fga': {'action': 'set_default', 'value': 0},
                    'base_totals_fg_pct': {'action': 'set_default', 'value': 0.0},
                    'base_totals_fg3m': {'action': 'set_default', 'value': 0},
                    'base_totals_fg3a': {'action': 'set_default', 'value': 0},
                    'base_totals_fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'base_totals_ftm': {'action': 'set_default', 'value': 0},
                    'base_totals_fta': {'action': 'set_default', 'value': 0},
                    'base_totals_ft_pct': {'action': 'set_default', 'value': 0.0},
                    'base_totals_oreb': {'action': 'set_default', 'value': 0},
                    'base_totals_dreb': {'action': 'set_default', 'value': 0},
                    'base_totals_reb': {'action': 'set_default', 'value': 0},
                    'base_totals_ast': {'action': 'set_default', 'value': 0},
                    'base_totals_tov': {'action': 'set_default', 'value': 0},
                    'base_totals_stl': {'action': 'set_default', 'value': 0},
                    'base_totals_blk': {'action': 'set_default', 'value': 0},
                    'base_totals_blka': {'action': 'set_default', 'value': 0},
                    'base_totals_pf': {'action': 'set_default', 'value': 0},
                    'base_totals_pfd': {'action': 'set_default', 'value': 0},
                    'base_totals_pts': {'action': 'set_default', 'value': 0},
                    'base_totals_plus_minus': {'action': 'set_default', 'value': 0.0},

                    # Base Stats - Per48
                    'base_per48_gp': {'action': 'set_default', 'value': 0},
                    'base_per48_w': {'action': 'set_default', 'value': 0},
                    'base_per48_l': {'action': 'set_default', 'value': 0},
                    'base_per48_w_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per48_min': {'action': 'set_default', 'value': 0.0},
                    'base_per48_fgm': {'action': 'set_default', 'value': 0},
                    'base_per48_fga': {'action': 'set_default', 'value': 0},
                    'base_per48_fg_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per48_fg3m': {'action': 'set_default', 'value': 0},
                    'base_per48_fg3a': {'action': 'set_default', 'value': 0},
                    'base_per48_fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per48_ftm': {'action': 'set_default', 'value': 0},
                    'base_per48_fta': {'action': 'set_default', 'value': 0},
                    'base_per48_ft_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per48_oreb': {'action': 'set_default', 'value': 0},
                    'base_per48_dreb': {'action': 'set_default', 'value': 0},
                    'base_per48_reb': {'action': 'set_default', 'value': 0},
                    'base_per48_ast': {'action': 'set_default', 'value': 0},
                    'base_per48_tov': {'action': 'set_default', 'value': 0},
                    'base_per48_stl': {'action': 'set_default', 'value': 0},
                    'base_per48_blk': {'action': 'set_default', 'value': 0},
                    'base_per48_blka': {'action': 'set_default', 'value': 0},
                    'base_per48_pf': {'action': 'set_default', 'value': 0},
                    'base_per48_pfd': {'action': 'set_default', 'value': 0},
                    'base_per48_pts': {'action': 'set_default', 'value': 0},
                    'base_per48_plus_minus': {'action': 'set_default', 'value': 0.0},

                    # Base Stats - Per100Possessions
                    'base_per100possessions_gp': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_w': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_l': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_w_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per100possessions_min': {'action': 'set_default', 'value': 0.0},
                    'base_per100possessions_fgm': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_fga': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_fg_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per100possessions_fg3m': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_fg3a': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per100possessions_ftm': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_fta': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_ft_pct': {'action': 'set_default', 'value': 0.0},
                    'base_per100possessions_oreb': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_dreb': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_reb': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_ast': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_tov': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_stl': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_blk': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_blka': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_pf': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_pfd': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_pts': {'action': 'set_default', 'value': 0},
                    'base_per100possessions_plus_minus': {'action': 'set_default', 'value': 0.0},

                    # Advanced Stats - Totals
                    'advanced_totals_gp': {'action': 'set_default', 'value': 0},
                    'advanced_totals_w': {'action': 'set_default', 'value': 0},
                    'advanced_totals_l': {'action': 'set_default', 'value': 0},
                    'advanced_totals_w_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_min': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_off_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_def_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_net_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_ast_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_ast_to': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_ast_ratio': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_oreb_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_dreb_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_reb_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_tm_tov_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_efg_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_ts_pct': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_pace': {'action': 'set_default', 'value': 0.0},
                    'advanced_totals_pie': {'action': 'set_default', 'value': 0.0},

                    # Advanced Stats - Per48 and Per100Possessions
                    'advanced_per48_off_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_per48_def_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_per48_net_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_per100possessions_off_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_per100possessions_def_rating': {'action': 'set_default', 'value': 0.0},
                    'advanced_per100possessions_net_rating': {'action': 'set_default', 'value': 0.0},

                    # Misc Stats - All variants
                    'misc_totals_pts_off_tov': {'action': 'set_default', 'value': 0},
                    'misc_totals_pts_2nd_chance': {'action': 'set_default', 'value': 0},
                    'misc_totals_pts_fb': {'action': 'set_default', 'value': 0},
                    'misc_totals_pts_paint': {'action': 'set_default', 'value': 0},
                    'misc_totals_opp_pts_off_tov': {'action': 'set_default', 'value': 0},
                    'misc_totals_opp_pts_2nd_chance': {'action': 'set_default', 'value': 0},
                    'misc_totals_opp_pts_fb': {'action': 'set_default', 'value': 0},
                    'misc_totals_opp_pts_paint': {'action': 'set_default', 'value': 0},

                    # Four Factors - All variants
                    'fourfactors_totals_efg_pct': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_fta_rate': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_tm_tov_pct': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_oreb_pct': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_opp_efg_pct': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_opp_fta_rate': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_opp_tov_pct': {'action': 'set_default', 'value': 0.0},
                    'fourfactors_totals_opp_oreb_pct': {'action': 'set_default', 'value': 0.0},

                    # Scoring Stats - All variants
                    'scoring_totals_pct_fga_2pt': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_fga_3pt': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_2pt': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_2pt_mr': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_3pt': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_fb': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_ft': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_off_tov': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_pts_paint': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_ast_2pm': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_uast_2pm': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_ast_3pm': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_uast_3pm': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_ast_fgm': {'action': 'set_default', 'value': 0.0},
                    'scoring_totals_pct_uast_fgm': {'action': 'set_default', 'value': 0.0},

                    # Defense Stats - All variants
                    'defense_totals_def_rating': {'action': 'set_default', 'value': 0.0},
                    'defense_totals_dreb': {'action': 'set_default', 'value': 0},
                    'defense_totals_dreb_pct': {'action': 'set_default', 'value': 0.0},
                    'defense_totals_stl': {'action': 'set_default', 'value': 0},
                    'defense_totals_blk': {'action': 'set_default', 'value': 0},
                    'defense_totals_opp_pts_off_tov': {'action': 'set_default', 'value': 0},
                    'defense_totals_opp_pts_2nd_chance': {'action': 'set_default', 'value': 0},
                    'defense_totals_opp_pts_fb': {'action': 'set_default', 'value': 0},
                    'defense_totals_opp_pts_paint': {'action': 'set_default', 'value': 0},

                    # Opponent Stats - All variants
                    'opponent_totals_opp_fgm': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_fga': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_fg_pct': {'action': 'set_default', 'value': 0.0},
                    'opponent_totals_opp_fg3m': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_fg3a': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_fg3_pct': {'action': 'set_default', 'value': 0.0},
                    'opponent_totals_opp_ftm': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_fta': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_ft_pct': {'action': 'set_default', 'value': 0.0},
                    'opponent_totals_opp_oreb': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_dreb': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_reb': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_ast': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_tov': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_stl': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_blk': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_blka': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_pf': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_pfd': {'action': 'set_default', 'value': 0},
                    'opponent_totals_opp_pts': {'action': 'set_default', 'value': 0},
                    'opponent_totals_plus_minus': {'action': 'set_default', 'value': 0.0}
                }
            }
            
            for table, rules in null_value_rules.items():
                if table in self.table_schemas:
                    try:
                        self.handle_null_values(table, rules)
                    except Exception as e:
                        logger.error(f"Failed to handle NULL values in {table}: {e}")
                        continue
                else:
                    logger.warning(f"⚠ Skipping NULL handling for {table} - table not found")
            
            # Handle season-based data retention
            logger.info("\n=== Managing Historical Seasons ===")
            seasons_to_keep = self.get_seasons_to_keep(num_seasons=10)  # Keep last 10 seasons
            logger.info(f"Keeping data for seasons: {seasons_to_keep}")
            
            season_based_tables = [
                'statistics', 
                'gamelogs', 
                'leaguedashplayerstats', 
                'game_schedule', 
                'team_game_stats',
                'player_streaks',
                'league_dash_team_stats'
            ]
            for table in season_based_tables:
                if table in self.table_schemas:
                    try:
                        self.remove_outdated_seasons(table, seasons_to_keep)
                    except Exception as e:
                        logger.error(f"Failed to remove outdated seasons from {table}: {e}")
                        continue
                else:
                    logger.warning(f"⚠ Skipping season cleanup for {table} - table not found")
            
            # Optimize indexes as final step
            logger.info("\n=== Optimizing Database Indexes ===")
            self.optimize_indexes()
            
            logger.info("\n=== Database Cleanup Complete ===")
            logger.info("✓ All cleanup procedures completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
            raise
        finally:
            self.disconnect()

def main():
    try:
        cleaner = DatabaseCleaner()
        cleaner.cleanup_all()
    except Exception as e:
        logger.error(f"❌ Database cleanup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 