# 客户环境部署指南

本指南详细说明如何在客户环境中部署 Bedrock Nova 代理服务，包括不同的部署选项、配置要求和最佳实践。

## 概述

Bedrock Nova 代理服务支持多种部署模式，可以适应不同客户的基础设施需求：

- **无服务器部署** (推荐)：API Gateway + Lambda
- **容器化部署**：ECS/EKS + ALB  
- **混合部署**：根据工作负载特点混合使用

## 部署前准备

### 1. 环境要求

#### AWS 权限要求
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
        "bedrock:*"
      ],
      "Resource": "*"
    }
  ]
}
```

#### 网络要求
- 如果部署在客户 VPC 中，需要：
  - 至少 2 个私有子网（不同 AZ）
  - NAT Gateway 或 VPC Endpoints 用于外网访问
  - 安全组配置允许 HTTPS 出站流量

#### 区域支持
- 推荐区域：`us-east-1`, `us-west-2`, `eu-west-1`
- 确保选择的区域支持 Bedrock Nova 模型

### 2. 客户配置文件

创建客户特定的配置文件：

```yaml
# config/customer-prod.yaml
customer:
  name: "客户名称"
  environment: "production"
  region: "us-east-1"
  account_id: "123456789012"

deployment:
  type: "serverless"  # serverless | container | hybrid
  
  # VPC 配置（可选）
  vpc:
    enabled: true
    vpc_id: "vpc-12345678"
    subnet_ids: 
      - "subnet-12345678"
      - "subnet-87654321"
    security_group_ids:
      - "sg-12345678"

  # 域名配置（可选）
  custom_domain:
    enabled: true
    domain_name: "api.customer.com"
    certificate_arn: "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012"

security:
  # 加密配置
  encryption:
    enabled: true
    kms_key_id: "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  
  # 跨账户访问（如果需要）
  cross_account:
    enabled: false
    role_arn: "arn:aws:iam::123456789012:role/BedrockNovaProxyRole"

monitoring:
  cloudwatch:
    enabled: true
    log_retention_days: 30
    dashboard_enabled: true
  
  # 自定义指标
  custom_metrics:
    enabled: true
    namespace: "Customer/BedrockNovaProxy"
  
  # 告警配置
  alerts:
    enabled: true
    sns_topic_arn: "arn:aws:sns:us-east-1:123456789012:bedrock-nova-alerts"

# 模型映射配置
models:
  mappings:
    "gpt-4o": "amazon.nova-pro-v1:0"
    "gpt-4o-mini": "amazon.nova-lite-v1:0"
    "gpt-3.5-turbo": "amazon.nova-micro-v1:0"
    "customer-premium": "amazon.nova-premier-v1:0"

# 性能配置
performance:
  lambda:
    memory_size: 1024
    timeout: 300
    reserved_concurrency: 100
    provisioned_concurrency: 10
  
  api_gateway:
    throttling:
      rate_limit: 1000
      burst_limit: 2000
```

## 部署选项

### 选项 1: 无服务器部署（推荐）

适用于大多数客户环境，成本效益高，自动扩缩容。

#### 部署步骤

1. **准备部署脚本**
```bash
#!/bin/bash
# deploy-customer-serverless.sh

CUSTOMER_CONFIG="config/customer-prod.yaml"
STACK_NAME="bedrock-nova-proxy-customer"
REGION="us-east-1"

echo "开始部署无服务器架构..."

# 验证配置
python scripts/validate-config.py --config $CUSTOMER_CONFIG

# 部署 CloudFormation 栈
aws cloudformation deploy \
  --template-file deployment/CustomerServerless.template \
  --stack-name $STACK_NAME \
  --parameter-overrides file://$CUSTOMER_CONFIG \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region $REGION

# 获取部署输出
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

echo "部署完成！"
echo "API 端点: $API_ENDPOINT"

# 运行部署后测试
python scripts/test-deployment.py --endpoint $API_ENDPOINT
```

2. **CloudFormation 模板**
```yaml
# deployment/CustomerServerless.template
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Bedrock Nova Proxy - Customer Serverless Deployment'

Parameters:
  CustomerName:
    Type: String
    Description: 'Customer name for resource naming'
  
  Environment:
    Type: String
    Default: 'prod'
    AllowedValues: ['dev', 'staging', 'prod']
  
  VpcId:
    Type: String
    Default: ''
    Description: 'Customer VPC ID (optional)'
  
  SubnetIds:
    Type: CommaDelimitedList
    Default: ''
    Description: 'Customer Subnet IDs (optional)'

Conditions:
  UseCustomVpc: !Not [!Equals [!Ref VpcId, '']]

Resources:
  # Lambda 执行角色
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${CustomerName}-bedrock-nova-proxy-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
      Policies:
        - PolicyName: BedrockAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - bedrock:InvokeModel
                  - bedrock:InvokeModelWithResponseStream
                  - bedrock:ListFoundationModels
                Resource: 'arn:aws:bedrock:*::foundation-model/amazon.nova-*'

  # Lambda 函数
  ProxyLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${CustomerName}-bedrock-nova-proxy'
      Runtime: python3.11
      Handler: lambda_function.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: |
          # Lambda 代码将在部署时注入
          def lambda_handler(event, context):
              return {"statusCode": 200, "body": "Hello from Lambda"}
      Timeout: 300
      MemorySize: 1024
      Environment:
        Variables:
          CUSTOMER_NAME: !Ref CustomerName
          ENVIRONMENT: !Ref Environment
      VpcConfig: !If
        - UseCustomVpc
        - SubnetIds: !Ref SubnetIds
          SecurityGroupIds: 
            - !Ref LambdaSecurityGroup
        - !Ref AWS::NoValue

  # 安全组（如果使用 VPC）
  LambdaSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Condition: UseCustomVpc
    Properties:
      GroupDescription: Security group for Bedrock Nova Proxy Lambda
      VpcId: !Ref VpcId
      SecurityGroupEgress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
          Description: HTTPS outbound for Bedrock API

  # API Gateway
  ApiGateway:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub '${CustomerName}-bedrock-nova-proxy-api'
      Description: 'Bedrock Nova Proxy API for customer'
      EndpointConfiguration:
        Types:
          - REGIONAL

  # API Gateway 部署
  ApiDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn: 
      - ProxyMethod
    Properties:
      RestApiId: !Ref ApiGateway
      StageName: prod

  # Lambda 权限
  LambdaPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ProxyLambda
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub '${ApiGateway}/*/POST/*'

Outputs:
  ApiEndpoint:
    Description: 'API Gateway endpoint URL'
    Value: !Sub 'https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/prod'
    Export:
      Name: !Sub '${AWS::StackName}-ApiEndpoint'
  
  LambdaFunctionArn:
    Description: 'Lambda function ARN'
    Value: !GetAtt ProxyLambda.Arn
    Export:
      Name: !Sub '${AWS::StackName}-LambdaArn'
```

### 选项 2: 容器化部署

适用于高吞吐量环境或已有容器基础设施的客户。

#### ECS 部署
```bash
#!/bin/bash
# deploy-customer-ecs.sh

CUSTOMER_CONFIG="config/customer-prod.yaml"
STACK_NAME="bedrock-nova-proxy-ecs-customer"
REGION="us-east-1"

echo "开始部署 ECS 容器架构..."

# 构建并推送 Docker 镜像
docker build -t bedrock-nova-proxy:latest .
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY
docker tag bedrock-nova-proxy:latest $ECR_REPOSITORY:latest
docker push $ECR_REPOSITORY:latest

# 部署 ECS 服务
aws cloudformation deploy \
  --template-file deployment/CustomerECS.template \
  --stack-name $STACK_NAME \
  --parameter-overrides file://$CUSTOMER_CONFIG \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region $REGION

echo "ECS 部署完成！"
```

#### EKS 部署
```yaml
# k8s/customer-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bedrock-nova-proxy
  namespace: customer-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bedrock-nova-proxy
  template:
    metadata:
      labels:
        app: bedrock-nova-proxy
    spec:
      serviceAccountName: bedrock-nova-proxy-sa
      containers:
      - name: bedrock-nova-proxy
        image: your-ecr-repo/bedrock-nova-proxy:latest
        ports:
        - containerPort: 8000
        env:
        - name: CUSTOMER_NAME
          value: "customer-name"
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: bedrock-nova-proxy-service
  namespace: customer-prod
spec:
  selector:
    app: bedrock-nova-proxy
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

## 部署后配置

### 1. 监控设置

```bash
#!/bin/bash
# setup-monitoring.sh

CUSTOMER_NAME="customer-name"
REGION="us-east-1"

# 创建 CloudWatch 仪表板
aws cloudwatch put-dashboard \
  --dashboard-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --dashboard-body file://monitoring/customer-dashboard.json \
  --region $REGION

# 设置告警
aws cloudwatch put-metric-alarm \
  --alarm-name "${CUSTOMER_NAME}-high-error-rate" \
  --alarm-description "High error rate for Bedrock Nova Proxy" \
  --metric-name ErrorCount \
  --namespace "Customer/BedrockNovaProxy" \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "arn:aws:sns:${REGION}:123456789012:bedrock-nova-alerts" \
  --region $REGION

echo "监控设置完成"
```

### 2. 安全配置

```bash
#!/bin/bash
# setup-security.sh

CUSTOMER_NAME="customer-name"
REGION="us-east-1"

# 创建 KMS 密钥（如果客户需要）
KMS_KEY_ID=$(aws kms create-key \
  --description "Bedrock Nova Proxy encryption key for ${CUSTOMER_NAME}" \
  --region $REGION \
  --query 'KeyMetadata.KeyId' \
  --output text)

# 创建密钥别名
aws kms create-alias \
  --alias-name "alias/${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --target-key-id $KMS_KEY_ID \
  --region $REGION

# 更新 Lambda 环境变量
aws lambda update-function-configuration \
  --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --kms-key-arn "arn:aws:kms:${REGION}:123456789012:key/${KMS_KEY_ID}" \
  --region $REGION

echo "安全配置完成"
```

## 测试和验证

### 1. 部署验证脚本

```python
#!/usr/bin/env python3
# scripts/test-deployment.py

import requests
import json
import sys
import argparse
from typing import Dict, Any

def test_health_endpoint(base_url: str) -> bool:
    """测试健康检查端点"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

def test_models_endpoint(base_url: str) -> bool:
    """测试模型列表端点"""
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        if response.status_code != 200:
            return False
        
        data = response.json()
        models = [model['id'] for model in data.get('data', [])]
        
        # 检查必需的模型
        required_models = ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo']
        return all(model in models for model in required_models)
    except Exception as e:
        print(f"模型端点测试失败: {e}")
        return False

def test_chat_completion(base_url: str) -> bool:
    """测试聊天完成端点"""
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "max_tokens": 50
        }
        
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"聊天完成测试失败，状态码: {response.status_code}")
            return False
        
        data = response.json()
        return 'choices' in data and len(data['choices']) > 0
    except Exception as e:
        print(f"聊天完成测试失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='测试 Bedrock Nova Proxy 部署')
    parser.add_argument('--endpoint', required=True, help='API 端点 URL')
    args = parser.parse_args()
    
    base_url = args.endpoint.rstrip('/')
    
    print(f"测试部署: {base_url}")
    
    tests = [
        ("健康检查", test_health_endpoint),
        ("模型列表", test_models_endpoint),
        ("聊天完成", test_chat_completion)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"运行 {test_name} 测试...")
        result = test_func(base_url)
        results.append((test_name, result))
        print(f"  {'✅ 通过' if result else '❌ 失败'}")
    
    # 总结
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！部署成功。")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查部署。")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 2. 性能测试

```python
#!/usr/bin/env python3
# scripts/performance-test.py

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict

async def make_request(session: aiohttp.ClientSession, url: str, payload: Dict) -> Dict:
    """发送单个请求并测量响应时间"""
    start_time = time.time()
    try:
        async with session.post(url, json=payload) as response:
            end_time = time.time()
            return {
                'status_code': response.status,
                'response_time': end_time - start_time,
                'success': response.status == 200
            }
    except Exception as e:
        end_time = time.time()
        return {
            'status_code': 0,
            'response_time': end_time - start_time,
            'success': False,
            'error': str(e)
        }

async def run_performance_test(base_url: str, concurrent_requests: int = 10, total_requests: int = 100):
    """运行性能测试"""
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Performance test message"}],
        "max_tokens": 50
    }
    
    print(f"开始性能测试: {concurrent_requests} 并发, {total_requests} 总请求")
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(total_requests):
            task = make_request(session, url, payload)
            tasks.append(task)
            
            # 控制并发数
            if len(tasks) >= concurrent_requests:
                results = await asyncio.gather(*tasks)
                tasks = []
                
                # 分析结果
                response_times = [r['response_time'] for r in results if r['success']]
                success_count = sum(1 for r in results if r['success'])
                
                print(f"批次完成: {success_count}/{len(results)} 成功")
                if response_times:
                    print(f"  平均响应时间: {statistics.mean(response_times):.2f}s")
                    print(f"  最大响应时间: {max(response_times):.2f}s")
        
        # 处理剩余任务
        if tasks:
            results = await asyncio.gather(*tasks)
            response_times = [r['response_time'] for r in results if r['success']]
            success_count = sum(1 for r in results if r['success'])
            print(f"最后批次: {success_count}/{len(results)} 成功")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("用法: python performance-test.py <API_ENDPOINT>")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    asyncio.run(run_performance_test(base_url))
```

## 运维和维护

### 1. 日常监控检查清单

- [ ] **API 健康状态**：检查 `/health` 端点响应
- [ ] **错误率监控**：CloudWatch 中的错误指标
- [ ] **响应时间**：平均响应时间是否在可接受范围内
- [ ] **成本监控**：AWS 成本和使用情况
- [ ] **安全审计**：访问日志和安全事件

### 2. 更新和升级流程

```bash
#!/bin/bash
# update-deployment.sh

CUSTOMER_NAME="customer-name"
NEW_VERSION="v1.2.0"
REGION="us-east-1"

echo "开始更新到版本 $NEW_VERSION..."

# 1. 备份当前配置
aws lambda get-function-configuration \
  --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --region $REGION > backup-config.json

# 2. 部署新版本（蓝绿部署）
./deploy-customer-serverless.sh --version $NEW_VERSION --stage green

# 3. 运行测试
python scripts/test-deployment.py --endpoint $GREEN_ENDPOINT

# 4. 切换流量
if [ $? -eq 0 ]; then
    echo "测试通过，切换流量到新版本"
    # 更新 API Gateway 指向新版本
    aws apigateway update-stage \
      --rest-api-id $API_ID \
      --stage-name prod \
      --patch-ops op=replace,path=/variables/lambda_alias,value=green
    
    echo "更新完成"
else
    echo "测试失败，保持当前版本"
    exit 1
fi
```

### 3. 故障排除指南

#### 常见问题和解决方案

1. **Lambda 超时**
   ```bash
   # 增加 Lambda 超时时间
   aws lambda update-function-configuration \
     --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
     --timeout 300
   ```

2. **内存不足**
   ```bash
   # 增加 Lambda 内存
   aws lambda update-function-configuration \
     --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
     --memory-size 1024
   ```

3. **网络连接问题**
   ```bash
   # 检查 VPC 配置和安全组
   aws ec2 describe-security-groups --group-ids sg-12345678
   aws ec2 describe-route-tables --filters "Name=vpc-id,Values=vpc-12345678"
   ```

## 成本优化

### 1. 成本监控脚本

```python
#!/usr/bin/env python3
# scripts/cost-monitor.py

import boto3
from datetime import datetime, timedelta
import json

def get_bedrock_costs(days: int = 30) -> Dict:
    """获取 Bedrock 相关成本"""
    ce = boto3.client('ce')
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    response = ce.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['BlendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['Amazon Bedrock', 'AWS Lambda', 'Amazon API Gateway']
            }
        }
    )
    
    costs = {}
    for result in response['ResultsByTime']:
        date = result['TimePeriod']['Start']
        for group in result['Groups']:
            service = group['Keys'][0]
            cost = float(group['Metrics']['BlendedCost']['Amount'])
            if service not in costs:
                costs[service] = []
            costs[service].append({'date': date, 'cost': cost})
    
    return costs

def main():
    costs = get_bedrock_costs()
    
    print("过去30天成本分析:")
    total_cost = 0
    
    for service, daily_costs in costs.items():
        service_total = sum(item['cost'] for item in daily_costs)
        total_cost += service_total
        print(f"{service}: ${service_total:.4f}")
    
    print(f"总计: ${total_cost:.4f}")
    
    # 成本优化建议
    if total_cost > 100:  # 如果月成本超过 $100
        print("\n💡 成本优化建议:")
        print("- 考虑使用预留容量降低 Lambda 成本")
        print("- 优化 Lambda 内存配置")
        print("- 使用 CloudWatch 日志保留策略")

if __name__ == "__main__":
    main()
```

### 2. 自动化成本优化

```bash
#!/bin/bash
# optimize-costs.sh

CUSTOMER_NAME="customer-name"
REGION="us-east-1"

echo "开始成本优化..."

# 1. 优化 Lambda 配置
CURRENT_MEMORY=$(aws lambda get-function-configuration \
  --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --region $REGION \
  --query 'MemorySize' --output text)

# 基于使用模式调整内存
if [ $CURRENT_MEMORY -gt 1024 ]; then
    echo "降低 Lambda 内存配置"
    aws lambda update-function-configuration \
      --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
      --memory-size 1024 \
      --region $REGION
fi

# 2. 设置日志保留策略
aws logs put-retention-policy \
  --log-group-name "/aws/lambda/${CUSTOMER_NAME}-bedrock-nova-proxy" \
  --retention-in-days 30 \
  --region $REGION

# 3. 启用预留并发（如果需要）
# aws lambda put-provisioned-concurrency-config \
#   --function-name "${CUSTOMER_NAME}-bedrock-nova-proxy" \
#   --provisioned-concurrency-units 5 \
#   --region $REGION

echo "成本优化完成"
```

## 支持和联系

### 技术支持
- **文档**: 查看完整的 API 文档和故障排除指南
- **监控**: 使用 CloudWatch 仪表板监控服务状态
- **日志**: 检查 CloudWatch 日志获取详细错误信息

### 升级和维护
- **定期更新**: 建议每季度检查并应用最新版本
- **安全补丁**: 关注安全更新通知
- **性能优化**: 定期审查性能指标和成本

---

*本部署指南会随着产品更新而持续维护。如有问题，请联系技术支持团队。*