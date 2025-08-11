#!/bin/bash

# Bedrock Nova Proxy - 客户环境一键部署脚本
# 使用方法: ./deploy-customer.sh --config config/customer.yaml

set -e

# 默认配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE=""
DRY_RUN=false
VERBOSE=false
REGION="us-east-1"
DEPLOYMENT_TYPE="serverless"
CUSTOMER_NAME=""
ENVIRONMENT="prod"

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

# 显示帮助信息
show_help() {
    cat << EOF
Bedrock Nova Proxy 客户环境部署脚本

使用方法:
    $0 --config <config-file> [选项]

必需参数:
    --config <file>         客户配置文件路径

可选参数:
    --region <region>       AWS 区域 (默认: us-east-1)
    --type <type>          部署类型: serverless|container|hybrid (默认: serverless)
    --customer <name>       客户名称 (从配置文件读取)
    --environment <env>     环境: dev|staging|prod (默认: prod)
    --dry-run              仅验证配置，不执行部署
    --verbose              详细输出
    --help                 显示此帮助信息

示例:
    $0 --config config/customer-prod.yaml
    $0 --config config/customer-dev.yaml --environment dev --dry-run
    $0 --config config/customer.yaml --type container --region us-west-2

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --type)
                DEPLOYMENT_TYPE="$2"
                shift 2
                ;;
            --customer)
                CUSTOMER_NAME="$2"
                shift 2
                ;;
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 验证必需参数
    if [[ -z "$CONFIG_FILE" ]]; then
        log_error "必须指定配置文件 --config"
        show_help
        exit 1
    fi

    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "配置文件不存在: $CONFIG_FILE"
        exit 1
    fi
}

# 验证 AWS CLI 和权限
validate_aws() {
    log_info "验证 AWS CLI 和权限..."
    
    # 检查 AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI 未安装，请先安装 AWS CLI"
        exit 1
    fi

    # 检查 AWS 凭证
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS 凭证未配置或无效，请运行 'aws configure'"
        exit 1
    fi

    # 获取当前账户信息
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CURRENT_REGION=$(aws configure get region || echo "us-east-1")
    
    log_info "AWS 账户: $ACCOUNT_ID"
    log_info "当前区域: $CURRENT_REGION"
    
    # 验证区域中的 Bedrock 可用性
    if ! aws bedrock list-foundation-models --region "$REGION" &> /dev/null; then
        log_warning "区域 $REGION 中 Bedrock 服务可能不可用"
    fi
}

# 解析配置文件
parse_config() {
    log_info "解析配置文件: $CONFIG_FILE"
    
    # 检查配置文件格式
    if [[ "$CONFIG_FILE" == *.yaml ]] || [[ "$CONFIG_FILE" == *.yml ]]; then
        # 使用 Python 解析 YAML（如果可用）
        if command -v python3 &> /dev/null; then
            CUSTOMER_NAME=$(python3 -c "
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
    print(config.get('customer', {}).get('name', ''))
" 2>/dev/null || echo "")
        fi
    fi
    
    # 如果无法从配置文件解析，使用命令行参数
    if [[ -z "$CUSTOMER_NAME" ]]; then
        if [[ -z "$CUSTOMER_NAME" ]]; then
            log_error "无法从配置文件解析客户名称，请使用 --customer 参数指定"
            exit 1
        fi
    fi
    
    log_info "客户名称: $CUSTOMER_NAME"
    log_info "部署类型: $DEPLOYMENT_TYPE"
    log_info "环境: $ENVIRONMENT"
}

# 验证部署前提条件
validate_prerequisites() {
    log_info "验证部署前提条件..."
    
    # 检查必需的工具
    local required_tools=("aws" "zip")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "缺少必需工具: $tool"
            exit 1
        fi
    done
    
    # 验证 Lambda 代码存在
    if [[ ! -f "$PROJECT_ROOT/lambda_proxy/lambda_function.py" ]]; then
        log_error "Lambda 代码不存在: $PROJECT_ROOT/lambda_proxy/lambda_function.py"
        exit 1
    fi
    
    # 验证 CloudFormation 模板存在
    local template_file=""
    case $DEPLOYMENT_TYPE in
        serverless)
            template_file="$SCRIPT_DIR/CustomerServerless.template"
            ;;
        container)
            template_file="$SCRIPT_DIR/CustomerContainer.template"
            ;;
        hybrid)
            template_file="$SCRIPT_DIR/CustomerHybrid.template"
            ;;
        *)
            log_error "不支持的部署类型: $DEPLOYMENT_TYPE"
            exit 1
            ;;
    esac
    
    if [[ ! -f "$template_file" ]]; then
        log_error "CloudFormation 模板不存在: $template_file"
        exit 1
    fi
    
    log_success "前提条件验证通过"
}

# 准备部署包
prepare_deployment_package() {
    log_info "准备部署包..."
    
    local temp_dir=$(mktemp -d)
    local zip_file="$temp_dir/bedrock-nova-proxy.zip"
    
    # 复制 Lambda 代码
    cp -r "$PROJECT_ROOT/lambda_proxy"/* "$temp_dir/"
    
    # 安装依赖
    if [[ -f "$temp_dir/requirements.txt" ]]; then
        log_info "安装 Python 依赖..."
        pip install -r "$temp_dir/requirements.txt" -t "$temp_dir/" --quiet
    fi
    
    # 创建部署包
    cd "$temp_dir"
    zip -r "$zip_file" . -x "*.pyc" "__pycache__/*" "tests/*" "*.md" &> /dev/null
    cd - > /dev/null
    
    # 上传到 S3（如果需要）
    local s3_bucket="bedrock-nova-proxy-deployments-$ACCOUNT_ID"
    local s3_key="$CUSTOMER_NAME/$ENVIRONMENT/bedrock-nova-proxy.zip"
    
    # 创建 S3 存储桶（如果不存在）
    if ! aws s3 ls "s3://$s3_bucket" &> /dev/null; then
        log_info "创建 S3 存储桶: $s3_bucket"
        aws s3 mb "s3://$s3_bucket" --region "$REGION"
    fi
    
    # 上传部署包
    log_info "上传部署包到 S3..."
    aws s3 cp "$zip_file" "s3://$s3_bucket/$s3_key" --region "$REGION"
    
    # 清理临时文件
    rm -rf "$temp_dir"
    
    echo "$s3_bucket/$s3_key"
}

# 执行 CloudFormation 部署
deploy_cloudformation() {
    local s3_location="$1"
    local stack_name="bedrock-nova-proxy-$CUSTOMER_NAME-$ENVIRONMENT"
    
    log_info "开始 CloudFormation 部署..."
    log_info "堆栈名称: $stack_name"
    
    # 准备参数
    local parameters=(
        "ParameterKey=CustomerName,ParameterValue=$CUSTOMER_NAME"
        "ParameterKey=Environment,ParameterValue=$ENVIRONMENT"
        "ParameterKey=DeploymentPackageS3Bucket,ParameterValue=${s3_location%/*}"
        "ParameterKey=DeploymentPackageS3Key,ParameterValue=${s3_location#*/}"
    )
    
    # 从配置文件读取额外参数
    # 这里可以添加更多配置解析逻辑
    
    # 选择模板文件
    local template_file=""
    case $DEPLOYMENT_TYPE in
        serverless)
            template_file="$SCRIPT_DIR/CustomerServerless.template"
            ;;
        container)
            template_file="$SCRIPT_DIR/CustomerContainer.template"
            ;;
        hybrid)
            template_file="$SCRIPT_DIR/CustomerHybrid.template"
            ;;
    esac
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: 将执行以下部署命令:"
        echo "aws cloudformation deploy \\"
        echo "  --template-file $template_file \\"
        echo "  --stack-name $stack_name \\"
        echo "  --parameter-overrides ${parameters[*]} \\"
        echo "  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \\"
        echo "  --region $REGION"
        return 0
    fi
    
    # 执行部署
    aws cloudformation deploy \
        --template-file "$template_file" \
        --stack-name "$stack_name" \
        --parameter-overrides "${parameters[@]}" \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    
    if [[ $? -eq 0 ]]; then
        log_success "CloudFormation 部署成功"
        
        # 获取输出
        local api_endpoint=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
            --output text)
        
        if [[ -n "$api_endpoint" ]]; then
            log_success "API 端点: $api_endpoint"
            echo "$api_endpoint" > "$PROJECT_ROOT/deployment-endpoint.txt"
        fi
    else
        log_error "CloudFormation 部署失败"
        exit 1
    fi
}

# 运行部署后测试
run_post_deployment_tests() {
    log_info "运行部署后测试..."
    
    local endpoint_file="$PROJECT_ROOT/deployment-endpoint.txt"
    if [[ ! -f "$endpoint_file" ]]; then
        log_warning "未找到 API 端点信息，跳过测试"
        return 0
    fi
    
    local api_endpoint=$(cat "$endpoint_file")
    
    # 运行测试脚本
    if [[ -f "$PROJECT_ROOT/scripts/test-deployment.py" ]]; then
        log_info "运行自动化测试..."
        python3 "$PROJECT_ROOT/scripts/test-deployment.py" --endpoint "$api_endpoint"
        
        if [[ $? -eq 0 ]]; then
            log_success "所有测试通过"
        else
            log_warning "部分测试失败，请检查部署"
        fi
    else
        log_info "手动测试 API 端点:"
        echo "curl -X GET $api_endpoint/health"
        echo "curl -X GET $api_endpoint/v1/models"
    fi
}

# 设置监控和告警
setup_monitoring() {
    log_info "设置监控和告警..."
    
    local stack_name="bedrock-nova-proxy-$CUSTOMER_NAME-$ENVIRONMENT"
    
    # 创建 CloudWatch 仪表板
    local dashboard_name="$CUSTOMER_NAME-bedrock-nova-proxy"
    local dashboard_body=$(cat << EOF
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", "FunctionName", "$CUSTOMER_NAME-bedrock-nova-proxy"],
          [".", "Errors", ".", "."],
          [".", "Invocations", ".", "."]
        ],
        "period": 300,
        "stat": "Average",
        "region": "$REGION",
        "title": "Lambda Metrics"
      }
    }
  ]
}
EOF
)
    
    if [[ "$DRY_RUN" != "true" ]]; then
        aws cloudwatch put-dashboard \
            --dashboard-name "$dashboard_name" \
            --dashboard-body "$dashboard_body" \
            --region "$REGION" &> /dev/null
        
        log_success "CloudWatch 仪表板已创建: $dashboard_name"
    fi
}

# 生成部署报告
generate_deployment_report() {
    log_info "生成部署报告..."
    
    local report_file="$PROJECT_ROOT/deployment-report-$CUSTOMER_NAME-$ENVIRONMENT.txt"
    
    cat > "$report_file" << EOF
Bedrock Nova Proxy 部署报告
============================

部署信息:
- 客户名称: $CUSTOMER_NAME
- 环境: $ENVIRONMENT
- 部署类型: $DEPLOYMENT_TYPE
- AWS 区域: $REGION
- AWS 账户: $ACCOUNT_ID
- 部署时间: $(date)

资源信息:
- CloudFormation 堆栈: bedrock-nova-proxy-$CUSTOMER_NAME-$ENVIRONMENT
- Lambda 函数: $CUSTOMER_NAME-bedrock-nova-proxy
- API Gateway: $CUSTOMER_NAME-bedrock-nova-proxy-api

EOF

    if [[ -f "$PROJECT_ROOT/deployment-endpoint.txt" ]]; then
        local api_endpoint=$(cat "$PROJECT_ROOT/deployment-endpoint.txt")
        echo "- API 端点: $api_endpoint" >> "$report_file"
    fi

    cat >> "$report_file" << EOF

后续步骤:
1. 测试 API 端点功能
2. 配置监控和告警
3. 设置备份和灾难恢复
4. 培训运维团队

联系支持:
- 文档: docs/Customer-Deployment-Guide.md
- 故障排除: docs/Troubleshooting.md

EOF

    log_success "部署报告已生成: $report_file"
}

# 主函数
main() {
    echo "========================================"
    echo "Bedrock Nova Proxy 客户环境部署"
    echo "========================================"
    
    parse_args "$@"
    validate_aws
    parse_config
    validate_prerequisites
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN 模式 - 仅验证配置"
    fi
    
    local s3_location
    s3_location=$(prepare_deployment_package)
    
    deploy_cloudformation "$s3_location"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        run_post_deployment_tests
        setup_monitoring
        generate_deployment_report
        
        log_success "部署完成！"
        log_info "请查看部署报告了解详细信息"
    else
        log_info "DRY RUN 完成 - 配置验证通过"
    fi
}

# 错误处理
trap 'log_error "部署过程中发生错误，请检查日志"; exit 1' ERR

# 运行主函数
main "$@"