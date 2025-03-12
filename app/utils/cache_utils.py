import json
from flask import current_app as app
from datetime import datetime
import numpy as np

def serialize(obj):
    """Custom serializer for Redis."""
    if isinstance(obj, (datetime, np.int64, np.int32)):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)

def get_cache(key):
    """Retrieve data from Redis cache and deserialize properly."""
    cached_data = app.redis.get(key)
    if cached_data is None:
        return None  # Handle cache miss
    
    try:
        return json.loads(cached_data)  # Convert JSON string back to Python dict
    except json.JSONDecodeError:
        return cached_data  # Return raw data if it's not JSON

def set_cache(key, data, ex=3600):
    """Store data in Redis cache with an expiration time."""
    app.redis.set(key, json.dumps(data, default=serialize), ex=ex)

def invalidate_cache(key):
    """Remove specific cache key."""
    app.redis.delete(key)

# Alias for invalidate_cache to maintain compatibility
delete_cache = invalidate_cache