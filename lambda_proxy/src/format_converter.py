"""
Format converter for transforming between Bedrock and OpenAI API formats.
"""
import logging
from typing import Dict, Any, List, Union, Optional
from .interfaces import FormatConverterInterface

logger = logging.getLogger(__name__)


class FormatConverter(FormatConverterInterface):
    """Format converter implementation for Bedrock <-> OpenAI conversion."""
    
    def __init__(self, model_mappings: Optional[Dict[str, str]] = None):
        """
        Initialize format converter.
        
        Args:
            model_mappings: Dictionary mapping Bedrock model names to OpenAI model names
        """
        self.model_mappings = model_mappings or {}
    
    def bedrock_to_openai_request(self, bedrock_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock format request to OpenAI format.
        
        Args:
            bedrock_request: Request in Bedrock Converse API format
            
        Returns:
            Request in OpenAI format
            
        Raises:
            ValueError: If request format is invalid
        """
        try:
            logger.debug(f"Converting Bedrock request: {bedrock_request}")
            
            # Extract model ID and convert
            model_id = bedrock_request.get('modelId')
            if not model_id:
                raise ValueError("Missing 'modelId' in Bedrock request")
            
            openai_model = self.convert_model_name(model_id)
            
            # Convert messages
            bedrock_messages = bedrock_request.get('messages', [])
            openai_messages = self._convert_messages_bedrock_to_openai(bedrock_messages)
            
            # Add system messages if present
            system_prompts = bedrock_request.get('system', [])
            if system_prompts:
                system_messages = self._convert_system_prompts_to_messages(system_prompts)
                openai_messages = system_messages + openai_messages
            
            # Convert inference config
            inference_config = bedrock_request.get('inferenceConfig', {})
            openai_params = self._convert_inference_config(inference_config)
            
            # Build OpenAI request
            openai_request = {
                'model': openai_model,
                'messages': openai_messages,
                **openai_params
            }
            
            # Handle tools if present
            tool_config = bedrock_request.get('toolConfig')
            if tool_config:
                openai_tools = self._convert_tools_bedrock_to_openai(tool_config)
                openai_request.update(openai_tools)
            
            logger.debug(f"Converted to OpenAI request: {openai_request}")
            return openai_request
            
        except Exception as e:
            logger.error(f"Failed to convert Bedrock request to OpenAI: {e}")
            raise ValueError(f"Request conversion failed: {e}")
    
    def openai_to_bedrock_response(self, openai_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI format response to Bedrock compatible format.
        
        Note: Since we're maintaining OpenAI compatibility, this method
        returns the response as-is but ensures proper format validation.
        
        Args:
            openai_response: Response in OpenAI format
            
        Returns:
            Response in Bedrock compatible format (currently OpenAI format)
        """
        logger.debug(f"Converting OpenAI response: {openai_response}")
        
        try:
            # Validate and normalize the response
            normalized_response = self._normalize_openai_response(openai_response)
            
            # For this proxy, we maintain OpenAI compatibility
            # so we return the normalized response
            return normalized_response
            
        except Exception as e:
            logger.error(f"Failed to convert OpenAI response: {e}")
            # Return a safe error response
            return self._create_error_response(str(e))
    
    def convert_streaming_response(self, openai_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI streaming response chunk to compatible format.
        
        Args:
            openai_chunk: OpenAI streaming response chunk
            
        Returns:
            Converted streaming response chunk
        """
        logger.debug(f"Converting streaming chunk: {openai_chunk}")
        
        try:
            # Validate chunk format
            if not isinstance(openai_chunk, dict):
                raise ValueError("Invalid chunk format: not a dictionary")
            
            # Ensure required fields are present
            if 'id' not in openai_chunk:
                openai_chunk['id'] = 'chatcmpl-stream'
            
            if 'object' not in openai_chunk:
                openai_chunk['object'] = 'chat.completion.chunk'
            
            if 'created' not in openai_chunk:
                import time
                openai_chunk['created'] = int(time.time())
            
            # Validate choices format
            if 'choices' in openai_chunk:
                choices = openai_chunk['choices']
                if isinstance(choices, list):
                    for i, choice in enumerate(choices):
                        if not isinstance(choice, dict):
                            continue
                        
                        # Ensure choice has required fields
                        if 'index' not in choice:
                            choice['index'] = i
                        
                        if 'delta' not in choice:
                            choice['delta'] = {}
            
            return openai_chunk
            
        except Exception as e:
            logger.error(f"Failed to convert streaming chunk: {e}")
            return self._create_error_chunk(str(e))
    
    def _normalize_openai_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize OpenAI response to ensure consistent format.
        
        Args:
            response: OpenAI response
            
        Returns:
            Normalized response
        """
        # Create a copy to avoid modifying the original
        normalized = response.copy()
        
        # Only add missing required fields, don't override existing ones
        if 'id' not in normalized:
            normalized['id'] = 'chatcmpl-proxy'
        
        if 'object' not in normalized:
            normalized['object'] = 'chat.completion'
        
        # Only add created timestamp if missing
        if 'created' not in normalized:
            import time
            normalized['created'] = int(time.time())
        
        if 'model' not in normalized:
            normalized['model'] = 'gpt-4o-mini'
        
        # Validate and normalize choices
        if 'choices' not in normalized:
            normalized['choices'] = []
        
        choices = normalized['choices']
        if isinstance(choices, list):
            for i, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    continue
                
                # Ensure choice has required fields
                if 'index' not in choice:
                    choice['index'] = i
                
                if 'message' not in choice:
                    choice['message'] = {
                        'role': 'assistant',
                        'content': ''
                    }
                
                # Validate message format
                message = choice['message']
                if isinstance(message, dict):
                    if 'role' not in message:
                        message['role'] = 'assistant'
                    
                    if 'content' not in message and 'tool_calls' not in message:
                        message['content'] = ''
                
                if 'finish_reason' not in choice:
                    choice['finish_reason'] = 'stop'
        
        # Only add usage if missing (for completion responses)
        if 'usage' not in normalized and normalized.get('object') == 'chat.completion':
            normalized['usage'] = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
        
        # Normalize existing usage if present
        if 'usage' in normalized:
            usage = normalized['usage']
            if isinstance(usage, dict):
                if 'prompt_tokens' not in usage:
                    usage['prompt_tokens'] = 0
                if 'completion_tokens' not in usage:
                    usage['completion_tokens'] = 0
                if 'total_tokens' not in usage:
                    usage['total_tokens'] = usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
        
        return normalized
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error_message: Error message
            
        Returns:
            Error response in OpenAI format
        """
        import time
        
        return {
            'id': 'chatcmpl-error',
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': f'Error: {error_message}'
                    },
                    'finish_reason': 'stop'
                }
            ],
            'usage': {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
        }
    
    def _create_error_chunk(self, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error chunk for streaming.
        
        Args:
            error_message: Error message
            
        Returns:
            Error chunk in OpenAI streaming format
        """
        import time
        
        return {
            'id': 'chatcmpl-error',
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': 'gpt-4o-mini',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'role': 'assistant',
                        'content': f'Error: {error_message}'
                    },
                    'finish_reason': 'stop'
                }
            ]
        }
    
    def validate_openai_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate OpenAI response format.
        
        Args:
            response: OpenAI format response
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ['id', 'object', 'created', 'model', 'choices']
            for field in required_fields:
                if field not in response:
                    logger.error(f"Missing required field in response: {field}")
                    return False
            
            # Validate object type
            if response['object'] not in ['chat.completion', 'chat.completion.chunk']:
                logger.error(f"Invalid object type: {response['object']}")
                return False
            
            # Validate choices
            choices = response['choices']
            if not isinstance(choices, list):
                logger.error("Choices must be a list")
                return False
            
            for i, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    logger.error(f"Choice {i} must be a dictionary")
                    return False
                
                if 'index' not in choice:
                    logger.error(f"Choice {i} missing index")
                    return False
                
                # For completion, check message; for chunk, check delta
                if response['object'] == 'chat.completion':
                    if 'message' not in choice:
                        logger.error(f"Choice {i} missing message")
                        return False
                    
                    message = choice['message']
                    if not isinstance(message, dict) or 'role' not in message:
                        logger.error(f"Choice {i} has invalid message format")
                        return False
                
                elif response['object'] == 'chat.completion.chunk':
                    if 'delta' not in choice:
                        logger.error(f"Choice {i} missing delta")
                        return False
            
            # Validate usage (for completion only)
            if response['object'] == 'chat.completion':
                if 'usage' not in response:
                    logger.error("Missing usage information")
                    return False
                
                usage = response['usage']
                if not isinstance(usage, dict):
                    logger.error("Usage must be a dictionary")
                    return False
                
                required_usage_fields = ['prompt_tokens', 'completion_tokens', 'total_tokens']
                for field in required_usage_fields:
                    if field not in usage:
                        logger.error(f"Missing usage field: {field}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Response validation error: {e}")
            return False
    
    def convert_model_name(self, model_name: str) -> str:
        """
        Convert Bedrock model name to OpenAI model name.
        
        Args:
            model_name: Bedrock model name
            
        Returns:
            OpenAI model name
        """
        openai_model = self.model_mappings.get(model_name, model_name)
        
        if openai_model != model_name:
            logger.info(f"Mapped model {model_name} -> {openai_model}")
        
        return openai_model
    
    def _convert_messages_bedrock_to_openai(self, bedrock_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Bedrock messages to OpenAI format.
        
        Args:
            bedrock_messages: List of Bedrock format messages
            
        Returns:
            List of OpenAI format messages
        """
        openai_messages = []
        
        for message in bedrock_messages:
            role = message.get('role')
            content = message.get('content', [])
            
            if role == 'user':
                openai_message = self._convert_user_message(content)
            elif role == 'assistant':
                openai_message = self._convert_assistant_message(content)
            else:
                logger.warning(f"Unsupported message role: {role}")
                continue
            
            if openai_message:
                openai_message['role'] = role
                openai_messages.append(openai_message)
        
        return openai_messages
    
    def _convert_user_message(self, content: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert Bedrock user message content to OpenAI format.
        
        Args:
            content: Bedrock message content blocks
            
        Returns:
            OpenAI format message
        """
        if not content:
            return {'content': ''}
        
        # Handle simple text content
        if len(content) == 1 and 'text' in content[0]:
            return {'content': content[0]['text']}
        
        # Handle multimodal content (text + images)
        openai_content = []
        
        for block in content:
            if 'text' in block:
                openai_content.append({
                    'type': 'text',
                    'text': block['text']
                })
            elif 'image' in block:
                # Convert Bedrock image format to OpenAI format
                image_data = block['image']
                if 'source' in image_data:
                    source = image_data['source']
                    if source.get('type') == 'base64':
                        # Convert base64 image
                        media_type = source.get('mediaType', 'image/jpeg')
                        data = source.get('bytes', '')
                        image_url = f"data:{media_type};base64,{data}"
                        
                        openai_content.append({
                            'type': 'image_url',
                            'image_url': {
                                'url': image_url,
                                'detail': 'auto'
                            }
                        })
            elif 'toolResult' in block:
                # Handle tool results - convert to text for now
                tool_result = block['toolResult']
                result_content = tool_result.get('content', [])
                
                text_parts = []
                for result_block in result_content:
                    if 'text' in result_block:
                        text_parts.append(result_block['text'])
                
                if text_parts:
                    openai_content.append({
                        'type': 'text',
                        'text': '\n'.join(text_parts)
                    })
        
        return {'content': openai_content if len(openai_content) > 1 else openai_content[0]['text'] if openai_content else ''}
    
    def _convert_assistant_message(self, content: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert Bedrock assistant message content to OpenAI format.
        
        Args:
            content: Bedrock message content blocks
            
        Returns:
            OpenAI format message
        """
        message = {}
        text_parts = []
        tool_calls = []
        
        for block in content:
            if 'text' in block:
                text_parts.append(block['text'])
            elif 'toolUse' in block:
                # Convert tool use to OpenAI format
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
        
        # Set content
        if text_parts:
            message['content'] = '\n'.join(text_parts)
        else:
            message['content'] = None
        
        # Set tool calls
        if tool_calls:
            message['tool_calls'] = tool_calls
        
        return message
    
    def _convert_system_prompts_to_messages(self, system_prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Bedrock system prompts to OpenAI system messages.
        
        Args:
            system_prompts: List of Bedrock system prompts
            
        Returns:
            List of OpenAI system messages
        """
        system_messages = []
        
        for prompt in system_prompts:
            if 'text' in prompt:
                system_messages.append({
                    'role': 'system',
                    'content': prompt['text']
                })
        
        return system_messages
    
    def _convert_inference_config(self, inference_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock inference config to OpenAI parameters.
        
        Args:
            inference_config: Bedrock inference configuration
            
        Returns:
            OpenAI API parameters
        """
        params = {}
        
        # Direct mappings
        if 'temperature' in inference_config:
            params['temperature'] = inference_config['temperature']
        
        if 'maxTokens' in inference_config:
            params['max_tokens'] = inference_config['maxTokens']
        
        if 'topP' in inference_config:
            params['top_p'] = inference_config['topP']
        
        if 'stopSequences' in inference_config:
            stop_sequences = inference_config['stopSequences']
            if isinstance(stop_sequences, list) and len(stop_sequences) == 1:
                params['stop'] = stop_sequences[0]
            else:
                params['stop'] = stop_sequences
        
        return params
    
    def _convert_tools_bedrock_to_openai(self, tool_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock tool config to OpenAI tools format.
        
        Args:
            tool_config: Bedrock tool configuration
            
        Returns:
            OpenAI tools parameters
        """
        result = {}
        
        # Convert tools
        bedrock_tools = tool_config.get('tools', [])
        if bedrock_tools:
            openai_tools = []
            
            for tool in bedrock_tools:
                if 'toolSpec' in tool:
                    tool_spec = tool['toolSpec']
                    openai_tool = {
                        'type': 'function',
                        'function': {
                            'name': tool_spec.get('name', ''),
                            'description': tool_spec.get('description', ''),
                            'parameters': tool_spec.get('inputSchema', {})
                        }
                    }
                    openai_tools.append(openai_tool)
            
            result['tools'] = openai_tools
        
        # Convert tool choice
        tool_choice = tool_config.get('toolChoice')
        if tool_choice:
            if isinstance(tool_choice, dict):
                if 'auto' in tool_choice:
                    result['tool_choice'] = 'auto'
                elif 'any' in tool_choice:
                    result['tool_choice'] = 'required'
                elif 'tool' in tool_choice:
                    tool_name = tool_choice['tool'].get('name', '')
                    result['tool_choice'] = {
                        'type': 'function',
                        'function': {'name': tool_name}
                    }
        
        return result
    
    def validate_bedrock_request(self, request: Dict[str, Any]) -> bool:
        """
        Validate Bedrock request format.
        
        Args:
            request: Bedrock format request
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if 'modelId' not in request:
                logger.error("Missing required field: modelId")
                return False
            
            if 'messages' not in request:
                logger.error("Missing required field: messages")
                return False
            
            messages = request['messages']
            if not isinstance(messages, list) or len(messages) == 0:
                logger.error("Messages must be a non-empty list")
                return False
            
            # Validate message structure
            for i, message in enumerate(messages):
                if not isinstance(message, dict):
                    logger.error(f"Message {i} must be a dictionary")
                    return False
                
                if 'role' not in message:
                    logger.error(f"Message {i} missing required field: role")
                    return False
                
                if message['role'] not in ['user', 'assistant']:
                    logger.error(f"Message {i} has invalid role: {message['role']}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            return False