from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from datetime import datetime, timedelta
import random
import logging
import traceback
from app.utils.cache_utils import get_cache, set_cache
from app.middleware.security import secure_endpoint, rate_limit_by_ip

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)

@main_bp.route("/", methods=['GET', 'POST'])
@secure_endpoint()
def welcome():
    """Welcome page for the application."""
    if request.method == 'POST':
        logger.info("Received POST request to root URL")
        logger.info(f"POST data: {request.form}")
        logger.info(f"Headers: {request.headers}")
        # Just return a simple response for POST requests
        return "OK", 200
    
    logger.info("Rendering welcome page")
    try:
        # Simple render - context processor will handle matchups
        return render_template("welcome.html")
    except Exception as e:
        logger.error(f"Error rendering welcome page: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}", 500

@main_bp.route("/home")
@secure_endpoint()
def home_dashboard():
    """Home dashboard with featured games and player stats."""
    logger.info("Rendering home dashboard")
    try:
        # Get dashboard data from service
        from app.services.dashboard_service import get_home_dashboard_data
        
        dashboard_data = get_home_dashboard_data()
        
        return render_template(
            "home_page.html",
            featured_games=dashboard_data.get("featured_games", []),
            games=dashboard_data.get("games", []),
            standings=dashboard_data.get("standings", {}),
            east_standings=dashboard_data.get("standings", {}).get("east", []),
            west_standings=dashboard_data.get("standings", {}).get("west", []),
            featured_streaks=dashboard_data.get("featured_streaks", []),
            player_streaks=dashboard_data.get("player_streaks", []),
            teams=dashboard_data.get("teams", []),
            team_names=dashboard_data.get("team_names", []),
            team_ppg=dashboard_data.get("team_ppg", []),
            team_rpg=dashboard_data.get("team_rpg", []),
            team_apg=dashboard_data.get("team_apg", []),
            team_fg_pct=dashboard_data.get("team_fg_pct", []),
            top_scorers=dashboard_data.get("top_scorers", []),
            top_assisters=dashboard_data.get("top_assisters", []),
            all_players=dashboard_data.get("all_players", []),
            calendar_days=dashboard_data.get("calendar_days", [])
        )
    except Exception as e:
        logger.error(f"Error rendering home dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        return render_template("error.html", error=str(e))

# Context processor moved to app/__init__.py
