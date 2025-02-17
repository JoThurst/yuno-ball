"""
Module: cache_utils
===================
This module provides utility functions for caching data using a Redis instance in a Flask application.
It offers methods for serializing complex objects, as well as for setting, retrieving, and invalidating cache entries.
The serialization is tailored to handle specific data types such as datetime objects and NumPy integers.
Functions:
----------
serialize(obj)
    Custom serializer for converting objects to a JSON-serializable form.
    Handles datetime objects and NumPy integer types by converting them to strings, and uses object dictionaries when available.
get_cache(key)
    Retrieves the cached data for the given key from Redis.
    Attempts to deserialize the cached JSON string back into a Python data structure, returning None on a cache miss 
    or raw data if JSON decoding fails.
set_cache(key, data, ex=3600)
    Stores data in the Redis cache under the specified key.
    Serializes the data to JSON using the custom serializer and sets an expiration time (default is 3600 seconds).
invalidate_cache(key)
    Deletes the specific cache entry associated with the given key from Redis.
Dependencies:
-------------
- json: for encoding and decoding JSON strings.
- datetime: to handle datetime objects.
- flask: for accessing the current Flask application instance and its Redis extension.
- numpy: for handling NumPy-specific data types.
"""

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
    cached_data = app.extensions["redis"].get(key)
    if cached_data is None:
        return None  # Handle cache miss

    try:
        return json.loads(s=cached_data)  # Convert JSON string back to Python dict
    except json.JSONDecodeError:
        return cached_data  # Return raw data if it's not JSON


def set_cache(key, data, ex=3600) -> None:
    """Store data in Redis cache with an expiration time."""
    app.extensions["redis"].set(key, json.dumps(obj=data, default=serialize), ex=ex)


def invalidate_cache(key) -> None:
    """Remove specific cache key."""
    app.extensions["redis"].delete(key)
