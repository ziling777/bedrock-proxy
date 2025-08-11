"""
Tests for RequestHandler.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.request_handler import RequestHandler
from src.openai_client import OpenAIAPIError


class TestRequestHandler:
    """Test cases for RequestHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = RequestHandler()
    
    def teardown_method(self):
        """Clean up after tests."""
        self.handler.cleanup()
    
    def test_initialization_success(self):
        """Test successful initialization."""
        # Mock config manager directly on the instance
        mock_config = Mock()
        mock_config.get_openai_api_key.return_value = 'sk-test-key'
        mock_config.get_model_mapping.return_value = {'test': 'gpt-4o-mini'}
        mock_config.get_timeout_settings.return_value = {'openai_api_timeout': 30}
        self.handler.config_manager = mock_config
        
        # Initialize
        self.handler._initialize()
        
        assert self.handler._initialized is True
        assert self.handler.openai_client is not None
        assert self.handler.format_converter is not None
    
    @patch('src.request_handler.ConfigManager')
    def test_initialization_failure(self, mock_config_class):
        """Test initialization failure."""
        # Mock config manager to raise exception
        mock_config_class.side_effect = Exception("Config error")
        
        with pytest.raises(RuntimeError, match="Initialization failed"):
            self.handler._initialize()
    
    def test_parse_request_body_valid_json(self):
        """Test parsing valid JSON request body."""
        event = {
            'body': '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
        }
        
        result = self.handler._parse_request_body(event)
        
        assert result is not None
        assert result['model'] == 'gpt-4o-mini'
        assert len(result['messages']) == 1
    
    def test_parse_request_body_invalid_json(self):
        """Test parsing invalid JSON request body."""
        event = {
            'body': 'invalid json'
        }
        
        result = self.handler._parse_request_body(event)
        
        assert result is None
    
    def test_parse_request_body_missing_body(self):
        """Test parsing request with missing body."""
        event = {}
        
        result = self.handler._parse_request_body(event)
        
        assert result is None
    
    def test_parse_request_body_base64_encoded(self):
        """Test parsing base64 encoded request body."""
        import base64
        
        original_data = '{"test": "data"}'
        encoded_data = base64.b64encode(original_data.encode('utf-8')).decode('utf-8')
        
        event = {
            'body': encoded_data,
            'isBase64Encoded': True
        }
        
        result = self.handler._parse_request_body(event)
        
        assert result is not None
        assert result['test'] == 'data'
    
    @patch.object(RequestHandler, '_initialize')
    def test_handle_chat_completion_success(self, mock_init):
        """Test successful chat completion handling."""
        # Mock dependencies
        mock_converter = Mock()
        mock_converter.validate_bedrock_request.return_value = True
        mock_converter.bedrock_to_openai_request.return_value = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        mock_converter.openai_to_bedrock_response.return_value = {
            'id': 'chatcmpl-test',
            'choices': [{'message': {'content': 'Hi there!'}}]
        }
        mock_converter.validate_openai_response.return_value = True
        
        mock_client = Mock()
        mock_client.chat_completion.return_value = {
            'id': 'chatcmpl-test',
            'choices': [{'message': {'content': 'Hi there!'}}]
        }
        
        self.handler.format_converter = mock_converter
        self.handler.openai_client = mock_client
        
        event = {
            'body': '{"modelId": "amazon.nova-lite-v1:0", "messages": [{"role": "user", "content": [{"text": "Hello"}]}]}'
        }
        
        result = self.handler.handle_chat_completion(event)
        
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert response_body['id'] == 'chatcmpl-test'
    
    @patch.object(RequestHandler, '_initialize')
    def test_handle_chat_completion_invalid_request(self, mock_init):
        """Test chat completion with invalid request."""
        mock_converter = Mock()
        mock_converter.validate_bedrock_request.return_value = False
        
        self.handler.format_converter = mock_converter
        
        event = {
            'body': '{"invalid": "request"}'
        }
        
        result = self.handler.handle_chat_completion(event)
        
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert 'error' in response_body
    
    @patch.object(RequestHandler, '_initialize')
    def test_handle_chat_completion_openai_error(self, mock_init):
        """Test chat completion with OpenAI API error."""
        mock_converter = Mock()
        mock_converter.validate_bedrock_request.return_value = True
        mock_converter.bedrock_to_openai_request.return_value = {'model': 'gpt-4o-mini'}
        
        mock_client = Mock()
        mock_client.chat_completion.side_effect = OpenAIAPIError("API Error", 429, "rate_limit_error")
        
        self.handler.format_converter = mock_converter
        self.handler.openai_client = mock_client
        
        event = {
            'body': '{"modelId": "test", "messages": []}'
        }
        
        result = self.handler.handle_chat_completion(event)
        
        assert result['statusCode'] == 429
        response_body = json.loads(result['body'])
        assert response_body['error']['type'] == 'rate_limit_error'
    
    @patch.object(RequestHandler, '_initialize')
    def test_handle_models_list_success(self, mock_init):
        """Test successful models list handling."""
        mock_client = Mock()
        mock_client.list_models.return_value = {
            'object': 'list',
            'data': [
                {'id': 'gpt-4o-mini', 'object': 'model'}
            ]
        }
        
        self.handler.openai_client = mock_client
        
        event = {}
        
        result = self.handler.handle_models_list(event)
        
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert response_body['object'] == 'list'
        assert len(response_body['data']) == 1
    
    @patch.object(RequestHandler, '_initialize')
    def test_handle_models_list_openai_error(self, mock_init):
        """Test models list with OpenAI API error."""
        mock_client = Mock()
        mock_client.list_models.side_effect = OpenAIAPIError("API Error", 401, "invalid_api_key")
        
        self.handler.openai_client = mock_client
        
        event = {}
        
        result = self.handler.handle_models_list(event)
        
        assert result['statusCode'] == 401
        response_body = json.loads(result['body'])
        assert response_body['error']['type'] == 'authentication_error'
    
    def test_handle_health_check_healthy(self):
        """Test health check with healthy status."""
        with patch.object(self.handler, '_initialize'):
            mock_client = Mock()
            mock_client.validate_api_key.return_value = True
            self.handler.openai_client = mock_client
            
            event = {}
            
            result = self.handler.handle_health_check(event)
            
            assert result['statusCode'] == 200
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'healthy'
            assert response_body['openai_api'] == 'connected'
    
    def test_handle_health_check_unhealthy(self):
        """Test health check with unhealthy status."""
        with patch.object(self.handler, '_initialize', side_effect=Exception("Init error")):
            event = {}
            
            result = self.handler.handle_health_check(event)
            
            assert result['statusCode'] == 503
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'unhealthy'
            assert 'error' in response_body
    
    def test_route_request_chat_completion(self):
        """Test request routing to chat completion."""
        with patch.object(self.handler, 'handle_chat_completion') as mock_handler:
            mock_handler.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'POST',
                'path': '/v1/chat/completions'
            }
            
            result = self.handler.route_request(event)
            
            mock_handler.assert_called_once_with(event)
            assert result['statusCode'] == 200
    
    def test_route_request_models_list(self):
        """Test request routing to models list."""
        with patch.object(self.handler, 'handle_models_list') as mock_handler:
            mock_handler.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': '/v1/models'
            }
            
            result = self.handler.route_request(event)
            
            mock_handler.assert_called_once_with(event)
            assert result['statusCode'] == 200
    
    def test_route_request_health_check(self):
        """Test request routing to health check."""
        with patch.object(self.handler, 'handle_health_check') as mock_handler:
            mock_handler.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': '/health'
            }
            
            result = self.handler.route_request(event)
            
            mock_handler.assert_called_once_with(event)
            assert result['statusCode'] == 200
    
    def test_route_request_cors_preflight(self):
        """Test CORS preflight request handling."""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/v1/chat/completions'
        }
        
        result = self.handler.route_request(event)
        
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        assert result['body'] == ''
    
    def test_route_request_not_found(self):
        """Test request routing for unsupported endpoint."""
        event = {
            'httpMethod': 'GET',
            'path': '/unsupported/endpoint'
        }
        
        result = self.handler.route_request(event)
        
        assert result['statusCode'] == 404
        response_body = json.loads(result['body'])
        assert 'Endpoint not found' in response_body['error']['message']
    
    def test_extract_auth_token_bearer(self):
        """Test extracting Bearer token from Authorization header."""
        event = {
            'headers': {
                'Authorization': 'Bearer sk-test-token-123'
            }
        }
        
        token = self.handler._extract_auth_token(event)
        
        assert token == 'sk-test-token-123'
    
    def test_extract_auth_token_api_key(self):
        """Test extracting token from X-API-Key header."""
        event = {
            'headers': {
                'X-API-Key': 'api-key-123'
            }
        }
        
        token = self.handler._extract_auth_token(event)
        
        assert token == 'api-key-123'
    
    def test_extract_auth_token_case_insensitive(self):
        """Test extracting token with case-insensitive headers."""
        event = {
            'headers': {
                'authorization': 'Bearer sk-test-token-456'
            }
        }
        
        token = self.handler._extract_auth_token(event)
        
        assert token == 'sk-test-token-456'
    
    def test_extract_auth_token_none(self):
        """Test extracting token when none present."""
        event = {
            'headers': {}
        }
        
        token = self.handler._extract_auth_token(event)
        
        assert token is None
    
    def test_validate_request_auth_with_token(self):
        """Test request authentication validation with token."""
        event = {
            'headers': {
                'Authorization': 'Bearer sk-test-token'
            }
        }
        
        result = self.handler.validate_request_auth(event)
        
        # Currently returns True for development
        assert result is True
    
    def test_validate_request_auth_without_token(self):
        """Test request authentication validation without token."""
        event = {
            'headers': {}
        }
        
        result = self.handler.validate_request_auth(event)
        
        # Currently returns True for development
        assert result is True
    
    def test_create_success_response(self):
        """Test creating successful response."""
        data = {'message': 'success'}
        
        result = self.handler._create_success_response(data)
        
        assert result['statusCode'] == 200
        assert 'Content-Type' in result['headers']
        assert 'Access-Control-Allow-Origin' in result['headers']
        response_body = json.loads(result['body'])
        assert response_body['message'] == 'success'
    
    def test_create_error_response(self):
        """Test creating error response."""
        result = self.handler._create_error_response(400, "Bad request", "validation_error")
        
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error']['message'] == "Bad request"
        assert response_body['error']['type'] == "validation_error"
        assert response_body['error']['code'] == "400"
    
    def test_context_manager(self):
        """Test RequestHandler as context manager."""
        with patch.object(self.handler, 'cleanup') as mock_cleanup:
            with self.handler as handler:
                assert handler is self.handler
            mock_cleanup.assert_called_once()
    
    def test_cleanup(self):
        """Test cleanup method."""
        mock_client = Mock()
        self.handler.openai_client = mock_client
        
        self.handler.cleanup()
        
        mock_client.close.assert_called_once()