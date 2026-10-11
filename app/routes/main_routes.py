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
    """Retire the duplicate home dashboard in favor of Daily Intelligence."""
    params = {
        key: request.args.get(key)
        for key in ("date", "season")
        if request.args.get(key)
    }
    return redirect(url_for("daily.fan_daily", **params), code=302)


@main_bp.route("/games", strict_slashes=False)
@secure_endpoint()
def games_lookup():
    """Canonical read-only historical game lookup surface."""
    from app.services.daily_archive_service import build_daily_archive_index

    try:
        page = build_daily_archive_index(
            season=request.args.get("season") or None,
            limit=request.args.get("limit", 12),
            offset=request.args.get("offset", 0),
        )
        return render_template("games_lookup.html", **page)
    except (TypeError, ValueError):
        return render_template("error.html", error="limit and offset must be numeric"), 400
    except Exception as exc:
        logger.exception("Games lookup failed")
        return render_template("error.html", error=str(exc)), 500


@main_bp.route("/teams", strict_slashes=False)
def legacy_teams_list():
    """Preserve the pre-blueprint team list URL while callers migrate."""
    return redirect(url_for("team.teams"))


@main_bp.route("/teams/<int:team_id>", strict_slashes=False)
def legacy_team_detail(team_id):
    """Preserve the pre-blueprint team detail URL while callers migrate."""
    return redirect(url_for("team.team_detail", team_id=team_id))


@main_bp.route("/teams/<int:team_id>/stats-visuals", strict_slashes=False)
def legacy_team_stats_visuals(team_id):
    """Preserve the legacy team visual route during the route cleanup."""
    return redirect(url_for("team.team_detail", team_id=team_id), code=302)


@main_bp.route("/games-dashboard", strict_slashes=False)
def legacy_games_dashboard():
    """Preserve the pre-blueprint games dashboard URL."""
    return redirect(url_for("main.games_lookup"), code=302)


@main_bp.route("/matchup/<int:team1_id>/<int:team2_id>", strict_slashes=False)
def legacy_matchup(team1_id, team2_id):
    """Retire the non-date-scoped matchup flow without breaking old links."""
    return redirect(url_for("daily.fan_daily"), code=302)

# Context processor moved to app/__init__.py
