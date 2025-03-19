from flask import request, current_app, g
from functools import wraps
import os
import secrets

# CORS Configuration
CORS_ORIGINS = [
    'http://localhost:3000',     # Local development
    'http://localhost:8000',     # Local Flask server
    'https://yunoball.xyz',      # Production domain 
    'https://www.yunoball.xyz',  # Production www subdomain
    'https://api.yunoball.xyz'   # API subdomain
]

CORS_METHODS = ['GET', 'POST', 'OPTIONS']
CORS_ALLOWED_HEADERS = [
    'Content-Type',
    'Authorization',
    'X-API-Key',
    'X-Requested-With',
    'Accept',
    'Origin'
]

# Maximum age for CORS preflight requests (in seconds)
CORS_MAX_AGE = 3600  # 1 hour

# Production Security Headers with enhanced CSP
PROD_SECURITY_HEADERS = {
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'X-Content-Type-Options': 'nosniff',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Content-Security-Policy': "\
        default-src 'self'; \
        script-src 'self' 'unsafe-inline' 'unsafe-eval'; \
        style-src 'self' 'unsafe-inline'; \
        img-src 'self' data: stats.nba.com *.nba.com; \
        font-src 'self' data:; \
        connect-src 'self' stats.nba.com api.yunoball.xyz; \
        frame-ancestors 'none'; \
        form-action 'self'; \
        base-uri 'self'; \
        object-src 'none'"
}

# Development Security Headers with relaxed CSP
DEV_SECURITY_HEADERS = {
    'X-Frame-Options': 'SAMEORIGIN',
    'X-XSS-Protection': '1; mode=block',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': "\
        default-src 'self'; \
        script-src 'self' 'unsafe-inline' 'unsafe-eval'; \
        style-src 'self' 'unsafe-inline'; \
        img-src 'self' data: stats.nba.com *.nba.com; \
        connect-src 'self' stats.nba.com api.yunoball.xyz ws: wss:; \
        frame-ancestors 'self'"
}

def get_request_nonce():
    """Get or create nonce for the current request"""
    if not hasattr(g, 'csp_nonce'):
        g.csp_nonce = secrets.token_urlsafe(32)
    return g.csp_nonce

def get_csp_headers():
    """Get Content Security Policy headers"""
    if current_app.config.get('IS_PRODUCTION', False):
        return PROD_SECURITY_HEADERS.copy()
    else:
        return DEV_SECURITY_HEADERS

def add_security_headers(response):
    """Add security headers to response"""
    headers = get_csp_headers()
    for header, value in headers.items():
        response.headers[header] = value
    return response

def validate_request_data():
    """Validate and sanitize request data"""
    if request.is_json:
        data = request.get_json()
        # Add validation logic here
        return data
    return None

def require_api_key(f):
    """Decorator to require API key for routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != current_app.config.get('API_KEY'):
            return {'error': 'Invalid API key'}, 401
        return f(*args, **kwargs)
    return decorated

def sanitize_input(data):
    """Sanitize user input"""
    if isinstance(data, str):
        # Remove potential script tags and other dangerous content
        data = data.replace('<script>', '').replace('</script>', '')
        # Add more sanitization as needed
    return data

def is_valid_path(path):
    """Check if a file path is valid and safe"""
    # Prevent directory traversal
    return not any(c in path for c in ['..', '~', '/']) 