#!/usr/bin/env python3
"""
Test script to analyze the washing machine instructions text truncation issue.

This script tests the TTS system with the washing machine instructions text
that is being truncated to determine if we need to further increase the
phoneme length limit.

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

# Washing machine instructions text that was truncated
TEST_TEXT = """Cycle for normal, regular, or typical
use for washing up to a full load
of normally soiled cotton clothing.
Choose the Heavy or Extra
Heavy soil level selection and
Warm or Hot water temperature
selection as appropriate for your
clothes load for a higher degree of
cleaning. Incorporates multi-stage
fills and wash periods to provide
optimal fabric care."""

def test_phoneme_processing():
    """Test phoneme processing to check if truncation occurs with current settings."""
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
        logger.warning("⚠️ Text was truncated! Need to increase DEFAULT_MAX_PHONEME_LENGTH.")
        logger.warning(f"Consider increasing DEFAULT_MAX_PHONEME_LENGTH beyond {DEFAULT_MAX_PHONEME_LENGTH}")
        
        # Calculate recommended phoneme length
        recommended_length = original_length + 50  # Add buffer
        recommended_length = ((recommended_length // 128) + 1) * 128  # Round up to next multiple of 128
        logger.info(f"Recommended phoneme length: {recommended_length}")
    else:
        logger.info("✅ Text was processed without truncation - current settings are sufficient.")
    
    return not truncated, original_length, padded_length

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
    logger.info("Starting TTS washing instructions text analysis")
    
    # Run tests
    phoneme_success, original_length, padded_length = test_phoneme_processing()
    segmentation_success = test_text_segmentation()
    
    # Report overall results
    if phoneme_success and segmentation_success:
        logger.info("✅ All tests passed! Current phoneme length settings are sufficient.")
    else:
        logger.warning("⚠️ Phoneme length insufficient for this text.")
        logger.warning(f"Current phoneme length: {DEFAULT_MAX_PHONEME_LENGTH}")
        logger.warning(f"Required phoneme length: {original_length}")
        
        # Recommend new phoneme length setting
        recommended = ((original_length // 128) + 1) * 128  # Round up to next multiple of 128
        logger.info(f"Recommended setting: export KOKORO_MAX_PHONEME_LENGTH={recommended}")
    
    logger.info("Analysis completed.")

if __name__ == "__main__":
    main()

