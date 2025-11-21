"""Custom exception classes for the application.

This module defines a hierarchy of custom exceptions that provide
structured error handling with error codes and detailed context.
"""

from typing import Optional, Dict, Any


class AppException(Exception):
    """Base exception for all application errors.
    
    All custom exceptions should inherit from this class to provide
    consistent error handling and structured error responses.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code for API responses
        details: Additional context about the error
    """
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "DATA_NOT_FOUND")
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON responses.
        
        Returns:
            Dictionary representation of the exception
        """
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class DataNotFoundError(AppException):
    """Raised when requested data doesn't exist.
    
    Use this when a resource (player, team, game, etc.) is not found
    in the database or API.
    """
    
    def __init__(self, resource: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        """Initialize the exception.
        
        Args:
            resource: Type of resource (e.g., "Player", "Team", "Game")
            resource_id: Identifier of the missing resource
            details: Optional additional context
        """
        super().__init__(
            message=f"{resource} not found",
            error_code="DATA_NOT_FOUND",
            details={
                "resource": resource,
                "id": resource_id,
                **(details or {})
            }
        )


class APIError(AppException):
    """Raised when external API call fails.
    
    Use this for errors from external APIs (NBA API, etc.)
    including timeouts, rate limits, and invalid responses.
    """
    
    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message describing what went wrong
            api_name: Name of the API that failed (e.g., "NBA API")
            status_code: HTTP status code if applicable
            details: Optional additional context
        """
        error_details = {}
        if api_name:
            error_details["api_name"] = api_name
        if status_code:
            error_details["status_code"] = status_code
        if details:
            error_details.update(details)
        
        super().__init__(
            message=message,
            error_code="API_ERROR",
            details=error_details
        )


class ValidationError(AppException):
    """Raised when data validation fails.
    
    Use this for input validation errors, schema validation,
    or data format issues.
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message describing the validation failure
            field: Name of the field that failed validation
            value: The invalid value
            details: Optional additional context
        """
        error_details = {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)
        if details:
            error_details.update(details)
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=error_details
        )


class DatabaseError(AppException):
    """Raised when database operations fail.
    
    Use this for connection errors, query failures, or transaction issues.
    """
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message describing the database error
            operation: The database operation that failed (e.g., "SELECT", "INSERT")
            details: Optional additional context
        """
        error_details = {}
        if operation:
            error_details["operation"] = operation
        if details:
            error_details.update(details)
        
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=error_details
        )


class AuthenticationError(AppException):
    """Raised when authentication fails.
    
    Use this for login failures, invalid tokens, or unauthorized access.
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message describing the authentication failure
            reason: Specific reason for failure (e.g., "invalid_credentials", "token_expired")
            details: Optional additional context
        """
        error_details = {}
        if reason:
            error_details["reason"] = reason
        if details:
            error_details.update(details)
        
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=error_details
        )


class AuthorizationError(AppException):
    """Raised when user lacks permission for an operation.
    
    Use this when a user is authenticated but doesn't have
    the required permissions.
    """
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message describing the authorization failure
            required_permission: The permission that was required
            details: Optional additional context
        """
        error_details = {}
        if required_permission:
            error_details["required_permission"] = required_permission
        if details:
            error_details.update(details)
        
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=error_details
        )

