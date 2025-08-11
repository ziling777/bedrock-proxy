"""
Tests for ErrorHandler.
"""
import json
import pytest
import logging
from unittest.mock import Mock, patch

from src.error_handler import ErrorHandler, ProxyError, ErrorType
from src.openai_client import OpenAIAPIError


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler('test_logger')
    
    def test_initialization(self):
        """Test error handler initialization."""
        assert self.error_handler.logger.name == 'test_logger'
        assert len(self.error_handler.logger.handlers) > 0
    
    def test_handle_proxy_error(self):
        """Test handling ProxyError exceptions."""
        error = ProxyError(
            message="Test proxy error",
            error_type=ErrorType.VALIDATION_ERROR,
            status_code=400,
            details={'field': 'invalid'}
        )
        
        with patch.object(self.error_handler.logger, 'error') as mock_log:
            response = self.error_handler.handle_exception(
                error,
                context={'test': 'context'},
                request_id='req-123'
            )
        
        # Check logging
        mock_log.assert_called_once()
        
        # Check response
        assert response['statusCode'] == 400
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Test proxy error"
        assert response_body['error']['type'] == 'validation_error'
        assert response_body['error']['details']['field'] == 'invalid'
        assert response_body['request_id'] == 'req-123'
    
    def test_handle_openai_error(self):
        """Test handling OpenAI API errors."""
        error = OpenAIAPIError(
            message="Invalid API key",
            status_code=401,
            error_type="authentication_error"
        )
        
        with patch.object(self.error_handler.logger, 'error') as mock_log:
            response = self.error_handler.handle_exception(
                error,
                request_id='req-456'
            )
        
        # Check logging
        mock_log.assert_called_once()
        
        # Check response
        assert response['statusCode'] == 401
        response_body = json.loads(response['body'])
        assert "OpenAI API error" in response_body['error']['message']
        assert response_body['error']['type'] == 'authentication_error'
    
    def test_handle_validation_error(self):
        """Test handling ValueError exceptions."""
        error = ValueError("Invalid request format")
        
        with patch.object(self.error_handler.logger, 'warning') as mock_log:
            response = self.error_handler.handle_exception(error)
        
        # Check logging
        mock_log.assert_called_once()
        
        # Check response
        assert response['statusCode'] == 400
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Invalid request format"
        assert response_body['error']['type'] == 'validation_error'
    
    def test_handle_timeout_error(self):
        """Test handling TimeoutError exceptions."""
        error = TimeoutError("Request timed out")
        
        with patch.object(self.error_handler.logger, 'error') as mock_log:
            response = self.error_handler.handle_exception(error)
        
        # Check logging
        mock_log.assert_called_once()
        
        # Check response
        assert response['statusCode'] == 408
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Request timeout"
        assert response_body['error']['type'] == 'timeout_error'
    
    def test_handle_connection_error(self):
        """Test handling ConnectionError exceptions."""
        error = ConnectionError("Connection failed")
        
        with patch.object(self.error_handler.logger, 'error') as mock_log:
            response = self.error_handler.handle_exception(error)
        
        # Check logging
        mock_log.assert_called_once()
        
        # Check response
        assert response['statusCode'] == 503
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Service temporarily unavailable"
        assert response_body['error']['type'] == 'connection_error'
    
    def test_handle_unknown_error(self):
        """Test handling unknown exceptions."""
        error = RuntimeError("Unexpected error")
        
        with patch.object(self.error_handler.logger, 'error') as mock_log:
            response = self.error_handler.handle_exception(error)
        
        # Check logging with traceback
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'traceback' in call_args[1]['extra']
        
        # Check response
        assert response['statusCode'] == 500
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Internal server error"
        assert response_body['error']['type'] == 'internal_error'
    
    def test_log_request(self):
        """Test request logging."""
        with patch.object(self.error_handler.logger, 'info') as mock_log:
            self.error_handler.log_request(
                method='POST',
                path='/v1/chat/completions',
                request_id='req-789',
                user_agent='test-agent',
                ip_address='192.168.1.1'
            )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Request [req-789]: POST /v1/chat/completions' in call_args[0][0]
        assert call_args[1]['extra']['event_type'] == 'request_start'
        assert call_args[1]['extra']['method'] == 'POST'
        assert call_args[1]['extra']['path'] == '/v1/chat/completions'
    
    def test_log_response(self):
        """Test response logging."""
        with patch.object(self.error_handler.logger, 'info') as mock_log:
            self.error_handler.log_response(
                status_code=200,
                request_id='req-789',
                duration_ms=150.5,
                response_size=1024
            )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Response [req-789]: 200' in call_args[0][0]
        assert call_args[1]['extra']['event_type'] == 'request_end'
        assert call_args[1]['extra']['status_code'] == 200
        assert call_args[1]['extra']['duration_ms'] == 150.5
    
    def test_log_openai_api_call(self):
        """Test OpenAI API call logging."""
        with patch.object(self.error_handler.logger, 'info') as mock_log:
            self.error_handler.log_openai_api_call(
                endpoint='/chat/completions',
                model='gpt-4o-mini',
                request_id='req-789',
                duration_ms=2500.0,
                tokens_used=150
            )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'OpenAI API call [req-789]: /chat/completions with gpt-4o-mini' in call_args[0][0]
        assert call_args[1]['extra']['event_type'] == 'openai_api_call'
        assert call_args[1]['extra']['model'] == 'gpt-4o-mini'
        assert call_args[1]['extra']['tokens_used'] == 150
    
    def test_log_configuration_event(self):
        """Test configuration event logging."""
        with patch.object(self.error_handler.logger, 'info') as mock_log:
            self.error_handler.log_configuration_event(
                event_type='loaded',
                message='Configuration loaded successfully',
                details={'source': 'secrets_manager'}
            )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Configuration loaded: Configuration loaded successfully' in call_args[0][0]
        assert call_args[1]['extra']['event_type'] == 'config_loaded'
        assert call_args[1]['extra']['details']['source'] == 'secrets_manager'
    
    def test_create_proxy_error(self):
        """Test creating ProxyError instances."""
        error = self.error_handler.create_proxy_error(
            message="Test error",
            error_type=ErrorType.AUTHENTICATION_ERROR,
            status_code=401,
            details={'reason': 'invalid_token'}
        )
        
        assert isinstance(error, ProxyError)
        assert error.message == "Test error"
        assert error.error_type == ErrorType.AUTHENTICATION_ERROR
        assert error.status_code == 401
        assert error.details['reason'] == 'invalid_token'
        assert error.timestamp > 0
    
    def test_create_error_response_minimal(self):
        """Test creating error response with minimal parameters."""
        response = self.error_handler._create_error_response(
            status_code=400,
            message="Bad request",
            error_type="validation_error"
        )
        
        assert response['statusCode'] == 400
        assert 'Content-Type' in response['headers']
        assert 'Access-Control-Allow-Origin' in response['headers']
        
        response_body = json.loads(response['body'])
        assert response_body['error']['message'] == "Bad request"
        assert response_body['error']['type'] == "validation_error"
        assert response_body['error']['code'] == "400"
        assert 'timestamp' in response_body
    
    def test_create_error_response_full(self):
        """Test creating error response with all parameters."""
        response = self.error_handler._create_error_response(
            status_code=422,
            message="Validation failed",
            error_type="validation_error",
            details={'field': 'email', 'issue': 'invalid_format'},
            request_id='req-999'
        )
        
        response_body = json.loads(response['body'])
        assert response_body['error']['details']['field'] == 'email'
        assert response_body['request_id'] == 'req-999'
    
    def test_openai_error_type_mapping(self):
        """Test OpenAI error type mapping."""
        test_cases = [
            ('invalid_request_error', 'validation_error'),
            ('authentication_error', 'authentication_error'),
            ('permission_error', 'authorization_error'),
            ('not_found_error', 'not_found_error'),
            ('rate_limit_error', 'rate_limit_error'),
            ('unknown_openai_error', 'api_error')  # fallback
        ]
        
        for openai_type, expected_type in test_cases:
            error = OpenAIAPIError("Test", 400, openai_type)
            
            with patch.object(self.error_handler.logger, 'error'):
                response = self.error_handler.handle_exception(error)
            
            response_body = json.loads(response['body'])
            assert response_body['error']['type'] == expected_type
    
    def test_error_response_cors_headers(self):
        """Test that error responses include CORS headers."""
        error = ValueError("Test error")
        
        with patch.object(self.error_handler.logger, 'warning'):
            response = self.error_handler.handle_exception(error)
        
        headers = response['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'GET, POST, OPTIONS' in headers['Access-Control-Allow-Methods']
        assert 'Content-Type, Authorization' in headers['Access-Control-Allow-Headers']
    
    def test_logging_setup(self):
        """Test logging setup configuration."""
        # Create new handler to test setup
        handler = ErrorHandler('test_setup')
        
        # Check that logger has handlers
        assert len(handler.logger.handlers) > 0
        
        # Check formatter is set
        for log_handler in handler.logger.handlers:
            assert log_handler.formatter is not None


class TestProxyError:
    """Test cases for ProxyError."""
    
    def test_proxy_error_creation(self):
        """Test ProxyError creation."""
        error = ProxyError(
            message="Test error",
            error_type=ErrorType.VALIDATION_ERROR,
            status_code=400,
            details={'field': 'test'}
        )
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_type == ErrorType.VALIDATION_ERROR
        assert error.status_code == 400
        assert error.details['field'] == 'test'
        assert error.timestamp > 0
    
    def test_proxy_error_defaults(self):
        """Test ProxyError with default values."""
        error = ProxyError("Default error")
        
        assert error.error_type == ErrorType.INTERNAL_ERROR
        assert error.status_code == 500
        assert error.details == {}


class TestErrorType:
    """Test cases for ErrorType enum."""
    
    def test_error_type_values(self):
        """Test ErrorType enum values."""
        assert ErrorType.VALIDATION_ERROR.value == "validation_error"
        assert ErrorType.AUTHENTICATION_ERROR.value == "authentication_error"
        assert ErrorType.AUTHORIZATION_ERROR.value == "authorization_error"
        assert ErrorType.NOT_FOUND_ERROR.value == "not_found_error"
        assert ErrorType.RATE_LIMIT_ERROR.value == "rate_limit_error"
        assert ErrorType.API_ERROR.value == "api_error"
        assert ErrorType.TIMEOUT_ERROR.value == "timeout_error"
        assert ErrorType.CONNECTION_ERROR.value == "connection_error"
        assert ErrorType.CONFIGURATION_ERROR.value == "configuration_error"
        assert ErrorType.INTERNAL_ERROR.value == "internal_error"
        assert ErrorType.UNKNOWN_ERROR.value == "unknown_error"