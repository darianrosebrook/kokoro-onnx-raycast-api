#!/usr/bin/env python3
"""
Test script to check behavior when there are NO sentence boundaries.

This tests cases where text should NOT be split because there are no
clear sentence boundaries (period + space + capital letter).
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_no_sentence_boundaries():
    """Test cases that should NOT be split because there are no sentence boundaries."""

    from api.tts.text_processing import normalize_for_tts, segment_text
    from api.config import TTSConfig

    # Cases that should NOT be split (no sentence boundaries)
    no_boundary_cases = [
        "Price is 1.25",           # Number with decimal
        "Visit google.com",        # URL/domain
        "Open file.md",            # File with extension
        "Contact user@domain.com", # Email address
        "Version 1.2.3",           # Version number
        "File size 1.5MB",         # Number with unit
        "Score 95.7%",             # Percentage
        "Address 192.168.1.1",     # IP address
    ]

    # Cases that SHOULD be split (clear sentence boundaries)
    with_boundary_cases = [
        "Price is 1.25. Please visit google.com",      # Clear sentence boundary
        "Version 1.2.3. This is the latest release",   # Clear sentence boundary
        "File is ready. Open file.md to view",        # Clear sentence boundary
    ]

    print("🚫 No Sentence Boundaries Test")
    print("=" * 50)

    print("\n❌ Cases that SHOULD NOT be split:")
    for case in no_boundary_cases:
        normalized = normalize_for_tts(case)
        segments = segment_text(case, TTSConfig.MAX_SEGMENT_LENGTH)

        if len(segments) == 1:
            print(f"   ✅ '{case}' → {segments} (correctly kept as single segment)")
        else:
            print(f"   ❌ '{case}' → {segments} (incorrectly split)")

    print("\n✅ Cases that SHOULD be split:")
    for case in with_boundary_cases:
        normalized = normalize_for_tts(case)
        segments = segment_text(case, TTSConfig.MAX_SEGMENT_LENGTH)

        if len(segments) > 1:
            print(f"   ✅ '{case}' → {segments} (correctly split)")
        else:
            print(f"   ❌ '{case}' → {segments} (should have been split)")

def test_isolated_contexts():
    """Test isolated contexts that should definitely not be split."""

    from api.tts.text_processing import normalize_for_tts, segment_text
    from api.config import TTSConfig

    isolated_cases = [
        "1.25",
        "google.com",
        "file.md",
        "user@domain.com",
        "1.2.3",
        "3.14159",
        "example.org",
        "document.txt",
        "test@example.com",
    ]

    print("\n🎯 Isolated Contexts Test")
    print("=" * 50)

    for case in isolated_cases:
        normalized = normalize_for_tts(case)
        segments = segment_text(case, TTSConfig.MAX_SEGMENT_LENGTH)

        if len(segments) == 1:
            print(f"   ✅ '{case}' → {segments} (correctly preserved)")
        else:
            print(f"   ❌ '{case}' → {segments} (incorrectly split)")

if __name__ == "__main__":
    test_no_sentence_boundaries()
    test_isolated_contexts()

    print("\n" + "=" * 50)
    print("✅ No sentence boundaries test completed!")
