"""
OpenAI API client for the Lambda proxy service.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .interfaces import OpenAIClientInterface
from .config import OPENAI_API_BASE_URL, OPENAI_MAX_RETRIES, OPENAI_RETRY_DELAY

logger = logging.getLogger(__name__)


class OpenAIAPIError(Exception):
    """Custom exception for OpenAI API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class OpenAIClient(OpenAIClientInterface):
    """OpenAI API client implementation."""
    
    def __init__(self, api_key: str, timeout: int = 30):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = OPENAI_API_BASE_URL
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'AWS-Lambda-Proxy/1.0'
        })
    
    @retry(
        stop=stop_after_attempt(OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=OPENAI_RETRY_DELAY, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, OpenAIAPIError)),
        reraise=True
    )
    def chat_completion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call OpenAI chat completion API.
        
        Args:
            request: OpenAI format chat completion request
            
        Returns:
            OpenAI chat completion response
            
        Raises:
            OpenAIAPIError: If API call fails
        """
        url = f"{self.base_url}/chat/completions"
        
        try:
            logger.info(f"Calling OpenAI chat completion API: {url}")
            logger.debug(f"Request payload: {json.dumps(request, indent=2)}")
            
            response = self.session.post(
                url,
                json=request,
                timeout=self.timeout
            )
            
            # Log response details
            logger.info(f"OpenAI API response status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                logger.debug(f"Response payload: {json.dumps(response_data, indent=2)}")
                return response_data
            
            # Handle error responses
            error_data = self._parse_error_response(response)
            raise OpenAIAPIError(
                message=error_data.get('message', f'HTTP {response.status_code}'),
                status_code=response.status_code,
                error_type=error_data.get('type', 'api_error')
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"OpenAI API request timeout after {self.timeout} seconds")
            raise OpenAIAPIError("Request timeout", status_code=408, error_type="timeout_error")
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"OpenAI API connection error: {e}")
            raise OpenAIAPIError("Connection error", status_code=503, error_type="connection_error")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request error: {e}")
            raise OpenAIAPIError(f"Request error: {e}", status_code=500, error_type="request_error")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI API response: {e}")
            raise OpenAIAPIError("Invalid JSON response", status_code=502, error_type="parse_error")
    
    @retry(
        stop=stop_after_attempt(OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=OPENAI_RETRY_DELAY, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, OpenAIAPIError)),
        reraise=True
    )
    def list_models(self) -> Dict[str, Any]:
        """
        List available models from OpenAI.
        
        Returns:
            OpenAI models list response
            
        Raises:
            OpenAIAPIError: If API call fails
        """
        url = f"{self.base_url}/models"
        
        try:
            logger.info(f"Calling OpenAI models API: {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            
            logger.info(f"OpenAI models API response status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                logger.debug(f"Models response: {json.dumps(response_data, indent=2)}")
                return response_data
            
            # Handle error responses
            error_data = self._parse_error_response(response)
            raise OpenAIAPIError(
                message=error_data.get('message', f'HTTP {response.status_code}'),
                status_code=response.status_code,
                error_type=error_data.get('type', 'api_error')
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"OpenAI models API request timeout after {self.timeout} seconds")
            raise OpenAIAPIError("Request timeout", status_code=408, error_type="timeout_error")
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"OpenAI models API connection error: {e}")
            raise OpenAIAPIError("Connection error", status_code=503, error_type="connection_error")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI models API request error: {e}")
            raise OpenAIAPIError(f"Request error: {e}", status_code=500, error_type="request_error")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI models API response: {e}")
            raise OpenAIAPIError("Invalid JSON response", status_code=502, error_type="parse_error")
    
    def _parse_error_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parse error response from OpenAI API.
        
        Args:
            response: HTTP response object
            
        Returns:
            Parsed error data
        """
        try:
            error_data = response.json()
            
            # OpenAI error format: {"error": {"message": "...", "type": "...", "code": "..."}}
            if 'error' in error_data:
                return error_data['error']
            
            return error_data
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse error response as JSON")
            return {
                'message': response.text or f'HTTP {response.status_code}',
                'type': 'unknown_error',
                'code': str(response.status_code)
            }
    
    def validate_api_key(self) -> bool:
        """
        Validate the OpenAI API key by making a test request.
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Make a simple models list request to validate the key
            self.list_models()
            logger.info("OpenAI API key validation successful")
            return True
            
        except OpenAIAPIError as e:
            if e.status_code == 401:
                logger.error("OpenAI API key validation failed: Invalid API key")
            else:
                logger.error(f"OpenAI API key validation failed: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error during API key validation: {e}")
            return False
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Model information or None if not found
        """
        try:
            models_response = self.list_models()
            models = models_response.get('data', [])
            
            for model in models:
                if model.get('id') == model_id:
                    return model
            
            logger.warning(f"Model {model_id} not found in available models")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            return None
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("OpenAI client session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()