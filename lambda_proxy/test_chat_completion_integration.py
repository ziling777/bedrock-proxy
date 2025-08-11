#!/usr/bin/env python3
"""
Integration tests for chat completion endpoint with Bedrock.
"""
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.request_handler import RequestHandler
from src.bedrock_client import BedrockAPIError


def test_chat_completion_basic():
    """Test basic chat completion functionality."""
    print("Testing basic chat completion...")
    
    # Mock event
    event = {
        'httpMethod': 'POST',
        'path': '/v1/chat/completions',
        'headers': {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json',
            'User-Agent': 'TestClient/1.0'
        },
        'body': json.dumps({
            'model': 'gpt-4o-mini',
            'messages': [
                {
                    'role': 'user',
                    'content': 'Hello, how are you?'
                }
            ],
            'temperature': 0.7,
            'max_tokens': 100
        }),
        'requestContext': {
            'requestId': 'test-request-basic',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Mock Bedrock response
    mock_bedrock_response = {
        'output': {
            'message': {
                'role': 'assistant',
                'content': [
                    {
                        'text': 'Hello! I\'m doing well, thank you for asking. How can I help you today?'
                    }
                ]
            }
        },
        'stopReason': 'end_turn',
        'usage': {
            'inputTokens': 12,
            'outputTokens': 18,
            'totalTokens': 30
        }
    }
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock all dependencies
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
    handler.bedrock_client.converse.return_value = mock_bedrock_response
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_bedrock_api_call = Mock()
    handler.error_handler.log_response = Mock()
    
    handler.monitoring = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Execute request
    response = handler.handle_chat_completion(event)
    
    # Verify response
    assert response['statusCode'] == 200
    
    response_body = json.loads(response['body'])
    
    # Check OpenAI format
    assert response_body['object'] == 'chat.completion'
    assert 'id' in response_body
    assert 'created' in response_body
    assert response_body['model'] == 'gpt-4o-mini'
    
    # Check choices
    assert len(response_body['choices']) == 1
    choice = response_body['choices'][0]
    assert choice['index'] == 0
    assert choice['message']['role'] == 'assistant'
    assert 'help you today' in choice['message']['content']
    assert choice['finish_reason'] == 'stop'
    
    # Check usage
    usage = response_body['usage']
    assert usage['prompt_tokens'] == 12
    assert usage['completion_tokens'] == 18
    assert usage['total_tokens'] == 30
    
    # Verify Bedrock client was called
    handler.bedrock_client.converse.assert_called_once()
    
    # Verify monitoring was called
    handler.monitoring.record_request.assert_called_once()
    handler.monitoring.record_bedrock_call.assert_called_once()
    
    print("✓ Basic chat completion test passed")
    return True


def test_chat_completion_multimodal():
    """Test chat completion with image input."""
    print("Testing multimodal chat completion...")
    
    # Create a simple base64 image
    import base64
    test_image_data = base64.b64encode(b'fake_jpeg_data').decode('utf-8')
    
    # Mock event with image
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
                    'content': [
                        {
                            'type': 'text',
                            'text': 'What do you see in this image?'
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{test_image_data}'
                            }
                        }
                    ]
                }
            ]
        }),
        'requestContext': {
            'requestId': 'test-request-multimodal',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Mock Bedrock response
    mock_bedrock_response = {
        'output': {
            'message': {
                'role': 'assistant',
                'content': [
                    {
                        'text': 'I can see an image, but I cannot determine its specific contents from the provided data.'
                    }
                ]
            }
        },
        'stopReason': 'end_turn',
        'usage': {
            'inputTokens': 25,
            'outputTokens': 20,
            'totalTokens': 45
        }
    }
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock dependencies
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
    handler.bedrock_client.converse.return_value = mock_bedrock_response
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_bedrock_api_call = Mock()
    handler.error_handler.log_response = Mock()
    
    handler.monitoring = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Execute request
    response = handler.handle_chat_completion(event)
    
    # Verify response
    assert response['statusCode'] == 200
    
    response_body = json.loads(response['body'])
    
    # Check that response is in OpenAI format
    assert response_body['object'] == 'chat.completion'
    assert len(response_body['choices']) == 1
    
    choice = response_body['choices'][0]
    assert choice['message']['role'] == 'assistant'
    assert 'image' in choice['message']['content'].lower()
    
    # Verify Bedrock client was called with converted request
    handler.bedrock_client.converse.assert_called_once()
    bedrock_request = handler.bedrock_client.converse.call_args[0][0]
    
    # Check that the request was converted to Bedrock format
    assert bedrock_request['modelId'] == 'amazon.nova-lite-v1:0'
    assert len(bedrock_request['messages']) == 1
    
    message = bedrock_request['messages'][0]
    assert message['role'] == 'user'
    assert len(message['content']) == 2  # Text + image
    
    # Check text content
    text_content = message['content'][0]
    assert text_content['text'] == 'What do you see in this image?'
    
    # Check image content
    image_content = message['content'][1]
    assert 'image' in image_content
    assert image_content['image']['format'] == 'jpeg'
    
    print("✓ Multimodal chat completion test passed")
    return True


def test_chat_completion_streaming():
    """Test streaming chat completion."""
    print("Testing streaming chat completion...")
    
    # Mock event with streaming enabled
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
                    'content': 'Tell me a short story'
                }
            ],
            'stream': True,
            'temperature': 0.8
        }),
        'requestContext': {
            'requestId': 'test-request-streaming',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Mock streaming response chunks
    mock_streaming_chunks = [
        {
            'type': 'message_start',
            'data': {
                'role': 'assistant'
            }
        },
        {
            'type': 'content_block_delta',
            'data': {
                'delta': {
                    'text': 'Once upon a time'
                }
            }
        },
        {
            'type': 'content_block_delta',
            'data': {
                'delta': {
                    'text': ', there was a brave knight.'
                }
            }
        },
        {
            'type': 'message_stop',
            'data': {
                'stopReason': 'end_turn'
            }
        },
        {
            'type': 'metadata',
            'data': {
                'usage': {
                    'inputTokens': 8,
                    'outputTokens': 12,
                    'totalTokens': 20
                }
            }
        }
    ]
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock dependencies
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
    handler.bedrock_client.converse_stream.return_value = iter(mock_streaming_chunks)
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_bedrock_api_call = Mock()
    handler.error_handler.log_response = Mock()
    
    handler.monitoring = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Execute request
    response = handler.handle_chat_completion(event)
    
    # Verify response (streaming is converted to regular response for API Gateway)
    assert response['statusCode'] == 200
    
    response_body = json.loads(response['body'])
    
    # Check that response is in OpenAI format
    assert response_body['object'] == 'chat.completion'
    assert len(response_body['choices']) == 1
    
    choice = response_body['choices'][0]
    assert choice['message']['role'] == 'assistant'
    
    # Verify streaming client was called
    handler.bedrock_client.converse_stream.assert_called_once()
    
    print("✓ Streaming chat completion test passed")
    return True


def test_chat_completion_error_handling():
    """Test error handling in chat completion."""
    print("Testing error handling...")
    
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
                    'content': 'Hello'
                }
            ]
        }),
        'requestContext': {
            'requestId': 'test-request-error',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock dependencies
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
    
    # Mock Bedrock client to raise an error
    handler.bedrock_client = Mock()
    handler.bedrock_client.converse.side_effect = BedrockAPIError(
        "Rate limit exceeded",
        status_code=429,
        error_type="rate_limit_error"
    )
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_response = Mock()
    
    handler.monitoring = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Execute request
    response = handler.handle_chat_completion(event)
    
    # Verify error response
    assert response['statusCode'] == 429
    
    response_body = json.loads(response['body'])
    
    # Check error format
    assert 'error' in response_body
    error = response_body['error']
    assert error['type'] == 'rate_limit_error'
    assert 'rate limit' in error['message'].lower()
    assert error['code'] == '429'
    
    print("✓ Error handling test passed")
    return True


def test_request_validation():
    """Test request validation."""
    print("Testing request validation...")
    
    # Test invalid request - missing model
    event = {
        'httpMethod': 'POST',
        'path': '/v1/chat/completions',
        'headers': {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'messages': [
                {
                    'role': 'user',
                    'content': 'Hello'
                }
            ]
        }),
        'requestContext': {
            'requestId': 'test-request-validation',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }
    
    # Create handler with mocked dependencies
    handler = RequestHandler()
    
    # Mock dependencies
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
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_response = Mock()
    handler.error_handler.create_proxy_error = Mock()
    handler.error_handler.create_proxy_error.return_value = Exception("Invalid request")
    
    handler.monitoring = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Execute request - should fail validation
    try:
        response = handler.handle_chat_completion(event)
        # If we get here, validation didn't work as expected
        assert False, "Expected validation error"
    except Exception as e:
        # This is expected
        assert "Invalid request" in str(e)
    
    print("✓ Request validation test passed")
    return True


if __name__ == '__main__':
    print("Running chat completion integration tests...")
    
    tests = [
        test_chat_completion_basic,
        test_chat_completion_multimodal,
        test_chat_completion_streaming,
        test_chat_completion_error_handling,
        test_request_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
    
    print(f"\nIntegration test results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All integration tests passed!")
        exit(0)
    else:
        print("❌ Some integration tests failed!")
        exit(1)