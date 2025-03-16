from flask import Blueprint
import logging

from app.routes.main_routes import main_bp
from app.routes.player_routes import player_bp
from app.routes.team_routes import team_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.api_routes import api_bp

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register all blueprints with the Flask application."""
    logger.info("Registering blueprints...")
    
    logger.info("Registering main_bp...")
    app.register_blueprint(main_bp)
    
    logger.info("Registering player_bp...")
    app.register_blueprint(player_bp)
    
    logger.info("Registering team_bp...")
    app.register_blueprint(team_bp)
    
    logger.info("Registering dashboard_bp...")
    app.register_blueprint(dashboard_bp)
    
    logger.info("Registering api_bp...")
    app.register_blueprint(api_bp)
    
    logger.info("All blueprints registered successfully!")
