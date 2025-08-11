#!/bin/bash

# Deployment script for API Gateway Lambda Proxy
set -e

# Configuration
STACK_NAME="openai-lambda-proxy"
TEMPLATE_FILE="deployment/ApiGatewayLambdaProxy.template"
LAMBDA_CODE_DIR="lambda_proxy"
DEPLOYMENT_BUCKET=""
REGION="us-east-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
    
    print_status "Prerequisites check passed"
}

# Function to create deployment bucket if needed
create_deployment_bucket() {
    if [ -z "$DEPLOYMENT_BUCKET" ]; then
        DEPLOYMENT_BUCKET="openai-lambda-proxy-deployment-$(date +%s)-$(openssl rand -hex 4)"
        print_status "Creating deployment bucket: $DEPLOYMENT_BUCKET"
        
        if [ "$REGION" = "us-east-1" ]; then
            aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION
        else
            aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION --create-bucket-configuration LocationConstraint=$REGION
        fi
    else
        print_status "Using existing deployment bucket: $DEPLOYMENT_BUCKET"
    fi
}

# Function to package Lambda code
package_lambda_code() {
    print_status "Packaging Lambda code..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_FILE="$TEMP_DIR/lambda-deployment-package.zip"
    
    # Copy Lambda code
    cp -r $LAMBDA_CODE_DIR/* $TEMP_DIR/
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    pip install -r $TEMP_DIR/requirements.txt -t $TEMP_DIR/ --quiet
    
    # Create deployment package
    cd $TEMP_DIR
    zip -r $PACKAGE_FILE . -x "tests/*" "*.pyc" "__pycache__/*" "*.git*" > /dev/null
    cd - > /dev/null
    
    # Upload to S3
    LAMBDA_CODE_S3_KEY="lambda-code/$(date +%Y%m%d-%H%M%S)/lambda-deployment-package.zip"
    print_status "Uploading Lambda package to S3..."
    aws s3 cp $PACKAGE_FILE s3://$DEPLOYMENT_BUCKET/$LAMBDA_CODE_S3_KEY
    
    # Clean up
    rm -rf $TEMP_DIR
    
    echo $LAMBDA_CODE_S3_KEY
}

# Function to deploy CloudFormation stack
deploy_stack() {
    local lambda_code_s3_key=$1
    
    print_status "Deploying CloudFormation stack: $STACK_NAME"
    
    # Check if OpenAI API key secret exists
    if [ -z "$OPENAI_API_KEY_SECRET_ARN" ]; then
        print_error "OPENAI_API_KEY_SECRET_ARN environment variable is required"
        print_error "Please set it to the ARN of your Secrets Manager secret containing the OpenAI API key"
        exit 1
    fi
    
    # Deploy stack
    aws cloudformation deploy \
        --template-file $TEMPLATE_FILE \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            OpenAIApiKeySecretArn=$OPENAI_API_KEY_SECRET_ARN \
            LambdaFunctionName=${LAMBDA_FUNCTION_NAME:-openai-lambda-proxy} \
            ApiGatewayName=${API_GATEWAY_NAME:-openai-proxy-api} \
            Stage=${STAGE:-prod} \
            LogLevel=${LOG_LEVEL:-INFO} \
            EnableAuthentication=${ENABLE_AUTHENTICATION:-false} \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
    
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
        
        print_status "Lambda function code updated successfully"
    else
        print_warning "Could not find Lambda function name from stack outputs"
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
    print_status "Deployment completed successfully!"
    echo ""
    echo "Stack Outputs:"
    echo "$OUTPUTS"
    echo ""
    
    # Get API Gateway URL
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text \
        --region $REGION)
    
    if [ -n "$API_URL" ]; then
        echo "API Endpoints:"
        echo "  Chat Completions: $API_URL/v1/chat/completions"
        echo "  Models List:      $API_URL/v1/models"
        echo "  Health Check:     $API_URL/health"
        echo ""
        
        print_status "Testing health endpoint..."
        if curl -s "$API_URL/health" > /dev/null; then
            print_status "Health check passed ✓"
        else
            print_warning "Health check failed - API might still be initializing"
        fi
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
    print_status "Starting deployment of OpenAI Lambda Proxy..."
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                REGION="$2"
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
            --cleanup-bucket)
                CLEANUP_BUCKET="true"
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --region REGION           AWS region (default: us-east-1)"
                echo "  --stack-name NAME         CloudFormation stack name (default: openai-lambda-proxy)"
                echo "  --bucket BUCKET           S3 bucket for deployment artifacts"
                echo "  --cleanup-bucket          Clean up deployment bucket after deployment"
                echo "  --help                    Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  OPENAI_API_KEY_SECRET_ARN    Required: ARN of Secrets Manager secret"
                echo "  LAMBDA_FUNCTION_NAME         Optional: Lambda function name"
                echo "  API_GATEWAY_NAME             Optional: API Gateway name"
                echo "  STAGE                        Optional: Deployment stage (default: prod)"
                echo "  LOG_LEVEL                    Optional: Log level (default: INFO)"
                echo "  ENABLE_AUTHENTICATION        Optional: Enable auth (default: false)"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run deployment steps
    check_prerequisites
    create_deployment_bucket
    
    # Package and upload Lambda code
    LAMBDA_CODE_S3_KEY=$(package_lambda_code)
    
    # Deploy CloudFormation stack
    deploy_stack $LAMBDA_CODE_S3_KEY
    
    # Update Lambda function code
    update_lambda_code $LAMBDA_CODE_S3_KEY
    
    # Show deployment information
    show_deployment_info
    
    # Cleanup if requested
    cleanup_deployment_bucket
    
    print_status "Deployment completed successfully!"
}

# Run main function
main "$@"