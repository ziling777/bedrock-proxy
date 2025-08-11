"""
Comprehensive tests for Bedrock format converter.
"""
import json
import pytest
import base64
from unittest.mock import Mock, patch
from src.bedrock_format_converter import BedrockFormatConverter


class TestBedrockFormatConverter:
    """Test cases for the Bedrock format converter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.model_mappings = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0'
        }
        self.converter = BedrockFormatConverter(self.model_mappings)
    
    def test_model_name_conversion(self):
        """Test OpenAI to Bedrock model name conversion."""
        # Test standard mappings
        assert self.converter.convert_model_name('gpt-4o-mini') == 'amazon.nova-lite-v1:0'
        assert self.converter.convert_model_name('gpt-4o') == 'amazon.nova-pro-v1:0'
        assert self.converter.convert_model_name('gpt-3.5-turbo') == 'amazon.nova-micro-v1:0'
        
        # Test direct Bedrock model names
        assert self.converter.convert_model_name('amazon.nova-lite-v1:0') == 'amazon.nova-lite-v1:0'
        
        # Test unknown model (should return as-is)
        assert self.converter.convert_model_name('unknown-model') == 'unknown-model'
    
    def test_openai_to_bedrock_request_basic(self):
        """Test basic OpenAI to Bedrock request conversion."""
        openai_request = {
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
        
        bedrock_request = self.converter.openai_to_bedrock_request(openai_request)
        
        # Check model conversion
        assert bedrock_request['modelId'] == 'amazon.nova-lite-v1:0'
        
        # Check messages conversion
        assert len(bedrock_request['messages']) == 1
        message = bedrock_request['messages'][0]
        assert message['role'] == 'user'
        assert message['content'][0]['text'] == 'Hello, how are you?'
        
        # Check inference config
        inference_config = bedrock_request['inferenceConfig']
        assert inference_config['temperature'] == 0.7
        assert inference_config['maxTokens'] == 100
        assert inference_config['topP'] == 0.9
    
    def test_openai_to_bedrock_request_with_system_message(self):
        """Test OpenAI to Bedrock conversion with system message."""
        openai_request = {
            'model': 'gpt-4o-mini',
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant.'
                },
                {
                    'role': 'user',
                    'content': 'Hello!'
                }
            ]
        }
        
        bedrock_request = self.converter.openai_to_bedrock_request(openai_request)
        
        # System message should be extracted to system field
        assert 'system' in bedrock_request
        assert len(bedrock_request['system']) == 1
        assert bedrock_request['system'][0]['text'] == 'You are a helpful assistant.'
        
        # Only user message should remain in messages
        assert len(bedrock_request['messages']) == 1
        assert bedrock_request['messages'][0]['role'] == 'user'
    
    def test_openai_to_bedrock_request_multimodal(self):
        """Test OpenAI to Bedrock conversion with image content."""
        # Create a simple base64 image
        test_image_data = base64.b64encode(b'fake_image_data').decode('utf-8')
        
        openai_request = {
            'model': 'gpt-4o-mini',
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': 'What is in this image?'
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
        }
        
        bedrock_request = self.converter.openai_to_bedrock_request(openai_request)
        
        # Check message content
        message = bedrock_request['messages'][0]
        assert len(message['content']) == 2
        
        # Check text content
        text_content = message['content'][0]
        assert text_content['text'] == 'What is in this image?'
        
        # Check image content
        image_content = message['content'][1]
        assert 'image' in image_content
        assert image_content['image']['format'] == 'jpeg'
        assert 'bytes' in image_content['image']['source']
    
    def test_openai_to_bedrock_request_with_stop_sequences(self):
        """Test OpenAI to Bedrock conversion with stop sequences."""
        openai_request = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'stop': ['END', 'STOP']
        }
        
        bedrock_request = self.converter.openai_to_bedrock_request(openai_request)
        
        assert 'inferenceConfig' in bedrock_request
        assert bedrock_request['inferenceConfig']['stopSequences'] == ['END', 'STOP']
    
    def test_openai_to_bedrock_request_invalid(self):
        """Test OpenAI to Bedrock conversion with invalid request."""
        # Missing model
        with pytest.raises(ValueError, match="Missing 'model'"):
            self.converter.openai_to_bedrock_request({})
        
        # Missing messages
        with pytest.raises(ValueError):
            self.converter.openai_to_bedrock_request({'model': 'gpt-4o-mini'})
    
    def test_bedrock_to_openai_response_basic(self):
        """Test basic Bedrock to OpenAI response conversion."""
        bedrock_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [
                        {
                            'text': 'Hello! I\'m doing well, thank you for asking.'
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
        
        openai_response = self.converter.bedrock_to_openai_response(bedrock_response, 'gpt-4o-mini')
        
        # Check basic structure
        assert openai_response['object'] == 'chat.completion'
        assert openai_response['model'] == 'gpt-4o-mini'
        assert 'id' in openai_response
        assert 'created' in openai_response
        
        # Check choices
        assert len(openai_response['choices']) == 1
        choice = openai_response['choices'][0]
        assert choice['index'] == 0
        assert choice['message']['role'] == 'assistant'
        assert choice['message']['content'] == 'Hello! I\'m doing well, thank you for asking.'
        assert choice['finish_reason'] == 'stop'
        
        # Check usage
        usage = openai_response['usage']
        assert usage['prompt_tokens'] == 10
        assert usage['completion_tokens'] == 15
        assert usage['total_tokens'] == 25
    
    def test_bedrock_to_openai_response_with_tool_calls(self):
        """Test Bedrock to OpenAI conversion with tool calls."""
        bedrock_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [
                        {
                            'text': 'I\'ll help you with that calculation.'
                        },
                        {
                            'toolUse': {
                                'toolUseId': 'tool_123',
                                'name': 'calculator',
                                'input': {'expression': '2 + 2'}
                            }
                        }
                    ]
                }
            },
            'stopReason': 'tool_use',
            'usage': {
                'inputTokens': 20,
                'outputTokens': 10,
                'totalTokens': 30
            }
        }
        
        openai_response = self.converter.bedrock_to_openai_response(bedrock_response, 'gpt-4o-mini')
        
        # Check message content
        choice = openai_response['choices'][0]
        assert choice['message']['content'] == 'I\'ll help you with that calculation.'
        assert choice['finish_reason'] == 'tool_calls'
        
        # Check tool calls
        assert 'tool_calls' in choice['message']
        tool_calls = choice['message']['tool_calls']
        assert len(tool_calls) == 1
        
        tool_call = tool_calls[0]
        assert tool_call['id'] == 'tool_123'
        assert tool_call['type'] == 'function'
        assert tool_call['function']['name'] == 'calculator'
    
    def test_convert_streaming_chunk(self):
        """Test streaming chunk conversion."""
        # Test content delta chunk
        bedrock_chunk = {
            'type': 'content_block_delta',
            'data': {
                'delta': {
                    'text': 'Hello'
                }
            }
        }
        
        openai_chunk = self.converter.convert_streaming_chunk(bedrock_chunk, 'gpt-4o-mini')
        
        assert openai_chunk['object'] == 'chat.completion.chunk'
        assert openai_chunk['model'] == 'gpt-4o-mini'
        assert len(openai_chunk['choices']) == 1
        
        choice = openai_chunk['choices'][0]
        assert choice['index'] == 0
        assert choice['delta']['content'] == 'Hello'
        assert choice['finish_reason'] is None
        
        # Test message stop chunk
        bedrock_chunk = {
            'type': 'message_stop',
            'data': {
                'stopReason': 'end_turn'
            }
        }
        
        openai_chunk = self.converter.convert_streaming_chunk(bedrock_chunk, 'gpt-4o-mini')
        
        choice = openai_chunk['choices'][0]
        assert choice['delta'] == {}
        assert choice['finish_reason'] == 'stop'
    
    def test_bedrock_models_to_openai_format(self):
        """Test Bedrock models list to OpenAI format conversion."""
        bedrock_models = {
            'modelSummaries': [
                {
                    'modelId': 'amazon.nova-lite-v1:0',
                    'modelName': 'Nova Lite',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    }
                },
                {
                    'modelId': 'amazon.nova-pro-v1:0',
                    'modelName': 'Nova Pro',
                    'providerName': 'Amazon',
                    'modelLifecycle': {
                        'status': 'ACTIVE'
                    }
                }
            ]
        }
        
        openai_models = self.converter.bedrock_models_to_openai_format(bedrock_models)
        
        assert openai_models['object'] == 'list'
        assert 'data' in openai_models
        
        models = openai_models['data']
        assert len(models) >= 2  # At least the Nova models
        
        # Check Nova Lite model
        nova_lite = next((m for m in models if m['id'] == 'amazon.nova-lite-v1:0'), None)
        assert nova_lite is not None
        assert nova_lite['object'] == 'model'
        assert nova_lite['owned_by'] == 'amazon'
        assert nova_lite['capabilities']['text'] is True
        assert nova_lite['capabilities']['images'] is True
    
    def test_stop_reason_conversion(self):
        """Test Bedrock stop reason to OpenAI finish reason conversion."""
        test_cases = [
            ('end_turn', 'stop'),
            ('tool_use', 'tool_calls'),
            ('max_tokens', 'length'),
            ('stop_sequence', 'stop'),
            ('content_filtered', 'content_filter'),
            ('unknown_reason', 'stop')  # Default case
        ]
        
        for bedrock_reason, expected_openai_reason in test_cases:
            result = self.converter._convert_bedrock_stop_reason(bedrock_reason)
            assert result == expected_openai_reason
    
    def test_usage_conversion(self):
        """Test Bedrock usage to OpenAI usage conversion."""
        bedrock_usage = {
            'inputTokens': 50,
            'outputTokens': 25,
            'totalTokens': 75
        }
        
        openai_usage = self.converter._convert_bedrock_usage_to_openai(bedrock_usage)
        
        assert openai_usage['prompt_tokens'] == 50
        assert openai_usage['completion_tokens'] == 25
        assert openai_usage['total_tokens'] == 75
    
    def test_image_format_detection(self):
        """Test image format detection from data URLs."""
        test_cases = [
            ('data:image/jpeg;base64,/9j/4AAQ...', 'jpeg'),
            ('data:image/png;base64,iVBORw0KGgo...', 'png'),
            ('data:image/webp;base64,UklGRh4AAABXRUJQVlA4...', 'webp'),
            ('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP...', 'gif')
        ]
        
        for data_url, expected_format in test_cases:
            image_url = {'url': data_url}
            result = self.converter._convert_image_openai_to_bedrock(image_url)
            
            assert result is not None
            assert result['image']['format'] == expected_format
            assert 'bytes' in result['image']['source']
    
    def test_error_response_creation(self):
        """Test error response creation."""
        error_response = self.converter._create_error_response("Test error", "gpt-4o-mini")
        
        assert error_response['object'] == 'chat.completion'
        assert error_response['model'] == 'gpt-4o-mini'
        assert len(error_response['choices']) == 1
        
        choice = error_response['choices'][0]
        assert choice['message']['role'] == 'assistant'
        assert 'Error: Test error' in choice['message']['content']
        assert choice['finish_reason'] == 'stop'
    
    def test_context_length_estimation(self):
        """Test context length estimation for different models."""
        test_cases = [
            ('amazon.nova-lite-v1:0', 128000),
            ('amazon.nova-pro-v1:0', 300000),
            ('amazon.nova-micro-v1:0', 128000),
            ('unknown-model', 128000)  # Default
        ]
        
        for model_id, expected_length in test_cases:
            result = self.converter._estimate_context_length(model_id)
            assert result == expected_length


if __name__ == '__main__':
    pytest.main([__file__])