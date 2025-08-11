#!/bin/bash

# Bedrock Nova Proxy 快速部署脚本
# 使用方法: ./quick-deploy.sh [customer-name] [environment] [region]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
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

# 默认参数
CUSTOMER_NAME=${1:-"my-company"}
ENVIRONMENT=${2:-"prod"}
REGION=${3:-"eu-north-1"}
STACK_NAME="bedrock-nova-proxy-${CUSTOMER_NAME}-${ENVIRONMENT}"
S3_BUCKET="bedrock-nova-proxy-deployments-$(aws sts get-caller-identity --query Account --output text)"
S3_KEY="${CUSTOMER_NAME}/bedrock-nova-proxy.zip"

echo "========================================="
echo "🚀 Bedrock Nova Proxy 快速部署"
echo "========================================="
echo "客户名称: $CUSTOMER_NAME"
echo "环境: $ENVIRONMENT"
echo "区域: $REGION"
echo "堆栈名称: $STACK_NAME"
echo "========================================="

# 检查 AWS CLI
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI 未安装，请先安装 AWS CLI"
    exit 1
fi

# 检查 AWS 凭证
log_info "检查 AWS 凭证..."
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS 凭证未配置，请运行 'aws configure'"
    exit 1
fi
log_success "AWS 凭证验证通过"

# 检查区域是否支持 Bedrock Nova
log_info "检查区域 $REGION 是否支持 Bedrock Nova..."
if aws bedrock list-foundation-models --region $REGION --by-provider Amazon --query 'modelSummaries[?contains(modelId, `nova`)]' --output text | grep -q nova; then
    log_success "区域 $REGION 支持 Bedrock Nova 模型"
else
    log_warning "区域 $REGION 可能不支持 Bedrock Nova 模型，建议使用 eu-north-1"
fi

# 创建 S3 存储桶
log_info "准备 S3 存储桶 $S3_BUCKET..."
if aws s3 ls "s3://$S3_BUCKET" 2>/dev/null; then
    log_info "S3 存储桶已存在"
else
    log_info "创建 S3 存储桶..."
    if [ "$REGION" = "us-east-1" ]; then
        aws s3 mb "s3://$S3_BUCKET"
    else
        aws s3 mb "s3://$S3_BUCKET" --region $REGION
    fi
    log_success "S3 存储桶创建完成"
fi

# 准备 Lambda 部署包
log_info "准备 Lambda 部署包..."
cd lambda_proxy

# 安装依赖
log_info "安装 Python 依赖..."
python3 -m pip install --platform linux_x86_64 --target . \
    --implementation cp --python-version 3.11 --only-binary=:all: \
    --upgrade pydantic boto3 requests > /dev/null 2>&1

# 打包代码
log_info "打包 Lambda 代码..."
cd ..
rm -f bedrock-nova-proxy.zip
cd lambda_proxy
zip -r ../bedrock-nova-proxy.zip . \
    -x "venv/*" "tests/*" "__pycache__/*" "*.pyc" ".pytest_cache/*" > /dev/null
cd ..

log_success "Lambda 部署包准备完成"

# 上传到 S3
log_info "上传部署包到 S3..."
aws s3 cp bedrock-nova-proxy.zip "s3://$S3_BUCKET/$S3_KEY" --region $REGION
log_success "部署包上传完成"

# 检查堆栈是否存在
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
    log_warning "堆栈 $STACK_NAME 已存在，将进行更新..."
    OPERATION="update-stack"
    WAIT_COMMAND="stack-update-complete"
else
    log_info "创建新堆栈 $STACK_NAME..."
    OPERATION="create-stack"
    WAIT_COMMAND="stack-create-complete"
fi

# 部署 CloudFormation 堆栈
log_info "部署 CloudFormation 堆栈..."
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deployment/SimpleServerless.template \
    --parameters \
        ParameterKey=CustomerName,ParameterValue=$CUSTOMER_NAME \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=DeploymentPackageS3Bucket,ParameterValue=$S3_BUCKET \
        ParameterKey=DeploymentPackageS3Key,ParameterValue=$S3_KEY \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

# 等待部署完成
log_info "等待部署完成..."
aws cloudformation wait $WAIT_COMMAND --stack-name $STACK_NAME --region $REGION

# 获取输出信息
log_info "获取部署信息..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text)

log_success "部署完成！"

echo ""
echo "========================================="
echo "🎉 部署成功！"
echo "========================================="
echo "API 端点: $API_ENDPOINT"
echo "Lambda 函数: $LAMBDA_FUNCTION"
echo "CloudFormation 堆栈: $STACK_NAME"
echo "区域: $REGION"
echo ""

# 运行基本测试
log_info "运行基本功能测试..."

echo "🔍 测试模型列表..."
if curl -s "$API_ENDPOINT/v1/models" | jq -e '.data | length > 0' > /dev/null; then
    log_success "模型列表 API 正常"
else
    log_warning "模型列表 API 可能有问题"
fi

echo "🔍 测试聊天完成..."
if curl -s -X POST "$API_ENDPOINT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"model": "eu.amazon.nova-lite-v1:0", "messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 10}' \
    | jq -e '.choices[0].message.content' > /dev/null; then
    log_success "聊天完成 API 正常"
else
    log_warning "聊天完成 API 可能有问题，请检查日志"
fi

echo ""
echo "========================================="
echo "📝 使用说明"
echo "========================================="
echo ""
echo "测试命令:"
echo "curl $API_ENDPOINT/v1/models"
echo ""
echo "curl -X POST $API_ENDPOINT/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"model\": \"eu.amazon.nova-lite-v1:0\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}], \"max_tokens\": 50}'"
echo ""
echo "查看日志:"
echo "aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow --region $REGION"
echo ""
echo "删除部署:"
echo "aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
echo ""
echo "========================================="
log_success "部署完成！享受您的 OpenAI 兼容 API！"
echo "========================================="
