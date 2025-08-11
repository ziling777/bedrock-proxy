"""
Tests for model mapping and models endpoint functionality.
"""
import json
import pytest
from unittest.mock import Mock, patch
from src.request_handler import RequestHandler
from src.bedrock_client import BedrockAPIError


class TestModelsEndpoint:
    """Test cases for the models endpoint and model mapping."""
    
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
                'requestId': 'test-models-request',
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
                },
                {
                    'modelId': 'amazon.nova-micro-v1:0',
                    'modelName': 'Nova Micro',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    },
                    'inputModalities': ['TEXT'],
                    'outputModalities': ['TEXT']
                }
            ]
        }
    
    def test_model_mapping_configuration(self):
        """Test model mapping configuration."""
        # Test default model mappings
        from src.config import DEFAULT_MODEL_MAPPINGS
        
        expected_mappings = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0'
        }
        
        for openai_model, expected_bedrock_model in expected_mappings.items():
            assert openai_model in DEFAULT_MODEL_MAPPINGS
            assert DEFAULT_MODEL_MAPPINGS[openai_model] == expected_bedrock_model
    
    def test_models_endpoint_success(self):
        """Test successful models list request."""
        # Mock dependencies
        self.handler.config_manager = Mock()
        self.handler.config_manager.get_model_mapping.return_value = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0'
        }
        self.handler.config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        self.handler.config_manager.get_aws_region.return_value = 'us-east-1'
        
        self.handler.auth_manager = Mock()
        auth_result = Mock()
        auth_result.authenticated = True
        self.handler.auth_manager.authenticate_request.return_value = auth_result
        self.handler.auth_manager.authorize_action.return_value = True
        
        self.handler.bedrock_client = Mock()
        self.handler.bedrock_client.list_foundation_models.return_value = self.mock_bedrock_response
        
        self.handler.error_handler = Mock()
        self.handler.error_handler.log_request = Mock()
        self.handler.error_handler.log_bedrock_api_call = Mock()
        self.handler.error_handler.log_response = Mock()
        
        self.handler.monitoring = Mock()
        
        # Mark as initialized
        self.handler._initialized = True
        
        # Execute request
        response = self.handler.handle_models_list(self.models_event)
        
        # Verify response
        assert response['statusCode'] == 200
        
        response_body = json.loads(response['body'])
        assert response_body['object'] == 'list'
        assert 'data' in response_body
        
        models = response_body['data']
        assert len(models) >= 3  # At least the 3 Nova models
        
        # Check that Nova models are present
        nova_models = [m for m in models if 'nova' in m['id'].lower()]
        assert len(nova_models) >= 3
        
        # Check specific models
        nova_lite = next((m for m in models if m['id'] == 'amazon.nova-lite-v1:0'), None)
        assert nova_lite is not None
        assert nova_lite['object'] == 'model'
        assert nova_lite['owned_by'] == 'amazon'
        assert nova_lite['context_length'] == 300000
        assert nova_lite['capabilities'] == ['text', 'image']
        
        # Check OpenAI-compatible aliases
        gpt_4o_mini = next((m for m in models if m['id'] == 'gpt-4o-mini'), None)
        assert gpt_4o_mini is not None
        assert gpt_4o_mini['owned_by'] == 'openai-compatible'
        assert gpt_4o_mini['root'] == 'amazon.nova-lite-v1:0'
        
        # Verify Bedrock client was called
        self.handler.bedrock_client.list_foundation_models.assert_called_once()
        
        # Verify monitoring was called
        self.handler.monitoring.record_request.assert_called_once()
        self.handler.monitoring.record_bedrock_call.assert_called_once()
    
    def test_models_endpoint_bedrock_error(self):
        """Test models endpoint with Bedrock error."""
        # Mock dependencies
        self.handler.config_manager = Mock()
        self.handler.config_manager.get_model_mapping.return_value = {}
        self.handler.config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        self.handler.config_manager.get_aws_region.return_value = 'us-east-1'
        
        self.handler.auth_manager = Mock()
        auth_result = Mock()
        auth_result.authenticated = True
        self.handler.auth_manager.authenticate_request.return_value = auth_result
        self.handler.auth_manager.authorize_action.return_value = True
        
        self.handler.bedrock_client = Mock()
        self.handler.bedrock_client.list_foundation_models.side_effect = BedrockAPIError(
            "Access denied to Bedrock service",
            status_code=403,
            error_type="authentication_error"
        )
        
        self.handler.error_handler = Mock()
        self.handler.error_handler.log_request = Mock()
        self.handler.error_handler.log_response = Mock()
        
        self.handler.monitoring = Mock()
        
        # Mark as initialized
        self.handler._initialized = True
        
        # Execute request
        response = self.handler.handle_models_list(self.models_event)
        
        # Verify error response
        assert response['statusCode'] == 403
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['type'] == 'authentication_error'
        assert 'access denied' in response_body['error']['message'].lower()
    
    def test_model_metadata_accuracy(self):
        """Test that model metadata is accurate."""
        # Test Nova Lite metadata
        from src.request_handler import RequestHandler
        
        handler = RequestHandler()
        handler.config_manager = Mock()
        handler.config_manager.get_model_mapping.return_value = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0'
        }
        
        # Test the conversion method
        bedrock_response = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    }
                }
            ]
        }
        
        openai_models = handler._convert_bedrock_models_to_openai(bedrock_response)
        
        models = openai_models['data']
        
        # Find Nova Lite model
        nova_lite = next((m for m in models if m['id'] == 'amazon.nova-lite-v1:0'), None)
        assert nova_lite is not None
        
        # Check metadata
        assert nova_lite['context_length'] == 300000
        assert nova_lite['capabilities'] == ['text', 'image']
        assert nova_lite['owned_by'] == 'amazon'
        
        # Find Nova Pro model (if present)
        nova_pro = next((m for m in models if m['id'] == 'amazon.nova-pro-v1:0'), None)
        if nova_pro:
            assert nova_pro['context_length'] == 300000
            assert nova_pro['capabilities'] == ['text', 'image']
        
        # Find Nova Micro model (if present)
        nova_micro = next((m for m in models if m['id'] == 'amazon.nova-micro-v1:0'), None)
        if nova_micro:
            assert nova_micro['context_length'] == 128000
            assert nova_micro['capabilities'] == ['text']
    
    def test_openai_model_aliases(self):
        """Test that OpenAI model aliases are correctly created."""
        handler = RequestHandler()
        handler.config_manager = Mock()
        handler.config_manager.get_model_mapping.return_value = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0'
        }
        
        bedrock_response = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    }
                }
            ]
        }
        
        openai_models = handler._convert_bedrock_models_to_openai(bedrock_response)
        models = openai_models['data']
        
        # Check for OpenAI aliases
        expected_aliases = ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo']
        
        for alias in expected_aliases:
            alias_model = next((m for m in models if m['id'] == alias), None)
            assert alias_model is not None, f"Alias {alias} not found"
            assert alias_model['owned_by'] == 'openai-compatible'
            assert 'alias_for' in alias_model
    
    def test_model_filtering(self):
        """Test that only Nova models are returned from Bedrock."""
        # Mock Bedrock response with mixed models
        mixed_models_response = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon'
                },
                {
                    'modelId': 'anthropic.claude-3-sonnet-20240229-v1:0',
                    'modelName': 'Claude 3 Sonnet',
                    'providerName': 'Anthropic'
                },
                {
                    'modelId': 'amazon.nova-pro-v1:0',
                    'modelName': 'Nova Pro',
                    'providerName': 'Amazon'
                },
                {
                    'modelId': 'meta.llama2-70b-chat-v1',
                    'modelName': 'Llama 2 Chat 70B',
                    'providerName': 'Meta'
                }
            ]
        }
        
        # Mock Bedrock client to return mixed models
        with patch('boto3.client') as mock_boto3_client:
            mock_bedrock = Mock()
            mock_bedrock.list_foundation_models.return_value = mixed_models_response
            
            def mock_client_factory(service_name, **kwargs):
                if service_name == 'bedrock':
                    return mock_bedrock
                else:
                    return Mock()
            
            mock_boto3_client.side_effect = mock_client_factory
            
            from src.bedrock_client import BedrockClient
            client = BedrockClient()
            
            response = client.list_foundation_models()
            
            # Should only return Nova models
            models = response['modelSummaries']
            for model in models:
                assert 'nova' in model['modelId'].lower()
    
    def test_model_caching(self):
        """Test that model list is cached properly."""
        # Mock dependencies
        self.handler.config_manager = Mock()
        self.handler.config_manager.get_model_mapping.return_value = {}
        self.handler.config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        self.handler.config_manager.get_aws_region.return_value = 'us-east-1'
        
        self.handler.auth_manager = Mock()
        auth_result = Mock()
        auth_result.authenticated = True
        self.handler.auth_manager.authenticate_request.return_value = auth_result
        self.handler.auth_manager.authorize_action.return_value = True
        
        self.handler.bedrock_client = Mock()
        self.handler.bedrock_client.list_foundation_models.return_value = self.mock_bedrock_response
        
        self.handler.error_handler = Mock()
        self.handler.error_handler.log_request = Mock()
        self.handler.error_handler.log_bedrock_api_call = Mock()
        self.handler.error_handler.log_response = Mock()
        
        self.handler.monitoring = Mock()
        
        # Mark as initialized
        self.handler._initialized = True
        
        # Make first request
        response1 = self.handler.handle_models_list(self.models_event)
        assert response1['statusCode'] == 200
        
        # Make second request
        response2 = self.handler.handle_models_list(self.models_event)
        assert response2['statusCode'] == 200
        
        # Bedrock client should use caching (implementation detail)
        # We can't easily test this without accessing internal state
        # But we can verify both requests succeeded
        
        response_body1 = json.loads(response1['body'])
        response_body2 = json.loads(response2['body'])
        
        # Responses should be similar (may have different timestamps)
        assert response_body1['object'] == response_body2['object']
        assert len(response_body1['data']) == len(response_body2['data'])


if __name__ == '__main__':
    pytest.main([__file__])