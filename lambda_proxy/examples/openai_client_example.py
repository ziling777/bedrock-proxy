"""
Example usage of OpenAI client.
"""
import os
import sys
import logging
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from openai_client import OpenAIClient, OpenAIAPIError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Demonstrate OpenAI client usage."""
    # Note: This example requires a real OpenAI API key
    api_key = os.environ.get('OPENAI_API_KEY', 'sk-test-key-placeholder')
    
    if api_key == 'sk-test-key-placeholder':
        logger.warning("⚠️  Using placeholder API key. Set OPENAI_API_KEY environment variable for real testing.")
        return 0
    
    try:
        # Initialize client
        logger.info("Initializing OpenAI client...")
        with OpenAIClient(api_key=api_key, timeout=30) as client:
            
            # Validate API key
            logger.info("Validating API key...")
            if client.validate_api_key():
                logger.info("✅ API key is valid")
            else:
                logger.error("❌ API key validation failed")
                return 1
            
            # List available models
            logger.info("Listing available models...")
            try:
                models_response = client.list_models()
                models = models_response.get('data', [])
                logger.info(f"✅ Found {len(models)} models")
                
                # Show first few models
                for i, model in enumerate(models[:3]):
                    logger.info(f"  - {model['id']} (owned by {model.get('owned_by', 'unknown')})")
                
                if len(models) > 3:
                    logger.info(f"  ... and {len(models) - 3} more models")
                    
            except OpenAIAPIError as e:
                logger.error(f"❌ Failed to list models: {e}")
            
            # Get specific model info
            logger.info("Getting model info for gpt-4o-mini...")
            try:
                model_info = client.get_model_info('gpt-4o-mini')
                if model_info:
                    logger.info(f"✅ Model info: {json.dumps(model_info, indent=2)}")
                else:
                    logger.warning("⚠️  Model gpt-4o-mini not found")
            except Exception as e:
                logger.error(f"❌ Failed to get model info: {e}")
            
            # Test chat completion
            logger.info("Testing chat completion...")
            try:
                request = {
                    'model': 'gpt-4o-mini',
                    'messages': [
                        {
                            'role': 'user',
                            'content': 'Hello! Please respond with a short greeting.'
                        }
                    ],
                    'temperature': 0.7,
                    'max_tokens': 50
                }
                
                response = client.chat_completion(request)
                
                logger.info("✅ Chat completion successful:")
                logger.info(f"  - ID: {response['id']}")
                logger.info(f"  - Model: {response['model']}")
                logger.info(f"  - Response: {response['choices'][0]['message']['content']}")
                logger.info(f"  - Usage: {response['usage']}")
                
            except OpenAIAPIError as e:
                logger.error(f"❌ Chat completion failed: {e}")
                logger.error(f"  - Status code: {e.status_code}")
                logger.error(f"  - Error type: {e.error_type}")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1
    
    logger.info("🎉 OpenAI client example completed successfully!")
    return 0


if __name__ == '__main__':
    exit(main())