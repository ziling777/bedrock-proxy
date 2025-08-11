"""
Core interfaces for the Lambda proxy service.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Iterator
from .models import ChatRequest, ChatResponse, ModelsResponse


class ConfigManagerInterface(ABC):
    """Interface for configuration management."""
    
    @abstractmethod
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key from secure storage."""
        pass
    
    @abstractmethod
    def get_model_mapping(self) -> Dict[str, str]:
        """Get model name mapping from Bedrock to OpenAI."""
        pass
    
    @abstractmethod
    def get_timeout_settings(self) -> Dict[str, int]:
        """Get timeout configuration."""
        pass


class OpenAIClientInterface(ABC):
    """Interface for OpenAI API client."""
    
    @abstractmethod
    def chat_completion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI chat completion API."""
        pass
    
    @abstractmethod
    def list_models(self) -> Dict[str, Any]:
        """List available models from OpenAI."""
        pass


class FormatConverterInterface(ABC):
    """Interface for request/response format conversion."""
    
    @abstractmethod
    def bedrock_to_openai_request(self, bedrock_request: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Bedrock format request to OpenAI format."""
        pass
    
    @abstractmethod
    def openai_to_bedrock_response(self, openai_response: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI format response to Bedrock compatible format."""
        pass
    
    @abstractmethod
    def convert_model_name(self, model_name: str) -> str:
        """Convert Bedrock model name to OpenAI model name."""
        pass


class BedrockClientInterface(ABC):
    """Interface for AWS Bedrock client."""
    
    @abstractmethod
    def converse(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call Bedrock Converse API."""
        pass
    
    @abstractmethod
    def converse_stream(self, request: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Call Bedrock ConverseStream API for streaming responses."""
        pass
    
    @abstractmethod
    def list_foundation_models(self) -> Dict[str, Any]:
        """List available foundation models from Bedrock."""
        pass
    
    @abstractmethod
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model."""
        pass
    
    @abstractmethod
    def validate_model_access(self, model_id: str) -> bool:
        """Validate that the model is accessible."""
        pass


class RequestHandlerInterface(ABC):
    """Interface for Lambda request handling."""
    
    @abstractmethod
    def handle_chat_completion(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat completion requests."""
        pass
    
    @abstractmethod
    def handle_models_list(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle models list requests."""
        pass
    
    @abstractmethod
    def handle_health_check(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check requests."""
        pass