import json
from flask import current_app as app
from datetime import datetime
import numpy as np

def serialize(obj):
    """Custom serializer for Redis."""
    if isinstance(obj, (datetime, np.int64, np.int32)):
        return str(obj)
    return obj

def get_cache(key):
    """Retrieve data from Redis cache."""
    cached_data = app.redis.get(key)
    if cached_data:
        return json.loads(cached_data)
    return None

def set_cache(key, data, ex=3600):
    """Store data in Redis cache with an expiration time."""
    app.redis.set(key, json.dumps(data, default=serialize), ex=ex)

def invalidate_cache(key):
    """Remove specific cache key."""
    app.redis.delete(key)