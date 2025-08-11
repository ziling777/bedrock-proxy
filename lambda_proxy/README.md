# Lambda Proxy Service

AWS Lambda function that proxies requests from Bedrock format to OpenAI GPT-4o mini API.

## Project Structure

```
lambda_proxy/
├── lambda_function.py          # Main Lambda handler
├── requirements.txt            # Python dependencies
├── README.md                  # This file
├── src/                       # Source code
│   ├── __init__.py
│   ├── models.py              # Pydantic data models
│   ├── interfaces.py          # Abstract interfaces
│   └── config.py              # Configuration settings
└── tests/                     # Test files
    ├── __init__.py
    ├── conftest.py            # Pytest fixtures
    └── test_models.py         # Model tests
```

## Core Components

### Models (`src/models.py`)
- `ChatMessage`: Message format for chat requests
- `ChatRequest`: Chat completion request model
- `ChatResponse`: Chat completion response model
- `ModelsResponse`: Models list response
- `ErrorResponse`: Error response format

### Interfaces (`src/interfaces.py`)
- `ConfigManagerInterface`: Configuration management
- `OpenAIClientInterface`: OpenAI API client
- `FormatConverterInterface`: Request/response conversion
- `RequestHandlerInterface`: Lambda request handling

### Configuration (`src/config.py`)
- Environment variables
- Model mappings
- Timeout settings
- CORS configuration

### Configuration Manager (`src/config_manager.py`)
- `ConfigManager`: Manages configuration and secrets
- Retrieves OpenAI API key from AWS Secrets Manager
- Supports custom model mappings and timeout settings
- Provides configuration validation

### OpenAI Client (`src/openai_client.py`)
- `OpenAIClient`: Handles OpenAI API communication
- Implements chat completion and models list APIs
- Includes retry mechanism with exponential backoff
- Comprehensive error handling and logging
- API key validation and model information retrieval

### Format Converter (`src/format_converter.py`)
- `FormatConverter`: Converts between Bedrock and OpenAI API formats
- Supports text and multimodal content (images)
- Handles tool calls and function calling
- Converts inference parameters and model names
- Validates request formats

### Request Handler (`src/request_handler.py`)
- `RequestHandler`: Processes Lambda requests and coordinates components
- Handles chat completion, models list, and health check endpoints
- Implements request routing and CORS support
- Provides comprehensive error handling and logging
- Supports authentication token extraction

### Error Handler (`src/error_handler.py`)
- `ErrorHandler`: Unified error handling and logging system
- `ProxyError`: Custom exception class with error types
- Standardized error responses and logging formats
- Request/response logging with performance metrics
- OpenAI API error mapping and handling

### Authentication (`src/auth.py`)
- `AuthManager`: Authentication and authorization management
- `AuthResult`: Authentication result with user info and permissions
- Multiple auth methods: API keys, Bearer tokens, JWT
- Permission-based authorization system
- Rate limiting key generation

## Development

### Running Tests
```bash
cd lambda_proxy
pip install -r requirements.txt
pytest tests/ -v
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Test Lambda function locally (requires SAM CLI)
sam local invoke -e test_event.json
```

## Environment Variables

- `OPENAI_API_KEY_SECRET_ARN`: ARN of the secret containing OpenAI API key
- `AWS_REGION`: AWS region (default: us-east-1)
- `DEBUG`: Enable debug logging (default: false)
- `LOG_LEVEL`: Logging level (default: INFO)

## Next Steps

This is the basic project structure. The following components need to be implemented:

1. ConfigManager - Manage configuration and secrets
2. OpenAIClient - Handle OpenAI API calls
3. FormatConverter - Convert between Bedrock and OpenAI formats
4. RequestHandler - Process Lambda requests
5. Error handling and logging
6. Authentication and authorization
7. CloudFormation deployment template