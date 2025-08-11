#!/usr/bin/env python3
"""
Test monitoring and metrics integration.
"""
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.monitoring import MonitoringManager, CloudWatchMetrics, StructuredLogger


def test_cloudwatch_metrics():
    """Test CloudWatch metrics functionality."""
    print("Testing CloudWatch metrics...")
    
    # Create metrics instance with mock CloudWatch client
    metrics = CloudWatchMetrics('TestNamespace')
    
    # Mock the CloudWatch client
    mock_cloudwatch = Mock()
    metrics._cloudwatch = mock_cloudwatch
    
    # Test adding metrics
    metrics.put_metric('TestMetric', 1.0, 'Count', {'TestDimension': 'TestValue'})
    metrics.put_metric('ResponseTime', 150.5, 'Milliseconds', {'Endpoint': 'chat_completions'})
    
    # Test specific metric methods
    metrics.record_request_count('chat_completions', 'POST', 200)
    metrics.record_response_time('chat_completions', 250.0)
    metrics.record_error_count('chat_completions', 'validation_error')
    metrics.record_bedrock_api_call('amazon.nova-lite-v1:0', 1200.0, 150)
    
    # Verify metrics are buffered
    assert len(metrics._metrics_buffer) > 0
    print(f"✓ {len(metrics._metrics_buffer)} metrics buffered")
    
    # Test flushing metrics
    metrics.flush_metrics()
    
    # Verify CloudWatch client was called
    mock_cloudwatch.put_metric_data.assert_called()
    print("✓ Metrics flushed to CloudWatch")
    
    # Verify buffer is cleared
    assert len(metrics._metrics_buffer) == 0
    print("✓ Metrics buffer cleared after flush")
    
    print("✅ CloudWatch metrics test passed!")
    return True


def test_structured_logger():
    """Test structured logging functionality."""
    print("\nTesting structured logger...")
    
    # Create structured logger
    structured_logger = StructuredLogger('test_logger')
    
    # Mock the underlying logger
    mock_logger = Mock()
    structured_logger.logger = mock_logger
    
    # Test different log methods
    structured_logger.log_request_start(
        'test-req-123', 'POST', '/v1/chat/completions', 
        'TestAgent/1.0', '127.0.0.1'
    )
    
    structured_logger.log_request_end(
        'test-req-123', 200, 1500.0, 2048
    )
    
    structured_logger.log_bedrock_call(
        'test-req-123', 'amazon.nova-lite-v1:0', '/converse',
        1200.0, 150, True
    )
    
    structured_logger.log_error(
        'test-req-123', 'validation_error', 'Invalid request format',
        '/v1/chat/completions', 'amazon.nova-lite-v1:0'
    )
    
    structured_logger.log_performance_warning(
        'test-req-123', 'response_time_ms', 15000.0, 10000.0
    )
    
    # Verify logger was called for each method
    assert mock_logger.info.call_count >= 3  # request_start, request_end, bedrock_call
    assert mock_logger.error.call_count >= 1  # error
    assert mock_logger.warning.call_count >= 1  # performance_warning
    
    print("✓ All structured logging methods called")
    
    # Check that structured data was passed in extra parameter
    calls = mock_logger.info.call_args_list + mock_logger.error.call_args_list + mock_logger.warning.call_args_list
    
    for call in calls:
        args, kwargs = call
        assert 'extra' in kwargs
        extra = kwargs['extra']
        assert 'event_type' in extra
        assert 'request_id' in extra
        assert 'timestamp' in extra
    
    print("✓ Structured data included in all log calls")
    print("✅ Structured logger test passed!")
    return True


def test_monitoring_manager():
    """Test the monitoring manager integration."""
    print("\nTesting monitoring manager...")
    
    # Create monitoring manager
    monitoring = MonitoringManager('TestProxy')
    
    # Mock the underlying components
    monitoring.metrics = Mock()
    monitoring.structured_logger = Mock()
    
    # Test recording a complete request
    monitoring.record_request(
        request_id='test-req-456',
        method='POST',
        path='/v1/chat/completions',
        status_code=200,
        duration_ms=1800.0,
        user_agent='TestClient/1.0',
        client_ip='192.168.1.1',
        response_size=1024
    )
    
    # Verify structured logger was called
    monitoring.structured_logger.log_request_start.assert_called_once()
    monitoring.structured_logger.log_request_end.assert_called_once()
    
    # Verify metrics were recorded
    monitoring.metrics.record_request_count.assert_called_once_with('chat_completions', 'POST', 200)
    monitoring.metrics.record_response_time.assert_called_once_with('chat_completions', 1800.0)
    
    print("✓ Request monitoring recorded")
    
    # Test recording a Bedrock API call
    monitoring.record_bedrock_call(
        request_id='test-req-456',
        model='amazon.nova-lite-v1:0',
        endpoint='/converse',
        duration_ms=1400.0,
        tokens_used=200,
        success=True
    )
    
    # Verify structured logger was called
    monitoring.structured_logger.log_bedrock_call.assert_called_once()
    
    # Verify metrics were recorded
    monitoring.metrics.record_bedrock_api_call.assert_called_once_with('amazon.nova-lite-v1:0', 1400.0, 200)
    
    print("✓ Bedrock API call monitoring recorded")
    
    # Test recording an error
    monitoring.record_error(
        request_id='test-req-456',
        endpoint='/v1/chat/completions',
        error_type='validation_error',
        error_message='Invalid model specified',
        model='invalid-model'
    )
    
    # Verify structured logger was called
    monitoring.structured_logger.log_error.assert_called_once()
    
    # Verify metrics were recorded
    monitoring.metrics.record_error_count.assert_called_once_with('chat_completions', 'validation_error')
    
    print("✓ Error monitoring recorded")
    
    # Test endpoint normalization
    assert monitoring._normalize_endpoint('/v1/chat/completions') == 'chat_completions'
    assert monitoring._normalize_endpoint('/v1/models') == 'models'
    assert monitoring._normalize_endpoint('/health') == 'health'
    assert monitoring._normalize_endpoint('/unknown/path') == 'unknown'
    
    print("✓ Endpoint normalization working")
    
    print("✅ Monitoring manager test passed!")
    return True


def test_monitoring_with_request_handler():
    """Test monitoring integration with request handler."""
    print("\nTesting monitoring with request handler...")
    
    from src.request_handler import RequestHandler
    
    # Create handler
    handler = RequestHandler()
    
    # Mock the monitoring manager
    handler.monitoring = Mock()
    
    # Mock other dependencies
    handler.config_manager = Mock()
    handler.config_manager.get_model_mapping.return_value = {'gpt-4o-mini': 'amazon.nova-lite-v1:0'}
    handler.config_manager.get_timeout_settings.return_value = {'openai_api_timeout': 30}
    handler.config_manager.get_aws_region.return_value = 'us-east-1'
    
    handler.auth_manager = Mock()
    auth_result = Mock()
    auth_result.authenticated = True
    handler.auth_manager.authenticate_request.return_value = auth_result
    handler.auth_manager.authorize_action.return_value = True
    
    handler.bedrock_client = Mock()
    handler.bedrock_client.converse.return_value = {
        'output': {
            'message': {
                'role': 'assistant',
                'content': [{'text': 'Test response'}]
            }
        },
        'stopReason': 'end_turn',
        'usage': {
            'inputTokens': 10,
            'outputTokens': 5,
            'totalTokens': 15
        }
    }
    
    handler.error_handler = Mock()
    handler.error_handler.log_request = Mock()
    handler.error_handler.log_bedrock_api_call = Mock()
    handler.error_handler.log_response = Mock()
    
    # Mark as initialized
    handler._initialized = True
    
    # Test event
    event = {
        'httpMethod': 'POST',
        'path': '/v1/chat/completions',
        'headers': {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json',
            'User-Agent': 'TestClient/1.0'
        },
        'body': json.dumps({
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }),
        'requestContext': {
            'requestId': 'test-monitoring-req',
            'identity': {'sourceIp': '10.0.0.1'}
        }
    }
    
    # Execute request
    response = handler.handle_chat_completion(event)
    
    # Verify monitoring was called
    handler.monitoring.record_request.assert_called_once()
    handler.monitoring.record_bedrock_call.assert_called_once()
    
    # Check the arguments passed to monitoring
    request_call = handler.monitoring.record_request.call_args
    assert request_call[1]['request_id'] == 'test-monitoring-req'
    assert request_call[1]['method'] == 'POST'
    assert request_call[1]['path'] == '/v1/chat/completions'
    assert request_call[1]['status_code'] == 200
    assert request_call[1]['user_agent'] == 'TestClient/1.0'
    assert request_call[1]['client_ip'] == '10.0.0.1'
    
    bedrock_call = handler.monitoring.record_bedrock_call.call_args
    assert bedrock_call[1]['request_id'] == 'test-monitoring-req'
    assert bedrock_call[1]['model'] == 'amazon.nova-lite-v1:0'
    assert bedrock_call[1]['endpoint'] == '/converse'
    assert bedrock_call[1]['success'] == True
    
    print("✓ Request handler monitoring integration working")
    print("✅ Monitoring integration test passed!")
    return True


if __name__ == '__main__':
    print("Testing monitoring functionality...")
    
    success1 = test_cloudwatch_metrics()
    success2 = test_structured_logger()
    success3 = test_monitoring_manager()
    success4 = test_monitoring_with_request_handler()
    
    if all([success1, success2, success3, success4]):
        print("\n✅ All monitoring tests passed!")
    else:
        print("\n❌ Some monitoring tests failed!")