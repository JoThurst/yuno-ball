"""SQLAlchemy database configuration and session management.

This module provides the SQLAlchemy engine, session factory, and declarative base
for the YunoBall sports analytics application. It supports both the new SQLAlchemy
ORM approach and maintains compatibility with the existing psycopg2 connection pool.
"""
import os
import logging
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Handle Neon.tech SSL requirement
if 'neon.tech' in DATABASE_URL and 'sslmode=' not in DATABASE_URL:
    DATABASE_URL += '?sslmode=require'


# SQLAlchemy Engine Configuration
# Using NullPool for serverless environments (can be changed to QueuePool for production)
engine = create_engine(
    DATABASE_URL,
    poolclass=pool.NullPool,  # No connection pooling (compatible with existing pool in db_config)
    echo=False,  # Set to True for SQL query logging during development
    connect_args={
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
        'connect_timeout': 3,
        'application_name': 'yunoball_sqlalchemy'
    }
)


# Event listener for setting search_path (schema) per connection
@event.listens_for(Engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """Set the default search_path for new connections."""
    # Default to public, can be overridden per session
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO public, nba, mlb")
    cursor.close()


# Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent lazy loading issues after commit
)


# Declarative Base for Models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.
    
    All model classes should inherit from this base class.
    """
    pass


# Dependency function for FastAPI/Flask integration
def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session.
    
    Usage in FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    
    Usage in Flask:
        from app.database import get_db_context
        with get_db_context() as db:
            ...
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions.
    
    Usage:
        with get_db_context() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database context error: {e}")
        raise
    finally:
        db.close()


def set_schema(session: Session, schema: str) -> None:
    """Set the search_path for a specific session.
    
    Args:
        session: SQLAlchemy session
        schema: Schema name (e.g., 'nba', 'mlb', 'public')
    
    Usage:
        with get_db_context() as db:
            set_schema(db, 'nba')
            teams = db.query(Team).all()
    """
    session.execute(text(f"SET search_path TO {schema}, public"))


# Health check function
def check_database_connection() -> bool:
    """Check if database connection is healthy.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        with get_db_context() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Initialize function (called from app startup)
def init_db():
    """Initialize database connection.
    
    This function can be called during application startup to verify
    database connectivity and perform any necessary initialization.
    """
    try:
        if check_database_connection():
            logger.info("Database connection established successfully")
        else:
            logger.error("Failed to establish database connection")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

