#!/usr/bin/env python3
"""
Simple integration test for the models list endpoint.
"""
import json
import os
import sys
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.request_handler import RequestHandler


def test_models_endpoint():
    """Test the models endpoint with mocked dependencies."""
    
    # Mock event
    event = {
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
    
    # Mock Bedrock response
    mock_bedrock_response = {
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
            }
        ]
    }
    
    with patch('src.config_manager.ConfigManager') as mock_config_class, \
         patch('src.auth.AuthManager') as mock_auth_class, \
         patch('src.bedrock_client.BedrockClient') as mock_bedrock_class:
        
        # Setup config manager mock
        mock_config = Mock()
        mock_config.get_model_mapping.return_value = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0'
        }
        mock_config.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        mock_config.get_aws_region.return_value = 'us-east-1'
        mock_config_class.return_value = mock_config
        
        # Setup auth manager mock
        mock_auth = Mock()
        mock_auth_result = Mock()
        mock_auth_result.authenticated = True
        mock_auth.authenticate_request.return_value = mock_auth_result
        mock_auth.authorize_action.return_value = True
        mock_auth_class.return_value = mock_auth
        
        # Setup Bedrock client mock
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = mock_bedrock_response
        mock_bedrock_class.return_value = mock_bedrock
        
        # Create handler and test
        handler = RequestHandler()
        response = handler.handle_models_list(event)
        
        # Verify response
        print(f"Status Code: {response['statusCode']}")
        
        if response['statusCode'] == 200:
            response_body = json.loads(response['body'])
            print(f"Response: {json.dumps(response_body, indent=2)}")
            
            # Check structure
            assert response_body['object'] == 'list'
            assert 'data' in response_body
            
            models = response_body['data']
            print(f"Found {len(models)} models")
            
            # Check for Nova Lite model
            nova_lite = next((m for m in models if m['id'] == 'amazon.nova-lite-v1:0'), None)
            if nova_lite:
                print("✓ Nova Lite model found")
                print(f"  Context length: {nova_lite.get('context_length')}")
                print(f"  Capabilities: {nova_lite.get('capabilities')}")
            
            # Check for alias model
            gpt_4o_mini = next((m for m in models if m['id'] == 'gpt-4o-mini'), None)
            if gpt_4o_mini:
                print("✓ GPT-4o-mini alias found")
                print(f"  Maps to: {gpt_4o_mini.get('root')}")
            
            print("✅ Models endpoint test passed!")
        else:
            print(f"❌ Test failed with status {response['statusCode']}")
            print(f"Response: {response.get('body', 'No body')}")


if __name__ == '__main__':
    test_models_endpoint()