#!/usr/bin/env python3
"""
Comprehensive test runner for Bedrock Nova Proxy.
"""
import os
import sys
import subprocess
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def run_command(command, description):
    """Run a command and return the result."""
    print(f"\n🧪 {description}")
    print(f"Command: {command}")
    print("-" * 60)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def run_pytest_tests():
    """Run pytest unit tests."""
    print("\n" + "="*80)
    print("🔬 RUNNING UNIT TESTS")
    print("="*80)
    
    test_files = [
        "tests/test_bedrock_format_converter.py",
        "tests/test_bedrock_client.py",
        "tests/test_models.py",
        "tests/test_models_endpoint.py"
    ]
    
    results = []
    
    for test_file in test_files:
        if os.path.exists(test_file):
            success = run_command(
                f"python -m pytest {test_file} -v --tb=short",
                f"Running {test_file}"
            )
            results.append((test_file, success))
        else:
            print(f"⚠️  Test file not found: {test_file}")
            results.append((test_file, False))
    
    return results


def run_integration_tests():
    """Run integration tests."""
    print("\n" + "="*80)
    print("🔗 RUNNING INTEGRATION TESTS")
    print("="*80)
    
    integration_tests = [
        ("test_bedrock_integration.py", "Bedrock Integration Test"),
        ("test_models_integration.py", "Models Integration Test"),
        ("test_monitoring_integration.py", "Monitoring Integration Test")
    ]
    
    results = []
    
    for test_file, description in integration_tests:
        if os.path.exists(test_file):
            success = run_command(
                f"python {test_file}",
                description
            )
            results.append((test_file, success))
        else:
            print(f"⚠️  Integration test not found: {test_file}")
            results.append((test_file, False))
    
    return results


def run_format_conversion_tests():
    """Run specific format conversion tests."""
    print("\n" + "="*80)
    print("🔄 RUNNING FORMAT CONVERSION TESTS")
    print("="*80)
    
    # Test basic format conversion
    try:
        from src.bedrock_format_converter import BedrockFormatConverter
        
        converter = BedrockFormatConverter({
            'gpt-4o-mini': 'amazon.nova-lite-v1:0'
        })
        
        # Test OpenAI to Bedrock conversion
        openai_request = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'user', 'content': 'Hello'}
            ],
            'temperature': 0.7
        }
        
        bedrock_request = converter.openai_to_bedrock_request(openai_request)
        
        assert bedrock_request['modelId'] == 'amazon.nova-lite-v1:0'
        assert len(bedrock_request['messages']) == 1
        assert bedrock_request['inferenceConfig']['temperature'] == 0.7
        
        print("✅ OpenAI to Bedrock conversion test passed")
        
        # Test Bedrock to OpenAI conversion
        bedrock_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [{'text': 'Hello there!'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {
                'inputTokens': 5,
                'outputTokens': 10,
                'totalTokens': 15
            }
        }
        
        openai_response = converter.bedrock_to_openai_response(bedrock_response, 'gpt-4o-mini')
        
        assert openai_response['object'] == 'chat.completion'
        assert openai_response['model'] == 'gpt-4o-mini'
        assert len(openai_response['choices']) == 1
        assert openai_response['choices'][0]['message']['content'] == 'Hello there!'
        
        print("✅ Bedrock to OpenAI conversion test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Format conversion test failed: {e}")
        return False


def run_model_mapping_tests():
    """Run model mapping tests."""
    print("\n" + "="*80)
    print("🗺️  RUNNING MODEL MAPPING TESTS")
    print("="*80)
    
    try:
        from src.config import DEFAULT_MODEL_MAPPINGS
        from src.bedrock_format_converter import BedrockFormatConverter
        
        # Test default mappings
        expected_mappings = {
            'gpt-4o-mini': 'amazon.nova-lite-v1:0',
            'gpt-4o': 'amazon.nova-pro-v1:0',
            'gpt-3.5-turbo': 'amazon.nova-micro-v1:0'
        }
        
        for openai_model, expected_bedrock in expected_mappings.items():
            if openai_model in DEFAULT_MODEL_MAPPINGS:
                actual_bedrock = DEFAULT_MODEL_MAPPINGS[openai_model]
                assert actual_bedrock == expected_bedrock, f"Mapping mismatch for {openai_model}"
                print(f"✅ {openai_model} -> {actual_bedrock}")
            else:
                print(f"❌ Missing mapping for {openai_model}")
                return False
        
        # Test converter model name conversion
        converter = BedrockFormatConverter(DEFAULT_MODEL_MAPPINGS)
        
        for openai_model, expected_bedrock in expected_mappings.items():
            actual_bedrock = converter.convert_model_name(openai_model)
            assert actual_bedrock == expected_bedrock
        
        print("✅ All model mapping tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Model mapping test failed: {e}")
        return False


def run_multimodal_tests():
    """Run multimodal content tests."""
    print("\n" + "="*80)
    print("🖼️  RUNNING MULTIMODAL TESTS")
    print("="*80)
    
    try:
        from src.bedrock_format_converter import BedrockFormatConverter
        import base64
        
        converter = BedrockFormatConverter()
        
        # Test image conversion
        test_image_data = base64.b64encode(b'fake_image_data').decode('utf-8')
        
        openai_request = {
            'model': 'gpt-4o-mini',
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': 'What is in this image?'
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{test_image_data}'
                            }
                        }
                    ]
                }
            ]
        }
        
        bedrock_request = converter.openai_to_bedrock_request(openai_request)
        
        # Check message content
        message = bedrock_request['messages'][0]
        assert len(message['content']) == 2
        
        # Check text content
        text_content = message['content'][0]
        assert text_content['text'] == 'What is in this image?'
        
        # Check image content
        image_content = message['content'][1]
        assert 'image' in image_content
        assert image_content['image']['format'] == 'jpeg'
        
        print("✅ Multimodal content conversion test passed")
        return True
        
    except Exception as e:
        print(f"❌ Multimodal test failed: {e}")
        return False


def print_summary(results):
    """Print test results summary."""
    print("\n" + "="*80)
    print("📊 TEST RESULTS SUMMARY")
    print("="*80)
    
    total_tests = 0
    passed_tests = 0
    
    for category, category_results in results.items():
        print(f"\n{category}:")
        
        if isinstance(category_results, list):
            for test_name, success in category_results:
                status = "✅ PASSED" if success else "❌ FAILED"
                print(f"  {test_name}: {status}")
                total_tests += 1
                if success:
                    passed_tests += 1
        else:
            status = "✅ PASSED" if category_results else "❌ FAILED"
            print(f"  {category}: {status}")
            total_tests += 1
            if category_results:
                passed_tests += 1
    
    print(f"\n📈 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED")
        return False


def main():
    """Main test runner."""
    print("🚀 Starting Bedrock Nova Proxy Test Suite")
    print("="*80)
    
    results = {}
    
    # Run unit tests
    results["Unit Tests"] = run_pytest_tests()
    
    # Run integration tests
    results["Integration Tests"] = run_integration_tests()
    
    # Run format conversion tests
    results["Format Conversion"] = run_format_conversion_tests()
    
    # Run model mapping tests
    results["Model Mapping"] = run_model_mapping_tests()
    
    # Run multimodal tests
    results["Multimodal Content"] = run_multimodal_tests()
    
    # Print summary
    all_passed = print_summary(results)
    
    if all_passed:
        print("\n🎯 Test suite completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Test suite completed with failures!")
        sys.exit(1)


if __name__ == '__main__':
    main()