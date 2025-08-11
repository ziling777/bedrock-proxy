"""
Monitoring and metrics collection for the Lambda proxy service.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CloudWatchMetrics:
    """CloudWatch metrics publisher for the proxy service."""
    
    def __init__(self, namespace: str = 'BedrockProxy'):
        """
        Initialize CloudWatch metrics publisher.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self._cloudwatch = None
        self._metrics_buffer = []
        self._buffer_size = 20  # CloudWatch PutMetricData limit
        
    @property
    def cloudwatch(self):
        """Lazy initialization of CloudWatch client."""
        if self._cloudwatch is None:
            try:
                self._cloudwatch = boto3.client('cloudwatch')
                logger.debug("CloudWatch client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize CloudWatch client: {e}")
                # Return a mock client that doesn't actually send metrics
                self._cloudwatch = MockCloudWatchClient()
        return self._cloudwatch
    
    def put_metric(
        self, 
        metric_name: str, 
        value: float, 
        unit: str = 'Count',
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None
    ):
        """
        Add a metric to the buffer for publishing.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit (Count, Seconds, Bytes, etc.)
            dimensions: Metric dimensions
            timestamp: Metric timestamp (defaults to current time)
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': timestamp or time.time()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': key, 'Value': value} 
                    for key, value in dimensions.items()
                ]
            
            self._metrics_buffer.append(metric_data)
            
            # Flush buffer if it's full
            if len(self._metrics_buffer) >= self._buffer_size:
                self.flush_metrics()
                
        except Exception as e:
            logger.error(f"Failed to add metric {metric_name}: {e}")
    
    def flush_metrics(self):
        """Flush all buffered metrics to CloudWatch."""
        if not self._metrics_buffer:
            return
        
        try:
            # Send metrics in batches
            for i in range(0, len(self._metrics_buffer), self._buffer_size):
                batch = self._metrics_buffer[i:i + self._buffer_size]
                
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
                
                logger.debug(f"Published {len(batch)} metrics to CloudWatch")
            
            # Clear the buffer
            self._metrics_buffer.clear()
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
        except Exception as e:
            logger.error(f"Unexpected error publishing metrics: {e}")
    
    def record_request_count(self, endpoint: str, method: str, status_code: int):
        """Record request count metric."""
        self.put_metric(
            'RequestCount',
            1.0,
            'Count',
            {
                'Endpoint': endpoint,
                'Method': method,
                'StatusCode': str(status_code)
            }
        )
    
    def record_response_time(self, endpoint: str, duration_ms: float):
        """Record response time metric."""
        self.put_metric(
            'ResponseTime',
            duration_ms,
            'Milliseconds',
            {'Endpoint': endpoint}
        )
    
    def record_error_count(self, endpoint: str, error_type: str):
        """Record error count metric."""
        self.put_metric(
            'ErrorCount',
            1.0,
            'Count',
            {
                'Endpoint': endpoint,
                'ErrorType': error_type
            }
        )
    
    def record_bedrock_api_call(self, model: str, duration_ms: float, tokens_used: int):
        """Record Bedrock API call metrics."""
        # API call duration
        self.put_metric(
            'BedrockAPILatency',
            duration_ms,
            'Milliseconds',
            {'Model': model}
        )
        
        # Token usage
        if tokens_used > 0:
            self.put_metric(
                'TokensUsed',
                float(tokens_used),
                'Count',
                {'Model': model}
            )
        
        # API call count
        self.put_metric(
            'BedrockAPICallCount',
            1.0,
            'Count',
            {'Model': model}
        )
    
    def record_streaming_metrics(self, model: str, chunk_count: int, total_duration_ms: float):
        """Record streaming response metrics."""
        self.put_metric(
            'StreamingChunkCount',
            float(chunk_count),
            'Count',
            {'Model': model}
        )
        
        self.put_metric(
            'StreamingDuration',
            total_duration_ms,
            'Milliseconds',
            {'Model': model}
        )
    
    def __del__(self):
        """Ensure metrics are flushed when the object is destroyed."""
        try:
            self.flush_metrics()
        except:
            pass  # Ignore errors during cleanup


class MockCloudWatchClient:
    """Mock CloudWatch client for testing or when CloudWatch is unavailable."""
    
    def put_metric_data(self, **kwargs):
        """Mock put_metric_data method."""
        logger.debug(f"Mock CloudWatch: would publish {len(kwargs.get('MetricData', []))} metrics")


class StructuredLogger:
    """Structured logging for the proxy service."""
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize structured logger.
        
        Args:
            logger_name: Name of the logger
        """
        self.logger = logging.getLogger(logger_name)
        
    def log_request_start(
        self, 
        request_id: str, 
        method: str, 
        path: str, 
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None
    ):
        """Log request start with structured data."""
        self.logger.info(
            f"Request started [{request_id}]: {method} {path}",
            extra={
                'event_type': 'request_start',
                'request_id': request_id,
                'method': method,
                'path': path,
                'user_agent': user_agent,
                'client_ip': client_ip,
                'timestamp': time.time()
            }
        )
    
    def log_request_end(
        self, 
        request_id: str, 
        status_code: int, 
        duration_ms: float,
        response_size: Optional[int] = None
    ):
        """Log request completion with structured data."""
        self.logger.info(
            f"Request completed [{request_id}]: {status_code} in {duration_ms:.2f}ms",
            extra={
                'event_type': 'request_end',
                'request_id': request_id,
                'status_code': status_code,
                'duration_ms': duration_ms,
                'response_size': response_size,
                'timestamp': time.time()
            }
        )
    
    def log_bedrock_call(
        self, 
        request_id: str, 
        model: str, 
        endpoint: str,
        duration_ms: float,
        tokens_used: Optional[int] = None,
        success: bool = True
    ):
        """Log Bedrock API call with structured data."""
        self.logger.info(
            f"Bedrock API call [{request_id}]: {endpoint} with {model} - {duration_ms:.2f}ms",
            extra={
                'event_type': 'bedrock_api_call',
                'request_id': request_id,
                'model': model,
                'endpoint': endpoint,
                'duration_ms': duration_ms,
                'tokens_used': tokens_used,
                'success': success,
                'timestamp': time.time()
            }
        )
    
    def log_error(
        self, 
        request_id: str, 
        error_type: str, 
        error_message: str,
        endpoint: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Log error with structured data."""
        self.logger.error(
            f"Error [{request_id}]: {error_type} - {error_message}",
            extra={
                'event_type': 'error',
                'request_id': request_id,
                'error_type': error_type,
                'error_message': error_message,
                'endpoint': endpoint,
                'model': model,
                'timestamp': time.time()
            }
        )
    
    def log_performance_warning(
        self, 
        request_id: str, 
        metric: str, 
        value: float, 
        threshold: float
    ):
        """Log performance warning with structured data."""
        self.logger.warning(
            f"Performance warning [{request_id}]: {metric} = {value} exceeds threshold {threshold}",
            extra={
                'event_type': 'performance_warning',
                'request_id': request_id,
                'metric': metric,
                'value': value,
                'threshold': threshold,
                'timestamp': time.time()
            }
        )


class MonitoringManager:
    """Central monitoring manager that coordinates metrics and logging."""
    
    def __init__(self, namespace: str = 'BedrockProxy'):
        """
        Initialize monitoring manager.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.metrics = CloudWatchMetrics(namespace)
        self.structured_logger = StructuredLogger('bedrock_proxy.monitoring')
        
        # Performance thresholds
        self.thresholds = {
            'response_time_ms': 10000,  # 10 seconds
            'bedrock_api_time_ms': 8000,  # 8 seconds
            'token_usage': 100000  # 100k tokens
        }
    
    def record_request(
        self, 
        request_id: str, 
        method: str, 
        path: str, 
        status_code: int,
        duration_ms: float,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
        response_size: Optional[int] = None
    ):
        """Record complete request metrics and logs."""
        # Log structured data
        self.structured_logger.log_request_start(
            request_id, method, path, user_agent, client_ip
        )
        self.structured_logger.log_request_end(
            request_id, status_code, duration_ms, response_size
        )
        
        # Record metrics
        endpoint = self._normalize_endpoint(path)
        self.metrics.record_request_count(endpoint, method, status_code)
        self.metrics.record_response_time(endpoint, duration_ms)
        
        # Check performance thresholds
        if duration_ms > self.thresholds['response_time_ms']:
            self.structured_logger.log_performance_warning(
                request_id, 'response_time_ms', duration_ms, self.thresholds['response_time_ms']
            )
    
    def record_bedrock_call(
        self, 
        request_id: str, 
        model: str, 
        endpoint: str,
        duration_ms: float,
        tokens_used: Optional[int] = None,
        success: bool = True
    ):
        """Record Bedrock API call metrics and logs."""
        # Log structured data
        self.structured_logger.log_bedrock_call(
            request_id, model, endpoint, duration_ms, tokens_used, success
        )
        
        # Record metrics
        if success:
            self.metrics.record_bedrock_api_call(model, duration_ms, tokens_used or 0)
        
        # Check performance thresholds
        if duration_ms > self.thresholds['bedrock_api_time_ms']:
            self.structured_logger.log_performance_warning(
                request_id, 'bedrock_api_time_ms', duration_ms, self.thresholds['bedrock_api_time_ms']
            )
        
        if tokens_used and tokens_used > self.thresholds['token_usage']:
            self.structured_logger.log_performance_warning(
                request_id, 'token_usage', float(tokens_used), float(self.thresholds['token_usage'])
            )
    
    def record_error(
        self, 
        request_id: str, 
        endpoint: str, 
        error_type: str, 
        error_message: str,
        model: Optional[str] = None
    ):
        """Record error metrics and logs."""
        # Log structured data
        self.structured_logger.log_error(
            request_id, error_type, error_message, endpoint, model
        )
        
        # Record metrics
        normalized_endpoint = self._normalize_endpoint(endpoint)
        self.metrics.record_error_count(normalized_endpoint, error_type)
    
    def record_streaming_session(
        self, 
        request_id: str, 
        model: str, 
        chunk_count: int, 
        total_duration_ms: float
    ):
        """Record streaming session metrics."""
        self.metrics.record_streaming_metrics(model, chunk_count, total_duration_ms)
        
        self.structured_logger.logger.info(
            f"Streaming session [{request_id}]: {chunk_count} chunks in {total_duration_ms:.2f}ms",
            extra={
                'event_type': 'streaming_session',
                'request_id': request_id,
                'model': model,
                'chunk_count': chunk_count,
                'total_duration_ms': total_duration_ms,
                'timestamp': time.time()
            }
        )
    
    def flush_metrics(self):
        """Flush all buffered metrics."""
        self.metrics.flush_metrics()
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for consistent metrics."""
        if path.startswith('/v1/chat/completions'):
            return 'chat_completions'
        elif path.startswith('/v1/models'):
            return 'models'
        elif path.startswith('/health'):
            return 'health'
        else:
            return 'unknown'
    
    def __del__(self):
        """Ensure metrics are flushed when the object is destroyed."""
        try:
            self.flush_metrics()
        except:
            pass  # Ignore errors during cleanup