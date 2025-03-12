"""
Application Factory Module.

This module provides the factory function `create_app` for creating and
configuring the Flask application instance. It initializes the Flask app,
registers blueprints, and sets up any necessary configurations required by the
application.
"""

from flask import Flask, request, redirect
from flask_cors import CORS
import redis
from app.routes import register_blueprints
import logging
import traceback
import os
from app.utils.security_config import (
    CORS_ORIGINS, CORS_METHODS, CORS_ALLOWED_HEADERS,
    CORS_MAX_AGE, add_security_headers
)
from app.config import init_app as init_config, API_KEY
from app.cli import init_app as init_cli
from flask_login import LoginManager
from app.models.user import User
from flask_wtf.csrf import CSRFProtect

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def register_context_processors(app):
    """Register context processors at the application level."""
    logger.info("Registering application-wide context processors...")
    
    @app.context_processor
    def inject_today_matchups():
        """Inject today's matchups into all templates."""
        logger.debug("Injecting today's matchups into templates")
        try:
            # Get today's matchups from service
            from app.services.dashboard_service import get_today_matchups
            
            today_matchups = get_today_matchups()
            return {"today_matchups": today_matchups}
        except Exception as e:
            logger.error(f"Error injecting today's matchups: {str(e)}")
            return {"today_matchups": []}
    
    # Add custom filters
    @app.template_filter('pprint')
    def pprint_filter(obj):
        """Pretty print an object for debugging."""
        import pprint
        return pprint.pformat(obj, indent=2)

def create_app(config_name=None):
    """
    Create and configure the Flask application.

    This function initializes the Flask app, registers the main blueprint,
    and performs any necessary configuration. It serves as the factory
    function for creating instances of the Flask application.

    Returns:
        Flask: The configured Flask application instance.
    """
    logger.info("Creating Flask application...")
    try:
        app = Flask(__name__)
        
        # Initialize CORS
        CORS(app)
        
        # Initialize configuration
        init_config(app, config_name)
        
        # Initialize CLI commands
        init_cli(app)
        
        # Initialize CSRF protection
        csrf = CSRFProtect()
        csrf.init_app(app)
        
        # Configure environment
        is_production = os.getenv('FLASK_ENV') == 'production'
        
        # Set configuration
        app.config.update(
            API_KEY=API_KEY,
            IS_PRODUCTION=is_production,
            PREFERRED_URL_SCHEME='https' if is_production else 'http'
        )

        # Configure CORS based on environment
        if is_production:
            cors_origins = [origin for origin in CORS_ORIGINS if not origin.startswith('http://localhost')]
        else:
            cors_origins = CORS_ORIGINS

        # Apply CORS with enhanced security
        CORS(app, 
             resources={
                 r"/api/*": {
                     "origins": cors_origins,
                     "methods": CORS_METHODS,
                     "allow_headers": CORS_ALLOWED_HEADERS,
                     "supports_credentials": True,
                     "max_age": CORS_MAX_AGE,
                     "expose_headers": ['Content-Type', 'X-Total-Count', 'X-API-Key'],
                     "vary_header": True
                 }
             }
        )
        
        # Configure Redis
        app.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        logger.info("Redis connection established")

        # Initialize Flask-Login
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message_category = 'info'

        @login_manager.user_loader
        def load_user(user_id):
            return User.get_by_id(user_id)

        # Register security headers
        @app.after_request
        def after_request(response):
            # Add security headers
            response = add_security_headers(response)
            
            # Force HTTPS in production
            if is_production:
                if request.is_secure:
                    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
                else:
                    return redirect(request.url.replace('http://', 'https://', 1), code=301)
            
            return response
        
        # Register routes
        try:
            register_blueprints(app)
            logger.info("Blueprints registered successfully")
        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            logger.error(traceback.format_exc())
            
        # Register context processors
        register_context_processors(app)
        logger.info("Context processors registered successfully")
        
        # Register error handlers
        @app.errorhandler(404)
        def not_found(error):
            logger.warning(f"404 error: {str(error)}")
            return {'error': 'Resource not found'}, 404
            
        @app.errorhandler(500)
        def server_error(error):
            logger.error(f"500 error: {str(error)}")
            return {'error': 'Internal server error'}, 500
            
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception: {str(e)}")
            logger.error(traceback.format_exc())
            return "Internal server error", 500
        
        logger.info(f"Flask application created successfully in {'production' if is_production else 'development'} mode")
        return app
    except Exception as e:
        logger.error(f"Error creating Flask application: {str(e)}")
        logger.error(traceback.format_exc())
        raise
