"""Structured logging configuration.

This module configures structlog for structured JSON logging
with request correlation IDs and consistent formatting.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import Processor


def configure_structlog(enable_json: bool = True) -> None:
    """Configure structlog for structured logging.
    
    Simple configuration that works reliably with PrintLoggerFactory.
    
    Args:
        enable_json: If True, output JSON format. If False, use console-friendly format.
    """
    # Configure processors for structlog (no stdlib-specific processors)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context variables
        structlog.processors.add_log_level,  # Add log level (not stdlib version)
        structlog.processors.StackInfoRenderer(),  # Add stack info
        structlog.processors.format_exc_info,  # Format exceptions
    ]
    
    # Choose renderer based on environment
    if enable_json:
        # JSON output for production
        renderer = structlog.processors.JSONRenderer()
        timestamper = structlog.processors.TimeStamper(fmt="iso")
    else:
        # Console-friendly output for development
        renderer = structlog.dev.ConsoleRenderer(colors=True)
        timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
    
    # Configure structlog with PrintLoggerFactory (simple and reliable)
    structlog.configure(
        processors=shared_processors + [timestamper, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Note: Standard logging.getLogger() calls will still work with their own format
    # Modules using get_logger() from this module will use structlog


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog logger
        
    Example:
        logger = get_logger(__name__)
        logger.info("user_login", user_id=123, ip_address="192.168.1.1")
    """
    return structlog.get_logger(name)


def add_request_context(request_id: str, **kwargs: Any) -> None:
    """Add context variables to all logs in the current request.
    
    Args:
        request_id: Unique request identifier
        **kwargs: Additional context variables
        
    Example:
        add_request_context(
            request_id="abc123",
            user_id=456,
            endpoint="/api/players"
        )
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, **kwargs)


def clear_request_context() -> None:
    """Clear all request context variables."""
    structlog.contextvars.clear_contextvars()

