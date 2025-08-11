# Cloud Deployment Design Document

## Overview

The cloud deployment system provides a comprehensive solution for deploying the API Gateway Lambda Proxy service to AWS. The design leverages Infrastructure as Code (IaC) principles using AWS CloudFormation, automated deployment scripts, and best practices for security, monitoring, and cost optimization.

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Developer     │    │   Deployment     │    │   AWS Cloud     │
│   Workstation   │───▶│   Scripts        │───▶│   Resources     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────┐         ┌─────────────────┐
                       │ Prerequisites│         │ CloudFormation  │
                       │ Validation   │         │ Stack           │
                       └──────────────┘         └─────────────────┘
```

### AWS Resources Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Account                               │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Secrets Manager │  │   API Gateway   │  │ Lambda Function │ │
│  │                 │  │                 │  │                 │ │
│  │ - OpenAI API Key│  │ - REST API      │  │ - Python 3.11   │ │
│  │ - Model Mappings│  │ - CORS Enabled  │  │ - ARM64 Arch    │ │
│  │ - Timeout Config│  │ - Rate Limiting │  │ - 512MB Memory  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                     │                     │        │
│           └─────────────────────┼─────────────────────┘        │
│                                 │                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  CloudWatch     │  │      IAM        │  │       S3        │ │
│  │                 │  │                 │  │                 │ │
│  │ - Log Groups    │  │ - Execution Role│  │ - Deployment    │ │
│  │ - Alarms        │  │ - Policies      │  │   Artifacts     │ │
│  │ - Metrics       │  │ - Permissions   │  │ - Lambda Code   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Deployment Scripts

#### setup-secrets.sh
- **Purpose**: Creates and manages AWS Secrets Manager secrets
- **Inputs**: OpenAI API key, AWS region, secret name
- **Outputs**: Secret ARN for use in deployment
- **Key Features**:
  - Interactive API key input with masking
  - API key format validation
  - Secret creation or update (idempotent)
  - JSON structure with model mappings and timeout settings

#### deploy.sh
- **Purpose**: Main deployment orchestrator
- **Inputs**: Environment variables, command-line options
- **Outputs**: Deployed infrastructure and API endpoints
- **Key Features**:
  - Prerequisites validation (AWS CLI, credentials, files)
  - Lambda code packaging with dependencies
  - S3 upload for deployment artifacts
  - CloudFormation stack deployment
  - Lambda function code updates
  - Deployment information display

#### test-deployment.sh
- **Purpose**: Automated testing of deployed services
- **Inputs**: API Gateway URL, test configuration
- **Outputs**: Test results and performance metrics
- **Key Features**:
  - Health endpoint testing
  - Models list endpoint testing
  - Chat completions endpoint testing
  - CORS headers validation
  - Error handling verification
  - Basic performance testing

### 2. CloudFormation Template

#### Infrastructure Components
- **Lambda Function**: Python 3.11 runtime, ARM64 architecture
- **API Gateway**: REST API with CORS, rate limiting
- **IAM Roles**: Minimal permissions for Lambda execution
- **CloudWatch**: Log groups, alarms, metrics
- **S3 Integration**: For deployment artifacts

#### Security Design
- **Secrets Manager**: Secure storage of sensitive data
- **IAM Policies**: Least privilege access
- **VPC**: Optional VPC deployment support
- **Encryption**: At-rest and in-transit encryption

### 3. Monitoring and Observability

#### CloudWatch Alarms
- Lambda function errors (threshold: 5 errors in 5 minutes)
- Lambda function duration (threshold: 30 seconds average)
- API Gateway 4xx errors (threshold: 10 errors in 5 minutes)
- API Gateway 5xx errors (threshold: 5 errors in 5 minutes)

#### Logging Strategy
- Structured logging with JSON format
- Request/response correlation IDs
- Performance metrics (duration, token usage)
- Error details with stack traces
- Log retention: 14 days (configurable)

## Data Models

### Secret Structure
```json
{
  "openai_api_key": "sk-...",
  "model_mappings": {
    "amazon.nova-lite-v1:0": "gpt-4o-mini",
    "amazon.nova-pro-v1:0": "gpt-4o-mini",
    "amazon.nova-micro-v1:0": "gpt-4o-mini"
  },
  "timeout_settings": {
    "openai_api_timeout": 30,
    "secrets_manager_timeout": 10,
    "lambda_timeout": 300
  }
}
```

### Environment Configuration
```bash
# Required
OPENAI_API_KEY_SECRET_ARN="arn:aws:secretsmanager:..."

# Optional
LAMBDA_FUNCTION_NAME="openai-lambda-proxy"
API_GATEWAY_NAME="openai-proxy-api"
STAGE="prod"
LOG_LEVEL="INFO"
ENABLE_AUTHENTICATION="false"
```

### CloudFormation Parameters
- OpenAIApiKeySecretArn: ARN of the Secrets Manager secret
- LambdaFunctionName: Name for the Lambda function
- ApiGatewayName: Name for the API Gateway
- Stage: Deployment stage (dev/test/prod)
- LogLevel: Logging level (DEBUG/INFO/WARNING/ERROR)
- EnableAuthentication: Enable/disable authentication

## Error Handling

### Deployment Error Scenarios
1. **Missing Prerequisites**: Clear error messages with remediation steps
2. **AWS Credential Issues**: Validation and helpful error messages
3. **CloudFormation Failures**: Stack rollback with detailed error reporting
4. **Lambda Code Upload Failures**: Retry logic and error recovery
5. **Secret Access Issues**: Permission validation and troubleshooting guides

### Runtime Error Handling
1. **Secret Retrieval Failures**: Graceful degradation and error responses
2. **OpenAI API Failures**: Retry logic and circuit breaker patterns
3. **Lambda Timeout**: Appropriate timeout settings and monitoring
4. **Memory Limits**: Monitoring and alerting for memory usage

### Error Recovery Strategies
- Idempotent deployment scripts
- CloudFormation rollback capabilities
- Manual cleanup procedures
- Backup and restore procedures for secrets

## Testing Strategy

### Deployment Testing
1. **Prerequisites Validation**: Test all prerequisite checks
2. **CloudFormation Template**: Validate template syntax and resources
3. **Deployment Scripts**: Test with various parameter combinations
4. **Rollback Testing**: Verify rollback procedures work correctly

### Integration Testing
1. **End-to-End API Testing**: Test all API endpoints
2. **Authentication Testing**: Verify auth mechanisms work
3. **Error Scenario Testing**: Test error handling paths
4. **Performance Testing**: Load testing and performance validation

### Monitoring Testing
1. **Alarm Testing**: Verify alarms trigger correctly
2. **Log Testing**: Validate log format and content
3. **Metrics Testing**: Verify metrics are collected properly
4. **Dashboard Testing**: Test monitoring dashboards

## Security Considerations

### Data Protection
- OpenAI API keys stored in AWS Secrets Manager
- Encryption at rest and in transit
- No sensitive data in CloudFormation templates or logs
- Secure parameter passing between components

### Access Control
- IAM roles with minimal required permissions
- Resource-based policies for fine-grained access
- Cross-account access controls if needed
- API Gateway authentication and authorization

### Network Security
- HTTPS-only communication
- CORS configuration for web clients
- Optional VPC deployment for network isolation
- Security group configurations

## Performance Optimization

### Lambda Optimization
- ARM64 architecture for better price/performance
- Appropriate memory allocation (512MB default)
- Connection pooling for external APIs
- Efficient code packaging and dependencies

### API Gateway Optimization
- Caching configuration for frequently accessed endpoints
- Request/response compression
- Throttling and rate limiting
- Regional deployment for low latency

### Cost Optimization
- Reserved concurrency limits to prevent runaway costs
- CloudWatch log retention policies
- S3 lifecycle policies for deployment artifacts
- Right-sizing of resources based on usage patterns

## Deployment Workflow

### Phase 1: Prerequisites
1. Validate AWS CLI installation and configuration
2. Check required permissions and access
3. Verify CloudFormation template syntax
4. Validate Lambda code and dependencies

### Phase 2: Secret Setup
1. Create or update Secrets Manager secret
2. Validate secret structure and content
3. Test secret access permissions
4. Export secret ARN for deployment

### Phase 3: Infrastructure Deployment
1. Package Lambda code with dependencies
2. Upload deployment artifacts to S3
3. Deploy CloudFormation stack
4. Update Lambda function code
5. Configure monitoring and alarms

### Phase 4: Validation and Testing
1. Run automated endpoint tests
2. Validate monitoring and logging
3. Perform basic performance tests
4. Generate deployment report

### Phase 5: Documentation and Handoff
1. Generate API documentation
2. Provide monitoring dashboard links
3. Document troubleshooting procedures
4. Create operational runbooks