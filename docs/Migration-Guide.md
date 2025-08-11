# Migration Guide: From OpenAI to Amazon Bedrock Nova

This guide helps you migrate your existing OpenAI-based applications to use Amazon Bedrock Nova models through our proxy service.

## Overview

The Bedrock Nova Proxy provides a seamless migration path by offering an OpenAI-compatible API that internally routes requests to Amazon Bedrock Nova models. This means you can keep your existing code structure while benefiting from Nova's performance and cost advantages.

## Quick Start Migration

### 1. Minimal Code Changes Required

For most applications, you only need to change the base URL:

```python
# Before (OpenAI)
from openai import OpenAI
client = OpenAI(api_key="your-openai-key")

# After (Bedrock Nova Proxy)
from openai import OpenAI
client = OpenAI(
    base_url="https://your-api-gateway-url/prod",
    api_key="dummy"  # Not used, but required by OpenAI client
)
```

### 2. Model Mapping

Your existing model names are automatically mapped to Nova models:

| OpenAI Model | Nova Model | Use Case |
|--------------|------------|----------|
| `gpt-3.5-turbo` | `amazon.nova-micro-v1:0` | Fast, cost-effective text |
| `gpt-4o-mini` | `amazon.nova-lite-v1:0` | Balanced performance, multimodal |
| `gpt-4o` | `amazon.nova-pro-v1:0` | High performance, multimodal |

## Detailed Migration Steps

### Step 1: Deploy the Proxy Service

```bash
cd deployment
./deploy-bedrock-nova.sh --region us-east-1 --test
```

This creates:
- API Gateway endpoint
- Lambda function with Nova integration
- CloudWatch monitoring
- IAM roles and policies

### Step 2: Update Your Application

#### Python Applications

```python
# Original OpenAI code
import openai
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

```python
# Migrated code (minimal changes)
import openai
from openai import OpenAI

client = OpenAI(
    base_url="https://your-api-gateway-url/prod",
    api_key="dummy"  # Required by client, but not used
)

# Everything else stays the same!
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Automatically maps to Nova Lite
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

#### Node.js Applications

```javascript
// Original OpenAI code
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const response = await openai.chat.completions.create({
  model: 'gpt-4o-mini',
  messages: [{ role: 'user', content: 'Hello!' }],
});
```

```javascript
// Migrated code
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'https://your-api-gateway-url/prod',
  apiKey: 'dummy', // Required but not used
});

// Everything else stays the same!
const response = await openai.chat.completions.create({
  model: 'gpt-4o-mini', // Maps to Nova Lite
  messages: [{ role: 'user', content: 'Hello!' }],
});
```

### Step 3: Test Your Migration

Use the provided test scripts to verify functionality:

```bash
# Test basic chat completion
python lambda_proxy/test_bedrock_integration.py

# Test model listing
python lambda_proxy/test_models_integration.py

# Test monitoring
python lambda_proxy/test_monitoring_integration.py
```

## Feature Compatibility

### ✅ Fully Supported Features

- **Chat Completions**: Complete OpenAI chat API compatibility
- **Streaming**: Real-time response streaming
- **Multimodal**: Text and image inputs (Nova Lite/Pro)
- **Model Listing**: `/v1/models` endpoint
- **Error Handling**: OpenAI-compatible error responses
- **Token Counting**: Accurate usage statistics

### ✅ Enhanced Features

- **Cost Optimization**: Nova models are significantly cheaper
- **Performance**: Faster response times in AWS regions
- **Monitoring**: Built-in CloudWatch metrics and logging
- **Security**: No API keys to manage, uses AWS IAM

### ⚠️ Differences to Note

1. **Authentication**: Uses AWS IAM instead of API keys
2. **Rate Limits**: Follows Bedrock service limits, not OpenAI limits
3. **Model Availability**: Limited to Nova model family
4. **Regional**: Deployed in specific AWS regions

## Advanced Configuration

### Custom Model Mappings

You can customize model mappings by updating the Lambda environment variables:

```bash
# In your CloudFormation template or AWS Console
MODEL_MAPPINGS='{
  "gpt-4o": "amazon.nova-premier-v1:0",
  "gpt-4o-mini": "amazon.nova-lite-v1:0",
  "custom-model": "amazon.nova-pro-v1:0"
}'
```

### Environment-Specific Deployments

```bash
# Development environment
./deploy-bedrock-nova.sh --region us-east-1 --stage dev

# Production environment  
./deploy-bedrock-nova.sh --region us-east-1 --stage prod --enable-monitoring
```

### Monitoring and Observability

The proxy automatically provides:

- **CloudWatch Metrics**: Request count, latency, errors
- **Structured Logging**: Detailed request/response logs
- **Cost Tracking**: Token usage and estimated costs
- **Health Checks**: Endpoint availability monitoring

Access monitoring through:
```bash
# View logs
aws logs tail /aws/lambda/bedrock-nova-proxy --follow

# View metrics
aws cloudwatch get-metric-statistics \
  --namespace "BedrockNovaProxy" \
  --metric-name "RequestCount" \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

## Migration Checklist

### Pre-Migration
- [ ] Review current OpenAI usage patterns
- [ ] Identify models used in your application
- [ ] Set up AWS credentials and permissions
- [ ] Choose target AWS region for deployment

### Deployment
- [ ] Deploy the Bedrock Nova Proxy
- [ ] Verify deployment with test scripts
- [ ] Configure monitoring and alerting
- [ ] Set up backup/rollback procedures

### Application Updates
- [ ] Update base URL in OpenAI client initialization
- [ ] Remove OpenAI API key dependencies
- [ ] Test all application endpoints
- [ ] Verify multimodal functionality (if used)
- [ ] Check streaming responses (if used)

### Post-Migration
- [ ] Monitor performance and costs
- [ ] Set up CloudWatch dashboards
- [ ] Configure alerts for errors/latency
- [ ] Document new deployment process
- [ ] Train team on new monitoring tools

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
```
Error: Invalid API key provided
```
**Solution**: Ensure your Lambda has proper Bedrock permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
    }
  ]
}
```

#### 2. Model Not Found
```
Error: Model 'gpt-4' not found
```
**Solution**: Check model mappings or use supported models:
```python
# List available models
response = client.models.list()
for model in response.data:
    print(f"ID: {model.id}, Owner: {model.owned_by}")
```

#### 3. Timeout Issues
```
Error: Request timeout
```
**Solution**: Increase Lambda timeout in CloudFormation template:
```yaml
Timeout: 300  # 5 minutes for long responses
```

### Performance Optimization

1. **Cold Start Reduction**:
   ```yaml
   # Enable provisioned concurrency
   ProvisionedConcurrencyConfig:
     ProvisionedConcurrencyUnits: 5
   ```

2. **Memory Optimization**:
   ```yaml
   # Adjust based on usage patterns
   MemorySize: 1024  # MB
   ```

3. **Regional Deployment**:
   - Deploy in regions closest to your users
   - Consider multi-region for global applications

## Cost Comparison

### Estimated Cost Savings

| Model Comparison | OpenAI Cost | Nova Cost | Savings |
|------------------|-------------|-----------|---------|
| GPT-3.5-turbo vs Nova Micro | $0.0015/1K tokens | $0.00035/1K tokens | ~77% |
| GPT-4o-mini vs Nova Lite | $0.00015/1K tokens | $0.0002/1K tokens | ~-33% |
| GPT-4o vs Nova Pro | $0.005/1K tokens | $0.0008/1K tokens | ~84% |

*Note: Costs are approximate and may vary by region and usage patterns*

### Additional AWS Costs
- API Gateway: $3.50 per million requests
- Lambda: $0.20 per 1M requests + compute time
- CloudWatch: Minimal for standard monitoring

## Real-World Migration Examples

### Enterprise Application Migration

Here's a complete example of migrating a production application:

```python
# enterprise_app.py - Before migration
import os
import logging
from openai import OpenAI
from typing import List, Dict

class ChatService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def generate_response(self, messages: List[Dict], model: str = "gpt-4o-mini"):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise

# After migration - Only 3 lines changed!
class ChatService:
    def __init__(self):
        # Changed: Use Bedrock Nova Proxy endpoint
        self.client = OpenAI(
            base_url="https://your-api-gateway-url/prod",
            api_key="dummy"  # Required by client but not used
        )
        self.logger = logging.getLogger(__name__)
    
    def generate_response(self, messages: List[Dict], model: str = "gpt-4o-mini"):
        try:
            # Same code - automatically uses Nova Lite!
            response = self.client.chat.completions.create(
                model=model,  # Maps to amazon.nova-lite-v1:0
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Bedrock API error: {e}")
            raise
```

### Multimodal Application Migration

```python
# multimodal_app.py - Image analysis with Nova
import base64
from openai import OpenAI

client = OpenAI(
    base_url="https://your-api-gateway-url/prod",
    api_key="dummy"
)

def analyze_image(image_path: str, question: str):
    # Read and encode image
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Uses Nova Lite with vision
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    }
                ]
            }
        ]
    )
    
    return response.choices[0].message.content

# Usage
result = analyze_image("product.jpg", "What product is shown in this image?")
print(result)
```

### Streaming Response Migration

```python
# streaming_app.py - Real-time responses
from openai import OpenAI

client = OpenAI(
    base_url="https://your-api-gateway-url/prod",
    api_key="dummy"
)

def stream_chat_response(messages):
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True  # Enable streaming
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="")
            yield chunk.choices[0].delta.content

# Usage
messages = [{"role": "user", "content": "Tell me a story"}]
for content in stream_chat_response(messages):
    # Process each chunk as it arrives
    pass
```

## Migration Testing Strategy

### Automated Testing Setup

Create comprehensive tests to validate your migration:

```python
# test_migration.py
import pytest
from openai import OpenAI
import json

class TestMigration:
    def setup_method(self):
        # Test both endpoints
        self.openai_client = OpenAI(api_key="your-openai-key")
        self.nova_client = OpenAI(
            base_url="https://your-api-gateway-url/prod",
            api_key="dummy"
        )
    
    def test_basic_completion(self):
        """Test basic chat completion works"""
        messages = [{"role": "user", "content": "Hello"}]
        
        response = self.nova_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        assert response.choices[0].message.content
        assert response.usage.total_tokens > 0
    
    def test_model_mapping(self):
        """Test that model mappings work correctly"""
        models = self.nova_client.models.list()
        model_ids = [model.id for model in models.data]
        
        # Check OpenAI-compatible models exist
        assert "gpt-4o-mini" in model_ids
        assert "gpt-4o" in model_ids
        assert "gpt-3.5-turbo" in model_ids
    
    def test_error_handling(self):
        """Test error responses are OpenAI-compatible"""
        with pytest.raises(Exception) as exc_info:
            self.nova_client.chat.completions.create(
                model="nonexistent-model",
                messages=[{"role": "user", "content": "test"}]
            )
        
        # Should get OpenAI-style error
        assert "model" in str(exc_info.value).lower()
    
    def test_streaming(self):
        """Test streaming responses work"""
        messages = [{"role": "user", "content": "Count to 5"}]
        
        stream = self.nova_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            stream=True
        )
        
        chunks = list(stream)
        assert len(chunks) > 1  # Should have multiple chunks
```

### Performance Comparison

```python
# performance_test.py
import time
import statistics
from openai import OpenAI

def benchmark_response_time(client, model, messages, iterations=10):
    """Benchmark response times"""
    times = []
    
    for _ in range(iterations):
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        end = time.time()
        times.append(end - start)
    
    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times)
    }

# Compare OpenAI vs Nova
openai_client = OpenAI(api_key="your-openai-key")
nova_client = OpenAI(
    base_url="https://your-api-gateway-url/prod",
    api_key="dummy"
)

messages = [{"role": "user", "content": "Explain quantum computing"}]

openai_times = benchmark_response_time(openai_client, "gpt-4o-mini", messages)
nova_times = benchmark_response_time(nova_client, "gpt-4o-mini", messages)

print(f"OpenAI average: {openai_times['mean']:.2f}s")
print(f"Nova average: {nova_times['mean']:.2f}s")
print(f"Improvement: {((openai_times['mean'] - nova_times['mean']) / openai_times['mean'] * 100):.1f}%")
```

## Production Deployment Best Practices

### Blue-Green Deployment Strategy

```bash
#!/bin/bash
# blue_green_deploy.sh

# Deploy new version (green)
./deploy-bedrock-nova.sh --region us-east-1 --stage green

# Test green deployment
python test_migration.py --endpoint https://green-api-gateway-url/prod

# Switch traffic gradually
aws apigateway update-stage \
  --rest-api-id your-api-id \
  --stage-name prod \
  --patch-ops op=replace,path=/variables/backend_url,value=https://green-lambda-url

# Monitor for 10 minutes
sleep 600

# If successful, clean up blue deployment
# If issues, rollback to blue
```

### Monitoring Dashboard Setup

```yaml
# cloudwatch_dashboard.yaml
Resources:
  MigrationDashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: BedrockNovaMigration
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "metrics": [
                  ["BedrockNovaProxy", "RequestCount"],
                  [".", "ErrorCount"],
                  [".", "ResponseTime"]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "${AWS::Region}",
                "title": "Migration Metrics"
              }
            },
            {
              "type": "log",
              "properties": {
                "query": "SOURCE '/aws/lambda/bedrock-nova-proxy'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 100",
                "region": "${AWS::Region}",
                "title": "Recent Errors"
              }
            }
          ]
        }
```

### Cost Monitoring

```python
# cost_monitor.py
import boto3
from datetime import datetime, timedelta

def get_migration_costs():
    """Monitor costs after migration"""
    ce = boto3.client('ce')
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=['BlendedCost'],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['Amazon Bedrock', 'AWS Lambda', 'Amazon API Gateway']
            }
        }
    )
    
    total_cost = 0
    for result in response['ResultsByTime']:
        for group in result['Groups']:
            cost = float(group['Metrics']['BlendedCost']['Amount'])
            service = group['Keys'][0]
            print(f"{service}: ${cost:.4f}")
            total_cost += cost
    
    print(f"Total monthly cost: ${total_cost:.2f}")
    return total_cost

# Run cost analysis
monthly_cost = get_migration_costs()
```

## Support and Resources

### Documentation
- [Amazon Bedrock Nova Models](https://docs.aws.amazon.com/bedrock/latest/userguide/nova-models.html)
- [OpenAI Python Client](https://github.com/openai/openai-python)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

### Community
- GitHub Issues: Report bugs and feature requests
- AWS Forums: Bedrock-specific questions
- Stack Overflow: General integration questions

### Getting Help

1. **Check Logs**: CloudWatch logs provide detailed error information
2. **Test Endpoints**: Use provided integration tests
3. **Monitor Metrics**: CloudWatch dashboards show system health
4. **Contact Support**: AWS Support for Bedrock-specific issues

### Migration Support Checklist

- [ ] **Pre-Migration Assessment**: Analyze current usage patterns
- [ ] **Pilot Testing**: Test with 10% of traffic first
- [ ] **Performance Validation**: Ensure response times meet requirements
- [ ] **Cost Validation**: Confirm expected cost savings
- [ ] **Monitoring Setup**: CloudWatch dashboards and alerts
- [ ] **Rollback Plan**: Documented procedure to revert if needed
- [ ] **Team Training**: Ensure team understands new monitoring tools
- [ ] **Documentation Update**: Update internal docs and runbooks

---

*This migration guide is maintained alongside the Bedrock Nova Proxy project. For the latest updates, check the project repository.*