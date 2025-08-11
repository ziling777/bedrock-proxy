# 客户环境快速部署指南

本指南帮助您在 **5 分钟内** 完成 Bedrock Nova 代理服务的客户环境部署。

## 🚀 一键部署

### 前提条件

1. **AWS CLI 已配置**
   ```bash
   aws configure
   # 确保有足够的权限部署 Lambda、API Gateway、IAM 等资源
   ```

2. **Python 3.8+ 已安装**
   ```bash
   python3 --version
   ```

### 步骤 1: 准备配置文件

复制示例配置并修改：

```bash
# 复制配置模板
cp config/customer-example.yaml config/my-customer.yaml

# 编辑配置文件
vim config/my-customer.yaml
```

**最小配置示例**：
```yaml
customer:
  name: "my-company"              # 改为您的公司名称
  environment: "production"
  region: "us-east-1"            # 选择合适的区域
  account_id: "123456789012"     # 您的 AWS 账户 ID

deployment:
  type: "serverless"             # 推荐使用无服务器部署

monitoring:
  cloudwatch:
    enabled: true
    log_retention_days: 30

models:
  mappings:
    "gpt-4o": "amazon.nova-pro-v1:0"
    "gpt-4o-mini": "amazon.nova-lite-v1:0"
    "gpt-3.5-turbo": "amazon.nova-micro-v1:0"
```

### 步骤 2: 一键部署

```bash
# 执行部署脚本
./deployment/deploy-customer.sh --config config/my-customer.yaml

# 如果想先验证配置（不实际部署）
./deployment/deploy-customer.sh --config config/my-customer.yaml --dry-run
```

### 步骤 3: 测试部署

部署完成后，脚本会自动运行测试并显示 API 端点：

```bash
# 手动测试 API 端点
curl -X GET https://your-api-endpoint/health

# 测试模型列表
curl -X GET https://your-api-endpoint/v1/models

# 测试聊天完成
curl -X POST https://your-api-endpoint/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 🔧 高级配置选项

### VPC 部署（私有网络）

如果需要部署在您的 VPC 中：

```yaml
deployment:
  type: "serverless"
  vpc:
    enabled: true
    vpc_id: "vpc-12345678"
    subnet_ids: 
      - "subnet-12345678"
      - "subnet-87654321"
```

### 自定义域名

如果需要使用自定义域名：

```yaml
deployment:
  custom_domain:
    enabled: true
    domain_name: "api.mycompany.com"
    certificate_arn: "arn:aws:acm:us-east-1:123456789012:certificate/..."
```

### 监控和告警

配置告警通知：

```yaml
monitoring:
  alerts:
    enabled: true
    sns_topic_arn: "arn:aws:sns:us-east-1:123456789012:my-alerts"
    error_threshold: 10
    latency_threshold: 5000
```

## 📊 部署后操作

### 1. 查看监控仪表板

部署完成后，访问 CloudWatch 仪表板：
- 仪表板名称：`{customer-name}-{environment}-bedrock-nova-proxy`
- 包含 Lambda、API Gateway 和自定义指标

### 2. 配置应用程序

更新您的应用程序代码：

```python
# 原来的 OpenAI 代码
from openai import OpenAI
client = OpenAI(api_key="your-openai-key")

# 更新后的代码（只需要改一行）
client = OpenAI(
    base_url="https://your-api-endpoint",  # 使用部署的端点
    api_key="dummy"  # 不使用，但客户端需要
)

# 其他代码完全不变
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### 3. 成本监控

查看成本分析：

```bash
# 运行成本监控脚本
python3 scripts/cost-monitor.py
```

## 🛠️ 故障排除

### 常见问题

1. **权限错误**
   ```bash
   # 确保 AWS 凭证有足够权限
   aws sts get-caller-identity
   ```

2. **区域不支持 Bedrock**
   ```bash
   # 检查区域中的 Bedrock 可用性
   aws bedrock list-foundation-models --region us-east-1
   ```

3. **Lambda 超时**
   ```bash
   # 增加超时时间
   aws lambda update-function-configuration \
     --function-name your-function-name \
     --timeout 300
   ```

### 查看日志

```bash
# 查看 Lambda 日志
aws logs tail /aws/lambda/your-function-name --follow

# 查看 API Gateway 日志
aws logs tail /aws/apigateway/your-api-name --follow
```

## 📈 性能优化

### 1. 调整 Lambda 配置

根据使用情况优化：

```bash
# 增加内存（提高性能）
aws lambda update-function-configuration \
  --function-name your-function-name \
  --memory-size 1024

# 设置预留并发（减少冷启动）
aws lambda put-reserved-concurrency-config \
  --function-name your-function-name \
  --reserved-concurrency-units 50
```

### 2. 启用预置并发

对于高频使用的场景：

```bash
aws lambda put-provisioned-concurrency-config \
  --function-name your-function-name \
  --provisioned-concurrency-units 10
```

## 🔄 更新和维护

### 更新到新版本

```bash
# 下载新版本代码
git pull origin main

# 重新部署
./deployment/deploy-customer.sh --config config/my-customer.yaml
```

### 备份配置

```bash
# 备份当前配置
aws lambda get-function-configuration \
  --function-name your-function-name > backup-config.json
```

## 💰 成本估算

### 典型成本（每月）

**无服务器部署**：
- Lambda: ~$20-50（基于使用量）
- API Gateway: ~$3.50/百万请求
- CloudWatch: ~$5-10（日志和指标）
- Bedrock Nova: ~$0.35-0.80/1K tokens（比 OpenAI 便宜 70-80%）

**总计**：通常比直接使用 OpenAI API 节省 60-80% 成本

### 成本优化建议

1. **选择合适的 Nova 模型**：
   - 简单任务使用 Nova Micro
   - 复杂任务使用 Nova Pro
   - 多模态任务使用 Nova Lite

2. **优化 Lambda 配置**：
   - 根据实际需要调整内存
   - 使用预留并发减少冷启动

3. **设置成本告警**：
   ```bash
   # 设置月度预算告警
   aws budgets create-budget \
     --account-id 123456789012 \
     --budget file://budget-config.json
   ```

## 📞 支持

### 获取帮助

1. **查看文档**：
   - [完整部署指南](Customer-Deployment-Guide.md)
   - [故障排除指南](Troubleshooting.md)
   - [API 文档](Usage.md)

2. **检查日志**：
   - CloudWatch 日志包含详细错误信息
   - 使用 CloudWatch Insights 查询日志

3. **监控指标**：
   - CloudWatch 仪表板显示实时状态
   - 设置告警获取主动通知

### 联系支持

- **技术问题**：查看 GitHub Issues
- **部署问题**：检查 CloudFormation 事件
- **性能问题**：分析 CloudWatch 指标

---

## 🎯 总结

通过这个快速部署指南，您可以：

✅ **5 分钟内完成部署**  
✅ **零代码修改迁移**（只需改 base_url）  
✅ **节省 60-80% API 成本**  
✅ **获得完整监控和告警**  
✅ **享受企业级安全和合规**  

立即开始您的 Bedrock Nova 迁移之旅！