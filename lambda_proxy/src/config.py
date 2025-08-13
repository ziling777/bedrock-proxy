"""
Configuration settings for the Lambda proxy service.
"""
import os
from typing import Dict, Any

# Environment variables
OPENAI_API_KEY_SECRET_ARN = os.environ.get('OPENAI_API_KEY_SECRET_ARN')
# Use AWS_DEFAULT_REGION (provided by Lambda runtime) or fallback to us-east-1
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('BEDROCK_REGION', 'us-east-1')
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Default model mappings (OpenAI model -> Bedrock model)
# For EU regions, all OpenAI models map to Nova Lite for cost optimization
DEFAULT_MODEL_MAPPINGS = {
    'gpt-4o-mini': 'eu.amazon.nova-lite-v1:0',
    'gpt-4o': 'eu.amazon.nova-lite-v1:0', 
    'gpt-3.5-turbo': 'eu.amazon.nova-lite-v1:0',
    'gpt-4': 'eu.amazon.nova-lite-v1:0',
    'gpt-4-turbo': 'eu.amazon.nova-lite-v1:0',
    'gpt-4-turbo-preview': 'eu.amazon.nova-lite-v1:0',
    # Support both direct model names and EU inference profiles
    'amazon.nova-lite-v1:0': 'eu.amazon.nova-lite-v1:0',
    'amazon.nova-pro-v1:0': 'eu.amazon.nova-lite-v1:0',
    'amazon.nova-micro-v1:0': 'eu.amazon.nova-lite-v1:0',
    # Direct EU inference profile support
    'eu.amazon.nova-lite-v1:0': 'eu.amazon.nova-lite-v1:0',
    'eu.amazon.nova-pro-v1:0': 'eu.amazon.nova-lite-v1:0',
    'eu.amazon.nova-micro-v1:0': 'eu.amazon.nova-lite-v1:0',
}

# Timeout settings (in seconds)
DEFAULT_TIMEOUT_SETTINGS = {
    'openai_api_timeout': 30,
    'secrets_manager_timeout': 10,
    'lambda_timeout': 300,
}

# OpenAI API settings
OPENAI_API_BASE_URL = 'https://api.openai.com/v1'
OPENAI_MAX_RETRIES = 3
OPENAI_RETRY_DELAY = 1  # seconds

# Supported endpoints
SUPPORTED_ENDPOINTS = {
    '/v1/chat/completions': 'chat_completion',
    '/v1/models': 'models_list',
    '/health': 'health_check',
}

# CORS settings
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}