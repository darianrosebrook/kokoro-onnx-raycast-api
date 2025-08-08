#!/usr/bin/env python3
"""
Test script to verify the fix for TTS truncation issues with long text.

This script tests the TTS system with the specific text that was previously
being truncated to ensure the fix properly handles the entire content.

@author: @darianrosebrook
@date: 2025-08-06
"""
import os
import sys
import logging
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import required modules
try:
    from api.tts.text_processing import (
        preprocess_text_for_inference,
        DEFAULT_MAX_PHONEME_LENGTH,
        segment_text
    )
    from api.config import TTSConfig
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Test text that was previously truncated
TEST_TEXT = """By weaving in these enhancements—automated discovery, composable override APIs, selective non-Tailwind workflows, and robust multi-platform codegen—you'll achieve a next-generation, headless design system strategy on par with Radix UI and Shadcn/ui best practices."""

def test_phoneme_processing():
    """Test phoneme processing to ensure no truncation occurs."""
    logger.info(f"Testing phoneme processing with text length: {len(TEST_TEXT)}")
    logger.info(f"Current DEFAULT_MAX_PHONEME_LENGTH: {DEFAULT_MAX_PHONEME_LENGTH}")
    
    # Process the text
    start_time = time.time()
    result = preprocess_text_for_inference(TEST_TEXT)
    processing_time = time.time() - start_time
    
    # Check for truncation
    original_length = result['original_length']
    padded_length = result['padded_length']
    truncated = result['truncated']
    
    logger.info(f"Phoneme processing results:")
    logger.info(f"  • Original phoneme length: {original_length}")
    logger.info(f"  • Padded phoneme length: {padded_length}")
    logger.info(f"  • Truncated: {truncated}")
    logger.info(f"  • Processing time: {processing_time:.4f}s")
    
    if truncated:
        logger.warning("⚠️ Text was still truncated! The fix may not be sufficient.")
        logger.warning(f"Consider further increasing DEFAULT_MAX_PHONEME_LENGTH beyond {DEFAULT_MAX_PHONEME_LENGTH}")
    else:
        logger.info("✅ Text was processed without truncation - fix successful!")
    
    return not truncated

def test_text_segmentation():
    """Test text segmentation to ensure proper handling of the text."""
    logger.info(f"Testing text segmentation with MAX_SEGMENT_LENGTH: {TTSConfig.MAX_SEGMENT_LENGTH}")
    
    # Segment the text
    segments = segment_text(TEST_TEXT, TTSConfig.MAX_SEGMENT_LENGTH)
    
    logger.info(f"Text segmentation results:")
    logger.info(f"  • Number of segments: {len(segments)}")
    
    for i, segment in enumerate(segments):
        logger.info(f"  • Segment {i+1} length: {len(segment)}")
        logger.info(f"  • Segment {i+1} text: '{segment[:50]}...'")
    
    return len(segments) > 0

def main():
    """Run all tests and report results."""
    logger.info("Starting TTS long text processing tests")
    
    # Run tests
    phoneme_success = test_phoneme_processing()
    segmentation_success = test_text_segmentation()
    
    # Report overall results
    if phoneme_success and segmentation_success:
        logger.info("✅ All tests passed! The fix appears to be working correctly.")
    else:
        logger.warning("⚠️ Some tests failed. The fix may need additional improvements.")
    
    logger.info("Test completed.")

if __name__ == "__main__":
    main()

