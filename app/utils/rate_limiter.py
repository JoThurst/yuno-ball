from app.utils.cache_utils import get_cache, set_cache
from flask import current_app

def check_login_attempts(username):
    """Check and update login attempts for a user."""
    key = f"login_attempts:{username}"
    attempts = get_cache(key)
    
    if attempts is None:
        # First attempt
        set_cache(key, 1, ex=300)  # 5 minutes expiry
        return True
    
    attempts = int(attempts)
    if attempts >= 5:  # Max 5 attempts per 5 minutes
        return False
        
    set_cache(key, attempts + 1, ex=300)
    return True

def reset_login_attempts(username):
    """Reset login attempts after successful login."""
    key = f"login_attempts:{username}"
    set_cache(key, 0, ex=300)

def check_rate_limit(key, max_attempts, window_seconds):
    """
    Generic rate limiting function.
    
    Args:
        key (str): Unique key for the rate limit (e.g., "password_reset:user@email.com")
        max_attempts (int): Maximum number of attempts allowed
        window_seconds (int): Time window in seconds
        
    Returns:
        bool: True if under rate limit, False if rate limit exceeded
    """
    # Skip rate limiting if disabled in config
    if not current_app.config.get('RATELIMIT_ENABLED', True):
        return True
        
    attempts = get_cache(key)
    
    if attempts is None:
        set_cache(key, 1, ex=window_seconds)
        return True
    
    attempts = int(attempts)
    if attempts >= max_attempts:
        return False
        
    set_cache(key, attempts + 1, ex=window_seconds)
    return True

def reset_rate_limit(key):
    """Reset rate limit counter for a given key."""
    set_cache(key, 0, ex=300)  # Keep the key alive for 5 minutes 

def increment_rate_limit(key, window_seconds=300):
    """
    Increment the rate limit counter for a given key.
    
    Args:
        key (str): Unique key for the rate limit (e.g., "password_reset:user@email.com")
        window_seconds (int): Time window in seconds (default: 300 seconds / 5 minutes)
        
    Returns:
        int: New number of attempts
    """
    attempts = get_cache(key)
    
    if attempts is None:
        new_attempts = 1
    else:
        new_attempts = int(attempts) + 1
        
    set_cache(key, new_attempts, ex=window_seconds)
    return new_attempts 