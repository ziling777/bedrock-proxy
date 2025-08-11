# Bedrock Nova Proxy Deployment

This directory contains deployment scripts and CloudFormation templates for the Bedrock Nova Proxy - an OpenAI-compatible API that uses AWS Bedrock Nova models.

## Overview

The Bedrock Nova Proxy allows you to use AWS Bedrock Nova models (Nova Lite, Nova Pro, Nova Micro) through an OpenAI-compatible API. This means you can switch from OpenAI to AWS Nova models by simply changing your API base URL, without modifying any existing client code.

## Features

- 🔄 **Drop-in OpenAI Replacement**: Change only the base URL in your existing OpenAI client code
- 🚀 **AWS Bedrock Nova Models**: Access to Nova Lite, Nova Pro, and Nova Micro models
- 🖼️ **Multimodal Support**: Text and image processing capabilities
- 📊 **Comprehensive Monitoring**: CloudWatch metrics and dashboards
- 🔒 **Secure**: Uses IAM roles, no API keys to manage
- ⚡ **High Performance**: ARM64 Lambda with optimized memory allocation

## Quick Start

### Prerequisites

1. **AWS CLI** installed and configured
2. **AWS Account** with appropriate permissions
3. **Bedrock Access** enabled in your AWS account
4. **Python 3.11+** for local development (optional)

### Deploy the Proxy

```bash
# Deploy with default settings
./deploy-bedrock-nova.sh

# Deploy with custom configuration
./deploy-bedrock-nova.sh \
  --region us-west-2 \
  --memory 2048 \
  --timeout 300 \
  --test
```

### Test the Deployment

```bash
# Run comprehensive tests
./test-deployment.sh

# Test specific region/stack
./test-deployment.sh --region us-west-2 --stack-name my-bedrock-proxy
```

## Usage

Once deployed, you can use the proxy as a drop-in replacement for OpenAI:

### Python Example

```python
from openai import OpenAI

# Instead of: client = OpenAI(api_key="your-openai-key")
client = OpenAI(
    base_url="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod",
    api_key="dummy"  # Not used, but required by OpenAI client
)

# Your existing code works unchanged!
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Maps to amazon.nova-lite-v1:0
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

### JavaScript Example

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod',
  apiKey: 'dummy', // Not used, but required
});

const response = await client.chat.completions.create({
  model: 'gpt-4o-mini', // Maps to amazon.nova-lite-v1:0
  messages: [
    { role: 'user', content: 'Hello, how are you?' }
  ],
});

console.log(response.choices[0].message.content);
```

### cURL Example

```bash
curl -X POST "https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

## Model Mapping

The proxy automatically maps OpenAI model names to Bedrock Nova models:

| OpenAI Model | Bedrock Model | Use Case |
|--------------|---------------|----------|
| `gpt-4o-mini` | `amazon.nova-lite-v1:0` | Fast, cost-effective tasks |
| `gpt-4o` | `amazon.nova-pro-v1:0` | Complex reasoning, multimodal |
| `gpt-3.5-turbo` | `amazon.nova-micro-v1:0` | Simple text tasks |

You can also use Bedrock model names directly:
- `amazon.nova-lite-v1:0`
- `amazon.nova-pro-v1:0`
- `amazon.nova-micro-v1:0`

## Deployment Options

### CloudFormation Template

The `BedrockNovaProxy.template` CloudFormation template includes:

- **Lambda Function**: ARM64 Python 3.11 runtime
- **API Gateway**: RESTful API with CORS support
- **IAM Roles**: Least-privilege permissions for Bedrock access
- **CloudWatch**: Comprehensive monitoring and alerting
- **Dead Letter Queue**: Error handling for failed invocations

### Deployment Script Options

```bash
./deploy-bedrock-nova.sh [OPTIONS]

Options:
  --region REGION           AWS region for deployment (default: us-east-1)
  --bedrock-region REGION   AWS region for Bedrock service (default: same as --region)
  --stack-name NAME         CloudFormation stack name (default: bedrock-nova-proxy)
  --bucket BUCKET           S3 bucket for deployment artifacts
  --memory SIZE             Lambda memory size in MB (default: 1024)
  --timeout SECONDS         Lambda timeout in seconds (default: 300)
  --cleanup-bucket          Clean up deployment bucket after deployment
  --test                    Run deployment tests after deployment
  --help                    Show help message
```

### Environment Variables

You can customize the deployment using environment variables:

```bash
export LAMBDA_FUNCTION_NAME="my-bedrock-proxy"
export API_GATEWAY_NAME="my-bedrock-api"
export STAGE="prod"
export LOG_LEVEL="INFO"
export LAMBDA_MEMORY_SIZE="2048"
export LAMBDA_TIMEOUT="300"
export RESERVED_CONCURRENCY="100"
export CLOUDWATCH_NAMESPACE="MyBedrockProxy"

./deploy-bedrock-nova.sh
```

## Monitoring

### CloudWatch Dashboard

The deployment creates a CloudWatch dashboard with:

- Lambda function metrics (invocations, errors, duration)
- API Gateway metrics (requests, 4xx/5xx errors)
- Bedrock API metrics (latency, token usage, call count)

### Custom Metrics

The proxy publishes custom metrics to CloudWatch:

- `BedrockAPILatency`: Time taken for Bedrock API calls
- `TokensUsed`: Number of tokens consumed
- `BedrockAPICallCount`: Number of Bedrock API calls
- `ErrorCount`: Number of errors by type
- `RequestCount`: Number of requests by endpoint

### Alarms

Pre-configured CloudWatch alarms monitor:

- Lambda function errors (> 5 in 10 minutes)
- Lambda function duration (> timeout threshold)
- Lambda function throttles
- API Gateway 4xx errors (> 10 in 10 minutes)
- API Gateway 5xx errors (> 5 in 10 minutes)
- Bedrock API errors (> 5 in 10 minutes)
- Bedrock API latency (> 10 seconds average)

## Security

### IAM Permissions

The Lambda function uses least-privilege IAM permissions:

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
      "Resource": "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
    },
    {
      "Effect": "Allow",
      "Action": "cloudwatch:PutMetricData",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "BedrockProxy"
        }
      }
    }
  ]
}
```

### Data Protection

- No sensitive data is logged
- Request/response data is not persisted
- Image data is processed in memory only
- No API keys required (uses IAM roles)

## Troubleshooting

### Common Issues

1. **Bedrock Access Denied**
   ```
   Error: AccessDeniedException
   ```
   - Ensure Bedrock service is enabled in your AWS account
   - Check IAM permissions for Bedrock access
   - Verify the region supports Nova models

2. **Lambda Timeout**
   ```
   Error: Task timed out after X seconds
   ```
   - Increase Lambda timeout (max 15 minutes)
   - Increase Lambda memory for better performance
   - Check Bedrock API latency

3. **Package Too Large**
   ```
   Error: Unzipped size must be smaller than X bytes
   ```
   - The deployment script automatically handles large packages
   - Dependencies are uploaded to S3 and referenced

4. **Region Not Supported**
   ```
   Error: Bedrock service not available
   ```
   - Use `--bedrock-region` to specify a different region for Bedrock
   - Check AWS documentation for Nova model availability

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL="DEBUG"
./deploy-bedrock-nova.sh
```

### Test Individual Components

```bash
# Test health endpoint
curl https://your-api-url/health

# Test models endpoint
curl https://your-api-url/v1/models

# Test chat completions
curl -X POST https://your-api-url/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"test"}]}'
```

## Cost Optimization

### Lambda Configuration

- **ARM64 Architecture**: Better price/performance ratio
- **Memory Allocation**: Start with 1024MB, adjust based on usage
- **Reserved Concurrency**: Limit concurrent executions to control costs

### Bedrock Usage

- **Model Selection**: Use Nova Lite for cost-effective tasks
- **Token Limits**: Set appropriate `max_tokens` in requests
- **Caching**: Implement client-side caching for repeated requests

### Monitoring Costs

- Use CloudWatch metrics to track token usage
- Set up billing alerts for Bedrock usage
- Monitor Lambda invocation costs

## Migration from OpenAI

### Step-by-Step Migration

1. **Deploy the Proxy**
   ```bash
   ./deploy-bedrock-nova.sh --test
   ```

2. **Update Your Code**
   ```python
   # Before
   client = OpenAI(api_key="sk-...")
   
   # After
   client = OpenAI(
       base_url="https://your-api-url",
       api_key="dummy"
   )
   ```

3. **Test Thoroughly**
   - Run your existing test suite
   - Compare response quality
   - Monitor performance metrics

4. **Gradual Rollout**
   - Start with non-critical workloads
   - Monitor error rates and latency
   - Gradually increase traffic

### Compatibility Notes

- **Streaming**: Supported with Server-Sent Events
- **Function Calling**: Not yet supported by Nova models
- **Fine-tuning**: Not supported (use prompt engineering)
- **Embeddings**: Use separate Bedrock embedding models

## Support

### Getting Help

1. **Check Logs**: CloudWatch logs for Lambda function
2. **Review Metrics**: CloudWatch dashboard for performance
3. **Test Endpoints**: Use the test script to validate functionality
4. **AWS Documentation**: Bedrock and Nova model documentation

### Contributing

This deployment is part of the larger Bedrock Access Gateway project. Contributions are welcome!

## License

This project is licensed under the MIT License. See the LICENSE file for details.