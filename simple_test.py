#!/usr/bin/env python3
"""
简单直接调用Bedrock Nova Proxy API
"""

import requests
import json

# 你的API端点
url = "https://itw9z9jxai.execute-api.eu-north-1.amazonaws.com/prod/v1/chat/completions"

# 请求数据
data = {
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "你好，请用中文回答我的问题"}
    ]
}

# 请求头
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer dummy"
}

# 发送请求
response = requests.post(url, json=data, headers=headers)

# 打印结果
if response.status_code == 200:
    result = response.json()
    print("回答:", result['choices'][0]['message']['content'])
else:
    print("错误:", response.status_code, response.text)
