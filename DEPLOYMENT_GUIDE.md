# Bedrock Nova Proxy 部署指南

🚀 **OpenAI 兼容的 Amazon Bedrock Nova 代理服务** - 零代码迁移，节省 60-80% API 成本

## 📋 目录

- [快速开始](#快速开始)
- [前置要求](#前置要求)
- [部署步骤](#部署步骤)
- [配置说明](#配置说明)
- [测试验证](#测试验证)
- [故障排除](#故障排除)
- [成本分析](#成本分析)
- [维护管理](#维护管理)

## 🚀 快速开始

### 一键部署命令

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/bedrock-nova-proxy.git
cd bedrock-nova-proxy

# 2. 部署到 AWS
aws cloudformation create-stack \
  --stack-name bedrock-nova-proxy-prod \
  --template-body file://deployment/SimpleServerless.template \
  --parameters \
    ParameterKey=CustomerName,ParameterValue=your-company \
    ParameterKey=Environment,ParameterValue=prod \
    ParameterKey=DeploymentPackageS3Bucket,ParameterValue=your-s3-bucket \
    ParameterKey=DeploymentPackageS3Key,ParameterValue=bedrock-nova-proxy.zip \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1

# 3. 等待部署完成
aws cloudformation wait stack-create-complete \
  --stack-name bedrock-nova-proxy-prod \
  --region eu-north-1
```

## 📋 前置要求

### AWS 权限要求

您的 AWS 账户需要以下权限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "apigateway:*",
        "iam:*",
        "logs:*",
        "s3:*",
        "bedrock:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 区域支持

推荐使用以下区域（支持 Nova 模型）：
- `eu-north-1` ✅ (推荐)
- `eu-central-1` ✅
- `eu-west-1` ✅
- `us-east-1` ✅
- `us-west-2` ✅

### 工具要求

- AWS CLI v2.0+
- jq (用于 JSON 处理)
- curl (用于 API 测试)

## 🛠️ 部署步骤

### 步骤 1: 准备部署包

```bash
# 进入项目目录
cd bedrock-access-gateway

# 安装 Python 依赖
cd lambda_proxy
python3 -m pip install --platform linux_x86_64 --target . \
  --implementation cp --python-version 3.11 --only-binary=:all: \
  --upgrade pydantic boto3 requests

# 打包 Lambda 代码
cd ..
rm -f bedrock-nova-proxy.zip
cd lambda_proxy
zip -r ../bedrock-nova-proxy.zip . \
  -x "venv/*" "tests/*" "__pycache__/*" "*.pyc" ".pytest_cache/*"
cd ..
```

### 步骤 2: 上传部署包到 S3

```bash
# 创建 S3 存储桶（如果不存在）
aws s3 mb s3://your-deployment-bucket --region eu-north-1

# 上传部署包
aws s3 cp bedrock-nova-proxy.zip \
  s3://your-deployment-bucket/bedrock-nova-proxy.zip \
  --region eu-north-1
```

### 步骤 3: 部署 CloudFormation 堆栈

```bash
aws cloudformation create-stack \
  --stack-name bedrock-nova-proxy-prod \
  --template-body file://deployment/SimpleServerless.template \
  --parameters \
    ParameterKey=CustomerName,ParameterValue=your-company \
    ParameterKey=Environment,ParameterValue=prod \
    ParameterKey=DeploymentPackageS3Bucket,ParameterValue=your-deployment-bucket \
    ParameterKey=DeploymentPackageS3Key,ParameterValue=bedrock-nova-proxy.zip \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1
```

### 步骤 4: 等待部署完成

```bash
# 等待堆栈创建完成
aws cloudformation wait stack-create-complete \
  --stack-name bedrock-nova-proxy-prod \
  --region eu-north-1

# 获取 API 端点
aws cloudformation describe-stacks \
  --stack-name bedrock-nova-proxy-prod \
  --region eu-north-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

## ⚙️ 配置说明

### CloudFormation 参数

| 参数名 | 描述 | 默认值 | 必填 |
|--------|------|--------|------|
| `CustomerName` | 客户名称，用于资源命名 | - | ✅ |
| `Environment` | 部署环境 | `dev` | ❌ |
| `DeploymentPackageS3Bucket` | S3 存储桶名称 | - | ✅ |
| `DeploymentPackageS3Key` | S3 对象键 | - | ✅ |

### 环境变量

Lambda 函数自动配置以下环境变量：

```bash
CUSTOMER_NAME=your-company
ENVIRONMENT=prod
LOG_LEVEL=INFO
ENABLE_METRICS=true
METRICS_NAMESPACE=Customer/BedrockNovaProxy
```

### IAM 权限

部署会自动创建以下 IAM 权限：

```yaml
Policies:
  - PolicyName: BedrockAccess
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Action:
            - bedrock:InvokeModel
            - bedrock:InvokeModelWithResponseStream
          Resource:
            - 'arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-*'
            - 'arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-*'
            - 'arn:aws:bedrock:eu-west-1::foundation-model/amazon.nova-*'
            - 'arn:aws:bedrock:eu-west-3::foundation-model/amazon.nova-*'
            - 'arn:aws:bedrock:*:*:inference-profile/*'
        - Effect: Allow
          Action:
            - bedrock:ListFoundationModels
            - bedrock:ListInferenceProfiles
          Resource: '*'
        - Effect: Allow
          Action:
            - cloudwatch:PutMetricData
          Resource: '*'
```

## 🧪 测试验证

### 基本功能测试

```bash
# 设置 API 端点
API_ENDPOINT="https://your-api-id.execute-api.eu-north-1.amazonaws.com/prod"

# 1. 测试模型列表
curl -s $API_ENDPOINT/v1/models | jq '.data | length'

# 2. 测试聊天完成
curl -X POST $API_ENDPOINT/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "eu.amazon.nova-lite-v1:0",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }' | jq '.choices[0].message.content'

# 3. 测试中文对话
curl -X POST $API_ENDPOINT/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "eu.amazon.nova-lite-v1:0", 
    "messages": [{"role": "user", "content": "你好！"}],
    "max_tokens": 50
  }' | jq '.choices[0].message.content'
```

### 性能测试

```bash
# 并发测试
for i in {1..10}; do
  curl -X POST $API_ENDPOINT/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model": "eu.amazon.nova-lite-v1:0", "messages": [{"role": "user", "content": "Test '$i'"}], "max_tokens": 10}' &
done
wait
```

### 可用模型

| 模型 ID | 描述 | 上下文长度 | 能力 |
|---------|------|------------|------|
| `eu.amazon.nova-micro-v1:0` | 轻量级文本模型 | 128K | 文本 |
| `eu.amazon.nova-lite-v1:0` | 平衡性能多模态 | 300K | 文本+图像 |
| `eu.amazon.nova-pro-v1:0` | 高性能多模态 | 300K | 文本+图像 |

## 🔧 故障排除

### 常见问题

#### 1. 部署失败：权限不足

**错误**: `User is not authorized to perform: cloudformation:CreateStack`

**解决方案**:
```bash
# 检查 AWS 凭证
aws sts get-caller-identity

# 确保有足够权限
aws iam attach-user-policy \
  --user-name your-username \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

#### 2. Lambda 函数错误：模块导入失败

**错误**: `Unable to import module 'lambda_function': No module named 'pydantic'`

**解决方案**:
```bash
# 重新安装依赖（使用正确的平台）
cd lambda_proxy
python3 -m pip install --platform linux_x86_64 --target . \
  --implementation cp --python-version 3.11 --only-binary=:all: \
  --upgrade pydantic boto3 requests

# 重新打包和部署
cd ..
zip -r bedrock-nova-proxy.zip lambda_proxy/* \
  -x "lambda_proxy/venv/*" "lambda_proxy/tests/*"
aws s3 cp bedrock-nova-proxy.zip s3://your-bucket/
aws lambda update-function-code \
  --function-name your-function-name \
  --s3-bucket your-bucket \
  --s3-key bedrock-nova-proxy.zip
```

#### 3. API 调用失败：权限错误

**错误**: `User is not authorized to perform: bedrock:InvokeModel`

**解决方案**:
```bash
# 更新 CloudFormation 堆栈以修复权限
aws cloudformation update-stack \
  --stack-name bedrock-nova-proxy-prod \
  --template-body file://deployment/SimpleServerless.template \
  --parameters file://parameters.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### 日志查看

```bash
# 查看 Lambda 日志
aws logs tail /aws/lambda/your-function-name --follow --region eu-north-1

# 查看特定时间段的日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --region eu-north-1
```

## 💰 成本分析

### 月度成本估算

基于 100万次 API 调用：

| 服务 | 成本 | 说明 |
|------|------|------|
| Lambda | $20-50 | 取决于执行时间和内存 |
| API Gateway | $3.50 | $3.50/百万请求 |
| CloudWatch | $5-10 | 日志和指标 |
| Bedrock Nova | $200-800 | 取决于模型和 token 使用 |
| **总计** | **$228-863** | **vs OpenAI $1500-5000** |

### 成本优化建议

1. **选择合适的模型**:
   - 简单任务使用 `nova-micro`
   - 复杂任务使用 `nova-lite`
   - 高要求任务使用 `nova-pro`

2. **优化 Lambda 配置**:
   ```bash
   # 调整内存和超时
   aws lambda update-function-configuration \
     --function-name your-function \
     --memory-size 512 \
     --timeout 30
   ```

3. **启用请求缓存**:
   - 对相同请求启用缓存
   - 减少重复的 Bedrock 调用

## 🔄 维护管理

### 更新部署

```bash
# 1. 更新代码
git pull origin main

# 2. 重新打包
cd lambda_proxy && zip -r ../bedrock-nova-proxy.zip . -x "venv/*" "tests/*"

# 3. 上传新版本
aws s3 cp ../bedrock-nova-proxy.zip s3://your-bucket/

# 4. 更新 Lambda 函数
aws lambda update-function-code \
  --function-name your-function-name \
  --s3-bucket your-bucket \
  --s3-key bedrock-nova-proxy.zip
```

### 监控设置

```bash
# 创建 CloudWatch 告警
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-Errors" \
  --alarm-description "Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=your-function-name
```

### 备份和恢复

```bash
# 备份 CloudFormation 模板
aws cloudformation get-template \
  --stack-name bedrock-nova-proxy-prod \
  --query 'TemplateBody' > backup-template.json

# 导出堆栈配置
aws cloudformation describe-stacks \
  --stack-name bedrock-nova-proxy-prod > backup-stack.json
```

### 删除部署

```bash
# 删除 CloudFormation 堆栈
aws cloudformation delete-stack \
  --stack-name bedrock-nova-proxy-prod \
  --region eu-north-1

# 等待删除完成
aws cloudformation wait stack-delete-complete \
  --stack-name bedrock-nova-proxy-prod \
  --region eu-north-1

# 清理 S3 存储桶
aws s3 rm s3://your-deployment-bucket/bedrock-nova-proxy.zip
```

## 📞 支持

- **文档**: 查看 `docs/` 目录
- **问题报告**: [GitHub Issues](https://github.com/YOUR_USERNAME/bedrock-nova-proxy/issues)
- **讨论**: [GitHub Discussions](https://github.com/YOUR_USERNAME/bedrock-nova-proxy/discussions)

---

**🎉 恭喜！您已成功部署 Bedrock Nova Proxy！**

立即开始使用您的 OpenAI 兼容 API，享受 60-80% 的成本节省！
