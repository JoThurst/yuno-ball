"""Test configuration settings."""

from app.config import Config
import os
from datetime import timedelta

class TestConfig(Config):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    REDIS_URL = 'redis://localhost:6379/1'
    
    # Email settings
    SMTP_SERVER = 'localhost'
    SMTP_PORT = 25
    SMTP_USERNAME = None
    SMTP_PASSWORD = None
    MAIL_DEFAULT_SENDER = 'test@yunoball.xyz'
    
    # Database settings
    DATABASE_URL = 'postgresql://localhost/yunoball_test'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_SECRET_KEY = 'test-jwt-secret'
    JWT_EXPIRATION_DELTA = timedelta(hours=1)
    
    # API settings
    API_KEY = 'test-api-key'
    
    # Rate limiting
    RATELIMIT_ENABLED = False 