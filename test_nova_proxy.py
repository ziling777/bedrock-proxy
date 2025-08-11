#!/usr/bin/env python3
"""
Quick test script for Bedrock Nova Proxy
"""
import requests
import json

# 替换为您的 API Gateway URL
API_BASE_URL = "https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{API_BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_models():
    """Test models endpoint"""
    print("\n📋 Testing models endpoint...")
    response = requests.get(f"{API_BASE_URL}/v1/models")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        models = response.json()
        print(f"Found {len(models['data'])} models:")
        for model in models['data'][:5]:  # Show first 5 models
            print(f"  - {model['id']} ({model.get('owned_by', 'unknown')})")
    
    return response.status_code == 200

def test_chat_completion():
    """Test chat completion"""
    print("\n💬 Testing chat completion...")
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Hello! Please respond with 'Nova Lite is working!'"}
        ],
        "max_tokens": 50,
        "temperature": 0.1
    }
    
    response = requests.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        message = result['choices'][0]['message']['content']
        print(f"Response: {message}")
        print(f"Usage: {result.get('usage', {})}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_multimodal():
    """Test multimodal input (text + image)"""
    print("\n🖼️  Testing multimodal input...")
    
    # Simple base64 encoded 1x1 pixel image
    import base64
    pixel_data = base64.b64encode(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82').decode()
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image? Just say 'I can process images!'"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{pixel_data}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 20
    }
    
    response = requests.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        message = result['choices'][0]['message']['content']
        print(f"Response: {message}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def main():
    print("🚀 Testing Bedrock Nova Proxy")
    print("=" * 50)
    
    if API_BASE_URL == "https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod":
        print("❌ Please update API_BASE_URL with your actual API Gateway URL")
        return
    
    tests = [
        ("Health Check", test_health),
        ("Models List", test_models),
        ("Chat Completion", test_chat_completion),
        ("Multimodal Input", test_multimodal)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_name} passed")
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your Bedrock Nova Proxy is working correctly!")
    else:
        print("⚠️  Some tests failed. Check your deployment and configuration.")

if __name__ == "__main__":
    main()