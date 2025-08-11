"""
Tests for the models list endpoint using Bedrock.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.request_handler import RequestHandler
from src.bedrock_client import BedrockAPIError


class TestModelsEndpoint:
    """Test cases for the /v1/models endpoint."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = RequestHandler()
        
        # Mock event for models list request
        self.models_event = {
            'httpMethod': 'GET',
            'path': '/v1/models',
            'headers': {
                'Authorization': 'Bearer test-token',
                'Content-Type': 'application/json'
            },
            'requestContext': {
                'requestId': 'test-request-123',
                'identity': {
                    'sourceIp': '127.0.0.1'
                }
            }
        }
        
        # Mock Bedrock models response
        self.mock_bedrock_response = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    },
                    'inputModalities': ['TEXT', 'IMAGE'],
                    'outputModalities': ['TEXT']
                },
                {
                    'modelId': 'amazon.nova-pro-v1:0',
                    'modelName': 'Nova Pro',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    },
                    'inputModalities': ['TEXT', 'IMAGE'],
                    'outputModalities': ['TEXT']
                }
            ]
        }
    
    @patch('src.request_handler.ConfigManager')
    @patch('src.request_handler.AuthManager')
    @patch('src.request_handler.BedrockClient')
    def test_handle_models_list_success(self, mock_bedrock_client_class, mock_auth_manager_class, mock_config_manager_class):
        """Test successful models list request."""
        # Setup mocks
        mock_config_manager = Mock()
        mock_config_manager.get_openai_api_key.return_value = 'sk-test-key'
        mock_config_manager.get_model_mapping.return_value = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0'
        }
        mock_config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        mock_config_manager.get_aws_region.return_value = 'us-east-1'
        mock_config_manager_class.return_value = mock_config_manager
        
        mock_auth_manager = Mock()
        mock_auth_result = Mock()
        mock_auth_result.authenticated = True
        mock_auth_manager.authenticate_request.return_value = mock_auth_result
        mock_auth_manager.authorize_action.return_value = True
        mock_auth_manager_class.return_value = mock_auth_manager
        
        mock_bedrock_client = Mock()
        mock_bedrock_client.list_foundation_models.return_value = self.mock_bedrock_response
        mock_bedrock_client_class.return_value = mock_bedrock_client
        
        # Execute
        response = self.handler.handle_models_list(self.models_event)
        
        # Verify
        assert response['statusCode'] == 200
        
        response_body = json.loads(response['body'])
        assert response_body['object'] == 'list'
        assert 'data' in response_body
        
        models = response_body['data']
        assert len(models) >= 2  # At least the 2 Nova models
        
        # Check that Nova models are present
        nova_lite_found = False
        nova_pro_found = False
        gpt_4o_mini_found = False
        
        for model in models:
            if model['id'] == 'amazon.nova-lite-v1:0':
                nova_lite_found = True
                assert model['object'] == 'model'
                assert model['owned_by'] == 'amazon'
                assert model['context_length'] == 300000
                assert model['capabilities'] == ['text', 'image']
            elif model['id'] == 'amazon.nova-pro-v1:0':
                nova_pro_found = True
                assert model['object'] == 'model'
                assert model['owned_by'] == 'amazon'
                assert model['context_length'] == 300000
                assert model['capabilities'] == ['text', 'image']
            elif model['id'] == 'gpt-4o-mini':
                gpt_4o_mini_found = True
                assert model['object'] == 'model'
                assert model['owned_by'] == 'openai-compatible'
                assert model['root'] == 'amazon.nova-lite-v1:0'
                assert model['alias_for'] == 'amazon.nova-lite-v1:0'
        
        assert nova_lite_found, "Nova Lite model not found in response"
        assert nova_pro_found, "Nova Pro model not found in response"
        assert gpt_4o_mini_found, "GPT-4o-mini alias not found in response"
        
        # Verify Bedrock client was called
        mock_bedrock_client.list_foundation_models.assert_called_once()
    
    @patch('src.request_handler.ConfigManager')
    @patch('src.request_handler.AuthManager')
    @patch('src.request_handler.BedrockClient')
    def test_handle_models_list_bedrock_error(self, mock_bedrock_client_class, mock_auth_manager_class, mock_config_manager_class):
        """Test models list request with Bedrock API error."""
        # Setup mocks
        mock_config_manager = Mock()
        mock_config_manager.get_openai_api_key.return_value = 'sk-test-key'
        mock_config_manager.get_model_mapping.return_value = {}
        mock_config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        mock_config_manager.get_aws_region.return_value = 'us-east-1'
        mock_config_manager_class.return_value = mock_config_manager
        
        mock_auth_manager = Mock()
        mock_auth_result = Mock()
        mock_auth_result.authenticated = True
        mock_auth_manager.authenticate_request.return_value = mock_auth_result
        mock_auth_manager.authorize_action.return_value = True
        mock_auth_manager_class.return_value = mock_auth_manager
        
        mock_bedrock_client = Mock()
        mock_bedrock_client.list_foundation_models.side_effect = BedrockAPIError(
            "Access denied to Bedrock service",
            status_code=403,
            error_type="authentication_error"
        )
        mock_bedrock_client_class.return_value = mock_bedrock_client
        
        # Execute
        response = self.handler.handle_models_list(self.models_event)
        
        # Verify
        assert response['statusCode'] == 403
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['type'] == 'authentication_error'
        assert 'Access denied' in response_body['error']['message']
    
    @patch('src.request_handler.ConfigManager')
    @patch('src.request_handler.AuthManager')
    def test_handle_models_list_auth_failure(self, mock_auth_manager_class, mock_config_manager_class):
        """Test models list request with authentication failure."""
        # Setup mocks
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager
        
        mock_auth_manager = Mock()
        mock_auth_result = Mock()
        mock_auth_result.authenticated = False
        mock_auth_manager.authenticate_request.return_value = mock_auth_result
        mock_auth_manager.create_auth_error.return_value = Exception("Authentication failed")
        mock_auth_manager_class.return_value = mock_auth_manager
        
        # Execute
        with pytest.raises(Exception, match="Authentication failed"):
            self.handler.handle_models_list(self.models_event)
    
    def test_convert_bedrock_models_to_openai(self):
        """Test conversion of Bedrock models to OpenAI format."""
        # Setup
        with patch('src.request_handler.ConfigManager') as mock_config_manager_class:
            mock_config_manager = Mock()
            mock_config_manager.get_model_mapping.return_value = {
                'gpt-4o-mini': 'amazon.nova-lite-v1:0'
            }
            mock_config_manager_class.return_value = mock_config_manager
            
            handler = RequestHandler()
            handler.config_manager = mock_config_manager
            
            # Execute
            result = handler._convert_bedrock_models_to_openai(self.mock_bedrock_response)
            
            # Verify
            assert result['object'] == 'list'
            assert 'data' in result
            
            models = result['data']
            assert len(models) >= 2  # At least Nova models
            
            # Check Nova Lite model
            nova_lite = next((m for m in models if m['id'] == 'amazon.nova-lite-v1:0'), None)
            assert nova_lite is not None
            assert nova_lite['object'] == 'model'
            assert nova_lite['owned_by'] == 'amazon'
            assert nova_lite['context_length'] == 300000
            assert nova_lite['capabilities'] == ['text', 'image']
            assert nova_lite['status'] == 'ACTIVE'
            
            # Check alias model
            gpt_4o_mini = next((m for m in models if m['id'] == 'gpt-4o-mini'), None)
            assert gpt_4o_mini is not None
            assert gpt_4o_mini['owned_by'] == 'openai-compatible'
            assert gpt_4o_mini['root'] == 'amazon.nova-lite-v1:0'
            assert gpt_4o_mini['alias_for'] == 'amazon.nova-lite-v1:0'
    
    def test_handle_bedrock_error(self):
        """Test Bedrock error handling."""
        handler = RequestHandler()
        
        # Test different error types
        test_cases = [
            (BedrockAPIError("Invalid request", status_code=400, error_type="invalid_request_error"), 400, "invalid_request_error"),
            (BedrockAPIError("Access denied", status_code=401, error_type="authentication_error"), 401, "authentication_error"),
            (BedrockAPIError("Rate limit exceeded", status_code=429, error_type="rate_limit_error"), 429, "rate_limit_error"),
            (BedrockAPIError("Model not ready", status_code=503, error_type="model_error"), 503, "model_error"),
            (BedrockAPIError("Internal server error", status_code=500, error_type="server_error"), 500, "server_error"),
        ]
        
        for bedrock_error, expected_status, expected_type in test_cases:
            result = handler._handle_bedrock_error(bedrock_error, "test-request-123")
            
            assert result['statusCode'] == expected_status
            
            response_body = json.loads(result['body'])
            assert response_body['error']['type'] == expected_type
            assert response_body['error']['message'] == bedrock_error.message
            assert response_body['request_id'] == "test-request-123"
            assert 'timestamp' in response_body
    
    def test_models_endpoint_integration(self):
        """Test the complete models endpoint integration."""
        # This would be an integration test that actually calls Bedrock
        # For now, we'll skip it as it requires AWS credentials
        pytest.skip("Integration test requires AWS credentials")


if __name__ == '__main__':
    pytest.main([__file__])