#!/bin/bash

# Test script for Bedrock Nova Proxy deployment
set -e

# Configuration
STACK_NAME="bedrock-nova-proxy"
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

# Function to get API URL from CloudFormation stack
get_api_url() {
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text \
        --region $REGION 2>/dev/null || echo ""
}

# Function to test health endpoint
test_health_endpoint() {
    local api_url=$1
    
    print_status "Testing health endpoint..."
    
    local response=$(curl -s -w "%{http_code}" "$api_url/health" 2>/dev/null || echo "000")
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" = "200" ]; then
        print_status "✓ Health endpoint returned 200 OK"
        
        if echo "$body" | grep -q "bedrock-nova-proxy"; then
            print_status "✓ Health response contains expected service identifier"
        else
            print_warning "⚠ Health response doesn't contain expected service identifier"
        fi
        
        return 0
    else
        print_error "✗ Health endpoint returned HTTP $http_code"
        return 1
    fi
}

# Function to test models endpoint
test_models_endpoint() {
    local api_url=$1
    
    print_status "Testing models endpoint..."
    
    local response=$(curl -s -w "%{http_code}" "$api_url/v1/models" 2>/dev/null || echo "000")
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" = "200" ]; then
        print_status "✓ Models endpoint returned 200 OK"
        
        if echo "$body" | grep -q '"object":"list"'; then
            print_status "✓ Models response has correct OpenAI format"
        else
            print_warning "⚠ Models response doesn't have expected OpenAI format"
        fi
        
        if echo "$body" | grep -q "nova"; then
            local model_count=$(echo "$body" | grep -o '"id"' | wc -l)
            print_status "✓ Found Nova models in response ($model_count models total)"
        else
            print_warning "⚠ No Nova models found in response"
        fi
        
        # Check for OpenAI-compatible model aliases
        if echo "$body" | grep -q "gpt-4o-mini"; then
            print_status "✓ Found OpenAI-compatible model aliases"
        else
            print_warning "⚠ No OpenAI-compatible model aliases found"
        fi
        
        return 0
    else
        print_error "✗ Models endpoint returned HTTP $http_code"
        return 1
    fi
}

# Function to test chat completions endpoint
test_chat_completions_endpoint() {
    local api_url=$1
    
    print_status "Testing chat completions endpoint..."
    
    local test_payload='{
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": "Hello! Please respond with exactly: TEST_SUCCESS"
            }
        ],
        "max_tokens": 10,
        "temperature": 0
    }'
    
    local response=$(curl -s -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$test_payload" \
        "$api_url/v1/chat/completions" 2>/dev/null || echo "000")
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" = "200" ]; then
        print_status "✓ Chat completions endpoint returned 200 OK"
        
        if echo "$body" | grep -q '"object":"chat.completion"'; then
            print_status "✓ Chat completion response has correct OpenAI format"
        else
            print_warning "⚠ Chat completion response doesn't have expected OpenAI format"
        fi
        
        if echo "$body" | grep -q '"role":"assistant"'; then
            print_status "✓ Chat completion response contains assistant message"
        else
            print_warning "⚠ Chat completion response doesn't contain assistant message"
        fi
        
        if echo "$body" | grep -q '"usage"'; then
            print_status "✓ Chat completion response includes token usage"
        else
            print_warning "⚠ Chat completion response doesn't include token usage"
        fi
        
        return 0
    else
        print_error "✗ Chat completions endpoint returned HTTP $http_code"
        if [ "$http_code" != "000" ]; then
            print_error "Response body: $body"
        fi
        return 1
    fi
}

# Function to test CORS headers
test_cors_headers() {
    local api_url=$1
    
    print_status "Testing CORS headers..."
    
    local response=$(curl -s -I -X OPTIONS \
        -H "Origin: https://example.com" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type,Authorization" \
        "$api_url/v1/chat/completions" 2>/dev/null || echo "")
    
    if echo "$response" | grep -qi "access-control-allow-origin"; then
        print_status "✓ CORS headers are present"
    else
        print_warning "⚠ CORS headers may not be configured properly"
    fi
}

# Function to run performance test
test_performance() {
    local api_url=$1
    
    print_status "Running basic performance test..."
    
    local test_payload='{
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
    }'
    
    local start_time=$(date +%s%N)
    local response=$(curl -s -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$test_payload" \
        "$api_url/v1/chat/completions" 2>/dev/null || echo "000")
    local end_time=$(date +%s%N)
    
    local http_code="${response: -3}"
    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    
    if [ "$http_code" = "200" ]; then
        print_status "✓ Performance test completed in ${duration_ms}ms"
        
        if [ $duration_ms -lt 10000 ]; then
            print_status "✓ Response time is good (< 10 seconds)"
        else
            print_warning "⚠ Response time is slow (> 10 seconds)"
        fi
    else
        print_error "✗ Performance test failed with HTTP $http_code"
    fi
}

# Function to check CloudWatch metrics
check_cloudwatch_metrics() {
    print_status "Checking CloudWatch metrics..."
    
    local function_name=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
        --output text \
        --region $REGION 2>/dev/null || echo "")
    
    if [ -n "$function_name" ]; then
        # Check if Lambda function exists and has recent invocations
        local invocations=$(aws cloudwatch get-metric-statistics \
            --namespace AWS/Lambda \
            --metric-name Invocations \
            --dimensions Name=FunctionName,Value=$function_name \
            --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
            --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
            --period 300 \
            --statistics Sum \
            --region $REGION \
            --query 'Datapoints[0].Sum' \
            --output text 2>/dev/null || echo "0")
        
        if [ "$invocations" != "None" ] && [ "$invocations" != "0" ]; then
            print_status "✓ Lambda function has recent invocations ($invocations)"
        else
            print_info "ℹ No recent Lambda invocations found (this is normal for a new deployment)"
        fi
    fi
}

# Main test function
main() {
    print_status "🧪 Starting Bedrock Nova Proxy deployment tests..."
    echo ""
    
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
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "🧪 Test Bedrock Nova Proxy deployment"
                echo ""
                echo "Options:"
                echo "  --region REGION           AWS region (default: us-east-1)"
                echo "  --stack-name NAME         CloudFormation stack name (default: bedrock-nova-proxy)"
                echo "  --help                    Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Get API URL
    API_URL=$(get_api_url)
    
    if [ -z "$API_URL" ]; then
        print_error "Could not find API Gateway URL from CloudFormation stack: $STACK_NAME"
        print_error "Make sure the stack is deployed and the region is correct"
        exit 1
    fi
    
    print_info "Testing API at: $API_URL"
    echo ""
    
    # Run tests
    local test_results=()
    
    # Test health endpoint
    if test_health_endpoint "$API_URL"; then
        test_results+=("health:PASS")
    else
        test_results+=("health:FAIL")
    fi
    
    echo ""
    
    # Test models endpoint
    if test_models_endpoint "$API_URL"; then
        test_results+=("models:PASS")
    else
        test_results+=("models:FAIL")
    fi
    
    echo ""
    
    # Test chat completions endpoint
    if test_chat_completions_endpoint "$API_URL"; then
        test_results+=("chat:PASS")
    else
        test_results+=("chat:FAIL")
    fi
    
    echo ""
    
    # Test CORS headers
    test_cors_headers "$API_URL"
    
    echo ""
    
    # Run performance test
    test_performance "$API_URL"
    
    echo ""
    
    # Check CloudWatch metrics
    check_cloudwatch_metrics
    
    echo ""
    
    # Summary
    print_status "📊 Test Results Summary:"
    local passed=0
    local total=0
    
    for result in "${test_results[@]}"; do
        local test_name="${result%:*}"
        local test_status="${result#*:}"
        total=$((total + 1))
        
        if [ "$test_status" = "PASS" ]; then
            echo -e "  ✓ ${test_name}: ${GREEN}PASSED${NC}"
            passed=$((passed + 1))
        else
            echo -e "  ✗ ${test_name}: ${RED}FAILED${NC}"
        fi
    done
    
    echo ""
    
    if [ $passed -eq $total ]; then
        print_status "🎉 All tests passed! ($passed/$total)"
        print_info "Your Bedrock Nova Proxy is working correctly!"
        echo ""
        print_info "You can now use this API as a drop-in replacement for OpenAI:"
        echo "  export OPENAI_BASE_URL=\"$API_URL\""
        exit 0
    else
        print_warning "⚠ Some tests failed ($passed/$total passed)"
        print_warning "Check the error messages above for troubleshooting"
        exit 1
    fi
}

# Run main function
main "$@"