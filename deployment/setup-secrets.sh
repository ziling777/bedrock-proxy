#!/bin/bash

# Script to set up AWS Secrets Manager secret for OpenAI API key
set -e

# Configuration
SECRET_NAME="openai-api-key"
REGION="us-east-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to create or update secret
setup_secret() {
    local openai_api_key=$1
    
    print_status "Setting up Secrets Manager secret..."
    
    # Create secret JSON
    SECRET_VALUE=$(cat <<EOF
{
  "openai_api_key": "$openai_api_key",
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
EOF
)
    
    # Check if secret already exists
    if aws secretsmanager describe-secret --secret-id $SECRET_NAME --region $REGION &> /dev/null; then
        print_status "Secret already exists. Updating..."
        aws secretsmanager update-secret \
            --secret-id $SECRET_NAME \
            --secret-string "$SECRET_VALUE" \
            --region $REGION > /dev/null
    else
        print_status "Creating new secret..."
        aws secretsmanager create-secret \
            --name $SECRET_NAME \
            --description "OpenAI API key and configuration for Lambda proxy" \
            --secret-string "$SECRET_VALUE" \
            --region $REGION > /dev/null
    fi
    
    # Get secret ARN
    SECRET_ARN=$(aws secretsmanager describe-secret \
        --secret-id $SECRET_NAME \
        --query 'ARN' \
        --output text \
        --region $REGION)
    
    print_status "Secret setup completed successfully!"
    echo "Secret ARN: $SECRET_ARN"
    echo ""
    echo "Export this ARN as an environment variable:"
    echo "export OPENAI_API_KEY_SECRET_ARN=\"$SECRET_ARN\""
}

# Main function
main() {
    echo "OpenAI API Key Secret Setup"
    echo "=========================="
    echo ""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                REGION="$2"
                shift 2
                ;;
            --secret-name)
                SECRET_NAME="$2"
                shift 2
                ;;
            --api-key)
                OPENAI_API_KEY="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --region REGION           AWS region (default: us-east-1)"
                echo "  --secret-name NAME        Secret name (default: openai-api-key)"
                echo "  --api-key KEY             OpenAI API key (will prompt if not provided)"
                echo "  --help                    Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure'."
        exit 1
    fi
    
    # Get OpenAI API key if not provided
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -n "Enter your OpenAI API key: "
        read -s OPENAI_API_KEY
        echo ""
        
        if [ -z "$OPENAI_API_KEY" ]; then
            print_error "OpenAI API key is required"
            exit 1
        fi
    fi
    
    # Validate API key format
    if [[ ! $OPENAI_API_KEY =~ ^sk-[a-zA-Z0-9]{48}$ ]]; then
        print_warning "API key format doesn't match expected OpenAI format (sk-...)"
        echo -n "Continue anyway? (y/N): "
        read -r response
        if [[ ! $response =~ ^[Yy]$ ]]; then
            print_status "Aborted"
            exit 0
        fi
    fi
    
    # Setup secret
    setup_secret "$OPENAI_API_KEY"
}

main "$@"