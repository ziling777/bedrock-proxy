"""
Configuration manager for the Lambda proxy service.
"""
import json
import logging
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, BotoCoreError
from .interfaces import ConfigManagerInterface
from .config import (
    OPENAI_API_KEY_SECRET_ARN,
    AWS_REGION,
    DEFAULT_MODEL_MAPPINGS,
    DEFAULT_TIMEOUT_SETTINGS,
    DEBUG
)

logger = logging.getLogger(__name__)


class ConfigManager(ConfigManagerInterface):
    """Configuration manager implementation."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._secrets_client = None
        self._cached_api_key = None
        self._cached_secret_data = None
        
    @property
    def secrets_client(self):
        """Lazy initialization of Secrets Manager client."""
        if self._secrets_client is None:
            self._secrets_client = boto3.client(
                'secretsmanager',
                region_name=AWS_REGION
            )
        return self._secrets_client
    
    def get_openai_api_key(self) -> str:
        """
        Get OpenAI API key from AWS Secrets Manager.
        
        Returns:
            OpenAI API key string
            
        Raises:
            ValueError: If secret ARN is not configured
            RuntimeError: If unable to retrieve secret
        """
        # Return cached key if available
        if self._cached_api_key:
            return self._cached_api_key
        
        if not OPENAI_API_KEY_SECRET_ARN:
            raise ValueError("OPENAI_API_KEY_SECRET_ARN environment variable is not set")
            
        try:
            logger.info(f"Retrieving OpenAI API key from secret: {OPENAI_API_KEY_SECRET_ARN}")
            
            response = self.secrets_client.get_secret_value(
                SecretId=OPENAI_API_KEY_SECRET_ARN
            )
            
            secret_string = response.get('SecretString')
            if not secret_string:
                raise RuntimeError("Secret value is empty")
            
            # Parse JSON secret
            try:
                secret_data = json.loads(secret_string)
                self._cached_secret_data = secret_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse secret JSON: {e}")
                raise RuntimeError(f"Invalid JSON in secret: {e}")
            
            # Extract API key
            api_key = secret_data.get('openai_api_key')
            if not api_key:
                raise RuntimeError("openai_api_key not found in secret")
            
            self._cached_api_key = api_key
            logger.info("Successfully retrieved OpenAI API key")
            
            return api_key
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS Secrets Manager error ({error_code}): {error_message}")
            raise RuntimeError(f"Failed to retrieve secret: {error_message}")
            
        except BotoCoreError as e:
            logger.error(f"AWS SDK error: {e}")
            raise RuntimeError(f"AWS SDK error: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret: {e}")
            raise RuntimeError(f"Unexpected error: {e}")
    
    def get_model_mapping(self) -> Dict[str, str]:
        """
        Get model name mapping from OpenAI to Bedrock.
        
        Returns:
            Dictionary mapping OpenAI model names to Bedrock model names
        """
        try:
            # Try to get custom mappings from secret first
            if self._cached_secret_data is None:
                try:
                    # This will populate _cached_secret_data
                    self.get_openai_api_key()
                except ValueError:
                    # If no secret is configured, use defaults
                    logger.info("No secret configured, using default model mappings")
                    return DEFAULT_MODEL_MAPPINGS.copy()
            
            custom_mappings = self._cached_secret_data.get('model_mappings', {})
            
            # Merge with default mappings (custom takes precedence)
            mappings = DEFAULT_MODEL_MAPPINGS.copy()
            mappings.update(custom_mappings)
            
            logger.info(f"Using model mappings: {mappings}")
            return mappings
            
        except Exception as e:
            logger.warning(f"Failed to get custom model mappings, using defaults: {e}")
            return DEFAULT_MODEL_MAPPINGS.copy()
    
    def get_timeout_settings(self) -> Dict[str, int]:
        """
        Get timeout configuration.
        
        Returns:
            Dictionary with timeout settings in seconds
        """
        try:
            # Try to get custom timeout settings from secret
            if self._cached_secret_data is None:
                try:
                    self.get_openai_api_key()
                except ValueError:
                    # If no secret is configured, use defaults
                    logger.info("No secret configured, using default timeout settings")
                    return DEFAULT_TIMEOUT_SETTINGS.copy()
            
            custom_timeouts = self._cached_secret_data.get('timeout_settings', {})
            
            # Merge with default timeouts (custom takes precedence)
            timeouts = DEFAULT_TIMEOUT_SETTINGS.copy()
            timeouts.update(custom_timeouts)
            
            logger.info(f"Using timeout settings: {timeouts}")
            return timeouts
            
        except Exception as e:
            logger.warning(f"Failed to get custom timeout settings, using defaults: {e}")
            return DEFAULT_TIMEOUT_SETTINGS.copy()
    
    def get_debug_mode(self) -> bool:
        """
        Get debug mode setting.
        
        Returns:
            True if debug mode is enabled
        """
        return DEBUG
    
    def get_aws_region(self) -> str:
        """
        Get AWS region.
        
        Returns:
            AWS region string
        """
        return AWS_REGION
    
    def clear_cache(self) -> None:
        """Clear cached configuration data."""
        self._cached_api_key = None
        self._cached_secret_data = None
        logger.info("Configuration cache cleared")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate configuration and return status.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check required environment variables
        if not OPENAI_API_KEY_SECRET_ARN:
            validation_results['valid'] = False
            validation_results['errors'].append('OPENAI_API_KEY_SECRET_ARN is not set')
        
        # Try to retrieve API key
        try:
            api_key = self.get_openai_api_key()
            if not api_key.startswith('sk-'):
                validation_results['warnings'].append('API key does not start with sk-')
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f'Failed to retrieve API key: {e}')
        
        # Validate model mappings
        try:
            mappings = self.get_model_mapping()
            if not mappings:
                validation_results['warnings'].append('No model mappings configured')
        except Exception as e:
            validation_results['warnings'].append(f'Failed to get model mappings: {e}')
        
        return validation_results