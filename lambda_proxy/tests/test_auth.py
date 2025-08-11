"""
Tests for authentication and authorization.
"""
import json
import time
import pytest
import jwt
from unittest.mock import Mock, patch

from src.auth import AuthManager, AuthResult, AuthMethod
from src.error_handler import ErrorType


class TestAuthManager:
    """Test cases for AuthManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.auth_manager = AuthManager()
    
    def test_initialization(self):
        """Test AuthManager initialization."""
        assert self.auth_manager.enabled_auth_methods == [AuthMethod.API_KEY, AuthMethod.BEARER_TOKEN]
        assert self.auth_manager.require_auth is False
    
    def test_authenticate_request_disabled_auth(self):
        """Test authentication when auth is disabled."""
        event = {'headers': {}}
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is True
        assert result.user_id == "anonymous"
        assert result.auth_method == AuthMethod.NONE
    
    def test_authenticate_request_no_credentials(self):
        """Test authentication with no credentials when auth is enabled."""
        self.auth_manager.enable_authentication(True)
        event = {'headers': {}}
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is False
        assert "No authentication credentials provided" in result.error_message
    
    def test_authenticate_api_key_valid(self):
        """Test API key authentication with valid key."""
        self.auth_manager.enable_authentication(True)
        event = {
            'headers': {
                'X-API-Key': 'sk-test-api-key-1234567890abcdef'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is True
        assert result.auth_method == AuthMethod.API_KEY
        assert result.user_id is not None
        assert "chat:completion" in result.permissions
        assert "models:list" in result.permissions
    
    def test_authenticate_api_key_invalid_format(self):
        """Test API key authentication with invalid format."""
        self.auth_manager.enable_authentication(True)
        event = {
            'headers': {
                'X-API-Key': 'short'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is False
        assert result.auth_method == AuthMethod.API_KEY
        assert "Invalid API key format" in result.error_message
    
    def test_authenticate_bearer_token_simple(self):
        """Test Bearer token authentication with simple token."""
        self.auth_manager.enable_authentication(True)
        event = {
            'headers': {
                'Authorization': 'Bearer simple-bearer-token-1234567890'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is True
        assert result.auth_method == AuthMethod.BEARER_TOKEN
        assert result.user_id is not None
        assert "chat:completion" in result.permissions
    
    def test_authenticate_bearer_token_too_short(self):
        """Test Bearer token authentication with too short token."""
        self.auth_manager.enable_authentication(True)
        event = {
            'headers': {
                'Authorization': 'Bearer short'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is False
        assert result.auth_method == AuthMethod.BEARER_TOKEN
        assert "Token too short" in result.error_message
    
    def test_authenticate_jwt_token_valid(self):
        """Test JWT token authentication with valid token."""
        self.auth_manager.enable_authentication(True)
        
        # Create a test JWT token
        payload = {
            'sub': 'user123',
            'permissions': ['chat:completion', 'models:list'],
            'exp': int(time.time()) + 3600  # Expires in 1 hour
        }
        token = jwt.encode(payload, 'secret', algorithm='HS256')
        
        event = {
            'headers': {
                'Authorization': f'Bearer {token}'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is True
        assert result.auth_method == AuthMethod.JWT
        assert result.user_id == 'user123'
        assert result.permissions == ['chat:completion', 'models:list']
    
    def test_authenticate_jwt_token_expired(self):
        """Test JWT token authentication with expired token."""
        self.auth_manager.enable_authentication(True)
        
        # Create an expired JWT token
        payload = {
            'sub': 'user123',
            'exp': int(time.time()) - 3600  # Expired 1 hour ago
        }
        token = jwt.encode(payload, 'secret', algorithm='HS256')
        
        event = {
            'headers': {
                'Authorization': f'Bearer {token}'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is False
        assert result.auth_method == AuthMethod.JWT
        assert "Token expired" in result.error_message
    
    def test_authenticate_jwt_token_invalid(self):
        """Test JWT token authentication with invalid token."""
        self.auth_manager.enable_authentication(True)
        event = {
            'headers': {
                'Authorization': 'Bearer invalid.jwt.token'
            }
        }
        
        result = self.auth_manager.authenticate_request(event)
        
        assert result.authenticated is False
        assert result.auth_method == AuthMethod.JWT
        assert "Invalid JWT token" in result.error_message
    
    def test_extract_auth_header_case_insensitive(self):
        """Test extracting auth header with different cases."""
        # Test uppercase
        event1 = {'headers': {'Authorization': 'Bearer token123'}}
        assert self.auth_manager._extract_auth_header(event1) == 'Bearer token123'
        
        # Test lowercase
        event2 = {'headers': {'authorization': 'Bearer token456'}}
        assert self.auth_manager._extract_auth_header(event2) == 'Bearer token456'
    
    def test_extract_api_key_various_headers(self):
        """Test extracting API key from various header formats."""
        # Test X-API-Key
        event1 = {'headers': {'X-API-Key': 'key123'}}
        assert self.auth_manager._extract_api_key(event1) == 'key123'
        
        # Test lowercase
        event2 = {'headers': {'x-api-key': 'key456'}}
        assert self.auth_manager._extract_api_key(event2) == 'key456'
        
        # Test mixed case
        event3 = {'headers': {'X-Api-Key': 'key789'}}
        assert self.auth_manager._extract_api_key(event3) == 'key789'
    
    def test_validate_api_key_format_valid_keys(self):
        """Test API key format validation with valid keys."""
        valid_keys = [
            'sk-1234567890abcdef1234567890abcdef',
            'pk-abcdef1234567890abcdef1234567890',
            'ak-fedcba0987654321fedcba0987654321',
            'abcdef1234567890abcdef1234567890abcdef12'
        ]
        
        for key in valid_keys:
            assert self.auth_manager._validate_api_key_format(key) is True
    
    def test_validate_api_key_format_invalid_keys(self):
        """Test API key format validation with invalid keys."""
        invalid_keys = [
            '',
            'short',
            '123',
            'invalid-key-format',
            None
        ]
        
        for key in invalid_keys:
            assert self.auth_manager._validate_api_key_format(key) is False
    
    def test_is_jwt_token(self):
        """Test JWT token detection."""
        # Valid JWT format (3 parts)
        assert self.auth_manager._is_jwt_token('header.payload.signature') is True
        
        # Invalid formats
        assert self.auth_manager._is_jwt_token('header.payload') is False
        assert self.auth_manager._is_jwt_token('simple-token') is False
        assert self.auth_manager._is_jwt_token('') is False
    
    def test_authorize_action_authenticated_with_permission(self):
        """Test action authorization with proper permission."""
        auth_result = AuthResult(
            authenticated=True,
            user_id='user123',
            permissions=['chat:completion', 'models:list']
        )
        
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is True
        assert self.auth_manager.authorize_action(auth_result, 'models:list') is True
    
    def test_authorize_action_authenticated_without_permission(self):
        """Test action authorization without proper permission."""
        self.auth_manager.enable_authentication(True)
        auth_result = AuthResult(
            authenticated=True,
            user_id='user123',
            permissions=['models:list']
        )
        
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is False
    
    def test_authorize_action_wildcard_permission(self):
        """Test action authorization with wildcard permission."""
        self.auth_manager.enable_authentication(True)
        auth_result = AuthResult(
            authenticated=True,
            user_id='user123',
            permissions=['chat:*']
        )
        
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is True
        assert self.auth_manager.authorize_action(auth_result, 'chat:stream') is True
        assert self.auth_manager.authorize_action(auth_result, 'models:list') is False
    
    def test_authorize_action_admin_permission(self):
        """Test action authorization with admin permission."""
        auth_result = AuthResult(
            authenticated=True,
            user_id='admin',
            permissions=['admin:*']
        )
        
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is True
        assert self.auth_manager.authorize_action(auth_result, 'models:list') is True
        assert self.auth_manager.authorize_action(auth_result, 'any:action') is True
    
    def test_authorize_action_not_authenticated(self):
        """Test action authorization when not authenticated."""
        self.auth_manager.enable_authentication(True)
        auth_result = AuthResult(authenticated=False)
        
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is False
    
    def test_authorize_action_auth_disabled(self):
        """Test action authorization when auth is disabled."""
        self.auth_manager.enable_authentication(False)
        auth_result = AuthResult(authenticated=False)
        
        # Should return True when auth is disabled
        assert self.auth_manager.authorize_action(auth_result, 'chat:completion') is True
    
    def test_create_auth_error_authentication_failed(self):
        """Test creating authentication error."""
        auth_result = AuthResult(
            authenticated=False,
            error_message="Invalid credentials",
            auth_method=AuthMethod.API_KEY
        )
        
        error = self.auth_manager.create_auth_error(auth_result)
        
        assert error.status_code == 401
        assert error.error_type == ErrorType.AUTHENTICATION_ERROR
        assert "Invalid credentials" in error.message
        assert error.details['auth_method'] == 'api_key'
    
    def test_create_auth_error_authorization_failed(self):
        """Test creating authorization error."""
        auth_result = AuthResult(
            authenticated=True,
            user_id='user123',
            permissions=['models:list']
        )
        
        error = self.auth_manager.create_auth_error(auth_result)
        
        assert error.status_code == 403
        assert error.error_type == ErrorType.AUTHORIZATION_ERROR
        assert "Insufficient permissions" in error.message
        assert error.details['user_id'] == 'user123'
    
    def test_get_rate_limit_key_authenticated(self):
        """Test rate limit key generation for authenticated user."""
        auth_result = AuthResult(
            authenticated=True,
            user_id='user123'
        )
        
        key = self.auth_manager.get_rate_limit_key(auth_result, 'chat_completion')
        
        assert key == 'user:user123:chat_completion'
    
    def test_get_rate_limit_key_anonymous(self):
        """Test rate limit key generation for anonymous user."""
        auth_result = AuthResult(authenticated=False)
        
        key = self.auth_manager.get_rate_limit_key(auth_result, 'chat_completion')
        
        assert key == 'anonymous:chat_completion'
    
    def test_enable_disable_authentication(self):
        """Test enabling and disabling authentication."""
        # Initially disabled
        assert self.auth_manager.require_auth is False
        
        # Enable
        self.auth_manager.enable_authentication(True)
        assert self.auth_manager.require_auth is True
        
        # Disable
        self.auth_manager.enable_authentication(False)
        assert self.auth_manager.require_auth is False
    
    def test_add_remove_auth_methods(self):
        """Test adding and removing authentication methods."""
        # Initially has API_KEY and BEARER_TOKEN
        assert AuthMethod.JWT not in self.auth_manager.enabled_auth_methods
        
        # Add JWT
        self.auth_manager.add_auth_method(AuthMethod.JWT)
        assert AuthMethod.JWT in self.auth_manager.enabled_auth_methods
        
        # Remove API_KEY
        self.auth_manager.remove_auth_method(AuthMethod.API_KEY)
        assert AuthMethod.API_KEY not in self.auth_manager.enabled_auth_methods
    
    def test_extract_user_from_api_key_consistency(self):
        """Test that user extraction from API key is consistent."""
        api_key = 'sk-test-key-1234567890abcdef'
        
        user1 = self.auth_manager._extract_user_from_api_key(api_key)
        user2 = self.auth_manager._extract_user_from_api_key(api_key)
        
        assert user1 == user2
        assert len(user1) == 16  # Should be 16 characters


class TestAuthResult:
    """Test cases for AuthResult."""
    
    def test_auth_result_creation(self):
        """Test AuthResult creation."""
        result = AuthResult(
            authenticated=True,
            user_id='user123',
            permissions=['chat:completion'],
            auth_method=AuthMethod.API_KEY
        )
        
        assert result.authenticated is True
        assert result.user_id == 'user123'
        assert result.permissions == ['chat:completion']
        assert result.auth_method == AuthMethod.API_KEY
        assert result.error_message is None
    
    def test_auth_result_defaults(self):
        """Test AuthResult with default values."""
        result = AuthResult(authenticated=False)
        
        assert result.authenticated is False
        assert result.user_id is None
        assert result.permissions == []
        assert result.error_message is None
        assert result.auth_method is None


class TestAuthMethod:
    """Test cases for AuthMethod enum."""
    
    def test_auth_method_values(self):
        """Test AuthMethod enum values."""
        assert AuthMethod.API_KEY.value == "api_key"
        assert AuthMethod.BEARER_TOKEN.value == "bearer_token"
        assert AuthMethod.JWT.value == "jwt"
        assert AuthMethod.NONE.value == "none"