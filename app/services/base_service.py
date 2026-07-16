"""Base service class with common patterns for all services.

This module provides a BaseService class that encapsulates common functionality
used across all service classes, including caching, session management, error handling,
and response formatting.
"""

import logging
from typing import Optional, Callable, Any, TypeVar, Dict, List
from functools import wraps

from sqlalchemy.orm import Session
from flask import current_app

from app.database import get_db_context
from app.utils.cache_utils import get_cache, set_cache

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseService:
    """Base class for all service classes.
    
    Provides common functionality:
    - Unified cache get/set pattern
    - Session management helpers
    - Error handling decorators
    - Response formatting utilities
    """
    
    @staticmethod
    def get_or_set_cache(
        cache_key: str,
        fetch_func: Callable[[], T],
        ttl: int = 3600,
        use_cache: bool = True
    ) -> T:
        """Get data from cache or fetch and cache it.
        
        Args:
            cache_key: Redis cache key
            fetch_func: Function to call if cache miss (no arguments)
            ttl: Time to live in seconds (default: 3600 = 1 hour)
            use_cache: Whether to use cache (default: True)
        
        Returns:
            Cached or freshly fetched data
        """
        if not use_cache:
            return fetch_func()
        
        # Try to get from cache
        cached_data = get_cache(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache HIT for key: {cache_key}")
            return cached_data
        
        # Cache miss - fetch and cache
        logger.debug(f"Cache MISS for key: {cache_key} - Fetching fresh data")
        data = fetch_func()
        
        if data is not None:
            set_cache(cache_key, data, ex=ttl)
        
        return data
    
    @staticmethod
    def with_db_session(
        func: Callable[[Session], T],
        db: Optional[Session] = None
    ) -> T:
        """Execute a function with a database session.
        
        If a session is provided, use it. Otherwise, create a new session.
        This allows for:
        - Transaction control (reuse session across multiple operations)
        - Testing (inject mock sessions)
        - Performance (reuse session for multiple queries)
        
        Args:
            func: Function that takes a Session as first argument
            db: Optional existing session. If None, creates a new one.
        
        Returns:
            Result of the function execution
        
        Example:
            def get_player(self, player_id: int, db: Optional[Session] = None):
                def _fetch(session):
                    return PlayerORM.get_by_id(player_id, session)
                return self.with_db_session(_fetch, db)
        """
        if db is not None:
            # Use provided session (caller manages lifecycle)
            return func(db)
        else:
            # Create new session (we manage lifecycle)
            with get_db_context() as session:
                return func(session)
    
    @staticmethod
    def handle_errors(func: Callable) -> Callable:
        """Decorator for error handling with logging.
        
        Catches exceptions, logs them, and optionally re-raises or returns None.
        
        Args:
            func: Function to wrap
        
        Returns:
            Wrapped function with error handling
        
        Example:
            @BaseService.handle_errors
            def risky_operation(self):
                # code that might fail
                pass
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}: {str(e)}",
                    exc_info=True,
                    extra={
                        'function': func.__name__,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }
                )
                raise
        
        return wrapper
    
    @staticmethod
    def format_response(
        data: Any,
        formatter: Optional[Callable[[Any], Any]] = None,
        default: Any = None
    ) -> Any:
        """Format response data consistently.
        
        Args:
            data: Data to format
            formatter: Optional formatting function
            default: Default value if data is None/empty
        
        Returns:
            Formatted data or default
        """
        if data is None:
            return default
        
        if formatter is not None:
            return formatter(data)
        
        # Default: convert ORM objects to dict if they have to_dict method
        if hasattr(data, 'to_dict'):
            return data.to_dict()
        
        # If it's a list of ORM objects, convert each
        if isinstance(data, list) and len(data) > 0:
            if hasattr(data[0], 'to_dict'):
                return [item.to_dict() for item in data]
        
        return data
    
    @staticmethod
    def to_dict_list(items: List[Any]) -> List[Dict[str, Any]]:
        """Convert a list of ORM objects to list of dicts.
        
        Args:
            items: List of ORM objects with to_dict() method
        
        Returns:
            List of dictionaries
        """
        if not items:
            return []
        
        return [item.to_dict() if hasattr(item, 'to_dict') else item for item in items]
    
    @staticmethod
    def safe_get(
        data: Dict[str, Any],
        key: str,
        default: Any = None
    ) -> Any:
        """Safely get a value from a dictionary.
        
        Args:
            data: Dictionary to get value from
            key: Key to look up
            default: Default value if key not found
        
        Returns:
            Value or default
        """
        if data is None:
            return default
        return data.get(key, default)
    
    @staticmethod
    def log_cache_operation(operation: str, key: str, hit: bool = False):
        """Log cache operations for debugging.
        
        Args:
            operation: Operation type ('get', 'set', 'invalidate')
            key: Cache key
            hit: Whether it was a cache hit (for 'get' operations)
        """
        status = "HIT" if hit else "MISS"
        logger.debug(f"Cache {operation.upper()}: {status} for key: {key}")

