"""
Example usage of ConfigManager.
"""
import os
import sys
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Demonstrate ConfigManager usage."""
    try:
        # Initialize config manager
        config = ConfigManager()
        
        # Validate configuration
        logger.info("Validating configuration...")
        validation_result = config.validate_configuration()
        
        if validation_result['valid']:
            logger.info("✅ Configuration is valid")
        else:
            logger.error("❌ Configuration validation failed:")
            for error in validation_result['errors']:
                logger.error(f"  - {error}")
        
        if validation_result['warnings']:
            logger.warning("⚠️  Configuration warnings:")
            for warning in validation_result['warnings']:
                logger.warning(f"  - {warning}")
        
        # Get configuration values
        try:
            api_key = config.get_openai_api_key()
            logger.info(f"✅ OpenAI API key retrieved: {api_key[:10]}...")
        except Exception as e:
            logger.error(f"❌ Failed to get API key: {e}")
        
        try:
            model_mappings = config.get_model_mapping()
            logger.info(f"✅ Model mappings: {model_mappings}")
        except Exception as e:
            logger.error(f"❌ Failed to get model mappings: {e}")
        
        try:
            timeout_settings = config.get_timeout_settings()
            logger.info(f"✅ Timeout settings: {timeout_settings}")
        except Exception as e:
            logger.error(f"❌ Failed to get timeout settings: {e}")
        
        # Other settings
        logger.info(f"Debug mode: {config.get_debug_mode()}")
        logger.info(f"AWS region: {config.get_aws_region()}")
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())