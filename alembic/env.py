"""Alembic environment configuration for YunoBall sports analytics."""
from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your SQLAlchemy Base and models here
# Import ALL models so Alembic can detect them for migrations
try:
    from app.database import Base
    
    # Import all SQLAlchemy models (IMPORTANT: must import for autogenerate to work)
    from app.models.user_sqlalchemy import UserORM
    from app.models.player_sqlalchemy import PlayerORM
    from app.models.team_sqlalchemy import TeamORM, RosterORM
    from app.models.statistics_sqlalchemy import StatisticsORM
    from app.models.gamelog_sqlalchemy import GameLogORM
    from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
    from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
    from app.models.gameschedule_sqlalchemy import GameScheduleORM
    from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
    from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
    from app.models.player_z_scores_sqlalchemy import PlayerZScoresORM
    from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
    from app.models.player_stat_window_sqlalchemy import PlayerStatWindowORM
    from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
    from app.models.player_consistency_sqlalchemy import PlayerConsistencyORM
    from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
    from app.models.team_daily_flags_sqlalchemy import TeamDailyFlagsORM
    from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
    from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
    from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
    from app.models.game_odds_sqlalchemy import GameOddsORM
    from app.models.ingestion_run_sqlalchemy import IngestionRunORM, IngestionTaskRunORM
    from app.models.player_analytics_snapshot_sqlalchemy import (
        PlayerConsecutiveStreakSnapshotORM,
        PlayerConsistencySnapshotORM,
        PlayerHeatIndexSnapshotORM,
        PlayerStatWindowSnapshotORM,
    )
    
    target_metadata = Base.metadata
except ImportError as e:
    # Fallback if database module doesn't exist yet
    import sys
    print(f"Warning: Could not import models: {e}", file=sys.stderr)
    target_metadata = None

# Get database URL from environment variable
from dotenv import load_dotenv
load_dotenv()

database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")

# Handle Neon.tech SSL requirement
if 'neon.tech' in database_url and 'sslmode=' not in database_url:
    database_url += '?sslmode=require'

config.set_main_option('sqlalchemy.url', database_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

