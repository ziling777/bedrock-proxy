"""
Authentication and authorization for the Lambda proxy service.
"""
import json
import logging
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import jwt
from .error_handler import ErrorType, ProxyError

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication method enumeration."""
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    JWT = "jwt"
    NONE = "none"


class AuthResult:
    """Authentication result."""
    
    def __init__(
        self,
        authenticated: bool,
        user_id: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        auth_method: Optional[AuthMethod] = None
    ):
        self.authenticated = authenticated
        self.user_id = user_id
        self.permissions = permissions or []
        self.error_message = error_message
        self.auth_method = auth_method


class AuthManager:
    """Authentication and authorization manager."""
    
    def __init__(self, config_manager=None):
        """
        Initialize authentication manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.enabled_auth_methods = [AuthMethod.API_KEY, AuthMethod.BEARER_TOKEN]
        self.require_auth = False  # Set to True for production
        
        # Load auth configuration
        self._load_auth_config()
    
    def _load_auth_config(self):
        """Load authentication configuration."""
        try:
            if self.config_manager:
                # In production, load from config
                # For now, use default settings
                pass
            
            logger.info("Authentication configuration loaded")
            
        except Exception as e:
            logger.warning(f"Failed to load auth config: {e}")
    
    def authenticate_request(self, event: Dict[str, Any]) -> AuthResult:
        """
        Authenticate incoming request.
        
        Args:
            event: API Gateway event
            
        Returns:
            Authentication result
        """
        try:
            # Skip authentication if not required (development mode)
            if not self.require_auth:
                logger.debug("Authentication disabled - allowing request")
                return AuthResult(
                    authenticated=True,
                    user_id="anonymous",
                    auth_method=AuthMethod.NONE
                )
            
            # Extract authentication information
            auth_header = self._extract_auth_header(event)
            api_key = self._extract_api_key(event)
            
            # Try different authentication methods
            if auth_header and auth_header.startswith('Bearer '):
                return self._authenticate_bearer_token(auth_header[7:])
            elif api_key:
                return self._authenticate_api_key(api_key)
            else:
                return AuthResult(
                    authenticated=False,
                    error_message="No authentication credentials provided"
                )
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthResult(
                authenticated=False,
                error_message="Authentication failed"
            )
    
    def _extract_auth_header(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract Authorization header from request."""
        headers = event.get('headers', {})
        return (
            headers.get('Authorization') or 
            headers.get('authorization')
        )
    
    def _extract_api_key(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract API key from request headers."""
        headers = event.get('headers', {})
        return (
            headers.get('X-API-Key') or 
            headers.get('x-api-key') or
            headers.get('X-Api-Key')
        )
    
    def _authenticate_bearer_token(self, token: str) -> AuthResult:
        """
        Authenticate using Bearer token.
        
        Args:
            token: Bearer token
            
        Returns:
            Authentication result
        """
        try:
            # Check if it's a JWT token
            if self._is_jwt_token(token):
                return self._authenticate_jwt(token)
            else:
                # Treat as simple bearer token
                return self._authenticate_simple_token(token)
                
        except Exception as e:
            logger.error(f"Bearer token authentication failed: {e}")
            return AuthResult(
                authenticated=False,
                error_message="Invalid bearer token",
                auth_method=AuthMethod.BEARER_TOKEN
            )
    
    def _authenticate_api_key(self, api_key: str) -> AuthResult:
        """
        Authenticate using API key.
        
        Args:
            api_key: API key
            
        Returns:
            Authentication result
        """
        try:
            # Validate API key format
            if not self._validate_api_key_format(api_key):
                return AuthResult(
                    authenticated=False,
                    error_message="Invalid API key format",
                    auth_method=AuthMethod.API_KEY
                )
            
            # In production, validate against stored API keys
            # For now, accept any properly formatted key
            user_id = self._extract_user_from_api_key(api_key)
            
            logger.info(f"API key authentication successful for user: {user_id}")
            
            return AuthResult(
                authenticated=True,
                user_id=user_id,
                permissions=["chat:completion", "models:list"],
                auth_method=AuthMethod.API_KEY
            )
            
        except Exception as e:
            logger.error(f"API key authentication failed: {e}")
            return AuthResult(
                authenticated=False,
                error_message="API key authentication failed",
                auth_method=AuthMethod.API_KEY
            )
    
    def _authenticate_jwt(self, token: str) -> AuthResult:
        """
        Authenticate using JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            Authentication result
        """
        try:
            # In production, use proper JWT secret/key
            # For now, just decode without verification for development
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Extract user information
            user_id = decoded.get('sub') or decoded.get('user_id')
            permissions = decoded.get('permissions', [])
            
            # Check token expiration
            exp = decoded.get('exp')
            if exp and exp < time.time():
                return AuthResult(
                    authenticated=False,
                    error_message="Token expired",
                    auth_method=AuthMethod.JWT
                )
            
            logger.info(f"JWT authentication successful for user: {user_id}")
            
            return AuthResult(
                authenticated=True,
                user_id=user_id,
                permissions=permissions,
                auth_method=AuthMethod.JWT
            )
            
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {e}")
            return AuthResult(
                authenticated=False,
                error_message="Invalid JWT token",
                auth_method=AuthMethod.JWT
            )
        except Exception as e:
            logger.error(f"JWT authentication failed: {e}")
            return AuthResult(
                authenticated=False,
                error_message="JWT authentication failed",
                auth_method=AuthMethod.JWT
            )
    
    def _authenticate_simple_token(self, token: str) -> AuthResult:
        """
        Authenticate using simple bearer token.
        
        Args:
            token: Simple token
            
        Returns:
            Authentication result
        """
        try:
            # In production, validate against stored tokens
            # For now, accept any non-empty token
            if len(token) < 10:
                return AuthResult(
                    authenticated=False,
                    error_message="Token too short",
                    auth_method=AuthMethod.BEARER_TOKEN
                )
            
            # Generate user ID from token hash
            user_id = hashlib.sha256(token.encode()).hexdigest()[:12]
            
            logger.info(f"Simple token authentication successful for user: {user_id}")
            
            return AuthResult(
                authenticated=True,
                user_id=user_id,
                permissions=["chat:completion", "models:list"],
                auth_method=AuthMethod.BEARER_TOKEN
            )
            
        except Exception as e:
            logger.error(f"Simple token authentication failed: {e}")
            return AuthResult(
                authenticated=False,
                error_message="Token authentication failed",
                auth_method=AuthMethod.BEARER_TOKEN
            )
    
    def _is_jwt_token(self, token: str) -> bool:
        """Check if token is a JWT token."""
        try:
            # JWT tokens have 3 parts separated by dots
            parts = token.split('.')
            return len(parts) == 3
        except:
            return False
    
    def _validate_api_key_format(self, api_key: str) -> bool:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if format is valid
        """
        try:
            # Basic format validation
            if not api_key or len(api_key) < 20:
                return False
            
            # Check for common API key patterns
            if api_key.startswith(('sk-', 'pk-', 'ak-')):
                return True
            
            # Accept alphanumeric keys of sufficient length
            if len(api_key) >= 32 and api_key.replace('-', '').replace('_', '').isalnum():
                return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_user_from_api_key(self, api_key: str) -> str:
        """
        Extract user identifier from API key.
        
        Args:
            api_key: API key
            
        Returns:
            User identifier
        """
        # Generate consistent user ID from API key
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    def authorize_action(
        self,
        auth_result: AuthResult,
        action: str,
        resource: Optional[str] = None
    ) -> bool:
        """
        Authorize action for authenticated user.
        
        Args:
            auth_result: Authentication result
            action: Action to authorize (e.g., "chat:completion")
            resource: Optional resource identifier
            
        Returns:
            True if authorized
        """
        try:
            # Skip authorization if not required (development mode)
            if not self.require_auth:
                return True
            
            # Skip authorization if authentication failed
            if not auth_result.authenticated:
                return False
            
            # Check permissions
            if action in auth_result.permissions:
                logger.debug(f"Action '{action}' authorized for user {auth_result.user_id}")
                return True
            
            # Check wildcard permissions
            action_parts = action.split(':')
            if len(action_parts) > 1:
                wildcard_permission = f"{action_parts[0]}:*"
                if wildcard_permission in auth_result.permissions:
                    logger.debug(f"Wildcard permission '{wildcard_permission}' authorized action '{action}'")
                    return True
            
            # Check for admin permissions
            if "admin:*" in auth_result.permissions:
                logger.debug(f"Admin permission authorized action '{action}'")
                return True
            
            logger.warning(f"Action '{action}' not authorized for user {auth_result.user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return False
    
    def create_auth_error(self, auth_result: AuthResult) -> ProxyError:
        """
        Create authentication error.
        
        Args:
            auth_result: Failed authentication result
            
        Returns:
            ProxyError for authentication failure
        """
        if not auth_result.authenticated:
            return ProxyError(
                message=auth_result.error_message or "Authentication required",
                error_type=ErrorType.AUTHENTICATION_ERROR,
                status_code=401,
                details={
                    'auth_method': auth_result.auth_method.value if auth_result.auth_method else None
                }
            )
        else:
            return ProxyError(
                message="Insufficient permissions",
                error_type=ErrorType.AUTHORIZATION_ERROR,
                status_code=403,
                details={
                    'user_id': auth_result.user_id,
                    'permissions': auth_result.permissions
                }
            )
    
    def get_rate_limit_key(self, auth_result: AuthResult, endpoint: str) -> str:
        """
        Get rate limiting key for user and endpoint.
        
        Args:
            auth_result: Authentication result
            endpoint: API endpoint
            
        Returns:
            Rate limit key
        """
        if auth_result.authenticated and auth_result.user_id:
            return f"user:{auth_result.user_id}:{endpoint}"
        else:
            return f"anonymous:{endpoint}"
    
    def enable_authentication(self, enabled: bool = True):
        """
        Enable or disable authentication requirement.
        
        Args:
            enabled: Whether to require authentication
        """
        self.require_auth = enabled
        logger.info(f"Authentication requirement {'enabled' if enabled else 'disabled'}")
    
    def add_auth_method(self, method: AuthMethod):
        """
        Add supported authentication method.
        
        Args:
            method: Authentication method to add
        """
        if method not in self.enabled_auth_methods:
            self.enabled_auth_methods.append(method)
            logger.info(f"Added authentication method: {method.value}")
    
    def remove_auth_method(self, method: AuthMethod):
        """
        Remove supported authentication method.
        
        Args:
            method: Authentication method to remove
        """
        if method in self.enabled_auth_methods:
            self.enabled_auth_methods.remove(method)
            logger.info(f"Removed authentication method: {method.value}")