"""
Tests for FormatConverter.
"""
import pytest
from src.format_converter import FormatConverter


class TestFormatConverter:
    """Test cases for FormatConverter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.model_mappings = {
            'amazon.nova-lite-v1:0': 'gpt-4o-mini',
            'amazon.nova-pro-v1:0': 'gpt-4o-mini'
        }
        self.converter = FormatConverter(model_mappings=self.model_mappings)
    
    def test_convert_model_name_with_mapping(self):
        """Test model name conversion with mapping."""
        result = self.converter.convert_model_name('amazon.nova-lite-v1:0')
        assert result == 'gpt-4o-mini'
    
    def test_convert_model_name_without_mapping(self):
        """Test model name conversion without mapping."""
        result = self.converter.convert_model_name('unknown-model')
        assert result == 'unknown-model'
    
    def test_bedrock_to_openai_simple_text_message(self):
        """Test conversion of simple text message."""
        bedrock_request = {
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
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert result['model'] == 'gpt-4o-mini'
        assert len(result['messages']) == 1
        assert result['messages'][0]['role'] == 'user'
        assert result['messages'][0]['content'] == 'Hello, how are you?'
        assert result['temperature'] == 0.7
        assert result['max_tokens'] == 100
        assert result['top_p'] == 0.9
    
    def test_bedrock_to_openai_with_system_message(self):
        """Test conversion with system message."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'system': [
                {'text': 'You are a helpful assistant.'}
            ],
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ]
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert len(result['messages']) == 2
        assert result['messages'][0]['role'] == 'system'
        assert result['messages'][0]['content'] == 'You are a helpful assistant.'
        assert result['messages'][1]['role'] == 'user'
        assert result['messages'][1]['content'] == 'Hello'
    
    def test_bedrock_to_openai_multimodal_content(self):
        """Test conversion of multimodal content."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'text': 'What do you see in this image?'},
                        {
                            'image': {
                                'source': {
                                    'type': 'base64',
                                    'mediaType': 'image/jpeg',
                                    'bytes': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert len(result['messages']) == 1
        message = result['messages'][0]
        assert message['role'] == 'user'
        assert isinstance(message['content'], list)
        assert len(message['content']) == 2
        
        # Check text content
        assert message['content'][0]['type'] == 'text'
        assert message['content'][0]['text'] == 'What do you see in this image?'
        
        # Check image content
        assert message['content'][1]['type'] == 'image_url'
        assert 'image_url' in message['content'][1]
        assert message['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    
    def test_bedrock_to_openai_assistant_with_tool_calls(self):
        """Test conversion of assistant message with tool calls."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'assistant',
                    'content': [
                        {'text': 'I need to call a function.'},
                        {
                            'toolUse': {
                                'toolUseId': 'tool-123',
                                'name': 'get_weather',
                                'input': {'location': 'New York'}
                            }
                        }
                    ]
                }
            ]
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert len(result['messages']) == 1
        message = result['messages'][0]
        assert message['role'] == 'assistant'
        assert message['content'] == 'I need to call a function.'
        assert 'tool_calls' in message
        assert len(message['tool_calls']) == 1
        
        tool_call = message['tool_calls'][0]
        assert tool_call['id'] == 'tool-123'
        assert tool_call['type'] == 'function'
        assert tool_call['function']['name'] == 'get_weather'
        assert "{'location': 'New York'}" in tool_call['function']['arguments']
    
    def test_bedrock_to_openai_with_tools_config(self):
        """Test conversion with tools configuration."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'What is the weather?'}]
                }
            ],
            'toolConfig': {
                'tools': [
                    {
                        'toolSpec': {
                            'name': 'get_weather',
                            'description': 'Get current weather',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'location': {'type': 'string'}
                                }
                            }
                        }
                    }
                ],
                'toolChoice': {'auto': {}}
            }
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert 'tools' in result
        assert len(result['tools']) == 1
        
        tool = result['tools'][0]
        assert tool['type'] == 'function'
        assert tool['function']['name'] == 'get_weather'
        assert tool['function']['description'] == 'Get current weather'
        assert 'properties' in tool['function']['parameters']
        
        assert result['tool_choice'] == 'auto'
    
    def test_bedrock_to_openai_stop_sequences(self):
        """Test conversion of stop sequences."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ],
            'inferenceConfig': {
                'stopSequences': ['\\n', 'END']
            }
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert 'stop' in result
        assert result['stop'] == ['\\n', 'END']
    
    def test_bedrock_to_openai_single_stop_sequence(self):
        """Test conversion of single stop sequence."""
        bedrock_request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ],
            'inferenceConfig': {
                'stopSequences': ['\\n']
            }
        }
        
        result = self.converter.bedrock_to_openai_request(bedrock_request)
        
        assert 'stop' in result
        assert result['stop'] == '\\n'
    
    def test_bedrock_to_openai_missing_model_id(self):
        """Test conversion with missing model ID."""
        bedrock_request = {
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ]
        }
        
        with pytest.raises(ValueError, match="Missing 'modelId' in Bedrock request"):
            self.converter.bedrock_to_openai_request(bedrock_request)
    
    def test_openai_to_bedrock_response_passthrough(self):
        """Test OpenAI to Bedrock response conversion (passthrough)."""
        openai_response = {
            'id': 'chatcmpl-test123',
            'object': 'chat.completion',
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': 'Hello!'
                    }
                }
            ]
        }
        
        result = self.converter.openai_to_bedrock_response(openai_response)
        
        # Should normalize the response by adding required fields
        assert result['id'] == openai_response['id']
        assert result['object'] == openai_response['object']
        assert result['model'] == openai_response['model']
        assert result['choices'] == openai_response['choices']
        assert 'created' in result
        assert 'usage' in result
    
    def test_validate_bedrock_request_valid(self):
        """Test validation of valid Bedrock request."""
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ]
        }
        
        assert self.converter.validate_bedrock_request(request) is True
    
    def test_validate_bedrock_request_missing_model_id(self):
        """Test validation with missing model ID."""
        request = {
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello'}]
                }
            ]
        }
        
        assert self.converter.validate_bedrock_request(request) is False
    
    def test_validate_bedrock_request_missing_messages(self):
        """Test validation with missing messages."""
        request = {
            'modelId': 'amazon.nova-lite-v1:0'
        }
        
        assert self.converter.validate_bedrock_request(request) is False
    
    def test_validate_bedrock_request_empty_messages(self):
        """Test validation with empty messages."""
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': []
        }
        
        assert self.converter.validate_bedrock_request(request) is False
    
    def test_validate_bedrock_request_invalid_message_role(self):
        """Test validation with invalid message role."""
        request = {
            'modelId': 'amazon.nova-lite-v1:0',
            'messages': [
                {
                    'role': 'invalid_role',
                    'content': [{'text': 'Hello'}]
                }
            ]
        }
        
        assert self.converter.validate_bedrock_request(request) is False
    
    def test_convert_user_message_with_tool_result(self):
        """Test conversion of user message with tool result."""
        content = [
            {'text': 'Here is the result:'},
            {
                'toolResult': {
                    'toolUseId': 'tool-123',
                    'content': [
                        {'text': 'Weather: 72°F, sunny'}
                    ]
                }
            }
        ]
        
        result = self.converter._convert_user_message(content)
        
        assert isinstance(result['content'], list)
        assert len(result['content']) == 2
        assert result['content'][0]['type'] == 'text'
        assert result['content'][0]['text'] == 'Here is the result:'
        assert result['content'][1]['type'] == 'text'
        assert result['content'][1]['text'] == 'Weather: 72°F, sunny'
    
    def test_convert_assistant_message_text_only(self):
        """Test conversion of assistant message with text only."""
        content = [
            {'text': 'Hello! How can I help you?'}
        ]
        
        result = self.converter._convert_assistant_message(content)
        
        assert result['content'] == 'Hello! How can I help you?'
        assert 'tool_calls' not in result
    
    def test_convert_assistant_message_tool_only(self):
        """Test conversion of assistant message with tool call only."""
        content = [
            {
                'toolUse': {
                    'toolUseId': 'tool-456',
                    'name': 'calculate',
                    'input': {'expression': '2+2'}
                }
            }
        ]
        
        result = self.converter._convert_assistant_message(content)
        
        assert result['content'] is None
        assert 'tool_calls' in result
        assert len(result['tool_calls']) == 1
        
        tool_call = result['tool_calls'][0]
        assert tool_call['id'] == 'tool-456'
        assert tool_call['function']['name'] == 'calculate'
    
    def test_convert_inference_config_all_params(self):
        """Test conversion of inference config with all parameters."""
        inference_config = {
            'temperature': 0.8,
            'maxTokens': 150,
            'topP': 0.95,
            'stopSequences': ['STOP', 'END']
        }
        
        result = self.converter._convert_inference_config(inference_config)
        
        assert result['temperature'] == 0.8
        assert result['max_tokens'] == 150
        assert result['top_p'] == 0.95
        assert result['stop'] == ['STOP', 'END']
    
    def test_convert_tools_with_specific_choice(self):
        """Test conversion of tools with specific tool choice."""
        tool_config = {
            'tools': [
                {
                    'toolSpec': {
                        'name': 'search',
                        'description': 'Search the web',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string'}
                            }
                        }
                    }
                }
            ],
            'toolChoice': {
                'tool': {'name': 'search'}
            }
        }
        
        result = self.converter._convert_tools_bedrock_to_openai(tool_config)
        
        assert 'tools' in result
        assert 'tool_choice' in result
        assert result['tool_choice']['type'] == 'function'
        assert result['tool_choice']['function']['name'] == 'search'
    
    def test_normalize_openai_response_complete(self):
        """Test normalization of complete OpenAI response."""
        response = {
            'id': 'chatcmpl-test123',
            'object': 'chat.completion',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': 'Hello!'
                    },
                    'finish_reason': 'stop'
                }
            ],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 5,
                'total_tokens': 15
            }
        }
        
        result = self.converter._normalize_openai_response(response)
        
        # Should remain unchanged as it's already complete
        assert result == response
    
    def test_normalize_openai_response_missing_fields(self):
        """Test normalization of OpenAI response with missing fields."""
        response = {
            'choices': [
                {
                    'message': {
                        'content': 'Hello!'
                    }
                }
            ]
        }
        
        result = self.converter._normalize_openai_response(response)
        
        # Check that missing fields are added
        assert 'id' in result
        assert 'object' in result
        assert 'created' in result
        assert 'model' in result
        assert 'usage' in result
        
        # Check choice normalization
        choice = result['choices'][0]
        assert 'index' in choice
        assert 'finish_reason' in choice
        assert choice['message']['role'] == 'assistant'
    
    def test_convert_streaming_response_valid(self):
        """Test conversion of valid streaming response chunk."""
        chunk = {
            'id': 'chatcmpl-stream123',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'role': 'assistant',
                        'content': 'Hello'
                    }
                }
            ]
        }
        
        result = self.converter.convert_streaming_response(chunk)
        
        # Should remain unchanged as it's already valid
        assert result == chunk
    
    def test_convert_streaming_response_missing_fields(self):
        """Test conversion of streaming response with missing fields."""
        chunk = {
            'choices': [
                {
                    'delta': {
                        'content': 'Hello'
                    }
                }
            ]
        }
        
        result = self.converter.convert_streaming_response(chunk)
        
        # Check that missing fields are added
        assert 'id' in result
        assert 'object' in result
        assert 'created' in result
        
        # Check choice normalization
        choice = result['choices'][0]
        assert 'index' in choice
    
    def test_convert_streaming_response_invalid_format(self):
        """Test conversion of invalid streaming response."""
        chunk = "invalid chunk format"
        
        result = self.converter.convert_streaming_response(chunk)
        
        # Should return error chunk
        assert result['id'] == 'chatcmpl-error'
        assert result['object'] == 'chat.completion.chunk'
        assert 'Error:' in result['choices'][0]['delta']['content']
    
    def test_create_error_response(self):
        """Test creation of error response."""
        error_message = "Test error message"
        
        result = self.converter._create_error_response(error_message)
        
        assert result['id'] == 'chatcmpl-error'
        assert result['object'] == 'chat.completion'
        assert 'created' in result
        assert result['model'] == 'gpt-4o-mini'
        assert len(result['choices']) == 1
        assert f'Error: {error_message}' in result['choices'][0]['message']['content']
        assert result['usage']['total_tokens'] == 0
    
    def test_create_error_chunk(self):
        """Test creation of error chunk for streaming."""
        error_message = "Test streaming error"
        
        result = self.converter._create_error_chunk(error_message)
        
        assert result['id'] == 'chatcmpl-error'
        assert result['object'] == 'chat.completion.chunk'
        assert 'created' in result
        assert result['model'] == 'gpt-4o-mini'
        assert len(result['choices']) == 1
        assert f'Error: {error_message}' in result['choices'][0]['delta']['content']
    
    def test_validate_openai_response_valid_completion(self):
        """Test validation of valid completion response."""
        response = {
            'id': 'chatcmpl-test123',
            'object': 'chat.completion',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': 'Hello!'
                    },
                    'finish_reason': 'stop'
                }
            ],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 5,
                'total_tokens': 15
            }
        }
        
        assert self.converter.validate_openai_response(response) is True
    
    def test_validate_openai_response_valid_chunk(self):
        """Test validation of valid streaming chunk."""
        response = {
            'id': 'chatcmpl-stream123',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'role': 'assistant',
                        'content': 'Hello'
                    }
                }
            ]
        }
        
        assert self.converter.validate_openai_response(response) is True
    
    def test_validate_openai_response_missing_required_field(self):
        """Test validation with missing required field."""
        response = {
            'object': 'chat.completion',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': []
            # Missing 'id'
        }
        
        assert self.converter.validate_openai_response(response) is False
    
    def test_validate_openai_response_invalid_object_type(self):
        """Test validation with invalid object type."""
        response = {
            'id': 'chatcmpl-test123',
            'object': 'invalid.object.type',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': []
        }
        
        assert self.converter.validate_openai_response(response) is False
    
    def test_validate_openai_response_invalid_choices(self):
        """Test validation with invalid choices format."""
        response = {
            'id': 'chatcmpl-test123',
            'object': 'chat.completion',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': 'not a list'
        }
        
        assert self.converter.validate_openai_response(response) is False
    
    def test_validate_openai_response_missing_usage(self):
        """Test validation of completion response missing usage."""
        response = {
            'id': 'chatcmpl-test123',
            'object': 'chat.completion',
            'created': 1234567890,
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': 'Hello!'
                    }
                }
            ]
            # Missing 'usage'
        }
        
        assert self.converter.validate_openai_response(response) is False
    
    def test_openai_to_bedrock_response_with_error(self):
        """Test OpenAI to Bedrock response conversion with error handling."""
        # Simulate an invalid response that causes normalization to fail
        invalid_response = None
        
        result = self.converter.openai_to_bedrock_response(invalid_response)
        
        # Should return error response
        assert result['id'] == 'chatcmpl-error'
        assert 'Error:' in result['choices'][0]['message']['content']