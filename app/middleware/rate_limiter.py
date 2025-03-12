from functools import wraps
from flask import request, jsonify, current_app
from app.utils.cache_utils import get_cache, set_cache
import time

def rate_limit(requests_per_minute=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr
            
            # Create Redis key for this IP
            key = f"rate_limit:{client_ip}"
            
            # Get current count
            current = get_cache(key)
            
            if current is None:
                # First request from this IP
                set_cache(key, 1, ex=60)  # 60 seconds expiry
            else:
                # Increment and check limit
                count = int(current)
                if count >= requests_per_minute:
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': 'Too many requests. Please try again later.'
                    }), 429
                
                set_cache(key, count + 1, ex=60)  # Reset after 60 seconds
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Helper function to apply rate limiting to all routes
def apply_global_rate_limiting(app, requests_per_minute=60):
    @app.before_request
    def limit_all_requests():
        # Skip rate limiting for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return None
            
        # Get client IP
        client_ip = request.remote_addr
        key = f"rate_limit:{client_ip}"
        
        current = get_cache(key)
        if current is None:
            set_cache(key, 1, ex=60)
        else:
            count = int(current)
            if count >= requests_per_minute:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': 'Too many requests. Please try again later.'
                }), 429
            set_cache(key, count + 1, ex=60) 