# Bedrock Nova Proxy Design Document

## Overview

This design document describes an API Gateway + Lambda proxy service that acts as a drop-in replacement for OpenAI API endpoints. The service accepts standard OpenAI API requests (originally targeting GPT-4o mini) and transparently routes them to AWS Bedrock Nova Lite models. This allows developers to switch from OpenAI to Nova Lite by simply changing their API base URL, without modifying any existing client code.

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client App    │───▶│   API Gateway    │───▶│ Lambda Function │
│ (OpenAI format) │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │ AWS Bedrock     │
                                                │ Nova Lite       │
                                                └─────────────────┘
```

### Request Flow

```
Client Request (OpenAI format)
    │
    ▼
API Gateway
    │
    ▼
Lambda Function
    │
    ├─ Parse OpenAI request
    ├─ Convert to Bedrock format
    ├─ Call Bedrock Nova Lite
    ├─ Convert Bedrock response
    └─ Return OpenAI format response
    │
    ▼
Client Response (OpenAI format)
```

## Components and Interfaces

### 1. API Gateway

**Endpoints:**
- `POST /v1/chat/completions` - Chat completion API
- `GET /v1/models` - List available models
- `GET /health` - Health check endpoint

**Configuration:**
- CORS enabled for web clients
- Request/response logging
- Rate limiting and throttling
- Request validation

### 2. Lambda Function Components

#### 2.1 Request Handler
```python
class RequestHandler:
    def handle_chat_completion(self, event: dict) -> dict
    def handle_models_list(self, event: dict) -> dict
    def handle_health_check(self, event: dict) -> dict
```

#### 2.2 Format Converter
```python
class BedrockFormatConverter:
    def openai_to_bedrock_request(self, openai_request: dict) -> dict
    def bedrock_to_openai_response(self, bedrock_response: dict) -> dict
    def convert_messages(self, openai_messages: list) -> list
    def convert_parameters(self, openai_params: dict) -> dict
```

#### 2.3 Bedrock Client
```python
class BedrockClient:
    def __init__(self, region: str = 'us-east-1')
    def converse(self, request: dict) -> dict
    def list_foundation_models(self) -> dict
    def converse_stream(self, request: dict) -> Iterator[dict]
```

#### 2.4 Error Handler
```python
class BedrockErrorHandler:
    def handle_bedrock_error(self, error: Exception) -> dict
    def convert_to_openai_error(self, bedrock_error: dict) -> dict
```

### 3. AWS Bedrock Integration

**Models Supported:**
- `amazon.nova-lite-v1:0` - Nova Lite model
- `amazon.nova-pro-v1:0` - Nova Pro model (if available)
- `amazon.nova-micro-v1:0` - Nova Micro model (if available)

**API Used:**
- Bedrock Converse API for chat completions
- Bedrock ListFoundationModels for model listing
- Bedrock ConverseStream for streaming responses

## Data Models

### Request Conversion

#### OpenAI to Bedrock Format

**OpenAI Chat Completion Request (from existing client code):**
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "top_p": 0.9,
  "stream": false
}
```

**Converted to Bedrock Converse Request:**
```json
{
  "modelId": "amazon.nova-lite-v1:0",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Hello, how are you?"
        }
      ]
    }
  ],
  "inferenceConfig": {
    "temperature": 0.7,
    "maxTokens": 1000,
    "topP": 0.9
  }
}
```

#### Model Mapping

| OpenAI Model (Client Request) | Bedrock Model (Actual Call) | Notes |
|-------------------------------|------------------------------|-------|
| gpt-4o-mini | amazon.nova-lite-v1:0 | Primary mapping for existing clients |
| gpt-4o | amazon.nova-pro-v1:0 | For clients using GPT-4o |
| gpt-3.5-turbo | amazon.nova-micro-v1:0 | For lighter workloads |

#### Parameter Mapping

| OpenAI Parameter | Bedrock Parameter | Notes |
|------------------|-------------------|-------|
| model | modelId | Mapped through model mapping table |
| messages | messages | Content structure conversion |
| temperature | inferenceConfig.temperature | Direct mapping |
| max_tokens | inferenceConfig.maxTokens | Direct mapping |
| top_p | inferenceConfig.topP | Direct mapping |
| stop | inferenceConfig.stopSequences | Array conversion |
| stream | N/A | Handled by different API call |

### Response Conversion

#### Bedrock to OpenAI Format

**Bedrock Converse Response:**
```json
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [
        {
          "text": "Hello! I'm doing well, thank you for asking."
        }
      ]
    }
  },
  "stopReason": "end_turn",
  "usage": {
    "inputTokens": 10,
    "outputTokens": 15,
    "totalTokens": 25
  }
}
```

**Converted to OpenAI Response:**
```json
{
  "id": "chatcmpl-nova-12345",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "amazon.nova-lite-v1:0",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

### Multimodal Support

#### Image Handling

**OpenAI Image Format:**
```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "What's in this image?"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
      }
    }
  ]
}
```

**Converted to Bedrock Format:**
```json
{
  "role": "user",
  "content": [
    {
      "text": "What's in this image?"
    },
    {
      "image": {
        "format": "jpeg",
        "source": {
          "bytes": "/9j/4AAQSkZJRgABAQAAAQ..."
        }
      }
    }
  ]
}
```

## Error Handling

### Error Type Mapping

| Bedrock Error | OpenAI Error Type | HTTP Status |
|---------------|-------------------|-------------|
| ValidationException | invalid_request_error | 400 |
| AccessDeniedException | authentication_error | 401 |
| ThrottlingException | rate_limit_error | 429 |
| ModelNotReadyException | model_error | 503 |
| InternalServerException | server_error | 500 |

### Error Response Format

```json
{
  "error": {
    "message": "The model is currently overloaded with other requests",
    "type": "server_error",
    "code": "model_overloaded"
  }
}
```

## Security Design

### IAM Permissions

**Lambda Execution Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### Data Protection

- No sensitive data stored in Lambda environment
- Request/response data not logged in full
- Image data handled securely in memory
- No persistent storage of user data

## Performance Optimization

### Lambda Configuration

- **Runtime:** Python 3.11
- **Architecture:** ARM64 (better price/performance)
- **Memory:** 1024MB (for image processing)
- **Timeout:** 5 minutes (for long conversations)
- **Reserved Concurrency:** 100 (cost control)

### Bedrock Optimization

- Connection pooling for Bedrock client
- Efficient JSON parsing and serialization
- Streaming support for real-time responses
- Retry logic with exponential backoff

### Caching Strategy

- Model list caching (5 minutes TTL)
- Bedrock client connection reuse
- Lambda container reuse optimization

## Monitoring and Observability

### CloudWatch Metrics

- Request count by endpoint
- Response latency percentiles
- Error rate by error type
- Token usage tracking
- Bedrock API call success rate

### Logging Strategy

```python
# Structured logging format
{
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req-12345",
  "event_type": "bedrock_api_call",
  "model": "amazon.nova-lite-v1:0",
  "duration_ms": 1500,
  "input_tokens": 10,
  "output_tokens": 15,
  "status": "success"
}
```

### Alarms

- Lambda function errors > 5%
- Average response time > 10 seconds
- Bedrock API error rate > 2%
- Lambda function throttling

## Streaming Implementation

### Server-Sent Events

```python
def handle_streaming_response(bedrock_stream):
    for chunk in bedrock_stream:
        openai_chunk = convert_bedrock_chunk_to_openai(chunk)
        yield f"data: {json.dumps(openai_chunk)}\n\n"
    
    yield "data: [DONE]\n\n"
```

### Streaming Response Format

```json
{
  "id": "chatcmpl-nova-12345",
  "object": "chat.completion.chunk",
  "created": 1234567890,
  "model": "amazon.nova-lite-v1:0",
  "choices": [
    {
      "index": 0,
      "delta": {
        "content": "Hello"
      },
      "finish_reason": null
    }
  ]
}
```

## Testing Strategy

### Unit Tests
- Format conversion functions
- Error handling logic
- Parameter validation
- Response transformation

### Integration Tests
- End-to-end API flow
- Bedrock integration
- Error scenarios
- Streaming functionality

### Performance Tests
- Load testing with concurrent requests
- Memory usage optimization
- Cold start performance
- Large image processing

## Deployment Architecture

### Infrastructure as Code

```yaml
# CloudFormation template structure
Resources:
  # API Gateway
  NovaProxyApi:
    Type: AWS::ApiGateway::RestApi
    
  # Lambda Function
  NovaProxyFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.11
      Architecture: arm64
      
  # IAM Role
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      Policies:
        - BedrockInvokePolicy
```

### Environment Configuration

- **Development:** Lower memory, detailed logging
- **Production:** Optimized memory, structured logging
- **Testing:** Mock Bedrock responses for unit tests