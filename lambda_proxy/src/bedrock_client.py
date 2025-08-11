"""
AWS Bedrock client for Nova Lite integration.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, Iterator
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from .interfaces import BedrockClientInterface

logger = logging.getLogger(__name__)


class BedrockAPIError(Exception):
    """Custom exception for Bedrock API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class BedrockClient(BedrockClientInterface):
    """AWS Bedrock client implementation for Nova models."""
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize Bedrock client.
        
        Args:
            region: AWS region for Bedrock service
        """
        self.region = region
        self._bedrock_client = None
        self._models_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
        
    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client."""
        if self._bedrock_client is None:
            try:
                self._bedrock_client = boto3.client(
                    'bedrock-runtime',
                    region_name=self.region
                )
                logger.info(f"Initialized Bedrock client for region: {self.region}")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock client: {e}")
                raise BedrockAPIError(f"Failed to initialize Bedrock client: {e}")
        
        return self._bedrock_client
    
    def converse(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Bedrock Converse API.
        
        Args:
            request: Bedrock Converse API request
            
        Returns:
            Bedrock Converse API response
            
        Raises:
            BedrockAPIError: If API call fails
        """
        try:
            logger.info(f"Calling Bedrock Converse API for model: {request.get('modelId')}")
            logger.debug(f"Request payload: {json.dumps(request, indent=2, default=str)}")
            
            start_time = time.time()
            response = self.bedrock_client.converse(**request)
            duration = (time.time() - start_time) * 1000
            
            logger.info(f"Bedrock API response received in {duration:.2f}ms")
            logger.debug(f"Response payload: {json.dumps(response, indent=2, default=str)}")
            
            return response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            status_code = e.response['ResponseMetadata']['HTTPStatusCode']
            
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            
            # Map Bedrock errors to appropriate error types
            error_type_mapping = {
                'ValidationException': 'invalid_request_error',
                'AccessDeniedException': 'authentication_error',
                'ThrottlingException': 'rate_limit_error',
                'ModelNotReadyException': 'model_error',
                'InternalServerException': 'server_error',
                'ServiceQuotaExceededException': 'quota_exceeded_error'
            }
            
            error_type = error_type_mapping.get(error_code, 'api_error')
            
            raise BedrockAPIError(
                message=error_message,
                status_code=status_code,
                error_type=error_type
            )
            
        except BotoCoreError as e:
            logger.error(f"AWS SDK error: {e}")
            raise BedrockAPIError(f"AWS SDK error: {e}", status_code=500, error_type="connection_error")
            
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock API: {e}")
            raise BedrockAPIError(f"Unexpected error: {e}", status_code=500, error_type="internal_error")
    
    def converse_stream(self, request: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Call Bedrock ConverseStream API for streaming responses.
        
        Args:
            request: Bedrock ConverseStream API request
            
        Yields:
            Streaming response chunks
            
        Raises:
            BedrockAPIError: If API call fails
        """
        try:
            logger.info(f"Calling Bedrock ConverseStream API for model: {request.get('modelId')}")
            
            response = self.bedrock_client.converse_stream(**request)
            
            # Process the streaming response
            for event in response.get('stream', []):
                if 'messageStart' in event:
                    yield {
                        'type': 'message_start',
                        'data': event['messageStart']
                    }
                elif 'contentBlockStart' in event:
                    yield {
                        'type': 'content_block_start',
                        'data': event['contentBlockStart']
                    }
                elif 'contentBlockDelta' in event:
                    yield {
                        'type': 'content_block_delta',
                        'data': event['contentBlockDelta']
                    }
                elif 'contentBlockStop' in event:
                    yield {
                        'type': 'content_block_stop',
                        'data': event['contentBlockStop']
                    }
                elif 'messageStop' in event:
                    yield {
                        'type': 'message_stop',
                        'data': event['messageStop']
                    }
                elif 'metadata' in event:
                    yield {
                        'type': 'metadata',
                        'data': event['metadata']
                    }
                    
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            status_code = e.response['ResponseMetadata']['HTTPStatusCode']
            
            logger.error(f"Bedrock streaming API error ({error_code}): {error_message}")
            
            raise BedrockAPIError(
                message=error_message,
                status_code=status_code,
                error_type='streaming_error'
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in streaming API: {e}")
            raise BedrockAPIError(f"Streaming error: {e}", status_code=500, error_type="streaming_error")
    
    def list_foundation_models(self) -> Dict[str, Any]:
        """
        List available foundation models from Bedrock.
        
        Returns:
            List of available models
            
        Raises:
            BedrockAPIError: If API call fails
        """
        try:
            # Check cache first
            current_time = time.time()
            if (self._models_cache is not None and 
                self._cache_timestamp is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                logger.debug("Returning cached models list")
                return self._models_cache
            
            logger.info("Fetching available foundation models from Bedrock")
            
            # Use bedrock client (not bedrock-runtime) for listing models
            bedrock_client = boto3.client('bedrock', region_name=self.region)
            response = bedrock_client.list_foundation_models()
            
            # Filter for Nova models
            nova_models = []
            for model in response.get('modelSummaries', []):
                model_id = model.get('modelId', '')
                if 'nova' in model_id.lower():
                    nova_models.append(model)
            
            models_response = {
                'modelSummaries': nova_models
            }
            
            # Cache the response
            self._models_cache = models_response
            self._cache_timestamp = current_time
            
            logger.info(f"Found {len(nova_models)} Nova models")
            return models_response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            status_code = e.response['ResponseMetadata']['HTTPStatusCode']
            
            logger.error(f"Bedrock models API error ({error_code}): {error_message}")
            
            raise BedrockAPIError(
                message=error_message,
                status_code=status_code,
                error_type='models_error'
            )
            
        except Exception as e:
            logger.error(f"Unexpected error listing models: {e}")
            raise BedrockAPIError(f"Models listing error: {e}", status_code=500, error_type="models_error")
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific model.
        
        Args:
            model_id: Bedrock model identifier
            
        Returns:
            Model information or None if not found
        """
        try:
            models_response = self.list_foundation_models()
            models = models_response.get('modelSummaries', [])
            
            for model in models:
                if model.get('modelId') == model_id:
                    return model
            
            logger.warning(f"Model {model_id} not found in available models")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            return None
    
    def validate_model_access(self, model_id: str) -> bool:
        """
        Validate that the model is accessible.
        
        Args:
            model_id: Bedrock model identifier
            
        Returns:
            True if model is accessible, False otherwise
        """
        try:
            model_info = self.get_model_info(model_id)
            if model_info is None:
                return False
            
            # Check if model is active
            model_status = model_info.get('modelLifecycle', {}).get('status')
            return model_status == 'ACTIVE'
            
        except Exception as e:
            logger.error(f"Error validating model access for {model_id}: {e}")
            return False
    
    def close(self):
        """Close the Bedrock client connection."""
        if self._bedrock_client:
            # boto3 clients don't need explicit closing
            self._bedrock_client = None
            logger.debug("Bedrock client connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()