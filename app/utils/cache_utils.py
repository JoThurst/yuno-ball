import json
from datetime import datetime
from flask import current_app as app

import numpy as np


def serialize(obj):
    """Custom serializer for Redis."""
    if isinstance(obj, (datetime, np.int64, np.int32)):
        return str(object=obj)
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(object=obj)


def get_cache(key):
    """Retrieve data from Redis cache and deserialize properly."""
    cached_data = app.redis.get(key)
    if cached_data is None:
        return None  # Handle cache miss

    try:
        return json.loads(s=cached_data)  # Convert JSON string back to Python dict
    except json.JSONDecodeError:
        return cached_data  # Return raw data if it's not JSON


def set_cache(key, data, ex=3600) -> None:
    """Store data in Redis cache with an expiration time."""
    app.redis.set(key, json.dumps(obj=data, default=serialize), ex=ex)


def invalidate_cache(key) -> None:
    """Remove specific cache key."""
    app.redis.delete(key)
