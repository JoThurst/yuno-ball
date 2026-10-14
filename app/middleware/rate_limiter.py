from functools import wraps
from flask import request, jsonify, current_app
from app.utils.cache_utils import get_cache, set_cache
import time
from collections import deque
from threading import Lock

_readiness_hits = {}
_readiness_hits_lock = Lock()


def _allow_readiness_probe(client_ip, *, now=None, limit=10, window_seconds=60):
    """Bound readiness probes per process even when Redis is unavailable."""
    now = time.monotonic() if now is None else now
    with _readiness_hits_lock:
        hits = _readiness_hits.get(client_ip)
        if hits is None:
            if len(_readiness_hits) >= 4096:
                _readiness_hits.pop(next(iter(_readiness_hits)))
            hits = deque()
            _readiness_hits[client_ip] = hits
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

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
        # Keep static assets cheap; readiness still probes PostgreSQL and Redis.
        if request.path.startswith('/static/') or request.path == '/health':
            return None

        if request.path == '/health/ready' and not _allow_readiness_probe(request.remote_addr):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'Too many readiness requests. Please try again later.'
            }), 429
            
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
