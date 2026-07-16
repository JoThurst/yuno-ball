"""
Application Factory Module.

This module provides the factory function `create_app` for creating and
configuring the Flask application instance. It initializes the Flask app,
registers blueprints, and sets up any necessary configurations required by the
application.
"""

from flask import Flask, request, redirect, g, jsonify
from flask_cors import CORS
import redis
from app.routes import register_blueprints
import logging
import traceback
import os
import uuid
from dotenv import load_dotenv
from app.utils.security_config import (
    CORS_ORIGINS, CORS_METHODS, CORS_ALLOWED_HEADERS,
    CORS_MAX_AGE, add_security_headers
)
from app.config import init_app as init_config, API_KEY
from app.cli import init_app as init_cli
from flask_login import LoginManager
from app.models.user_sqlalchemy import UserORM
from flask_wtf.csrf import CSRFProtect
from app.middleware.monitoring import init_monitoring
from app.exceptions import (
    AppException, DataNotFoundError, APIError, 
    ValidationError, DatabaseError, AuthenticationError, AuthorizationError
)
from app.utils.logging_config import (
    configure_structlog, get_logger, add_request_context, clear_request_context
)
import sys
import re
import time

# Load environment variables from .env file
load_dotenv()

# Configure structured logging FIRST, before any other imports that use logging
# Use JSON in production, console-friendly in development
is_prod_env = os.getenv('FLASK_ENV') == 'production'
configure_structlog(enable_json=is_prod_env)

# Get structured logger
logger = get_logger(__name__)

# Note: Other modules may still call logging.basicConfig(), but structlog
# is configured to work with standard logging, so both will work together.

# Initialize Sentry for error monitoring (optional)
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            environment=os.getenv('FLASK_ENV', 'development'),
            traces_sample_rate=0.1,  # 10% of requests traced
            profiles_sample_rate=0.1,  # 10% of requests profiled
        )
        logger.info("sentry_initialized")
    else:
        logger.info("sentry_disabled", reason="DSN not configured")
except ImportError:
    logger.warning("sentry_disabled", reason="sentry-sdk not installed")
except Exception as e:
    logger.warning("sentry_init_failed", error=str(e))

def register_context_processors(app):
    """Register context processors at the application level."""
    logger.info("registering_context_processors")
    
    @app.context_processor
    def inject_today_matchups():
        """Inject today's matchups into all templates."""
        logger.debug("injecting_matchups")
        try:
            # Get today's matchups from service
            from app.services.dashboard_service import get_today_matchups
            
            today_matchups = get_today_matchups()
            return {"today_matchups": today_matchups}
        except Exception as e:
            logger.error("matchup_injection_failed", error=str(e))
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
    logger.info("creating_flask_app")
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
            logger.info("proxy_mode_enabled")
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
        logger.info("redis_connected")

        # Initialize Flask-Login
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message_category = 'info'

        @login_manager.user_loader
        def load_user(user_id):
            return UserORM.get_by_id(int(user_id))

        # Register request tracing middleware (before security headers)
        @app.before_request
        def before_request():
            """Add request tracing and context."""
            # Generate or use existing request ID
            request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
            g.request_id = request_id
            g.start_time = time.time()
            
            # Add request context to structured logging
            add_request_context(
                request_id=request_id,
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'unknown')
            )
            
            logger.info(
                "request_start",
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr
            )
        
        # Register security headers and request tracing
        @app.after_request
        def after_request(response):
            # Request tracing: Calculate duration and log completion
            if hasattr(g, 'start_time'):
                duration = time.time() - g.start_time
                duration_ms = duration * 1000
            else:
                duration_ms = 0
            
            # Add request ID to response header
            if hasattr(g, 'request_id'):
                response.headers['X-Request-ID'] = g.request_id
            
            # Log request completion
            logger.info(
                "request_end",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
            # Security headers and HTTPS enforcement
            host = request.host.split(':')[0]
            # Check if request is AJAX/XHR
            is_xhr = request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest'
            
            logger.debug("processing_request", host=host, scheme=request.scheme, is_xhr=is_xhr, is_local=is_local, is_production=is_production)
            
            if is_production and not is_local:  # Only enforce HTTPS in production and not local mode
                # Add security headers
                response = add_security_headers(response)
                
                # Force HTTPS in production, but only for non-local addresses
                if request.scheme == 'https':
                    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
                else:
                    # Check if it's a production domain that needs HTTPS
                    is_prod_domain = any(domain in request.host for domain in ['yunoball.xyz', 'www.yunoball.xyz', 'api.yunoball.xyz'])
                    
                    logger.debug("https_redirect_check", is_prod_domain=is_prod_domain)
                    
                    if is_prod_domain and not is_xhr and request.url.startswith('http://'):
                        logger.debug("redirecting_to_https", url=request.url)
                        return redirect(request.url.replace('http://', 'https://', 1), code=301)
            else:
                # In development/local mode
                logger.debug("development_mode", note="using relaxed security headers")
                # Clear any existing HSTS headers to prevent HTTPS forcing
                response.headers.pop('Strict-Transport-Security', None)
                # Add relaxed security headers for local development
                response.headers.update({
                    'X-Frame-Options': 'SAMEORIGIN',
                    'X-XSS-Protection': '1; mode=block',
                    'X-Content-Type-Options': 'nosniff',
                    'Referrer-Policy': 'strict-origin-when-cross-origin'
                })
            
            # Clear request context after response
            clear_request_context()
            
            return response
        
        # Register routes
        try:
            register_blueprints(app)
            logger.info("blueprints_registered")
        except Exception as e:
            logger.error("blueprint_registration_failed", error=str(e), exc_info=True)
            
        # Initialize monitoring
        init_monitoring(app)
        logger.info("monitoring_initialized")
        
        # Register context processors
        register_context_processors(app)
        logger.info("context_processors_registered")
        
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
        
        # Register error handlers with custom exceptions
        @app.errorhandler(404)
        def not_found(error):
            request_id = getattr(g, 'request_id', 'unknown')
            logger.warning(
                "resource_not_found",
                path=request.path,
                method=request.method,
                request_id=request_id
            )
            return jsonify({
                'error': 'RESOURCE_NOT_FOUND',
                'message': 'Resource not found',
                'request_id': request_id
            }), 404
        
        @app.errorhandler(AppException)
        def handle_app_exception(error: AppException):
            """Handle custom application exceptions."""
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.error(
                "application_error",
                error_code=error.error_code,
                message=error.message,
                details=error.details,
                request_id=request_id,
                exc_info=True
            )
            
            # Sentry will automatically capture this if configured
            return jsonify({
                'error': error.error_code,
                'message': error.message,
                'details': error.details,
                'request_id': request_id
            }), 400
        
        @app.errorhandler(500)
        def server_error(error):
            request_id = getattr(g, 'request_id', 'unknown')
            logger.error(
                "internal_server_error",
                error=str(error),
                request_id=request_id,
                exc_info=True
            )
            return jsonify({
                'error': 'INTERNAL_SERVER_ERROR',
                'message': 'An internal server error occurred',
                'request_id': request_id
            }), 500
        
        @app.errorhandler(Exception)
        def handle_unexpected_exception(e: Exception):
            """Handle unexpected exceptions that aren't AppException subclasses."""
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.error(
                "unexpected_error",
                error_type=type(e).__name__,
                error_message=str(e),
                request_id=request_id,
                exc_info=True
            )
            
            # Sentry will automatically capture this if configured
            return jsonify({
                'error': 'INTERNAL_ERROR',
                'message': 'An unexpected error occurred',
                'request_id': request_id
            }), 500
        
        # Note: Security headers are already added in after_request handler above
        
        logger.info("flask_app_created", mode="production" if is_production else "development")
        return app
    except Exception as e:
        logger.error("flask_app_creation_failed", error=str(e), exc_info=True)
        raise
