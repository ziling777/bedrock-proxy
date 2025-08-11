"""
Format converter for transforming between OpenAI and AWS Bedrock API formats.
"""
import logging
import base64
import time
from typing import Dict, Any, List, Union, Optional

logger = logging.getLogger(__name__)


class BedrockFormatConverter:
    """Format converter for OpenAI <-> Bedrock conversion."""
    
    def __init__(self, model_mappings: Optional[Dict[str, str]] = None):
        """
        Initialize format converter.
        
        Args:
            model_mappings: Dictionary mapping OpenAI model names to Bedrock model IDs
        """
        # Default model mappings from OpenAI models to Bedrock Nova models
        self.model_mappings = model_mappings or {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0',
            # Also support direct Bedrock model names
            'amazon.nova-lite-v1:0': 'amazon.nova-lite-v1:0',
            'amazon.nova-pro-v1:0': 'amazon.nova-pro-v1:0',
            'amazon.nova-micro-v1:0': 'amazon.nova-micro-v1:0'
        }
    
    def openai_to_bedrock_request(self, openai_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI format request to Bedrock Converse API format.
        
        Args:
            openai_request: Request in OpenAI format
            
        Returns:
            Request in Bedrock Converse API format
            
        Raises:
            ValueError: If request format is invalid
        """
        try:
            logger.debug(f"Converting OpenAI request: {openai_request}")
            
            # Extract and convert model ID
            openai_model = openai_request.get('model')
            if not openai_model:
                raise ValueError("Missing 'model' in OpenAI request")
            
            bedrock_model = self.convert_model_name(openai_model)
            
            # Convert messages
            openai_messages = openai_request.get('messages', [])
            bedrock_messages = self._convert_messages_openai_to_bedrock(openai_messages)
            
            # Build base Bedrock request
            bedrock_request = {
                'modelId': bedrock_model,
                'messages': bedrock_messages
            }
            
            # Convert inference parameters
            inference_config = self._convert_inference_config_openai_to_bedrock(openai_request)
            if inference_config:
                bedrock_request['inferenceConfig'] = inference_config
            
            # Handle system messages
            system_messages = self._extract_system_messages(openai_messages)
            if system_messages:
                bedrock_request['system'] = system_messages
            
            # Handle tools if present
            tools = openai_request.get('tools')
            if tools:
                tool_config = self._convert_tools_openai_to_bedrock(tools, openai_request.get('tool_choice'))
                bedrock_request['toolConfig'] = tool_config
            
            logger.debug(f"Converted to Bedrock request: {bedrock_request}")
            return bedrock_request
            
        except Exception as e:
            logger.error(f"Failed to convert OpenAI request to Bedrock: {e}")
            raise ValueError(f"Request conversion failed: {e}")
    
    def bedrock_to_openai_response(self, bedrock_response: Dict[str, Any], original_model: str = None) -> Dict[str, Any]:
        """
        Convert Bedrock Converse API response to OpenAI format.
        
        Args:
            bedrock_response: Response in Bedrock format
            original_model: Original OpenAI model name from request
            
        Returns:
            Response in OpenAI format
        """
        logger.debug(f"Converting Bedrock response: {bedrock_response}")
        
        try:
            # Extract response components
            output = bedrock_response.get('output', {})
            message = output.get('message', {})
            stop_reason = bedrock_response.get('stopReason', 'end_turn')
            usage = bedrock_response.get('usage', {})
            
            # Convert message content
            choices = self._convert_bedrock_message_to_openai_choice(message, stop_reason)
            
            # Convert usage information
            openai_usage = self._convert_bedrock_usage_to_openai(usage)
            
            # Build OpenAI response
            openai_response = {
                'id': f"chatcmpl-nova-{int(time.time())}-{hash(str(bedrock_response)) % 10000:04d}",
                'object': 'chat.completion',
                'created': int(time.time()),
                'model': original_model or 'gpt-4o-mini',
                'choices': choices,
                'usage': openai_usage
            }
            
            logger.debug(f"Converted to OpenAI response: {openai_response}")
            return openai_response
            
        except Exception as e:
            logger.error(f"Failed to convert Bedrock response to OpenAI: {e}")
            # Return a safe error response
            return self._create_error_response(str(e), original_model)
    
    def convert_streaming_chunk(self, bedrock_chunk: Dict[str, Any], original_model: str = None) -> Dict[str, Any]:
        """
        Convert Bedrock streaming response chunk to OpenAI format.
        
        Args:
            bedrock_chunk: Bedrock streaming response chunk
            original_model: Original OpenAI model name from request
            
        Returns:
            OpenAI streaming response chunk
        """
        logger.debug(f"Converting streaming chunk: {bedrock_chunk}")
        
        try:
            chunk_type = bedrock_chunk.get('type')
            chunk_data = bedrock_chunk.get('data', {})
            
            # Base chunk structure
            openai_chunk = {
                'id': f"chatcmpl-nova-stream-{int(time.time())}",
                'object': 'chat.completion.chunk',
                'created': int(time.time()),
                'model': original_model or 'gpt-4o-mini',
                'choices': []
            }
            
            if chunk_type == 'content_block_delta':
                # Text content delta
                delta_data = chunk_data.get('delta', {})
                if 'text' in delta_data:
                    openai_chunk['choices'] = [{
                        'index': 0,
                        'delta': {
                            'content': delta_data['text']
                        },
                        'finish_reason': None
                    }]
            
            elif chunk_type == 'message_start':
                # Message start
                openai_chunk['choices'] = [{
                    'index': 0,
                    'delta': {
                        'role': 'assistant'
                    },
                    'finish_reason': None
                }]
            
            elif chunk_type == 'message_stop':
                # Message end
                stop_reason = chunk_data.get('stopReason', 'stop')
                finish_reason = self._convert_bedrock_stop_reason(stop_reason)
                
                openai_chunk['choices'] = [{
                    'index': 0,
                    'delta': {},
                    'finish_reason': finish_reason
                }]
            
            elif chunk_type == 'metadata':
                # Usage information
                usage_data = chunk_data.get('usage', {})
                if usage_data:
                    openai_chunk['usage'] = self._convert_bedrock_usage_to_openai(usage_data)
            
            return openai_chunk
            
        except Exception as e:
            logger.error(f"Failed to convert streaming chunk: {e}")
            return self._create_error_chunk(str(e), original_model)
    
    def convert_model_name(self, openai_model: str) -> str:
        """
        Convert OpenAI model name to Bedrock model ID.
        
        Args:
            openai_model: OpenAI model name
            
        Returns:
            Bedrock model ID
        """
        bedrock_model = self.model_mappings.get(openai_model, openai_model)
        
        if bedrock_model != openai_model:
            logger.info(f"Mapped model {openai_model} -> {bedrock_model}")
        
        return bedrock_model
    
    def _convert_messages_openai_to_bedrock(self, openai_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI messages to Bedrock format.
        
        Args:
            openai_messages: List of OpenAI format messages
            
        Returns:
            List of Bedrock format messages
        """
        bedrock_messages = []
        
        for message in openai_messages:
            role = message.get('role')
            
            # Skip system messages (handled separately)
            if role == 'system':
                continue
            
            content = message.get('content')
            
            if role == 'user':
                bedrock_message = self._convert_user_message_openai_to_bedrock(content)
            elif role == 'assistant':
                bedrock_message = self._convert_assistant_message_openai_to_bedrock(message)
            else:
                logger.warning(f"Unsupported message role: {role}")
                continue
            
            if bedrock_message:
                bedrock_message['role'] = role
                bedrock_messages.append(bedrock_message)
        
        return bedrock_messages
    
    def _convert_user_message_openai_to_bedrock(self, content: Union[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Convert OpenAI user message content to Bedrock format.
        
        Args:
            content: OpenAI message content (string or list of content blocks)
            
        Returns:
            Bedrock format message
        """
        if isinstance(content, str):
            # Simple text content
            return {
                'content': [{'text': content}]
            }
        
        elif isinstance(content, list):
            # Multimodal content
            bedrock_content = []
            
            for block in content:
                if not isinstance(block, dict):
                    continue
                
                block_type = block.get('type')
                
                if block_type == 'text':
                    bedrock_content.append({
                        'text': block.get('text', '')
                    })
                
                elif block_type == 'image_url':
                    image_block = self._convert_image_openai_to_bedrock(block.get('image_url', {}))
                    if image_block:
                        bedrock_content.append(image_block)
            
            return {'content': bedrock_content}
        
        else:
            logger.warning(f"Unsupported content type: {type(content)}")
            return {'content': [{'text': str(content)}]}
    
    def _convert_assistant_message_openai_to_bedrock(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI assistant message to Bedrock format.
        
        Args:
            message: OpenAI assistant message
            
        Returns:
            Bedrock format message
        """
        content_blocks = []
        
        # Handle text content
        text_content = message.get('content')
        if text_content:
            content_blocks.append({'text': text_content})
        
        # Handle tool calls
        tool_calls = message.get('tool_calls', [])
        for tool_call in tool_calls:
            if tool_call.get('type') == 'function':
                function = tool_call.get('function', {})
                tool_use_block = {
                    'toolUse': {
                        'toolUseId': tool_call.get('id', ''),
                        'name': function.get('name', ''),
                        'input': function.get('arguments', {})
                    }
                }
                content_blocks.append(tool_use_block)
        
        return {'content': content_blocks}
    
    def _convert_image_openai_to_bedrock(self, image_url: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert OpenAI image_url to Bedrock image format.
        
        Args:
            image_url: OpenAI image_url object
            
        Returns:
            Bedrock image block or None if conversion fails
        """
        try:
            url = image_url.get('url', '')
            
            if url.startswith('data:'):
                # Handle base64 data URL
                if ';base64,' in url:
                    header, data = url.split(';base64,', 1)
                    media_type = header.split(':', 1)[1]
                    
                    # Extract format from media type
                    format_mapping = {
                        'image/jpeg': 'jpeg',
                        'image/jpg': 'jpeg',
                        'image/png': 'png',
                        'image/webp': 'webp',
                        'image/gif': 'gif'
                    }
                    
                    image_format = format_mapping.get(media_type.lower(), 'jpeg')
                    
                    return {
                        'image': {
                            'format': image_format,
                            'source': {
                                'bytes': base64.b64decode(data)
                            }
                        }
                    }
            
            else:
                logger.warning(f"Unsupported image URL format: {url[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"Failed to convert image: {e}")
            return None
    
    def _extract_system_messages(self, openai_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract system messages from OpenAI messages.
        
        Args:
            openai_messages: List of OpenAI messages
            
        Returns:
            List of Bedrock system prompts
        """
        system_prompts = []
        
        for message in openai_messages:
            if message.get('role') == 'system':
                content = message.get('content', '')
                if content:
                    system_prompts.append({'text': content})
        
        return system_prompts
    
    def _convert_inference_config_openai_to_bedrock(self, openai_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI parameters to Bedrock inference config.
        
        Args:
            openai_request: OpenAI request
            
        Returns:
            Bedrock inference configuration
        """
        config = {}
        
        # Direct mappings
        if 'temperature' in openai_request:
            config['temperature'] = openai_request['temperature']
        
        if 'max_tokens' in openai_request:
            config['maxTokens'] = openai_request['max_tokens']
        
        if 'top_p' in openai_request:
            config['topP'] = openai_request['top_p']
        
        # Convert stop sequences
        if 'stop' in openai_request:
            stop = openai_request['stop']
            if isinstance(stop, str):
                config['stopSequences'] = [stop]
            elif isinstance(stop, list):
                config['stopSequences'] = stop
        
        return config
    
    def _convert_tools_openai_to_bedrock(self, tools: List[Dict[str, Any]], tool_choice: Any = None) -> Dict[str, Any]:
        """
        Convert OpenAI tools to Bedrock tool config.
        
        Args:
            tools: OpenAI tools list
            tool_choice: OpenAI tool choice setting
            
        Returns:
            Bedrock tool configuration
        """
        bedrock_tools = []
        
        for tool in tools:
            if tool.get('type') == 'function':
                function = tool.get('function', {})
                bedrock_tool = {
                    'toolSpec': {
                        'name': function.get('name', ''),
                        'description': function.get('description', ''),
                        'inputSchema': function.get('parameters', {})
                    }
                }
                bedrock_tools.append(bedrock_tool)
        
        tool_config = {'tools': bedrock_tools}
        
        # Convert tool choice
        if tool_choice:
            if tool_choice == 'auto':
                tool_config['toolChoice'] = {'auto': {}}
            elif tool_choice == 'required':
                tool_config['toolChoice'] = {'any': {}}
            elif isinstance(tool_choice, dict) and tool_choice.get('type') == 'function':
                function_name = tool_choice.get('function', {}).get('name', '')
                tool_config['toolChoice'] = {
                    'tool': {'name': function_name}
                }
        
        return tool_config
    
    def _convert_bedrock_message_to_openai_choice(self, message: Dict[str, Any], stop_reason: str) -> List[Dict[str, Any]]:
        """
        Convert Bedrock message to OpenAI choice format.
        
        Args:
            message: Bedrock message
            stop_reason: Bedrock stop reason
            
        Returns:
            OpenAI choices list
        """
        content_blocks = message.get('content', [])
        
        # Extract text content
        text_parts = []
        tool_calls = []
        
        for block in content_blocks:
            if 'text' in block:
                text_parts.append(block['text'])
            elif 'toolUse' in block:
                tool_use = block['toolUse']
                tool_call = {
                    'id': tool_use.get('toolUseId', ''),
                    'type': 'function',
                    'function': {
                        'name': tool_use.get('name', ''),
                        'arguments': str(tool_use.get('input', {}))
                    }
                }
                tool_calls.append(tool_call)
        
        # Build OpenAI message
        openai_message = {
            'role': 'assistant',
            'content': '\n'.join(text_parts) if text_parts else None
        }
        
        if tool_calls:
            openai_message['tool_calls'] = tool_calls
        
        # Convert stop reason
        finish_reason = self._convert_bedrock_stop_reason(stop_reason)
        
        return [{
            'index': 0,
            'message': openai_message,
            'finish_reason': finish_reason
        }]
    
    def _convert_bedrock_stop_reason(self, stop_reason: str) -> str:
        """
        Convert Bedrock stop reason to OpenAI finish reason.
        
        Args:
            stop_reason: Bedrock stop reason
            
        Returns:
            OpenAI finish reason
        """
        mapping = {
            'end_turn': 'stop',
            'tool_use': 'tool_calls',
            'max_tokens': 'length',
            'stop_sequence': 'stop',
            'content_filtered': 'content_filter'
        }
        
        return mapping.get(stop_reason, 'stop')
    
    def _convert_bedrock_usage_to_openai(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock usage to OpenAI usage format.
        
        Args:
            usage: Bedrock usage information
            
        Returns:
            OpenAI usage format
        """
        return {
            'prompt_tokens': usage.get('inputTokens', 0),
            'completion_tokens': usage.get('outputTokens', 0),
            'total_tokens': usage.get('totalTokens', 0)
        }
    
    def _create_error_response(self, error_message: str, model: str = None) -> Dict[str, Any]:
        """
        Create a standardized error response in OpenAI format.
        
        Args:
            error_message: Error message
            model: Model name
            
        Returns:
            Error response in OpenAI format
        """
        return {
            'id': f"chatcmpl-error-{int(time.time())}",
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': model or 'gpt-4o-mini',
            'choices': [{
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': f'Error: {error_message}'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
        }
    
    def _create_error_chunk(self, error_message: str, model: str = None) -> Dict[str, Any]:
        """
        Create a standardized error chunk for streaming.
        
        Args:
            error_message: Error message
            model: Model name
            
        Returns:
            Error chunk in OpenAI streaming format
        """
        return {
            'id': f"chatcmpl-error-{int(time.time())}",
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': model or 'gpt-4o-mini',
            'choices': [{
                'index': 0,
                'delta': {
                    'role': 'assistant',
                    'content': f'Error: {error_message}'
                },
                'finish_reason': 'stop'
            }]
        }
    
    def bedrock_models_to_openai_format(self, bedrock_models: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock models list to OpenAI models format.
        
        Args:
            bedrock_models: Bedrock models response
            
        Returns:
            OpenAI models list format
        """
        try:
            model_summaries = bedrock_models.get('modelSummaries', [])
            openai_models = []
            
            # Create reverse mapping for display names
            reverse_mapping = {}
            for openai_name, bedrock_id in self.model_mappings.items():
                if bedrock_id not in reverse_mapping:
                    reverse_mapping[bedrock_id] = openai_name
            
            for model in model_summaries:
                model_id = model.get('modelId', '')
                model_name = model.get('modelName', '')
                provider = model.get('providerName', 'Amazon')
                
                # Use OpenAI name if available, otherwise use Bedrock ID
                display_id = reverse_mapping.get(model_id, model_id)
                
                # Estimate context length based on model type
                context_length = self._estimate_context_length(model_id)
                
                openai_model = {
                    'id': display_id,
                    'object': 'model',
                    'created': int(time.time()),
                    'owned_by': provider.lower(),
                    'permission': [],
                    'root': display_id,
                    'parent': None
                }
                
                # Add Nova-specific metadata
                if 'nova' in model_id.lower():
                    openai_model['capabilities'] = {
                        'text': True,
                        'images': True,
                        'function_calling': True,
                        'streaming': True
                    }
                    openai_model['context_length'] = context_length
                    openai_model['description'] = f"{model_name} - {provider} Nova model"
                
                openai_models.append(openai_model)
            
            return {
                'object': 'list',
                'data': openai_models
            }
            
        except Exception as e:
            logger.error(f"Failed to convert models list: {e}")
            return {
                'object': 'list',
                'data': []
            }
    
    def _estimate_context_length(self, model_id: str) -> int:
        """
        Estimate context length based on model ID.
        
        Args:
            model_id: Bedrock model ID
            
        Returns:
            Estimated context length
        """
        # Nova model context lengths (estimated)
        if 'nova-lite' in model_id:
            return 128000  # 128K tokens
        elif 'nova-pro' in model_id:
            return 300000  # 300K tokens
        elif 'nova-micro' in model_id:
            return 128000  # 128K tokens
        else:
            return 128000  # Default