from functools import wraps
from flask import request, jsonify, current_app
import jwt
from app.models.user import User
import logging
from datetime import datetime
from app.utils.cache_utils import get_cache, set_cache
from app.utils.rate_limiter import check_login_attempts, reset_login_attempts

def get_token_from_header():
    """Extract JWT token from the Authorization header."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    return auth_header.split(' ')[1]

def verify_jwt_token(token):
    """
    Verify JWT token and return decoded payload.
    
    Args:
        token (str): JWT token to verify
        
    Returns:
        dict: Decoded token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        
        # Check if token is expired
        exp = payload.get('exp')
        if exp and datetime.utcnow().timestamp() > exp:
            return None
            
        return payload
    except jwt.InvalidTokenError as e:
        logging.error(f"Invalid token: {e}")
        return None

def login_required(f):
    """Decorator to require valid JWT token for access."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = get_token_from_header()
        if not token:
            return jsonify({"error": "No token provided"}), 401
            
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
            
        # Add user info to request context
        request.user = User.get_user_by_id(payload['user_id'])
        if not request.user:
            return jsonify({"error": "User not found"}), 401
            
        if not request.user['is_active']:
            return jsonify({"error": "User account is deactivated"}), 401
            
        # Check if token needs refresh
        new_token = refresh_token()
        response = f(*args, **kwargs)
        
        # If response is a tuple (response, status_code)
        if isinstance(response, tuple):
            response_obj, status_code = response
            if new_token and isinstance(response_obj, dict):
                response_obj['new_token'] = new_token
            return response_obj, status_code
            
        # If response is just the response object
        if new_token and isinstance(response, dict):
            response['new_token'] = new_token
        return response
        
    return wrapped

def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not request.user['is_admin']:
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)
    return wrapped

def refresh_token():
    """
    Refresh JWT token if it's about to expire.
    Should be called after login_required to ensure request.user exists.
    """
    token = get_token_from_header()
    if not token:
        return None
        
    payload = verify_jwt_token(token)
    if not payload:
        return None
        
    # Check if token needs refresh (e.g., if it expires in less than 1 hour)
    exp = payload.get('exp')
    if not exp or (exp - datetime.utcnow().timestamp()) > 3600:
        return None
        
    # Generate new token
    new_token = jwt.encode(
        {
            'user_id': request.user['user_id'],
            'username': request.user['username'],
            'is_admin': request.user['is_admin'],
            'exp': datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    
    return new_token

def optional_auth(f):
    """
    Decorator to optionally authenticate user.
    Useful for endpoints that work both with and without authentication.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = get_token_from_header()
        if token:
            payload = verify_jwt_token(token)
            if payload:
                request.user = User.get_user_by_id(payload['user_id'])
            else:
                request.user = None
        else:
            request.user = None
        return f(*args, **kwargs)
    return wrapped 