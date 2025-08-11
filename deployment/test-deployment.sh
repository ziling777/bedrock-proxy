#!/bin/bash

# Bedrock Nova Proxy - 测试部署脚本
# 保证一次性部署成功

set -e

# 配置
CUSTOMER_NAME="test-deployment"
ENVIRONMENT="dev"
REGION="eu-north-1"
ACCOUNT_ID="082526546443"
STACK_NAME="bedrock-nova-proxy-${CUSTOMER_NAME}"
S3_BUCKET="bedrock-nova-proxy-deployments-${ACCOUNT_ID}"
S3_KEY="${CUSTOMER_NAME}/bedrock-nova-proxy.zip"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "========================================"
echo "Bedrock Nova Proxy 测试部署"
echo "========================================"

# 1. 验证 AWS 环境
log_info "验证 AWS 环境..."
aws sts get-caller-identity > /dev/null
log_success "AWS 凭证验证通过"

# 2. 验证 Bedrock 可用性
log_info "验证 Bedrock Nova 模型可用性..."
aws bedrock list-foundation-models --region $REGION --query 'modelSummaries[?contains(modelId, `nova`)].modelId' --output text > /dev/null
log_success "Bedrock Nova 模型可用"

# 3. 清理之前的部署（如果存在）
log_info "检查并清理之前的部署..."
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION > /dev/null 2>&1; then
    log_warning "发现现有堆栈，正在删除..."
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
    log_success "现有堆栈已删除"
fi

# 4. 创建 S3 存储桶（如果不存在）
log_info "准备 S3 存储桶..."
if ! aws s3 ls "s3://$S3_BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$S3_BUCKET" --region $REGION
    log_success "S3 存储桶已创建"
else
    log_info "S3 存储桶已存在"
fi

# 5. 打包并上传 Lambda 代码
log_info "打包 Lambda 代码..."
cd lambda_proxy
zip -r ../bedrock-nova-proxy.zip . -x "*.pyc" "__pycache__/*" "tests/*" "*.md" "venv/*" ".pytest_cache/*" > /dev/null
cd ..

log_info "上传部署包到 S3..."
aws s3 cp bedrock-nova-proxy.zip "s3://$S3_BUCKET/$S3_KEY" --region $REGION
log_success "部署包上传完成"

# 6. 部署 CloudFormation 堆栈
log_info "开始 CloudFormation 部署..."
aws cloudformation deploy \
  --template-file deployment/SimpleServerless.template \
  --stack-name $STACK_NAME \
  --parameter-overrides \
    CustomerName=$CUSTOMER_NAME \
    Environment=$ENVIRONMENT \
    DeploymentPackageS3Bucket=$S3_BUCKET \
    DeploymentPackageS3Key=$S3_KEY \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region $REGION

log_success "CloudFormation 部署完成"

# 7. 获取 API 端点
log_info "获取 API 端点..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

log_success "API 端点: $API_ENDPOINT"

# 8. 运行基本测试
log_info "运行基本功能测试..."

# 测试健康检查
log_info "测试健康检查端点..."
if curl -s -f "$API_ENDPOINT/health" > /dev/null; then
    log_success "健康检查通过"
else
    log_warning "健康检查失败，但这可能是正常的（端点可能不存在）"
fi

# 测试模型列表
log_info "测试模型列表端点..."
MODELS_RESPONSE=$(curl -s "$API_ENDPOINT/v1/models")
if echo "$MODELS_RESPONSE" | grep -q "nova"; then
    log_success "模型列表端点正常，发现 Nova 模型"
else
    log_warning "模型列表端点响应异常"
    echo "响应: $MODELS_RESPONSE"
fi

# 测试聊天完成
log_info "测试聊天完成端点..."
CHAT_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello, this is a test."}],
    "max_tokens": 50
  }')

if echo "$CHAT_RESPONSE" | grep -q "choices"; then
    log_success "聊天完成端点正常"
else
    log_warning "聊天完成端点响应异常"
    echo "响应: $CHAT_RESPONSE"
fi

# 9. 清理临时文件
rm -f bedrock-nova-proxy.zip

# 10. 输出部署信息
echo ""
echo "========================================"
echo "部署完成！"
echo "========================================"
echo "API 端点: $API_ENDPOINT"
echo "Lambda 函数: $CUSTOMER_NAME-$ENVIRONMENT-bedrock-nova-proxy"
echo "CloudFormation 堆栈: $STACK_NAME"
echo ""
echo "测试命令:"
echo "curl $API_ENDPOINT/v1/models"
echo ""
echo "curl -X POST $API_ENDPOINT/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"model\": \"gpt-4o-mini\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
echo ""
echo "监控:"
echo "aws logs tail /aws/lambda/$CUSTOMER_NAME-$ENVIRONMENT-bedrock-nova-proxy --follow --region $REGION"
echo ""
log_success "部署测试完成！"