"""Test configuration settings."""

from app.config import Config
import os

class TestConfig(Config):
    """Testing configuration."""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    REDIS_URL = 'redis://localhost:6379/1'
    
    # Email settings
    SMTP_SERVER = 'localhost'
    SMTP_PORT = 25
    SMTP_USERNAME = None
    SMTP_PASSWORD = None
    MAIL_DEFAULT_SENDER = 'test@yunoball.xyz'
    
    # Database settings
    # For tests, we use SQLAlchemy directly, so we don't need the old connection pool
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/yunoball_test')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API settings
    API_KEY = 'test-api-key'
    
    # Rate limiting
    RATELIMIT_ENABLED = False
