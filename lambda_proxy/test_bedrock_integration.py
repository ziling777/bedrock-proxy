#!/usr/bin/env python3
"""
Simple test to verify Bedrock integration is working.
"""
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.request_handler import RequestHandler


def test_bedrock_chat_completion():
    """Test that chat completion uses Bedrock instead of OpenAI."""
    
    # Mock event
    event = {
        'httpMethod': 'POST',
        'path': '/v1/chat/completions',
        'headers': {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'model': 'gpt-4o-mini',
            'messages': [
                {
                    'role': 'user',
                    'content': 'Hello!'
                }
            ]
        }),
        'requestContext': {
            'requestId': 'test-request-bedrock',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock all the dependencies at the instance level
    handler.config_manager = Mock()
    handler.config_manager.get_model_mapping.return_value = {
        'gpt-4o-mini': 'amazon.nova-lite-v1:0'
    }
    handler.config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
    handler.config_manager.get_aws_region.return_value = 'us-east-1'
    
    handler.auth_manager = Mock()
    auth_result = Mock()
    auth_result.authenticated = True
    handler.auth_manager.authenticate_request.return_value = auth_result
    handler.auth_manager.authorize_action.return_value = True
    
    handler.bedrock_client = Mock()
    handler.bedrock_client.converse.return_value = {
        'output': {
            'message': {
                'role': 'assistant',
                'content': [{'text': 'Hello! How can I help you?'}]
            }
        },
        'stopReason': 'end_turn',
        'usage': {
            'inputTokens': 5,
            'outputTokens': 10,
            'totalTokens': 15
        }
    }
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_bedrock_api_call = Mock()
    handler.error_handler.log_response = Mock()
    
    # Mark as initialized to skip the initialization process
    handler._initialized = True
    
    # Test the handler
    response = handler.handle_chat_completion(event)
    
    print(f"Status Code: {response['statusCode']}")
    
    if response['statusCode'] == 200:
        response_body = json.loads(response['body'])
        print(f"Response: {json.dumps(response_body, indent=2)}")
        
        # Verify Bedrock client was called
        handler.bedrock_client.converse.assert_called_once()
        print("✓ Bedrock client was called instead of OpenAI")
        
        # Verify the response structure
        assert 'choices' in response_body
        assert len(response_body['choices']) > 0
        choice = response_body['choices'][0]
        assert 'message' in choice
        assert choice['message']['role'] == 'assistant'
        
        print("✅ Bedrock integration test passed!")
        return True
    else:
        print(f"❌ Test failed with status {response['statusCode']}")
        if 'body' in response:
            print(f"Error: {response['body']}")
        return False


def test_request_validation():
    """Test that OpenAI request validation works."""
    
    handler = RequestHandler()
    
    # Test valid request
    valid_request = {
        'model': 'gpt-4o-mini',
        'messages': [
            {'role': 'user', 'content': 'Hello'}
        ]
    }
    
    assert handler._validate_openai_request(valid_request) == True
    print("✓ Valid request validation passed")
    
    # Test invalid request - missing model
    invalid_request1 = {
        'messages': [
            {'role': 'user', 'content': 'Hello'}
        ]
    }
    
    assert handler._validate_openai_request(invalid_request1) == False
    print("✓ Invalid request (missing model) validation passed")
    
    # Test invalid request - missing messages
    invalid_request2 = {
        'model': 'gpt-4o-mini'
    }
    
    assert handler._validate_openai_request(invalid_request2) == False
    print("✓ Invalid request (missing messages) validation passed")
    
    # Test invalid request - empty messages
    invalid_request3 = {
        'model': 'gpt-4o-mini',
        'messages': []
    }
    
    assert handler._validate_openai_request(invalid_request3) == False
    print("✓ Invalid request (empty messages) validation passed")
    
    print("✅ Request validation tests passed!")
    return True


if __name__ == '__main__':
    print("Testing Bedrock integration...")
    success1 = test_bedrock_chat_completion()
    
    print("\nTesting request validation...")
    success2 = test_request_validation()
    
    if success1 and success2:
        print("\n✅ All Bedrock integration tests passed!")
    else:
        print("\n❌ Some tests failed!")