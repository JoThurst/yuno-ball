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
from dotenv import load_dotenv
from app.utils.security_config import (
    CORS_ORIGINS, CORS_METHODS, CORS_ALLOWED_HEADERS,
    CORS_MAX_AGE, add_security_headers
)
from app.config import init_app as init_config, API_KEY
from app.cli import init_app as init_cli
from flask_login import LoginManager
from app.models.user import User
from flask_wtf.csrf import CSRFProtect
from app.middleware.monitoring import init_monitoring
import sys
import re
import time

# Load environment variables from .env file
load_dotenv()

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
        is_local = (
            ('--local' in sys.argv if 'sys.argv' in globals() else False) or
            os.getenv('FORCE_LOCAL', 'false').lower() == 'true'
        ) and not (os.getenv('PROXY_ENABLED') == 'true' or os.getenv('FORCE_PROXY') == 'true')

        if os.getenv('PROXY_ENABLED') == 'true' or os.getenv('FORCE_PROXY') == 'true':
            logger.info("Proxy mode enabled via environment variables")
            is_local = False

        # Determine production mode - if local mode is forced, we're not in production
        is_production = os.getenv('FLASK_ENV') == 'production' and not is_local

        # Set configuration
        app.config.update(
            API_KEY=API_KEY,
            IS_PRODUCTION=is_production,
            IS_LOCAL=is_local,
            FORCE_HTTPS=not is_local,
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
            host = request.host.split(':')[0]
            # Check if request is AJAX/XHR
            is_xhr = request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest'
            
            logger.debug(f"Processing request for host: {host}, scheme: {request.scheme}, is_xhr: {is_xhr}, is_local: {is_local}, is_production: {is_production}")
            
            if is_production and not is_local:  # Only enforce HTTPS in production and not local mode
                # Add security headers
                response = add_security_headers(response)
                
                # Force HTTPS in production, but only for non-local addresses
                if request.scheme == 'https':
                    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
                else:
                    # Check if it's a production domain that needs HTTPS
                    is_prod_domain = any(domain in request.host for domain in ['yunoball.xyz', 'www.yunoball.xyz', 'api.yunoball.xyz'])
                    
                    logger.debug(f"HTTPS redirect check - is_prod_domain: {is_prod_domain}")
                    
                    if is_prod_domain and not is_xhr and request.url.startswith('http://'):
                        logger.debug(f"Redirecting production domain to HTTPS: {request.url}")
                        return redirect(request.url.replace('http://', 'https://', 1), code=301)
            else:
                # In development/local mode
                logger.debug("Development/local mode - using relaxed security headers")
                # Clear any existing HSTS headers to prevent HTTPS forcing
                response.headers.pop('Strict-Transport-Security', None)
                # Add relaxed security headers for local development
                response.headers.update({
                    'X-Frame-Options': 'SAMEORIGIN',
                    'X-XSS-Protection': '1; mode=block',
                    'X-Content-Type-Options': 'nosniff',
                    'Referrer-Policy': 'strict-origin-when-cross-origin'
                })
            
            return response
        
        # Register routes
        try:
            register_blueprints(app)
            logger.info("Blueprints registered successfully")
        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            logger.error(traceback.format_exc())
            
        # Initialize monitoring
        init_monitoring(app)
        logger.info("Monitoring initialized successfully")
        
        # Register context processors
        register_context_processors(app)
        logger.info("Context processors registered successfully")
        
        @app.context_processor
        def inject_css_version():
            css_path = os.path.join(app.static_folder, 'css/output.css')
            css_version = None
            if os.path.exists(css_path):
                with open(css_path, 'r') as f:
                    first_line = f.readline().strip()
                    match = re.search(r'Build: (\d+)', first_line)
                    if match:
                        css_version = match.group(1)
            return {'css_version': css_version or str(int(time.time()))}
        
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
        
        # Add security headers to all responses
        app.after_request(add_security_headers)
        
        logger.info(f"Flask application created successfully in {'production' if is_production else 'development'} mode")
        return app
    except Exception as e:
        logger.error(f"Error creating Flask application: {str(e)}")
        logger.error(traceback.format_exc())
        raise
