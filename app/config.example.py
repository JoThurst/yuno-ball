import os
from datetime import timedelta
from psycopg2 import pool

# Database Configuration
DATABASE_URL = "postgresql://user:password@localhost:5432/database"

# API Configuration
API_KEY = "your-api-key-here"  # Change this to a secure random key

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key-here')  # Change in production
JWT_EXPIRATION_DELTA = timedelta(days=1)

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'your-email@gmail.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your-app-specific-password')  # Use app-specific password for Gmail
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@yourdomain.com')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')  # Change in production

# Initialize the connection pool globally
connection_pool = pool.SimpleConnectionPool(
    1, 10, DATABASE_URL
)

if connection_pool:
    print("Connection pool created successfully")

def get_connection(schema="public"):
    """Get a database connection from the pool and set schema."""
    if not connection_pool:
        raise Exception("Connection pool is not initialized")

    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute(f"SET search_path TO {schema};")
    conn.commit()
    return conn

def release_connection(conn):
    """Release the connection back to the pool."""
    if connection_pool and conn:
        connection_pool.putconn(conn)

def close_pool():
    """Close all connections when shutting down the app."""
    if connection_pool:
        connection_pool.closeall()

# Flask Configuration
class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    JWT_SECRET_KEY = JWT_SECRET_KEY
    JWT_EXPIRATION_DELTA = JWT_EXPIRATION_DELTA
    API_KEY = API_KEY
    DATABASE_URL = DATABASE_URL

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True

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
    
    app.config.from_object(config[config_name])
    
    # Ensure all required config values are set
    required_configs = [
        'JWT_SECRET_KEY',
        'JWT_EXPIRATION_DELTA',
        'API_KEY',
        'DATABASE_URL'
    ]
    
    for config_key in required_configs:
        if not app.config.get(config_key):
            raise ValueError(f"Missing required configuration: {config_key}")
            
    return app 