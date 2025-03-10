"""
Application Factory Module.

This module provides the factory function `create_app` for creating and
configuring the Flask application instance. It initializes the Flask app,
registers blueprints, and sets up any necessary configurations required by the
application.
"""

from flask import Flask
import redis
from app.routes import register_blueprints
import logging
import traceback

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

def create_app():
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

        app.config['REDIS_HOST'] = 'localhost'
        app.config['REDIS_PORT'] = 6379
        app.redis = redis.StrictRedis(host='localhost', port=6379, db=0)
        logger.info("Redis connection established")

        # Register all blueprints
        try:
            register_blueprints(app)
            logger.info("Blueprints registered successfully")
        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            logger.error(traceback.format_exc())
            
        # Register context processors
        register_context_processors(app)
        logger.info("Context processors registered successfully")
        
        # Add error handlers
        @app.errorhandler(404)
        def page_not_found(e):
            logger.warning(f"404 error: {str(e)}")
            return "Page not found", 404
            
        @app.errorhandler(500)
        def internal_server_error(e):
            logger.error(f"500 error: {str(e)}")
            return "Internal server error", 500
            
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception: {str(e)}")
            logger.error(traceback.format_exc())
            return "Internal server error", 500
        
        logger.info("Flask application created successfully")
        return app
    except Exception as e:
        logger.error(f"Error creating Flask application: {str(e)}")
        logger.error(traceback.format_exc())
        raise
