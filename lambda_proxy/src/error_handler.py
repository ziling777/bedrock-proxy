"""
Unified error handling and logging for the Lambda proxy service.
"""
import json
import logging
import traceback
import time
from typing import Dict, Any, Optional, Union
from enum import Enum
from .openai_client import OpenAIAPIError


class ErrorType(Enum):
    """Error type enumeration."""
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND_ERROR = "not_found_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    API_ERROR = "api_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_ERROR = "connection_error"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN_ERROR = "unknown_error"


class ProxyError(Exception):
    """Custom exception for proxy service errors."""
    
    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = int(time.time())


class ErrorHandler:
    """Centralized error handling and logging."""
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize error handler.
        
        Args:
            logger_name: Name for the logger
        """
        self.logger = logging.getLogger(logger_name)
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        # Configure logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Ensure handler has formatter
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def handle_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle and log exceptions, return API Gateway response.
        
        Args:
            exception: The exception to handle
            context: Additional context information
            request_id: Request ID for tracking
            
        Returns:
            API Gateway error response
        """
        context = context or {}
        
        # Determine error details based on exception type
        if isinstance(exception, ProxyError):
            error_response = self._handle_proxy_error(exception, context, request_id)
        elif isinstance(exception, OpenAIAPIError):
            error_response = self._handle_openai_error(exception, context, request_id)
        elif isinstance(exception, ValueError):
            error_response = self._handle_validation_error(exception, context, request_id)
        elif isinstance(exception, TimeoutError):
            error_response = self._handle_timeout_error(exception, context, request_id)
        elif isinstance(exception, ConnectionError):
            error_response = self._handle_connection_error(exception, context, request_id)
        else:
            error_response = self._handle_unknown_error(exception, context, request_id)
        
        return error_response
    
    def _handle_proxy_error(
        self,
        error: ProxyError,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle ProxyError exceptions."""
        self.logger.error(
            f"Proxy error [{request_id}]: {error.message}",
            extra={
                'error_type': error.error_type.value,
                'status_code': error.status_code,
                'details': error.details,
                'context': context,
                'request_id': request_id
            }
        )
        
        return self._create_error_response(
            status_code=error.status_code,
            message=error.message,
            error_type=error.error_type.value,
            details=error.details,
            request_id=request_id
        )
    
    def _handle_openai_error(
        self,
        error: OpenAIAPIError,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle OpenAI API errors."""
        # Map OpenAI error types to our error types
        error_type_mapping = {
            'invalid_request_error': ErrorType.VALIDATION_ERROR,
            'authentication_error': ErrorType.AUTHENTICATION_ERROR,
            'invalid_api_key': ErrorType.AUTHENTICATION_ERROR,
            'permission_error': ErrorType.AUTHORIZATION_ERROR,
            'not_found_error': ErrorType.NOT_FOUND_ERROR,
            'rate_limit_error': ErrorType.RATE_LIMIT_ERROR,
            'api_error': ErrorType.API_ERROR,
            'timeout_error': ErrorType.TIMEOUT_ERROR,
            'connection_error': ErrorType.CONNECTION_ERROR
        }
        
        mapped_error_type = error_type_mapping.get(
            error.error_type,
            ErrorType.API_ERROR
        )
        
        self.logger.error(
            f"OpenAI API error [{request_id}]: {error.message}",
            extra={
                'error_type': error.error_type,
                'status_code': error.status_code,
                'context': context,
                'request_id': request_id
            }
        )
        
        return self._create_error_response(
            status_code=error.status_code or 500,
            message=f"OpenAI API error: {error.message}",
            error_type=mapped_error_type.value,
            request_id=request_id
        )
    
    def _handle_validation_error(
        self,
        error: ValueError,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle validation errors."""
        self.logger.warning(
            f"Validation error [{request_id}]: {str(error)}",
            extra={
                'context': context,
                'request_id': request_id
            }
        )
        
        return self._create_error_response(
            status_code=400,
            message=str(error),
            error_type=ErrorType.VALIDATION_ERROR.value,
            request_id=request_id
        )
    
    def _handle_timeout_error(
        self,
        error: TimeoutError,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle timeout errors."""
        self.logger.error(
            f"Timeout error [{request_id}]: {str(error)}",
            extra={
                'context': context,
                'request_id': request_id
            }
        )
        
        return self._create_error_response(
            status_code=408,
            message="Request timeout",
            error_type=ErrorType.TIMEOUT_ERROR.value,
            request_id=request_id
        )
    
    def _handle_connection_error(
        self,
        error: ConnectionError,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle connection errors."""
        self.logger.error(
            f"Connection error [{request_id}]: {str(error)}",
            extra={
                'context': context,
                'request_id': request_id
            }
        )
        
        return self._create_error_response(
            status_code=503,
            message="Service temporarily unavailable",
            error_type=ErrorType.CONNECTION_ERROR.value,
            request_id=request_id
        )
    
    def _handle_unknown_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle unknown/unexpected errors."""
        # Log full traceback for unknown errors
        self.logger.error(
            f"Unknown error [{request_id}]: {str(error)}",
            extra={
                'error_type': type(error).__name__,
                'traceback': traceback.format_exc(),
                'context': context,
                'request_id': request_id
            },
            exc_info=True
        )
        
        return self._create_error_response(
            status_code=500,
            message="Internal server error",
            error_type=ErrorType.INTERNAL_ERROR.value,
            request_id=request_id
        )
    
    def _create_error_response(
        self,
        status_code: int,
        message: str,
        error_type: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create standardized error response.
        
        Args:
            status_code: HTTP status code
            message: Error message
            error_type: Error type string
            details: Additional error details
            request_id: Request ID for tracking
            
        Returns:
            API Gateway error response
        """
        error_data = {
            'error': {
                'message': message,
                'type': error_type,
                'code': str(status_code)
            }
        }
        
        # Add details if provided
        if details:
            error_data['error']['details'] = details
        
        # Add request ID if provided
        if request_id:
            error_data['request_id'] = request_id
        
        # Add timestamp
        error_data['timestamp'] = int(time.time())
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            },
            'body': json.dumps(error_data, ensure_ascii=False)
        }
    
    def log_request(
        self,
        method: str,
        path: str,
        request_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Log incoming request.
        
        Args:
            method: HTTP method
            path: Request path
            request_id: Request ID
            user_agent: User agent string
            ip_address: Client IP address
        """
        self.logger.info(
            f"Request [{request_id}]: {method} {path}",
            extra={
                'method': method,
                'path': path,
                'request_id': request_id,
                'user_agent': user_agent,
                'ip_address': ip_address,
                'event_type': 'request_start'
            }
        )
    
    def log_response(
        self,
        status_code: int,
        request_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        response_size: Optional[int] = None
    ):
        """
        Log response.
        
        Args:
            status_code: HTTP status code
            request_id: Request ID
            duration_ms: Request duration in milliseconds
            response_size: Response size in bytes
        """
        self.logger.info(
            f"Response [{request_id}]: {status_code}",
            extra={
                'status_code': status_code,
                'request_id': request_id,
                'duration_ms': duration_ms,
                'response_size': response_size,
                'event_type': 'request_end'
            }
        )
    
    def log_openai_api_call(
        self,
        endpoint: str,
        model: str,
        request_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        tokens_used: Optional[int] = None
    ):
        """
        Log OpenAI API call.
        
        Args:
            endpoint: API endpoint called
            model: Model used
            request_id: Request ID
            duration_ms: API call duration
            tokens_used: Total tokens used
        """
        self.logger.info(
            f"OpenAI API call [{request_id}]: {endpoint} with {model}",
            extra={
                'endpoint': endpoint,
                'model': model,
                'request_id': request_id,
                'duration_ms': duration_ms,
                'tokens_used': tokens_used,
                'event_type': 'openai_api_call'
            }
        )
    
    def log_bedrock_api_call(
        self,
        endpoint: str,
        model: str,
        request_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        tokens_used: Optional[int] = None
    ):
        """
        Log Bedrock API call.
        
        Args:
            endpoint: API endpoint called
            model: Model used
            request_id: Request ID
            duration_ms: API call duration
            tokens_used: Total tokens used
        """
        self.logger.info(
            f"Bedrock API call [{request_id}]: {endpoint} with {model}",
            extra={
                'endpoint': endpoint,
                'model': model,
                'request_id': request_id,
                'duration_ms': duration_ms,
                'tokens_used': tokens_used,
                'event_type': 'bedrock_api_call'
            }
        )
    
    def log_configuration_event(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log configuration-related events.
        
        Args:
            event_type: Type of configuration event
            message: Event message
            details: Additional details
        """
        self.logger.info(
            f"Configuration {event_type}: {message}",
            extra={
                'event_type': f'config_{event_type}',
                'details': details or {}
            }
        )
    
    def create_proxy_error(
        self,
        message: str,
        error_type: ErrorType = ErrorType.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ) -> ProxyError:
        """
        Create a ProxyError instance.
        
        Args:
            message: Error message
            error_type: Error type
            status_code: HTTP status code
            details: Additional details
            
        Returns:
            ProxyError instance
        """
        return ProxyError(
            message=message,
            error_type=error_type,
            status_code=status_code,
            details=details
        )