"""
AWS Lambda function entry point for the OpenAI proxy service.
"""
import json
import logging
import os
from typing import Dict, Any

from src.request_handler import RequestHandler
from src.error_handler import ErrorHandler

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

# Global request handler instance for reuse across invocations
request_handler = None
error_handler = ErrorHandler('lambda_proxy.main')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    global request_handler
    
    try:
        # Log the incoming event (excluding sensitive data)
        safe_event = _sanitize_event_for_logging(event)
        logger.info(f"Processing Lambda request: {json.dumps(safe_event, default=str)}")
        
        # Initialize request handler if not already done
        if request_handler is None:
            logger.info("Initializing request handler")
            request_handler = RequestHandler()
        
        # Route the request to appropriate handler
        response = request_handler.route_request(event)
        
        # Log response status
        logger.info(f"Request completed with status: {response.get('statusCode', 'unknown')}")
        
        return response
        
    except Exception as e:
        # Handle unexpected errors at the Lambda level
        logger.error(f"Unexpected error in Lambda handler: {str(e)}", exc_info=True)
        
        # Use error handler to create standardized error response
        return error_handler.handle_exception(
            e,
            context={
                'lambda_function': 'lambda_handler',
                'aws_request_id': getattr(context, 'aws_request_id', None),
                'function_name': getattr(context, 'function_name', None)
            }
        )


def _sanitize_event_for_logging(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize event data for safe logging by removing sensitive information.
    
    Args:
        event: Original API Gateway event
        
    Returns:
        Sanitized event safe for logging
    """
    try:
        # Create a copy to avoid modifying the original
        safe_event = event.copy()
        
        # Remove or mask sensitive headers
        if 'headers' in safe_event:
            headers = safe_event['headers'].copy()
            
            # Mask authorization headers
            for header_name in ['Authorization', 'authorization', 'X-API-Key', 'x-api-key']:
                if header_name in headers:
                    value = headers[header_name]
                    if value:
                        # Show only first 10 characters for debugging
                        headers[header_name] = f"{value[:10]}***"
            
            safe_event['headers'] = headers
        
        # Remove request body if it's too large or contains sensitive data
        if 'body' in safe_event:
            body = safe_event['body']
            if body and len(body) > 1000:
                safe_event['body'] = f"<body truncated, length: {len(body)}>"
        
        # Keep only essential fields for logging
        essential_fields = [
            'httpMethod', 'path', 'headers', 'queryStringParameters',
            'requestContext', 'isBase64Encoded'
        ]
        
        sanitized = {}
        for field in essential_fields:
            if field in safe_event:
                sanitized[field] = safe_event[field]
        
        # Add request context info if available
        if 'requestContext' in event:
            request_context = event['requestContext']
            sanitized['requestContext'] = {
                'requestId': request_context.get('requestId'),
                'stage': request_context.get('stage'),
                'httpMethod': request_context.get('httpMethod'),
                'path': request_context.get('path')
            }
        
        return sanitized
        
    except Exception as e:
        logger.warning(f"Failed to sanitize event for logging: {e}")
        return {'error': 'Failed to sanitize event'}


def health_check() -> Dict[str, Any]:
    """
    Simple health check function for testing.
    
    Returns:
        Health status response
    """
    try:
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'service': 'lambda-proxy',
                'version': '1.0.0'
            })
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e)
            })
        }


# For local testing
if __name__ == '__main__':
    # Example test event
    test_event = {
        'httpMethod': 'GET',
        'path': '/health',
        'headers': {},
        'requestContext': {
            'requestId': 'test-request-id',
            'stage': 'test'
        }
    }
    
    # Mock context
    class MockContext:
        aws_request_id = 'test-request-id'
        function_name = 'test-function'
    
    # Test the handler
    response = lambda_handler(test_event, MockContext())
    print(json.dumps(response, indent=2))