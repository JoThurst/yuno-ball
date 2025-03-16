import os
from datetime import timedelta
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# API Configuration
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY environment variable is not set")

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")
JWT_EXPIRATION_DELTA = timedelta(days=int(os.getenv('JWT_EXPIRATION_DAYS', '1')))

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@yunoball.xyz')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

# Flask Configuration
class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is not set")
    
    JWT_SECRET_KEY = JWT_SECRET_KEY
    JWT_EXPIRATION_DELTA = JWT_EXPIRATION_DELTA
    API_KEY = API_KEY
    DATABASE_URL = DATABASE_URL
    
    # Email settings
    SMTP_SERVER = SMTP_SERVER
    SMTP_PORT = SMTP_PORT
    SMTP_USERNAME = SMTP_USERNAME
    SMTP_PASSWORD = SMTP_PASSWORD
    FROM_EMAIL = FROM_EMAIL
    BASE_URL = BASE_URL
    
    # Security settings
    IS_LOCAL = (
        os.getenv('FORCE_LOCAL', 'false').lower() == 'true' or
        '--local' in sys.argv if 'sys.argv' in globals() else False
    )
    FORCE_HTTPS = not IS_LOCAL
    PREFERRED_URL_SCHEME = 'http' if IS_LOCAL else 'https'

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    IS_LOCAL = True
    FORCE_HTTPS = False
    PREFERRED_URL_SCHEME = 'http'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    IS_LOCAL = False
    FORCE_HTTPS = True
    PREFERRED_URL_SCHEME = 'https'

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    # Use test-specific environment variables or fallback to test values
    DATABASE_URL = os.getenv('TEST_DATABASE_URL', 'postgresql://localhost/yunoball_test')
    JWT_SECRET_KEY = os.getenv('TEST_JWT_SECRET_KEY', 'test-jwt-secret')
    SECRET_KEY = os.getenv('TEST_SECRET_KEY', 'test-secret-key')
    JWT_EXPIRATION_DELTA = timedelta(hours=1)
    API_KEY = os.getenv('TEST_API_KEY', 'test-api-key')
    SMTP_SERVER = 'localhost'
    SMTP_PORT = 25
    SMTP_USERNAME = None
    SMTP_PASSWORD = None
    FROM_EMAIL = 'test@yunoball.xyz'
    REDIS_URL = os.getenv('TEST_REDIS_URL', 'redis://localhost:6379/1')
    RATELIMIT_ENABLED = False
    IS_LOCAL = True
    FORCE_HTTPS = False
    PREFERRED_URL_SCHEME = 'http'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def init_app(app, config_name=None):
    """Initialize the Flask app with the given configuration."""
    if not config_name:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Handle both string config names and config class objects
    if isinstance(config_name, str):
        config_obj = config.get(config_name, config['default'])
    else:
        config_obj = config_name
    
    app.config.from_object(config_obj)
    
    # Initialize database connection pool
    from db_config import init_db
    init_db(app.config['DATABASE_URL'])
    
    # Ensure all required config values are set
    required_configs = [
        'JWT_SECRET_KEY',
        'JWT_EXPIRATION_DELTA',
        'API_KEY',
        'DATABASE_URL',
        'SECRET_KEY'
    ]
    
    missing_configs = []
    for config_key in required_configs:
        if not app.config.get(config_key):
            missing_configs.append(config_key)
    
    if missing_configs:
        raise ValueError(f"Missing required configuration(s): {', '.join(missing_configs)}")
            
    return app 