from functools import wraps
from flask import request, jsonify, current_app
import re
from app.utils.security_config import sanitize_input, is_valid_path

def validate_player_id(player_id):
    """Validate player ID format"""
    try:
        player_id = int(player_id)
        return 0 < player_id < 10000000  # Reasonable range for player IDs
    except (ValueError, TypeError):
        return False

def validate_team_id(team_id):
    """Validate team ID format"""
    try:
        team_id = int(team_id)
        return 1610600000 < team_id < 1610612800  # NBA Team range ID 16106127XX
    except (ValueError, TypeError):
        return False

def validate_season(season):
    """Validate season format (e.g., '2024-25')"""
    pattern = r'^\d{4}-\d{2}$'
    if not season or not re.match(pattern, season):
        return False
    year = int(season.split('-')[0])
    return 2010 <= year <= 2025  # Valid range for seasons

def secure_endpoint():
    """Decorator to add security checks to endpoints"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Validate player IDs
            player_id = request.args.get('player_id') or kwargs.get('player_id')
            if player_id and not validate_player_id(player_id):
                return jsonify({"error": "Invalid player ID"}), 400

            # Validate team IDs
            team_id = request.args.get('team_id') or kwargs.get('team_id')
            if team_id and not validate_team_id(team_id):
                return jsonify({"error": "Invalid team ID"}), 400

            # Validate season format
            season = request.args.get('season')
            if season and not validate_season(season):
                return jsonify({"error": "Invalid season format"}), 400

            # Sanitize query parameters
            for key, value in request.args.items():
                request.args = request.args.copy()
                request.args[key] = sanitize_input(value)

            # Validate file paths if present
            path = request.args.get('path')
            if path and not is_valid_path(path):
                return jsonify({"error": "Invalid file path"}), 400

            return f(*args, **kwargs)
        return wrapped
    return decorator

def api_key_required():
    """Decorator to require API key for sensitive endpoints"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if not api_key or api_key != current_app.config.get('API_KEY'):
                return jsonify({"error": "Invalid or missing API key"}), 401
            return f(*args, **kwargs)
        return wrapped
    return decorator

def rate_limit_by_ip():
    """Decorator to apply rate limiting by IP address"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from app.middleware.rate_limiter import rate_limit
            return rate_limit(requests_per_minute=60)(f)(*args, **kwargs)
        return wrapped
    return decorator 