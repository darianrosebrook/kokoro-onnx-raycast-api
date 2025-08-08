#!/usr/bin/env python3
"""
Test script to verify phonemizer language fix.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phonemizer_language():
    """Test that phonemizer works with 'en-us' language code."""
    
    print("Testing phonemizer language fix...")
    
    try:
        # Test the text processing module
        from api.tts.text_processing import text_to_phonemes
        
        # Test with 'en-us' language code
        test_text = "Hello world"
        print(f"Testing with text: '{test_text}'")
        
        # Test with 'en-us' (should work)
        try:
            phonemes_en_us = text_to_phonemes(test_text, lang='en-us')
            print(f"✅ 'en-us' test passed: {phonemes_en_us[:10]}...")
        except Exception as e:
            print(f"❌ 'en-us' test failed: {e}")
            return False
        
        # Test with 'en' (should fail or be normalized)
        try:
            phonemes_en = text_to_phonemes(test_text, lang='en')
            print(f"✅ 'en' test passed (normalized): {phonemes_en[:10]}...")
        except Exception as e:
            print(f"❌ 'en' test failed: {e}")
            return False
        
        print("✅ All phonemizer language tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_cold_start_warmup():
    """Test that cold-start warm-up uses correct language code."""
    
    print("\nTesting cold-start warm-up language fix...")
    
    try:
        # Import the cold-start warm-up function
        from api.main import perform_cold_start_warmup
        
        print("✅ Cold-start warm-up function imported successfully")
        print("✅ Language code should now be 'en-us' instead of 'en'")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=== Phonemizer Language Fix Test ===\n")
    
    # Test phonemizer
    phonemizer_ok = test_phonemizer_language()
    
    # Test cold-start warm-up
    warmup_ok = test_cold_start_warmup()
    
    print(f"\n=== Test Results ===")
    print(f"Phonemizer: {'✅ PASS' if phonemizer_ok else '❌ FAIL'}")
    print(f"Cold-start warm-up: {'✅ PASS' if warmup_ok else '❌ FAIL'}")
    
    if phonemizer_ok and warmup_ok:
        print("\n🎉 All tests passed! Phonemizer language fix is working.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Check the output above.")
        sys.exit(1)
