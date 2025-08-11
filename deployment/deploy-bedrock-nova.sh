#!/bin/bash

# Deployment script for Bedrock Nova Proxy
set -e

# Configuration
STACK_NAME="bedrock-nova-proxy"
TEMPLATE_FILE="deployment/BedrockNovaProxy.template"
LAMBDA_CODE_DIR="lambda_proxy"
DEPLOYMENT_BUCKET=""
REGION="us-east-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure'."
        exit 1
    fi
    
    # Check if template file exists
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    # Check if Lambda code directory exists
    if [ ! -d "$LAMBDA_CODE_DIR" ]; then
        print_error "Lambda code directory not found: $LAMBDA_CODE_DIR"
        exit 1
    fi
    
    # Check Bedrock service availability in region
    print_status "Checking Bedrock service availability in region $REGION..."
    if aws bedrock list-foundation-models --region $REGION &> /dev/null; then
        print_status "Bedrock service is available in region $REGION"
    else
        print_warning "Bedrock service may not be available in region $REGION"
        print_warning "Consider using us-east-1 or us-west-2 for better Nova model availability"
    fi
    
    print_status "Prerequisites check passed"
}

# Function to create deployment bucket if needed
create_deployment_bucket() {
    if [ -z "$DEPLOYMENT_BUCKET" ]; then
        DEPLOYMENT_BUCKET="bedrock-nova-proxy-deployment-$(date +%s)-$(openssl rand -hex 4)"
        print_status "Creating deployment bucket: $DEPLOYMENT_BUCKET"
        
        if [ "$REGION" = "us-east-1" ]; then
            aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION
        else
            aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION --create-bucket-configuration LocationConstraint=$REGION
        fi
        
        # Enable versioning for better deployment tracking
        aws s3api put-bucket-versioning \
            --bucket $DEPLOYMENT_BUCKET \
            --versioning-configuration Status=Enabled
    else
        print_status "Using existing deployment bucket: $DEPLOYMENT_BUCKET"
    fi
}

# Function to package Lambda code
package_lambda_code() {
    print_status "Packaging Lambda code for Bedrock Nova Proxy..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_FILE="$TEMP_DIR/bedrock-nova-proxy-package.zip"
    
    # Copy Lambda code
    cp -r $LAMBDA_CODE_DIR/* $TEMP_DIR/
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    if [ -f "$TEMP_DIR/requirements.txt" ]; then
        pip install -r $TEMP_DIR/requirements.txt -t $TEMP_DIR/ --quiet --no-deps
        
        # Install boto3 and botocore with specific versions for Bedrock support
        pip install boto3>=1.34.0 botocore>=1.34.0 -t $TEMP_DIR/ --quiet --upgrade
    else
        print_warning "No requirements.txt found, installing basic dependencies..."
        pip install boto3>=1.34.0 botocore>=1.34.0 -t $TEMP_DIR/ --quiet
    fi
    
    # Create deployment package
    cd $TEMP_DIR
    
    # Exclude unnecessary files to reduce package size
    zip -r $PACKAGE_FILE . \
        -x "tests/*" \
        -x "test_*" \
        -x "*.pyc" \
        -x "__pycache__/*" \
        -x "*.git*" \
        -x "venv/*" \
        -x ".pytest_cache/*" \
        -x "*.md" \
        -x "examples/*" > /dev/null
    
    cd - > /dev/null
    
    # Check package size
    PACKAGE_SIZE=$(stat -f%z "$PACKAGE_FILE" 2>/dev/null || stat -c%s "$PACKAGE_FILE" 2>/dev/null)
    PACKAGE_SIZE_MB=$((PACKAGE_SIZE / 1024 / 1024))
    
    if [ $PACKAGE_SIZE_MB -gt 50 ]; then
        print_warning "Lambda package size is ${PACKAGE_SIZE_MB}MB (limit is 50MB for direct upload)"
        print_info "Package will be uploaded to S3 for deployment"
    else
        print_status "Lambda package size: ${PACKAGE_SIZE_MB}MB"
    fi
    
    # Upload to S3
    LAMBDA_CODE_S3_KEY="lambda-code/bedrock-nova-proxy/$(date +%Y%m%d-%H%M%S)/deployment-package.zip"
    print_status "Uploading Lambda package to S3..."
    aws s3 cp $PACKAGE_FILE s3://$DEPLOYMENT_BUCKET/$LAMBDA_CODE_S3_KEY
    
    # Clean up
    rm -rf $TEMP_DIR
    
    echo $LAMBDA_CODE_S3_KEY
}

# Function to validate Bedrock permissions
validate_bedrock_permissions() {
    print_status "Validating Bedrock permissions..."
    
    # Try to list foundation models
    if aws bedrock list-foundation-models --region $REGION > /dev/null 2>&1; then
        print_status "Bedrock permissions validated successfully"
        
        # Check for Nova models specifically
        NOVA_MODELS=$(aws bedrock list-foundation-models \
            --region $REGION \
            --query 'modelSummaries[?contains(modelId, `nova`)].modelId' \
            --output text)
        
        if [ -n "$NOVA_MODELS" ]; then
            print_status "Available Nova models found:"
            echo "$NOVA_MODELS" | tr '\t' '\n' | sed 's/^/  - /'
        else
            print_warning "No Nova models found in region $REGION"
            print_warning "Nova models may not be available in this region yet"
        fi
    else
        print_warning "Could not validate Bedrock permissions"
        print_warning "Make sure your AWS credentials have bedrock:ListFoundationModels permission"
    fi
}

# Function to deploy CloudFormation stack
deploy_stack() {
    local lambda_code_s3_key=$1
    
    print_status "Deploying CloudFormation stack: $STACK_NAME"
    
    # Prepare parameters
    PARAMETERS=(
        "LambdaFunctionName=${LAMBDA_FUNCTION_NAME:-bedrock-nova-proxy}"
        "ApiGatewayName=${API_GATEWAY_NAME:-bedrock-nova-proxy-api}"
        "Stage=${STAGE:-prod}"
        "LogLevel=${LOG_LEVEL:-INFO}"
        "EnableAuthentication=${ENABLE_AUTHENTICATION:-false}"
        "BedrockRegion=${BEDROCK_REGION:-$REGION}"
        "LambdaMemorySize=${LAMBDA_MEMORY_SIZE:-1024}"
        "LambdaTimeout=${LAMBDA_TIMEOUT:-300}"
        "ReservedConcurrency=${RESERVED_CONCURRENCY:-100}"
        "CloudWatchNamespace=${CLOUDWATCH_NAMESPACE:-BedrockProxy}"
    )
    
    # Add OpenAI secret ARN if provided (for backward compatibility)
    if [ -n "$OPENAI_API_KEY_SECRET_ARN" ]; then
        PARAMETERS+=("OpenAIApiKeySecretArn=$OPENAI_API_KEY_SECRET_ARN")
        print_info "Including OpenAI API key secret for backward compatibility"
    fi
    
    # Convert parameters array to parameter-overrides format
    PARAM_OVERRIDES=""
    for param in "${PARAMETERS[@]}"; do
        PARAM_OVERRIDES="$PARAM_OVERRIDES $param"
    done
    
    # Deploy stack
    aws cloudformation deploy \
        --template-file $TEMPLATE_FILE \
        --stack-name $STACK_NAME \
        --parameter-overrides $PARAM_OVERRIDES \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION \
        --no-fail-on-empty-changeset
    
    if [ $? -eq 0 ]; then
        print_status "Stack deployment completed successfully"
    else
        print_error "Stack deployment failed"
        exit 1
    fi
}

# Function to update Lambda function code
update_lambda_code() {
    local lambda_code_s3_key=$1
    
    print_status "Updating Lambda function code..."
    
    FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
        --output text \
        --region $REGION)
    
    if [ -n "$FUNCTION_NAME" ]; then
        aws lambda update-function-code \
            --function-name $FUNCTION_NAME \
            --s3-bucket $DEPLOYMENT_BUCKET \
            --s3-key $lambda_code_s3_key \
            --region $REGION > /dev/null
        
        # Wait for update to complete
        print_status "Waiting for Lambda function update to complete..."
        aws lambda wait function-updated \
            --function-name $FUNCTION_NAME \
            --region $REGION
        
        print_status "Lambda function code updated successfully"
    else
        print_warning "Could not find Lambda function name from stack outputs"
    fi
}

# Function to test the deployment
test_deployment() {
    print_status "Testing deployment..."
    
    # Get API Gateway URL
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text \
        --region $REGION)
    
    if [ -n "$API_URL" ]; then
        # Test health endpoint
        print_status "Testing health endpoint..."
        HEALTH_RESPONSE=$(curl -s "$API_URL/health" || echo "")
        
        if echo "$HEALTH_RESPONSE" | grep -q "bedrock-nova-proxy"; then
            print_status "Health check passed ✓"
        else
            print_warning "Health check failed - API might still be initializing"
        fi
        
        # Test models endpoint
        print_status "Testing models endpoint..."
        MODELS_RESPONSE=$(curl -s "$API_URL/v1/models" || echo "")
        
        if echo "$MODELS_RESPONSE" | grep -q "nova"; then
            print_status "Models endpoint working ✓"
            MODEL_COUNT=$(echo "$MODELS_RESPONSE" | grep -o '"id"' | wc -l)
            print_info "Found $MODEL_COUNT models available"
        else
            print_warning "Models endpoint may not be working properly"
        fi
    fi
}

# Function to display deployment information
show_deployment_info() {
    print_status "Retrieving deployment information..."
    
    # Get stack outputs
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs' \
        --output table \
        --region $REGION)
    
    echo ""
    print_status "🎉 Bedrock Nova Proxy deployment completed successfully!"
    echo ""
    echo "Stack Outputs:"
    echo "$OUTPUTS"
    echo ""
    
    # Get specific endpoints
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text \
        --region $REGION)
    
    DASHBOARD_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchDashboardUrl`].OutputValue' \
        --output text \
        --region $REGION)
    
    if [ -n "$API_URL" ]; then
        echo "🔗 API Endpoints:"
        echo "  Chat Completions: $API_URL/v1/chat/completions"
        echo "  Models List:      $API_URL/v1/models"
        echo "  Health Check:     $API_URL/health"
        echo ""
        
        echo "📊 Monitoring:"
        if [ -n "$DASHBOARD_URL" ]; then
            echo "  CloudWatch Dashboard: $DASHBOARD_URL"
        fi
        echo ""
        
        echo "🚀 Usage Example:"
        echo "  # Set your OpenAI client base URL to:"
        echo "  export OPENAI_BASE_URL=\"$API_URL\""
        echo ""
        echo "  # Your existing OpenAI code will now use Bedrock Nova models!"
        echo "  # Model 'gpt-4o-mini' → 'amazon.nova-lite-v1:0'"
        echo "  # Model 'gpt-4o' → 'amazon.nova-pro-v1:0'"
        echo ""
    fi
}

# Function to clean up deployment bucket
cleanup_deployment_bucket() {
    if [ -n "$DEPLOYMENT_BUCKET" ] && [ "$CLEANUP_BUCKET" = "true" ]; then
        print_status "Cleaning up deployment bucket..."
        aws s3 rm s3://$DEPLOYMENT_BUCKET --recursive
        aws s3 rb s3://$DEPLOYMENT_BUCKET
    fi
}

# Main deployment function
main() {
    print_status "🚀 Starting deployment of Bedrock Nova Proxy..."
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                REGION="$2"
                shift 2
                ;;
            --bedrock-region)
                BEDROCK_REGION="$2"
                shift 2
                ;;
            --stack-name)
                STACK_NAME="$2"
                shift 2
                ;;
            --bucket)
                DEPLOYMENT_BUCKET="$2"
                shift 2
                ;;
            --memory)
                LAMBDA_MEMORY_SIZE="$2"
                shift 2
                ;;
            --timeout)
                LAMBDA_TIMEOUT="$2"
                shift 2
                ;;
            --cleanup-bucket)
                CLEANUP_BUCKET="true"
                shift
                ;;
            --test)
                RUN_TESTS="true"
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "🎯 Deploy Bedrock Nova Proxy - OpenAI-compatible API for AWS Bedrock Nova models"
                echo ""
                echo "Options:"
                echo "  --region REGION           AWS region for deployment (default: us-east-1)"
                echo "  --bedrock-region REGION   AWS region for Bedrock service (default: same as --region)"
                echo "  --stack-name NAME         CloudFormation stack name (default: bedrock-nova-proxy)"
                echo "  --bucket BUCKET           S3 bucket for deployment artifacts"
                echo "  --memory SIZE             Lambda memory size in MB (default: 1024)"
                echo "  --timeout SECONDS         Lambda timeout in seconds (default: 300)"
                echo "  --cleanup-bucket          Clean up deployment bucket after deployment"
                echo "  --test                    Run deployment tests after deployment"
                echo "  --help                    Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  LAMBDA_FUNCTION_NAME         Optional: Lambda function name"
                echo "  API_GATEWAY_NAME             Optional: API Gateway name"
                echo "  STAGE                        Optional: Deployment stage (default: prod)"
                echo "  LOG_LEVEL                    Optional: Log level (default: INFO)"
                echo "  ENABLE_AUTHENTICATION        Optional: Enable auth (default: false)"
                echo "  RESERVED_CONCURRENCY         Optional: Reserved concurrency (default: 100)"
                echo "  CLOUDWATCH_NAMESPACE         Optional: CloudWatch namespace (default: BedrockProxy)"
                echo "  OPENAI_API_KEY_SECRET_ARN    Optional: For backward compatibility"
                echo ""
                echo "Examples:"
                echo "  $0                                    # Deploy with defaults"
                echo "  $0 --region us-west-2 --memory 2048  # Deploy in us-west-2 with 2GB memory"
                echo "  $0 --test                             # Deploy and run tests"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Set Bedrock region if not specified
    if [ -z "$BEDROCK_REGION" ]; then
        BEDROCK_REGION=$REGION
    fi
    
    # Run deployment steps
    check_prerequisites
    validate_bedrock_permissions
    create_deployment_bucket
    
    # Package and upload Lambda code
    LAMBDA_CODE_S3_KEY=$(package_lambda_code)
    
    # Deploy CloudFormation stack
    deploy_stack $LAMBDA_CODE_S3_KEY
    
    # Update Lambda function code
    update_lambda_code $LAMBDA_CODE_S3_KEY
    
    # Run tests if requested
    if [ "$RUN_TESTS" = "true" ]; then
        test_deployment
    fi
    
    # Show deployment information
    show_deployment_info
    
    # Cleanup if requested
    cleanup_deployment_bucket
    
    print_status "✅ Bedrock Nova Proxy deployment completed successfully!"
    print_info "Your OpenAI-compatible API is now ready to use AWS Bedrock Nova models!"
}

# Run main function
main "$@"