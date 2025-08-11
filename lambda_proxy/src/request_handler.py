"""
Request handler for Lambda proxy service.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
from .interfaces import RequestHandlerInterface
from .config_manager import ConfigManager
from .openai_client import OpenAIClient, OpenAIAPIError
from .bedrock_client import BedrockClient, BedrockAPIError
from .bedrock_format_converter import BedrockFormatConverter
from .format_converter import FormatConverter
from .error_handler import ErrorHandler, ProxyError, ErrorType
from .auth import AuthManager
from .monitoring import MonitoringManager
from .config import CORS_HEADERS, SUPPORTED_ENDPOINTS

logger = logging.getLogger(__name__)


class RequestHandler(RequestHandlerInterface):
    """Request handler implementation for Lambda proxy."""
    
    def __init__(self):
        """Initialize request handler with dependencies."""
        self.config_manager = ConfigManager()
        self.openai_client = None
        self.bedrock_client = None
        self.format_converter = None
        self.error_handler = ErrorHandler('lambda_proxy.request_handler')
        self.auth_manager = AuthManager(self.config_manager)
        self.monitoring = MonitoringManager('BedrockProxy')
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of dependencies."""
        if self._initialized:
            return
        
        try:
            # Get configuration
            model_mappings = self.config_manager.get_model_mapping()
            timeout_settings = self.config_manager.get_timeout_settings()
            aws_region = self.config_manager.get_aws_region()
            
            # Initialize Bedrock client (always needed)
            self.bedrock_client = BedrockClient(region=aws_region)
            
            # Initialize OpenAI client only if API key is available
            try:
                api_key = self.config_manager.get_openai_api_key()
                openai_timeout = timeout_settings.get('openai_api_timeout', 30)
                self.openai_client = OpenAIClient(api_key=api_key, timeout=openai_timeout)
                logger.info("OpenAI client initialized")
            except ValueError as e:
                logger.warning(f"OpenAI client not initialized: {e}")
                self.openai_client = None
            
            # Initialize format converter
            self.format_converter = FormatConverter(model_mappings=model_mappings)
            
            self._initialized = True
            logger.info("Request handler initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize request handler: {e}")
            raise RuntimeError(f"Initialization failed: {e}")
    
    def handle_chat_completion(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle chat completion requests.
        
        Args:
            event: API Gateway event
            
        Returns:
            API Gateway response
        """
        request_id = self._get_request_id(event)
        start_time = time.time()
        
        try:
            # Log request
            self.error_handler.log_request(
                method=event.get('httpMethod', 'POST'),
                path=event.get('path', '/v1/chat/completions'),
                request_id=request_id,
                user_agent=self._get_user_agent(event),
                ip_address=self._get_client_ip(event)
            )
            
            self._initialize()
            
            # Authenticate request
            auth_result = self.auth_manager.authenticate_request(event)
            if not auth_result.authenticated:
                raise self.auth_manager.create_auth_error(auth_result)
            
            # Authorize action
            if not self.auth_manager.authorize_action(auth_result, 'chat:completion'):
                raise self.auth_manager.create_auth_error(auth_result)
            
            # Parse request body
            request_body = self._parse_request_body(event)
            if not request_body:
                raise self.error_handler.create_proxy_error(
                    "Invalid or missing request body",
                    ErrorType.VALIDATION_ERROR,
                    400
                )
            
            # Validate OpenAI request format
            if not self._validate_openai_request(request_body):
                raise self.error_handler.create_proxy_error(
                    "Invalid OpenAI request format",
                    ErrorType.VALIDATION_ERROR,
                    400
                )
            
            # Check if streaming is requested
            is_streaming = request_body.get('stream', False)
            original_model = request_body.get('model', 'unknown')
            
            # Convert OpenAI request to Bedrock format
            bedrock_converter = BedrockFormatConverter(self.config_manager.get_model_mapping())
            bedrock_request = bedrock_converter.openai_to_bedrock_request(request_body)
            
            # Call Bedrock API
            api_start_time = time.time()
            if is_streaming:
                # Handle streaming response
                return self._handle_streaming_response(
                    bedrock_request, 
                    bedrock_converter, 
                    original_model, 
                    request_id, 
                    start_time
                )
            else:
                # Handle non-streaming response
                bedrock_response = self.bedrock_client.converse(bedrock_request)
                api_duration = (time.time() - api_start_time) * 1000
                
                # Log Bedrock API call
                tokens_used = bedrock_response.get('usage', {}).get('totalTokens', 0)
                self.error_handler.log_bedrock_api_call(
                    endpoint='/converse',
                    model=bedrock_request.get('modelId', 'unknown'),
                    request_id=request_id,
                    duration_ms=api_duration,
                    tokens_used=tokens_used
                )
                
                # Convert Bedrock response to OpenAI format
                response_data = bedrock_converter.bedrock_to_openai_response(bedrock_response, original_model)
            
            # Log successful response and record monitoring metrics
            duration_ms = (time.time() - start_time) * 1000
            response_body = json.dumps(response_data, ensure_ascii=False)
            response_size = len(response_body.encode('utf-8'))
            
            self.error_handler.log_response(
                status_code=200,
                request_id=request_id,
                duration_ms=duration_ms,
                response_size=response_size
            )
            
            # Record comprehensive monitoring metrics
            self.monitoring.record_request(
                request_id=request_id,
                method=event.get('httpMethod', 'POST'),
                path=event.get('path', '/v1/chat/completions'),
                status_code=200,
                duration_ms=duration_ms,
                user_agent=self._get_user_agent(event),
                client_ip=self._get_client_ip(event),
                response_size=response_size
            )
            
            # Record Bedrock API call metrics
            self.monitoring.record_bedrock_call(
                request_id=request_id,
                model=bedrock_request.get('modelId', 'unknown'),
                endpoint='/converse',
                duration_ms=api_duration,
                tokens_used=tokens_used,
                success=True
            )
            
            return self._create_success_response(response_data)
            
        except BedrockAPIError as e:
            # Handle Bedrock-specific errors
            duration_ms = (time.time() - start_time) * 1000
            error_response = self._handle_bedrock_error(e, request_id)
            
            self.error_handler.log_response(
                status_code=error_response['statusCode'],
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return error_response
            
        except Exception as e:
            # Log error response
            duration_ms = (time.time() - start_time) * 1000
            error_response = self.error_handler.handle_exception(
                e,
                context={'endpoint': 'chat_completion', 'method': 'POST'},
                request_id=request_id
            )
            
            self.error_handler.log_response(
                status_code=error_response['statusCode'],
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return error_response
    
    def handle_models_list(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle models list requests.
        
        Args:
            event: API Gateway event
            
        Returns:
            API Gateway response
        """
        request_id = self._get_request_id(event)
        start_time = time.time()
        
        try:
            # Log request
            self.error_handler.log_request(
                method=event.get('httpMethod', 'GET'),
                path=event.get('path', '/v1/models'),
                request_id=request_id,
                user_agent=self._get_user_agent(event),
                ip_address=self._get_client_ip(event)
            )
            
            self._initialize()
            
            # Authenticate request
            auth_result = self.auth_manager.authenticate_request(event)
            if not auth_result.authenticated:
                raise self.auth_manager.create_auth_error(auth_result)
            
            # Authorize action
            if not self.auth_manager.authorize_action(auth_result, 'models:list'):
                raise self.auth_manager.create_auth_error(auth_result)
            
            # Call Bedrock API to get Nova models
            api_start_time = time.time()
            bedrock_response = self.bedrock_client.list_foundation_models()
            api_duration = (time.time() - api_start_time) * 1000
            
            # Convert Bedrock models to OpenAI format
            openai_response = self._convert_bedrock_models_to_openai(bedrock_response)
            
            # Log Bedrock API call
            self.error_handler.log_bedrock_api_call(
                endpoint='/list-foundation-models',
                model='N/A',
                request_id=request_id,
                duration_ms=api_duration
            )
            
            # Log successful response and record monitoring metrics
            duration_ms = (time.time() - start_time) * 1000
            response_body = json.dumps(openai_response, ensure_ascii=False)
            response_size = len(response_body.encode('utf-8'))
            
            self.error_handler.log_response(
                status_code=200,
                request_id=request_id,
                duration_ms=duration_ms,
                response_size=response_size
            )
            
            # Record comprehensive monitoring metrics
            self.monitoring.record_request(
                request_id=request_id,
                method=event.get('httpMethod', 'GET'),
                path=event.get('path', '/v1/models'),
                status_code=200,
                duration_ms=duration_ms,
                user_agent=self._get_user_agent(event),
                client_ip=self._get_client_ip(event),
                response_size=response_size
            )
            
            # Record Bedrock API call metrics
            self.monitoring.record_bedrock_call(
                request_id=request_id,
                model='N/A',
                endpoint='/list-foundation-models',
                duration_ms=api_duration,
                tokens_used=0,
                success=True
            )
            
            return self._create_success_response(openai_response)
            
        except BedrockAPIError as e:
            # Handle Bedrock-specific errors
            duration_ms = (time.time() - start_time) * 1000
            error_response = self._handle_bedrock_error(e, request_id)
            
            self.error_handler.log_response(
                status_code=error_response['statusCode'],
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return error_response
            
        except Exception as e:
            # Log error response
            duration_ms = (time.time() - start_time) * 1000
            error_response = self.error_handler.handle_exception(
                e,
                context={'endpoint': 'models_list', 'method': 'GET'},
                request_id=request_id
            )
            
            self.error_handler.log_response(
                status_code=error_response['statusCode'],
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return error_response
    
    def handle_health_check(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle health check requests.
        
        Args:
            event: API Gateway event
            
        Returns:
            API Gateway response
        """
        try:
            logger.info("Processing health check request")
            
            # Basic health check
            health_status = {
                'status': 'healthy',
                'timestamp': self._get_current_timestamp(),
                'service': 'lambda-proxy',
                'version': '1.0.0'
            }
            
            # Try to initialize and validate configuration
            try:
                self._initialize()
                
                # Test OpenAI API connectivity
                if self.openai_client and self.openai_client.validate_api_key():
                    health_status['openai_api'] = 'connected'
                else:
                    health_status['openai_api'] = 'disconnected'
                    health_status['status'] = 'degraded'
                    
            except Exception as e:
                logger.warning(f"Health check initialization failed: {e}")
                health_status['status'] = 'unhealthy'
                health_status['error'] = str(e)
            
            # Determine HTTP status code based on health
            status_code = 200 if health_status['status'] == 'healthy' else 503
            
            return self._create_response(status_code, health_status)
            
        except Exception as e:
            logger.error(f"Unexpected error in health check: {e}", exc_info=True)
            return self._create_error_response(500, "Health check failed")
    
    def route_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route request to appropriate handler based on path and method.
        
        Args:
            event: API Gateway event
            
        Returns:
            API Gateway response
        """
        try:
            # Extract HTTP method and path
            http_method = event.get('httpMethod', 'GET').upper()
            path = event.get('path', '/')
            
            logger.info(f"Routing request: {http_method} {path}")
            
            # Handle CORS preflight requests
            if http_method == 'OPTIONS':
                return self._create_cors_response()
            
            # Route to appropriate handler
            if path == '/v1/chat/completions' and http_method == 'POST':
                return self.handle_chat_completion(event)
            elif path == '/v1/models' and http_method == 'GET':
                return self.handle_models_list(event)
            elif path == '/health' and http_method == 'GET':
                return self.handle_health_check(event)
            else:
                logger.warning(f"Unsupported endpoint: {http_method} {path}")
                return self._create_error_response(404, f"Endpoint not found: {http_method} {path}")
                
        except Exception as e:
            logger.error(f"Request routing error: {e}", exc_info=True)
            return self._create_error_response(500, "Request routing failed")
    
    def _parse_request_body(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse request body from API Gateway event.
        
        Args:
            event: API Gateway event
            
        Returns:
            Parsed request body or None if invalid
        """
        try:
            body = event.get('body')
            if not body:
                logger.error("Missing request body")
                return None
            
            # Handle base64 encoded body
            if event.get('isBase64Encoded', False):
                import base64
                body = base64.b64decode(body).decode('utf-8')
            
            # Parse JSON
            request_data = json.loads(body)
            logger.debug(f"Parsed request body: {request_data}")
            
            return request_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse request body: {e}")
            return None
    
    def _create_success_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create successful API Gateway response.
        
        Args:
            data: Response data
            
        Returns:
            API Gateway response
        """
        return self._create_response(200, data)
    
    def _create_error_response(self, status_code: int, message: str, error_type: str = "error") -> Dict[str, Any]:
        """
        Create error API Gateway response.
        
        Args:
            status_code: HTTP status code
            message: Error message
            error_type: Error type
            
        Returns:
            API Gateway response
        """
        error_data = {
            'error': {
                'message': message,
                'type': error_type,
                'code': str(status_code)
            }
        }
        
        return self._create_response(status_code, error_data)
    
    def _create_response(self, status_code: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create API Gateway response.
        
        Args:
            status_code: HTTP status code
            data: Response data
            
        Returns:
            API Gateway response
        """
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                **CORS_HEADERS
            },
            'body': json.dumps(data, ensure_ascii=False)
        }
    
    def _create_cors_response(self) -> Dict[str, Any]:
        """
        Create CORS preflight response.
        
        Returns:
            API Gateway CORS response
        """
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    def _get_current_timestamp(self) -> int:
        """
        Get current timestamp.
        
        Returns:
            Current timestamp as integer
        """
        import time
        return int(time.time())
    
    def _get_request_id(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract request ID from API Gateway event.
        
        Args:
            event: API Gateway event
            
        Returns:
            Request ID or None if not found
        """
        request_context = event.get('requestContext', {})
        return request_context.get('requestId')
    
    def _get_user_agent(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract User-Agent from request headers.
        
        Args:
            event: API Gateway event
            
        Returns:
            User-Agent string or None if not found
        """
        headers = event.get('headers', {})
        return headers.get('User-Agent') or headers.get('user-agent')
    
    def _get_client_ip(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract client IP address from API Gateway event.
        
        Args:
            event: API Gateway event
            
        Returns:
            Client IP address or None if not found
        """
        request_context = event.get('requestContext', {})
        identity = request_context.get('identity', {})
        return identity.get('sourceIp')
    
    def _extract_auth_token(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract authentication token from request headers.
        
        Args:
            event: API Gateway event
            
        Returns:
            Auth token or None if not found
        """
        headers = event.get('headers', {})
        
        # Check Authorization header
        auth_header = headers.get('Authorization') or headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Check X-API-Key header
        api_key = headers.get('X-API-Key') or headers.get('x-api-key')
        if api_key:
            return api_key
        
        return None
    
    def validate_request_auth(self, event: Dict[str, Any]) -> bool:
        """
        Validate request authentication.
        
        Args:
            event: API Gateway event
            
        Returns:
            True if authenticated, False otherwise
        """
        # For now, we'll skip authentication validation
        # In a production environment, you would implement proper auth validation
        # This could check API keys, JWT tokens, etc.
        
        auth_token = self._extract_auth_token(event)
        if not auth_token:
            logger.warning("No authentication token provided")
            # For development, we'll allow requests without auth
            return True
        
        logger.debug(f"Auth token provided: {auth_token[:10]}...")
        return True
    
    def _convert_bedrock_models_to_openai(self, bedrock_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Bedrock models list to OpenAI format.
        
        Args:
            bedrock_response: Bedrock list_foundation_models response
            
        Returns:
            OpenAI-formatted models response
        """
        models = []
        current_time = int(time.time())
        
        # Model metadata mapping
        model_metadata = {
            'amazon.nova-lite-v1:0': {
                'id': 'amazon.nova-lite-v1:0',
                'object': 'model',
                'created': current_time,
                'owned_by': 'amazon',
                'permission': [],
                'root': 'amazon.nova-lite-v1:0',
                'parent': None,
                'context_length': 300000,  # Nova Lite context length
                'capabilities': ['text', 'image']
            },
            'amazon.nova-pro-v1:0': {
                'id': 'amazon.nova-pro-v1:0',
                'object': 'model',
                'created': current_time,
                'owned_by': 'amazon',
                'permission': [],
                'root': 'amazon.nova-pro-v1:0',
                'parent': None,
                'context_length': 300000,  # Nova Pro context length
                'capabilities': ['text', 'image']
            },
            'amazon.nova-micro-v1:0': {
                'id': 'amazon.nova-micro-v1:0',
                'object': 'model',
                'created': current_time,
                'owned_by': 'amazon',
                'permission': [],
                'root': 'amazon.nova-micro-v1:0',
                'parent': None,
                'context_length': 128000,  # Nova Micro context length
                'capabilities': ['text']
            }
        }
        
        # Convert Bedrock models to OpenAI format
        for model_summary in bedrock_response.get('modelSummaries', []):
            model_id = model_summary.get('modelId', '')
            
            # Use predefined metadata if available, otherwise create basic entry
            if model_id in model_metadata:
                model_info = model_metadata[model_id].copy()
            else:
                model_info = {
                    'id': model_id,
                    'object': 'model',
                    'created': current_time,
                    'owned_by': 'amazon',
                    'permission': [],
                    'root': model_id,
                    'parent': None
                }
            
            # Add additional info from Bedrock response if available
            if 'modelLifecycle' in model_summary:
                lifecycle = model_summary['modelLifecycle']
                model_info['status'] = lifecycle.get('status', 'UNKNOWN')
            
            models.append(model_info)
        
        # Also add OpenAI model aliases for backward compatibility
        model_mappings = self.config_manager.get_model_mapping()
        for openai_model, bedrock_model in model_mappings.items():
            # Add OpenAI model name as an alias
            alias_model = {
                'id': openai_model,
                'object': 'model',
                'created': current_time,
                'owned_by': 'openai-compatible',
                'permission': [],
                'root': bedrock_model,
                'parent': bedrock_model,
                'alias_for': bedrock_model
            }
            models.append(alias_model)
        
        return {
            'object': 'list',
            'data': models
        }
    
    def _handle_bedrock_error(self, error: BedrockAPIError, request_id: Optional[str]) -> Dict[str, Any]:
        """
        Handle Bedrock API errors and convert to OpenAI format.
        
        Args:
            error: BedrockAPIError instance
            request_id: Request ID for tracking
            
        Returns:
            API Gateway error response
        """
        # Map Bedrock error types to HTTP status codes and OpenAI error types
        error_mapping = {
            'invalid_request_error': (400, 'invalid_request_error'),
            'authentication_error': (401, 'authentication_error'),
            'rate_limit_error': (429, 'rate_limit_error'),
            'model_error': (503, 'model_error'),
            'server_error': (500, 'server_error'),
            'quota_exceeded_error': (429, 'rate_limit_error'),
            'connection_error': (503, 'connection_error'),
            'models_error': (503, 'server_error')
        }
        
        status_code, openai_error_type = error_mapping.get(
            error.error_type, 
            (500, 'server_error')
        )
        
        # Use the status code from the error if available
        if error.status_code:
            status_code = error.status_code
        
        # Log the error
        logger.error(
            f"Bedrock API error [{request_id}]: {error.message}",
            extra={
                'error_type': error.error_type,
                'status_code': status_code,
                'request_id': request_id
            }
        )
        
        # Create OpenAI-compatible error response
        error_data = {
            'error': {
                'message': error.message,
                'type': openai_error_type,
                'code': str(status_code)
            }
        }
        
        if request_id:
            error_data['request_id'] = request_id
        
        error_data['timestamp'] = int(time.time())
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            },
            'body': json.dumps(error_data, ensure_ascii=False)
        }

    def _validate_openai_request(self, request_body: Dict[str, Any]) -> bool:
        """
        Validate OpenAI request format.
        
        Args:
            request_body: Parsed request body
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if 'model' not in request_body:
                logger.error("Missing 'model' field in request")
                return False
            
            if 'messages' not in request_body:
                logger.error("Missing 'messages' field in request")
                return False
            
            messages = request_body['messages']
            if not isinstance(messages, list) or len(messages) == 0:
                logger.error("'messages' must be a non-empty list")
                return False
            
            # Validate each message
            for i, message in enumerate(messages):
                if not isinstance(message, dict):
                    logger.error(f"Message {i} is not a dictionary")
                    return False
                
                if 'role' not in message:
                    logger.error(f"Message {i} missing 'role' field")
                    return False
                
                if 'content' not in message:
                    logger.error(f"Message {i} missing 'content' field")
                    return False
                
                role = message['role']
                if role not in ['system', 'user', 'assistant']:
                    logger.error(f"Message {i} has invalid role: {role}")
                    return False
            
            # Validate optional parameters
            if 'temperature' in request_body:
                temp = request_body['temperature']
                if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                    logger.error(f"Invalid temperature: {temp}")
                    return False
            
            if 'max_tokens' in request_body:
                max_tokens = request_body['max_tokens']
                if not isinstance(max_tokens, int) or max_tokens <= 0:
                    logger.error(f"Invalid max_tokens: {max_tokens}")
                    return False
            
            if 'top_p' in request_body:
                top_p = request_body['top_p']
                if not isinstance(top_p, (int, float)) or top_p <= 0 or top_p > 1:
                    logger.error(f"Invalid top_p: {top_p}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            return False
    
    def _handle_streaming_response(
        self, 
        bedrock_request: Dict[str, Any], 
        bedrock_converter: BedrockFormatConverter, 
        original_model: str, 
        request_id: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """
        Handle streaming response from Bedrock.
        
        Args:
            bedrock_request: Bedrock API request
            bedrock_converter: Format converter instance
            original_model: Original model name from request
            request_id: Request ID for tracking
            start_time: Request start time
            
        Returns:
            API Gateway streaming response
        """
        try:
            logger.info(f"Handling streaming response for request {request_id}")
            
            # Start streaming response
            api_start_time = time.time()
            stream = self.bedrock_client.converse_stream(bedrock_request)
            
            # Collect streaming chunks and convert to OpenAI format
            streaming_chunks = []
            total_tokens = 0
            
            for chunk in stream:
                # Convert Bedrock chunk to OpenAI format
                openai_chunk = bedrock_converter.convert_streaming_chunk(chunk, original_model)
                streaming_chunks.append(openai_chunk)
                
                # Track tokens if available
                if 'usage' in chunk.get('data', {}):
                    usage = chunk['data']['usage']
                    total_tokens += usage.get('totalTokens', 0)
            
            api_duration = (time.time() - api_start_time) * 1000
            
            # Log Bedrock API call
            self.error_handler.log_bedrock_api_call(
                endpoint='/converse-stream',
                model=bedrock_request.get('modelId', 'unknown'),
                request_id=request_id,
                duration_ms=api_duration,
                tokens_used=total_tokens
            )
            
            # For API Gateway, we need to return a complete response
            # In a real streaming scenario, this would be handled differently
            # For now, we'll combine all chunks into a single response
            if streaming_chunks:
                # Use the last chunk as the final response
                final_chunk = streaming_chunks[-1]
                
                # Convert to non-streaming format
                if 'choices' in final_chunk and len(final_chunk['choices']) > 0:
                    choice = final_chunk['choices'][0]
                    if 'delta' in choice:
                        # Convert delta to message format
                        choice['message'] = choice.pop('delta')
                        choice['finish_reason'] = choice.get('finish_reason', 'stop')
                
                response_data = final_chunk
            else:
                # Fallback response
                response_data = {
                    'id': f'chatcmpl-{request_id}',
                    'object': 'chat.completion',
                    'created': int(time.time()),
                    'model': original_model,
                    'choices': [{
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': 'Stream completed but no content received.'
                        },
                        'finish_reason': 'stop'
                    }],
                    'usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0
                    }
                }
            
            # Log successful response
            duration_ms = (time.time() - start_time) * 1000
            response_body = json.dumps(response_data, ensure_ascii=False)
            self.error_handler.log_response(
                status_code=200,
                request_id=request_id,
                duration_ms=duration_ms,
                response_size=len(response_body.encode('utf-8'))
            )
            
            return self._create_success_response(response_data)
            
        except BedrockAPIError as e:
            # Handle Bedrock streaming errors
            logger.error(f"Bedrock streaming error [{request_id}]: {e.message}")
            return self._handle_bedrock_error(e, request_id)
            
        except Exception as e:
            # Handle other streaming errors
            logger.error(f"Streaming error [{request_id}]: {e}")
            duration_ms = (time.time() - start_time) * 1000
            
            error_response = self.error_handler.handle_exception(
                e,
                context={'endpoint': 'chat_completion_stream', 'method': 'POST'},
                request_id=request_id
            )
            
            self.error_handler.log_response(
                status_code=error_response['statusCode'],
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return error_response

    def cleanup(self):
        """Clean up resources."""
        if self.openai_client:
            self.openai_client.close()
            logger.debug("OpenAI client closed")
        if self.bedrock_client:
            self.bedrock_client.close()
            logger.debug("Bedrock client closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()