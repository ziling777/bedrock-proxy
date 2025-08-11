"""
Data models for the Lambda proxy service.
"""
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
import time


class ChatMessage(BaseModel):
    """Chat message model compatible with both Bedrock and OpenAI formats."""
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Dict[str, Any]], None] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat completion request model."""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, gt=0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    stop: Optional[Union[str, List[str]]] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = "auto"


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponseMessage(BaseModel):
    """Chat response message."""
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class Choice(BaseModel):
    """Chat completion choice."""
    index: int = 0
    message: ChatResponseMessage
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat completion response."""
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[Choice]
    usage: Usage
    system_fingerprint: Optional[str] = "fp"


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "openai"


class ModelsResponse(BaseModel):
    """Models list response."""
    object: Literal["list"] = "list"
    data: List[ModelInfo]


class ErrorDetail(BaseModel):
    """Error detail information."""
    message: str
    type: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail