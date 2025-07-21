#!/usr/bin/env python3
"""
Misaki Setup Validation Script

Quick validation script to check if Misaki G2P integration is properly configured
and working. This provides a simple way for users to verify their setup.

@author @darianrosebrook
@date 2025-01-09
@version 1.0.0
"""

import sys
import os

def check_misaki_import():
    """Check if misaki can be imported."""
    try:
        import misaki
        print("✅ Misaki G2P module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Misaki G2P import failed: {e}")
        print("   • Run: pip install misaki")
        print("   • Or use Python 3.12 environment")
        return False

def check_misaki_backend():
    """Check if misaki backend can be initialized."""
    try:
        from misaki import en
        g2p = en.G2P(trf=False, british=False)
        print("✅ Misaki G2P backend initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Misaki G2P backend initialization failed: {e}")
        return False

def test_basic_phonemization():
    """Test basic phonemization functionality."""
    try:
        from misaki import en
        g2p = en.G2P(trf=False, british=False)
        
        text = "Hello world"
        phonemes, tokens = g2p(text)
        
        print(f"✅ Basic phonemization test successful")
        print(f"   Text: '{text}'")
        print(f"   Phonemes: {phonemes[:20]}...")
        print(f"   Tokens: {len(tokens)} tokens")
        return True
    except Exception as e:
        print(f"❌ Basic phonemization test failed: {e}")
        return False

def check_api_integration():
    """Check if API integration modules work."""
    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.getcwd())
        
        from api.tts.misaki_processing import is_misaki_available, text_to_phonemes_misaki
        
        available = is_misaki_available()
        print(f"✅ API integration check passed")
        print(f"   Misaki available: {available}")
        
        if available:
            # Test phonemization through API
            result = text_to_phonemes_misaki("Test API integration")
            if result and len(result) > 0:
                print(f"   API phonemization: {len(result)} phonemes")
                return True
        
        return available
    except Exception as e:
        print(f"❌ API integration check failed: {e}")
        print("   • Make sure you're running from the project root")
        print("   • Or set PYTHONPATH=. before running")
        return False

def check_configuration():
    """Check configuration values."""
    try:
        sys.path.insert(0, os.getcwd())
        from api.config import TTSConfig
        
        print("✅ Configuration check passed")
        print(f"   MISAKI_ENABLED: {TTSConfig.MISAKI_ENABLED}")
        print(f"   MISAKI_FALLBACK_ENABLED: {TTSConfig.MISAKI_FALLBACK_ENABLED}")
        print(f"   MISAKI_DEFAULT_LANG: {TTSConfig.MISAKI_DEFAULT_LANG}")
        print(f"   MISAKI_CACHE_SIZE: {TTSConfig.MISAKI_CACHE_SIZE}")
        return True
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")
        return False

def main():
    """Main validation function."""
    print("🔍 Misaki G2P Setup Validation")
    print("=" * 40)
    
    tests = [
        ("Import Test", check_misaki_import),
        ("Backend Test", check_misaki_backend),
        ("Phonemization Test", test_basic_phonemization),
        ("API Integration Test", check_api_integration),
        ("Configuration Test", check_configuration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 40)
    print("📋 VALIDATION SUMMARY")
    print("=" * 40)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"{test_name:20}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Misaki G2P is properly configured.")
        return 0
    elif passed >= total - 1:
        print("⚠️ Most tests passed. Minor configuration adjustments may be needed.")
        return 0
    else:
        print("🚨 Multiple test failures. Check your Misaki G2P installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 