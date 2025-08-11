"""
Tests for Bedrock client integration.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from src.bedrock_client import BedrockClient, BedrockAPIError


class TestBedrockClient:
    """Test cases for the Bedrock client."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = BedrockClient(region='us-east-1')
        
        # Mock Bedrock response
        self.mock_converse_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [
                        {
                            'text': 'Hello! How can I help you today?'
                        }
                    ]
                }
            },
            'stopReason': 'end_turn',
            'usage': {
                'inputTokens': 10,
                'outputTokens': 15,
                'totalTokens': 25
            }
        }
        
        # Mock models response
        self.mock_models_response = {
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
    
    @patch('boto3.client')
    def test_bedrock_client_initialization(self, mock_boto3_client):
        """Test Bedrock client initialization."""
        mock_bedrock = Mock()
        mock_boto3_client.return_value = mock_bedrock
        
        client = BedrockClient(region='us-west-2')
        
        # Access the property to trigger lazy initialization
        _ = client.bedrock_client
        
        mock_boto3_client.assert_called_with(
            'bedrock-runtime',
            region_name='us-west-2'
        )
    
    @patch('boto3.client')
    def test_converse_success(self, mock_boto3_client):
        """Test successful Bedrock converse API call."""
        mock_bedrock = Mock()
        mock_bedrock.converse.return_value = self.mock_converse_response
        mock_boto3_client.return_value = mock_bedrock
        
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': 'Hello!'
                        }
                    ]
                }
            ]
        }
        
        response = self.client.converse(request)
        
        assert response == self.mock_converse_response
        mock_bedrock.converse.assert_called_once_with(**request)
    
    @patch('boto3.client')
    def test_converse_client_error(self, mock_boto3_client):
        """Test Bedrock converse API client error handling."""
        mock_bedrock = Mock()
        mock_bedrock.converse.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'ValidationException',
                    'Message': 'The provided model identifier is invalid.'
                },
                'ResponseMetadata': {
                    'HTTPStatusCode': 400
                }
            },
            operation_name='Converse'
        )
        mock_boto3_client.return_value = mock_bedrock
        
        request = {
            'modelId': 'invalid-model',
            'messages': [{'role': 'user', 'content': [{'text': 'Hello'}]}]
        }
        
        with pytest.raises(BedrockAPIError) as exc_info:
            self.client.converse(request)
        
        error = exc_info.value
        assert error.status_code == 400
        assert error.error_type == 'invalid_request_error'
        assert 'invalid' in error.message.lower()
    
    @patch('boto3.client')
    def test_converse_stream_success(self, mock_boto3_client):
        """Test successful Bedrock converse stream API call."""
        mock_bedrock = Mock()
        
        # Mock streaming response
        mock_stream_events = [
            {
                'messageStart': {
                    'role': 'assistant'
                }
            },
            {
                'contentBlockStart': {
                    'start': {
                        'toolUse': {
                            'toolUseId': 'tool_123'
                        }
                    }
                }
            },
            {
                'contentBlockDelta': {
                    'delta': {
                        'text': 'Hello'
                    }
                }
            },
            {
                'contentBlockDelta': {
                    'delta': {
                        'text': ' there!'
                    }
                }
            },
            {
                'messageStop': {
                    'stopReason': 'end_turn'
                }
            },
            {
                'metadata': {
                    'usage': {
                        'inputTokens': 5,
                        'outputTokens': 10,
                        'totalTokens': 15
                    }
                }
            }
        ]
        
        mock_bedrock.converse_stream.return_value = {
            'stream': mock_stream_events
        }
        mock_boto3_client.return_value = mock_bedrock
        
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [{'role': 'user', 'content': [{'text': 'Hello'}]}]
        }
        
        # Collect streaming events
        events = list(self.client.converse_stream(request))
        
        assert len(events) == 6
        
        # Check event types
        assert events[0]['type'] == 'message_start'
        assert events[1]['type'] == 'content_block_start'
        assert events[2]['type'] == 'content_block_delta'
        assert events[3]['type'] == 'content_block_delta'
        assert events[4]['type'] == 'message_stop'
        assert events[5]['type'] == 'metadata'
        
        # Check event data
        assert events[2]['data']['delta']['text'] == 'Hello'
        assert events[3]['data']['delta']['text'] == ' there!'
        assert events[4]['data']['stopReason'] == 'end_turn'
    
    @patch('boto3.client')
    def test_converse_stream_error(self, mock_boto3_client):
        """Test Bedrock converse stream API error handling."""
        mock_bedrock = Mock()
        mock_bedrock.converse_stream.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'ThrottlingException',
                    'Message': 'Rate limit exceeded'
                },
                'ResponseMetadata': {
                    'HTTPStatusCode': 429
                }
            },
            operation_name='ConverseStream'
        )
        mock_boto3_client.return_value = mock_bedrock
        
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [{'role': 'user', 'content': [{'text': 'Hello'}]}]
        }
        
        with pytest.raises(BedrockAPIError) as exc_info:
            list(self.client.converse_stream(request))
        
        error = exc_info.value
        assert error.status_code == 429
        assert error.error_type == 'streaming_error'
    
    @patch('boto3.client')
    def test_list_foundation_models_success(self, mock_boto3_client):
        """Test successful list foundation models API call."""
        # Mock both bedrock-runtime and bedrock clients
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = self.mock_models_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        response = self.client.list_foundation_models()
        
        # Should filter for Nova models only
        assert 'modelSummaries' in response
        models = response['modelSummaries']
        
        # All returned models should be Nova models
        for model in models:
            assert 'nova' in model['modelId'].lower()
        
        mock_bedrock.list_foundation_models.assert_called_once()
    
    @patch('boto3.client')
    def test_list_foundation_models_caching(self, mock_boto3_client):
        """Test that foundation models list is cached."""
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = self.mock_models_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        # First call
        response1 = self.client.list_foundation_models()
        
        # Second call (should use cache)
        response2 = self.client.list_foundation_models()
        
        # Should only call the API once due to caching
        mock_bedrock.list_foundation_models.assert_called_once()
        
        # Responses should be identical
        assert response1 == response2
    
    @patch('boto3.client')
    def test_get_model_info_success(self, mock_boto3_client):
        """Test successful get model info."""
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = self.mock_models_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        model_info = self.client.get_model_info('amazon.nova-lite-v1:0')
        
        assert model_info is not None
        assert model_info['modelId'] == 'amazon.nova-lite-v1:0'
        assert model_info['modelName'] == 'Nova Lite'
        assert model_info['providerName'] == 'Amazon'
    
    @patch('boto3.client')
    def test_get_model_info_not_found(self, mock_boto3_client):
        """Test get model info for non-existent model."""
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = self.mock_models_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        model_info = self.client.get_model_info('non-existent-model')
        
        assert model_info is None
    
    @patch('boto3.client')
    def test_validate_model_access_success(self, mock_boto3_client):
        """Test successful model access validation."""
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        mock_bedrock.list_foundation_models.return_value = self.mock_models_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        is_accessible = self.client.validate_model_access('amazon.nova-lite-v1:0')
        
        assert is_accessible is True
    
    @patch('boto3.client')
    def test_validate_model_access_inactive(self, mock_boto3_client):
        """Test model access validation for inactive model."""
        mock_bedrock_runtime = Mock()
        mock_bedrock = Mock()
        
        # Mock response with inactive model
        inactive_model_response = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'INACTIVE'
                    }
                }
            ]
        }
        mock_bedrock.list_foundation_models.return_value = inactive_model_response
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_runtime
            elif service_name == 'bedrock':
                return mock_bedrock
            else:
                raise ValueError(f"Unexpected service: {service_name}")
        
        mock_boto3_client.side_effect = mock_client_factory
        
        is_accessible = self.client.validate_model_access('amazon.nova-lite-v1:0')
        
        assert is_accessible is False
    
    def test_error_type_mapping(self):
        """Test that Bedrock error codes are mapped correctly."""
        error_mappings = [
            ('ValidationException', 'invalid_request_error'),
            ('AccessDeniedException', 'authentication_error'),
            ('ThrottlingException', 'rate_limit_error'),
            ('ModelNotReadyException', 'model_error'),
            ('InternalServerException', 'server_error'),
            ('ServiceQuotaExceededException', 'quota_exceeded_error'),
            ('UnknownException', 'api_error')  # Default case
        ]
        
        for bedrock_error, expected_type in error_mappings:
            with patch('boto3.client') as mock_boto3_client:
                mock_bedrock = Mock()
                mock_bedrock.converse.side_effect = ClientError(
                    error_response={
                        'Error': {
                            'Code': bedrock_error,
                            'Message': f'Test {bedrock_error}'
                        },
                        'ResponseMetadata': {
                            'HTTPStatusCode': 400
                        }
                    },
                    operation_name='Converse'
                )
                mock_boto3_client.return_value = mock_bedrock
                
                with pytest.raises(BedrockAPIError) as exc_info:
                    self.client.converse({'modelId': 'test', 'messages': []})
                
                error = exc_info.value
                assert error.error_type == expected_type
    
    def test_context_manager(self):
        """Test BedrockClient as context manager."""
        with BedrockClient(region='us-east-1') as client:
            assert client is not None
            assert client.region == 'us-east-1'
        
        # Client should be closed after context exit
        assert client._bedrock_client is None
    
    def test_close_method(self):
        """Test explicit close method."""
        client = BedrockClient(region='us-east-1')
        
        # Initialize the client
        with patch('boto3.client'):
            _ = client.bedrock_client
        
        # Close the client
        client.close()
        
        assert client._bedrock_client is None


if __name__ == '__main__':
    pytest.main([__file__])