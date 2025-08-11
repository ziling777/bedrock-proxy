"""
Tests for ConfigManager.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from src.config_manager import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager()
        self.config_manager._cached_api_key = None
        self.config_manager._cached_secret_data = None
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    @patch('boto3.client')
    def test_get_openai_api_key_success(self, mock_boto_client):
        """Test successful API key retrieval."""
        # Mock Secrets Manager response
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'openai_api_key': 'sk-test-key-123',
                'model_mappings': {'test-model': 'gpt-4o-mini'}
            })
        }
        
        # Test API key retrieval
        api_key = self.config_manager.get_openai_api_key()
        
        assert api_key == 'sk-test-key-123'
        assert self.config_manager._cached_api_key == 'sk-test-key-123'
        mock_client.get_secret_value.assert_called_once()
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', None)
    def test_get_openai_api_key_no_secret_arn(self):
        """Test API key retrieval when secret ARN is not configured."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY_SECRET_ARN environment variable is not set"):
            self.config_manager.get_openai_api_key()
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    @patch('boto3.client')
    def test_get_openai_api_key_client_error(self, mock_boto_client):
        """Test API key retrieval with AWS client error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.side_effect = ClientError(
            error_response={'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
            operation_name='GetSecretValue'
        )
        
        with pytest.raises(RuntimeError, match="Failed to retrieve secret: Secret not found"):
            self.config_manager.get_openai_api_key()
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    @patch('boto3.client')
    def test_get_openai_api_key_invalid_json(self, mock_boto_client):
        """Test API key retrieval with invalid JSON in secret."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            'SecretString': 'invalid-json'
        }
        
        with pytest.raises(RuntimeError, match="Invalid JSON in secret"):
            self.config_manager.get_openai_api_key()
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    @patch('boto3.client')
    def test_get_openai_api_key_missing_key(self, mock_boto_client):
        """Test API key retrieval when key is missing from secret."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'other_key': 'value'})
        }
        
        with pytest.raises(RuntimeError, match="openai_api_key not found in secret"):
            self.config_manager.get_openai_api_key()
    
    def test_get_openai_api_key_cached(self):
        """Test that cached API key is returned."""
        self.config_manager._cached_api_key = 'sk-cached-key'
        
        api_key = self.config_manager.get_openai_api_key()
        
        assert api_key == 'sk-cached-key'
    
    @patch('src.config_manager.DEFAULT_MODEL_MAPPINGS', {'default-model': 'gpt-4o-mini'})
    def test_get_model_mapping_defaults(self):
        """Test getting default model mappings."""
        mappings = self.config_manager.get_model_mapping()
        
        assert mappings == {'default-model': 'gpt-4o-mini'}
    
    def test_get_model_mapping_with_custom(self):
        """Test getting model mappings with custom overrides."""
        self.config_manager._cached_secret_data = {
            'model_mappings': {
                'custom-model': 'gpt-4',
                'default-model': 'gpt-4o-mini-override'
            }
        }
        
        with patch('src.config_manager.DEFAULT_MODEL_MAPPINGS', {'default-model': 'gpt-4o-mini'}):
            mappings = self.config_manager.get_model_mapping()
        
        expected = {
            'default-model': 'gpt-4o-mini-override',  # Custom override
            'custom-model': 'gpt-4'  # Custom addition
        }
        assert mappings == expected
    
    @patch('src.config_manager.DEFAULT_TIMEOUT_SETTINGS', {'openai_api_timeout': 30})
    def test_get_timeout_settings_defaults(self):
        """Test getting default timeout settings."""
        timeouts = self.config_manager.get_timeout_settings()
        
        assert timeouts == {'openai_api_timeout': 30}
    
    def test_get_timeout_settings_with_custom(self):
        """Test getting timeout settings with custom overrides."""
        self.config_manager._cached_secret_data = {
            'timeout_settings': {
                'openai_api_timeout': 60,
                'custom_timeout': 120
            }
        }
        
        with patch('src.config_manager.DEFAULT_TIMEOUT_SETTINGS', {'openai_api_timeout': 30}):
            timeouts = self.config_manager.get_timeout_settings()
        
        expected = {
            'openai_api_timeout': 60,  # Custom override
            'custom_timeout': 120  # Custom addition
        }
        assert timeouts == expected
    
    @patch('src.config_manager.DEBUG', True)
    def test_get_debug_mode(self):
        """Test getting debug mode setting."""
        assert self.config_manager.get_debug_mode() is True
    
    @patch('src.config_manager.AWS_REGION', 'us-west-2')
    def test_get_aws_region(self):
        """Test getting AWS region."""
        assert self.config_manager.get_aws_region() == 'us-west-2'
    
    def test_clear_cache(self):
        """Test clearing configuration cache."""
        self.config_manager._cached_api_key = 'sk-test'
        self.config_manager._cached_secret_data = {'test': 'data'}
        
        self.config_manager.clear_cache()
        
        assert self.config_manager._cached_api_key is None
        assert self.config_manager._cached_secret_data is None
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    def test_validate_configuration_success(self):
        """Test successful configuration validation."""
        self.config_manager._cached_api_key = 'sk-test-key'
        self.config_manager._cached_secret_data = {'model_mappings': {'test': 'gpt-4o-mini'}}
        
        with patch.object(self.config_manager, 'get_openai_api_key', return_value='sk-test-key'):
            result = self.config_manager.validate_configuration()
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', None)
    def test_validate_configuration_missing_secret_arn(self):
        """Test configuration validation with missing secret ARN."""
        result = self.config_manager.validate_configuration()
        
        assert result['valid'] is False
        assert 'OPENAI_API_KEY_SECRET_ARN is not set' in result['errors']
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    def test_validate_configuration_api_key_error(self):
        """Test configuration validation with API key retrieval error."""
        with patch.object(self.config_manager, 'get_openai_api_key', side_effect=RuntimeError('Test error')):
            result = self.config_manager.validate_configuration()
        
        assert result['valid'] is False
        assert 'Failed to retrieve API key: Test error' in result['errors']
    
    @patch('src.config_manager.OPENAI_API_KEY_SECRET_ARN', 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret')
    def test_validate_configuration_invalid_api_key_format(self):
        """Test configuration validation with invalid API key format."""
        with patch.object(self.config_manager, 'get_openai_api_key', return_value='invalid-key'):
            result = self.config_manager.validate_configuration()
        
        assert result['valid'] is True  # Still valid, just a warning
        assert 'API key does not start with sk-' in result['warnings']