#!/usr/bin/env python3
"""
Integration example for Bedrock Nova Proxy
Replace your OpenAI calls with this configuration
"""

from openai import OpenAI

# Your Bedrock Nova Proxy configuration
client = OpenAI(
    base_url="https://itw9z9jxai.execute-api.eu-north-1.amazonaws.com/prod/v1",
    api_key="dummy"  # Not used but required by OpenAI client
)

def example_chat():
    """Example chat completion"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Maps to eu.amazon.nova-lite-v1:0
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are the benefits of using AWS Bedrock?"}
        ],
        max_tokens=200,
        temperature=0.7
    )
    
    print("Response:", response.choices[0].message.content)
    print("Tokens used:", response.usage)

def example_streaming():
    """Example streaming response"""
    print("Streaming response:")
    
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Write a short poem about cloud computing"}
        ],
        stream=True,
        max_tokens=150
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")

if __name__ == "__main__":
    print("🚀 Bedrock Nova Proxy Integration Examples")
    print("=" * 50)
    
    print("\n1. Regular Chat Completion:")
    example_chat()
    
    print("\n2. Streaming Response:")
    example_streaming()
    
    print("\n✅ Integration examples completed!")
