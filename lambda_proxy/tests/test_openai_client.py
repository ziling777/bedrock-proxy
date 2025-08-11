"""
Tests for OpenAI client.
"""
import json
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, ConnectionError, RequestException

from src.openai_client import OpenAIClient, OpenAIAPIError


class TestOpenAIClient:
    """Test cases for OpenAIClient."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "sk-test-key-123"
        self.client = OpenAIClient(api_key=self.api_key, timeout=30)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.client.close()
    
    @patch('requests.Session.post')
    def test_chat_completion_success(self, mock_post):
        """Test successful chat completion request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
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
        mock_post.return_value = mock_response
        
        # Test request
        request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'temperature': 0.7
        }
        
        response = self.client.chat_completion(request)
        
        # Verify response
        assert response['id'] == 'chatcmpl-test123'
        assert response['model'] == 'gpt-4o-mini'
        assert len(response['choices']) == 1
        assert response['choices'][0]['message']['content'] == 'Hello! How can I help you?'
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json'] == request
        assert call_args[1]['timeout'] == 30
    
    @patch('requests.Session.post')
    def test_chat_completion_api_error(self, mock_post):
        """Test chat completion with API error response."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'message': 'Invalid request',
                'type': 'invalid_request_error',
                'code': 'invalid_request'
            }
        }
        mock_post.return_value = mock_response
        
        request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        
        with pytest.raises(OpenAIAPIError) as exc_info:
            self.client.chat_completion(request)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_type == 'invalid_request_error'
        assert 'Invalid request' in str(exc_info.value)
    
    @patch('requests.Session.post')
    def test_chat_completion_timeout(self, mock_post):
        """Test chat completion with timeout error."""
        mock_post.side_effect = Timeout("Request timeout")
        
        request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        
        with pytest.raises(OpenAIAPIError) as exc_info:
            self.client.chat_completion(request)
        
        assert exc_info.value.status_code == 408
        assert exc_info.value.error_type == 'timeout_error'
    
    @patch('requests.Session.post')
    def test_chat_completion_connection_error(self, mock_post):
        """Test chat completion with connection error."""
        mock_post.side_effect = ConnectionError("Connection failed")
        
        request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        
        with pytest.raises(OpenAIAPIError) as exc_info:
            self.client.chat_completion(request)
        
        assert exc_info.value.status_code == 503
        assert exc_info.value.error_type == 'connection_error'
    
    @patch('requests.Session.get')
    def test_list_models_success(self, mock_get):
        """Test successful models list request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'object': 'list',
            'data': [
                {
                    'id': 'gpt-4o-mini',
                    'object': 'model',
                    'created': 1234567890,
                    'owned_by': 'openai'
                },
                {
                    'id': 'gpt-4',
                    'object': 'model',
                    'created': 1234567890,
                    'owned_by': 'openai'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        response = self.client.list_models()
        
        # Verify response
        assert response['object'] == 'list'
        assert len(response['data']) == 2
        assert response['data'][0]['id'] == 'gpt-4o-mini'
        assert response['data'][1]['id'] == 'gpt-4'
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]['timeout'] == 30
    
    @patch('requests.Session.get')
    def test_list_models_error(self, mock_get):
        """Test models list with error response."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {
                'message': 'Invalid API key',
                'type': 'invalid_request_error'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(OpenAIAPIError) as exc_info:
            self.client.list_models()
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_type == 'invalid_request_error'
    
    def test_parse_error_response_with_error_field(self):
        """Test parsing error response with error field."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'error': {
                'message': 'Test error',
                'type': 'test_error',
                'code': 'test_code'
            }
        }
        
        error_data = self.client._parse_error_response(mock_response)
        
        assert error_data['message'] == 'Test error'
        assert error_data['type'] == 'test_error'
        assert error_data['code'] == 'test_code'
    
    def test_parse_error_response_invalid_json(self):
        """Test parsing error response with invalid JSON."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        error_data = self.client._parse_error_response(mock_response)
        
        assert error_data['message'] == 'Internal Server Error'
        assert error_data['type'] == 'unknown_error'
        assert error_data['code'] == '500'
    
    @patch('requests.Session.get')
    def test_validate_api_key_success(self, mock_get):
        """Test successful API key validation."""
        # Mock successful models response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'object': 'list', 'data': []}
        mock_get.return_value = mock_response
        
        result = self.client.validate_api_key()
        
        assert result is True
    
    @patch('requests.Session.get')
    def test_validate_api_key_invalid(self, mock_get):
        """Test API key validation with invalid key."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {'message': 'Invalid API key', 'type': 'invalid_request_error'}
        }
        mock_get.return_value = mock_response
        
        result = self.client.validate_api_key()
        
        assert result is False
    
    @patch('requests.Session.get')
    def test_get_model_info_found(self, mock_get):
        """Test getting model info for existing model."""
        # Mock models response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
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
        mock_get.return_value = mock_response
        
        model_info = self.client.get_model_info('gpt-4o-mini')
        
        assert model_info is not None
        assert model_info['id'] == 'gpt-4o-mini'
        assert model_info['object'] == 'model'
    
    @patch('requests.Session.get')
    def test_get_model_info_not_found(self, mock_get):
        """Test getting model info for non-existing model."""
        # Mock models response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'object': 'list',
            'data': [
                {
                    'id': 'gpt-4',
                    'object': 'model',
                    'created': 1234567890,
                    'owned_by': 'openai'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        model_info = self.client.get_model_info('non-existing-model')
        
        assert model_info is None
    
    def test_context_manager(self):
        """Test OpenAI client as context manager."""
        with patch.object(self.client, 'close') as mock_close:
            with self.client as client:
                assert client is self.client
            mock_close.assert_called_once()
    
    def test_initialization(self):
        """Test client initialization."""
        client = OpenAIClient(api_key="sk-test", timeout=60)
        
        assert client.api_key == "sk-test"
        assert client.timeout == 60
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'] == 'Bearer sk-test'
        assert client.session.headers['Content-Type'] == 'application/json'
        
        client.close()
    
    @patch('requests.Session.post')
    def test_retry_mechanism(self, mock_post):
        """Test retry mechanism on transient failures."""
        # First call fails, second succeeds
        mock_response_error = Mock()
        mock_response_error.status_code = 500
        mock_response_error.json.return_value = {
            'error': {'message': 'Server error', 'type': 'server_error'}
        }
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'id': 'chatcmpl-test123',
            'choices': [{'message': {'content': 'Success'}}]
        }
        
        mock_post.side_effect = [
            OpenAIAPIError("Server error", 500, "server_error"),
            mock_response_success
        ]
        
        request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        
        # This should succeed after retry
        response = self.client.chat_completion(request)
        
        assert response['id'] == 'chatcmpl-test123'
        # Verify it was called twice (original + 1 retry)
        assert mock_post.call_count == 2