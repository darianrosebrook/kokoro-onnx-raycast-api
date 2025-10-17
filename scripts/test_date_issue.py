#!/usr/bin/env python3
"""
Test script to reproduce the date pronunciation issue mentioned by the user.

The user reported: "Dates come out as 'zero one slash zero two slash twenty five'"
This suggests dates like "01/02/2025" are being pronounced as individual numbers
instead of being treated as a coherent date.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_date_pronunciation():
    """Test various date formats to see how they're handled."""

    from api.tts.text_processing import normalize_for_tts, segment_text
    from api.config import TTSConfig

    test_cases = [
        # Various date formats
        "Today is 01/02/2025",
        "The date is 2025-01-02",
        "Meeting on 12/25/2024",
        "Born on 03.15.1990",
        "Version 1.2.3 released",
        "Price is $1.99",
        "File version.txt",
        "Visit site.com",
        "Email user@domain.com"
    ]

    print("🗓️  Date Pronunciation Test")
    print("=" * 50)

    for test_case in test_cases:
        print(f"\n📝 Input: '{test_case}'")

        # Test normalization
        normalized = normalize_for_tts(test_case)
        print(f"   🔄 Normalized: '{normalized}'")

        # Test segmentation
        segments = segment_text(test_case, TTSConfig.MAX_SEGMENT_LENGTH)
        print(f"   ✂️  Segments: {segments}")

        # Check if any segment contains problematic patterns
        for i, segment in enumerate(segments):
            if re.search(r'\d+/\d+/\d+', segment):
                print(f"   ⚠️  Segment {i} contains date-like pattern: '{segment}'")
            if re.search(r'\d+\.\d+\.\d+', segment):
                print(f"   ⚠️  Segment {i} contains version-like pattern: '{segment}'")

def test_problematic_cases():
    """Test the specific cases mentioned by the user."""

    from api.tts.text_processing import normalize_for_tts, segment_text
    from api.config import TTSConfig

    problematic_cases = [
        "01/02/2025",  # Should be treated as a date
        "1.25",        # Should be treated as a decimal number
        "google.com",  # Should be treated as a domain
        "file.md",     # Should be treated as a filename
        "user@domain.com",  # Should be treated as an email
    ]

    print("\n🎯 Problematic Cases Test")
    print("=" * 50)

    for case in problematic_cases:
        print(f"\n📝 Input: '{case}'")

        # Test normalization
        normalized = normalize_for_tts(case)
        print(f"   🔄 Normalized: '{normalized}'")

        # Test segmentation
        segments = segment_text(case, TTSConfig.MAX_SEGMENT_LENGTH)
        print(f"   ✂️  Segments: {segments}")

        # Analyze the result
        if len(segments) > 1:
            print("   ❌ SPLIT: This input was split into multiple segments")
        else:
            print("   ✅ KEPT: This input was kept as a single segment")

if __name__ == "__main__":
    import re

    test_date_pronunciation()
    test_problematic_cases()

    print("\n" + "=" * 50)
    print("✅ Date pronunciation test completed!")
