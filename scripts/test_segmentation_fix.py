#!/usr/bin/env python3
"""
Test script to verify context-aware text segmentation fixes.

This script tests the improved segmentation that preserves:
- Numbers with decimals (1.25, 3.14159)
- URLs and domain names (google.com, example.org)
- File extensions (file.md, document.txt)
- Email addresses (user@domain.com)
- Common abbreviations (Dr., Mr., etc.)

Usage:
    python scripts/test_segmentation_fix.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_context_aware_segmentation():
    """Test the context-aware segmentation fixes."""
    from api.tts.text_processing import test_context_aware_segmentation

    print("🔍 Testing Context-Aware Text Segmentation")
    print("=" * 60)

    # Run the built-in test
    test_context_aware_segmentation()

    print("\n" + "=" * 60)
    print("✅ Context-aware segmentation test completed!")

    # Additional manual tests
    print("\n🧪 Additional Manual Tests:")
    print("-" * 40)

    from api.tts.text_processing import segment_text
    from api.config import TTSConfig

    # Test cases that were problematic before
    problematic_cases = [
        "The price is 1.25 dollars per item",
        "Visit google.com for more information",
        "Open the file.md document",
        "Contact support@company.com for help",
        "Version 2.0.1 is now available",
        "Dr. Smith is the lead researcher",
        "The meeting is at 2:30 PM",
        "File sizes: 1.5MB, 2.3GB, 500KB",
        "Website: https://example.com/path",
        "Email: user@domain.org for inquiries"
    ]

    all_passed = True

    for test_case in problematic_cases:
        segments = segment_text(test_case, TTSConfig.MAX_SEGMENT_LENGTH)

        # Check if any segment contains broken contexts
        broken_segments = []
        for segment in segments:
            # Look for broken patterns (like "1" "25" instead of "1.25")
            if re.search(r'\b\d+\s+\d+\b', segment):  # Numbers split by space
                broken_segments.append(f"Number split: {segment}")
            elif re.search(r'\b[a-zA-Z]+\s+\.(com|org|net|edu)\b', segment):  # Domain split
                broken_segments.append(f"Domain split: {segment}")
            elif re.search(r'\b[a-zA-Z0-9_.-]+\s+\.(md|txt|pdf|doc|jpg|png)\b', segment):  # File extension split
                broken_segments.append(f"File extension split: {segment}")

        if broken_segments:
            print(f"❌ FAILED: '{test_case}'")
            for broken in broken_segments:
                print(f"   {broken}")
            all_passed = False
        else:
            print(f"✅ PASSED: '{test_case}' -> {segments}")

    if all_passed:
        print("\n🎉 All tests passed! Context-aware segmentation is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Context-aware segmentation needs improvement.")

    return all_passed

if __name__ == "__main__":
    import re

    try:
        success = test_context_aware_segmentation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)
