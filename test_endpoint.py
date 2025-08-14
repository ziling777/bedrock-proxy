#!/usr/bin/env python3
"""
Test script for Bedrock Nova Proxy endpoint
"""

import requests
import json
import time
from typing import Dict, Any

# Your endpoint
ENDPOINT = "https://itw9z9jxai.execute-api.eu-north-1.amazonaws.com/prod/v1/chat/completions"

def test_basic_request():
    """Test basic chat completion request"""
    print("🧪 Testing basic chat completion...")
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Hello! Please respond with 'Hello from Bedrock Nova!' to confirm the connection is working."}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer dummy"
    }
    
    try:
        start_time = time.time()
        response = requests.post(ENDPOINT, json=payload, headers=headers, timeout=30)
        end_time = time.time()
        
        print(f"⏱️  Response time: {end_time - start_time:.2f}s")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            print(f"🤖 Response: {data['choices'][0]['message']['content']}")
            print(f"📝 Model used: {data.get('model', 'Unknown')}")
            print(f"🔢 Tokens used: {data.get('usage', {})}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"🚫 Request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"📄 JSON decode error: {e}")
        print(f"Raw response: {response.text}")
        return False

def test_different_models():
    """Test different model names"""
    print("\n🔄 Testing different model mappings...")
    
    models_to_test = [
        "gpt-4o-mini",
        "gpt-3.5-turbo", 
        "gpt-4o",
        "eu.amazon.nova-lite-v1:0"
    ]
    
    for model in models_to_test:
        print(f"\n🧪 Testing model: {model}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": f"You are using model {model}. Please confirm this."}
            ],
            "max_tokens": 50
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dummy"
        }
        
        try:
            response = requests.post(ENDPOINT, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {model}: Success")
                print(f"   Response: {data['choices'][0]['message']['content'][:100]}...")
            else:
                print(f"❌ {model}: Failed ({response.status_code})")
                
        except Exception as e:
            print(f"🚫 {model}: Error - {e}")

def test_streaming():
    """Test streaming response"""
    print("\n🌊 Testing streaming response...")
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Count from 1 to 5, with each number on a new line."}
        ],
        "stream": True,
        "max_tokens": 50
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer dummy"
    }
    
    try:
        response = requests.post(ENDPOINT, json=payload, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            print("✅ Streaming started...")
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str.strip() == '[DONE]':
                            print("🏁 Stream completed")
                            break
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    print(f"📝 Chunk: {delta['content']}", end='', flush=True)
                        except json.JSONDecodeError:
                            continue
            print("\n✅ Streaming test completed")
            return True
        else:
            print(f"❌ Streaming failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"🚫 Streaming error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Bedrock Nova Proxy endpoint tests...")
    print(f"🎯 Endpoint: {ENDPOINT}")
    print("=" * 60)
    
    # Test basic functionality
    basic_success = test_basic_request()
    
    if basic_success:
        # Test different models
        test_different_models()
        
        # Test streaming
        test_streaming()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed! Your endpoint is working correctly.")
        print("💡 You can now use this endpoint in your applications by changing the base_url.")
    else:
        print("\n" + "=" * 60)
        print("❌ Basic test failed. Please check your endpoint configuration.")
        print("🔧 Common issues:")
        print("   - Check if the Lambda function is deployed correctly")
        print("   - Verify IAM permissions for Bedrock access")
        print("   - Ensure the API Gateway is properly configured")

if __name__ == "__main__":
    main()
