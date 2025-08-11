"""
Pytest configuration and fixtures.
"""
import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any


@pytest.fixture
def mock_secrets_manager():
    """Mock AWS Secrets Manager client."""
    mock_client = Mock()
    mock_client.get_secret_value.return_value = {
        'SecretString': json.dumps({
            'openai_api_key': 'sk-test-key-123',
            'model_mappings': {
                'amazon.nova-lite-v1:0': 'gpt-4o-mini',
                'amazon.nova-pro-v1:0': 'gpt-4o-mini'
            },
            'timeout_settings': {
                'openai_api_timeout': 30,
                'secrets_manager_timeout': 10
            }
        })
    }
    return mock_client


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager."""
    mock_manager = Mock()
    mock_manager.get_openai_api_key.return_value = 'sk-test-key-123'
    mock_manager.get_model_mapping.return_value = {
        'amazon.nova-lite-v1:0': 'gpt-4o-mini',
        'amazon.nova-pro-v1:0': 'gpt-4o-mini'
    }
    mock_manager.get_timeout_settings.return_value = {
        'openai_api_timeout': 30,
        'secrets_manager_timeout': 10,
        'lambda_timeout': 300
    }
    mock_manager.get_debug_mode.return_value = False
    mock_manager.get_aws_region.return_value = 'us-east-1'
    return mock_manager


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    mock_client = Mock()
    mock_client.chat_completion.return_value = {
        'id': 'chatcmpl-test123',
        'object': 'chat.completion',
        'created': 1234567890,
        'model': 'gpt-4o-mini',
        'choices': [{
            'index': 0,
            'message': {
                'role': 'assistant',
                'content': 'Hello! How can I help you?'
            },
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 8,
            'total_tokens': 18
        }
    }
    mock_client.list_models.return_value = {
        'object': 'list',
        'data': [
            {
                'id': 'gpt-4o-mini',
                'object': 'model',
                'created': 1234567890,
                'owned_by': 'openai'
            }
        ]
    }
    mock_client.validate_api_key.return_value = True
    mock_client.get_model_info.return_value = {
        'id': 'gpt-4o-mini',
        'object': 'model',
        'created': 1234567890,
        'owned_by': 'openai'
    }
    return mock_client


@pytest.fixture
def sample_openai_response():
    """Sample OpenAI API response."""
    return {
        'id': 'chatcmpl-test123',
        'object': 'chat.completion',
        'created': 1234567890,
        'model': 'gpt-4o-mini',
        'choices': [{
            'index': 0,
            'message': {
                'role': 'assistant',
                'content': 'Hello! How can I help you?'
            },
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 8,
            'total_tokens': 18
        }
    }


@pytest.fixture
def sample_bedrock_request():
    """Sample Bedrock format request."""
    return {
        'modelId': 'amazon.nova-lite-v1:0',
        'messages': [
            {
                'role': 'user',
                'content': [{'text': 'Hello, how are you?'}]
            }
        ],
        'inferenceConfig': {
            'temperature': 0.7,
            'maxTokens': 100,
            'topP': 0.9
        }
    }


@pytest.fixture
def sample_openai_request():
    """Sample OpenAI format request."""
    return {
        'model': 'gpt-4o-mini',
        'messages': [
            {
                'role': 'user',
                'content': 'Hello, how are you?'
            }
        ],
        'temperature': 0.7,
        'max_tokens': 100,
        'top_p': 0.9
    }


@pytest.fixture
def sample_api_gateway_event():
    """Sample API Gateway event."""
    return {
        'httpMethod': 'POST',
        'path': '/v1/chat/completions',
        'headers': {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-key'
        },
        'body': '{"model": "amazon.nova-lite-v1:0", "messages": [{"role": "user", "content": "Hello"}]}',
        'requestContext': {
            'requestId': 'test-request-id',
            'stage': 'prod'
        }
    }