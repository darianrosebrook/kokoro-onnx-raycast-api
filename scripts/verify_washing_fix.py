#!/usr/bin/env python3
"""
Test script to verify the fix for the washing machine instructions text.

This script tests the TTS system with the washing machine instructions text
to verify that our fix for line breaks and phonemizer issues works correctly.

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
        text_to_phonemes,
        _preprocess_for_phonemizer,
        DEFAULT_MAX_PHONEME_LENGTH
    )
    from api.tts.misaki_processing import text_to_phonemes_misaki
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

def test_preprocessing():
    """Test the preprocessing function with the problematic text."""
    logger.info("Testing preprocessing function")
    
    # Test the preprocessing function
    preprocessed = _preprocess_for_phonemizer(TEST_TEXT)
    logger.info(f"Preprocessed text: '{preprocessed}'")
    
    # Check if problematic parts are preserved
    if "water temperature" in preprocessed:
        logger.info("✅ 'water temperature' preserved in preprocessed text")
    else:
        logger.warning("⚠️ 'water temperature' NOT found in preprocessed text")
        
    if "appropriate for your" in preprocessed:
        logger.info("✅ 'appropriate for your' preserved in preprocessed text")
    else:
        logger.warning("⚠️ 'appropriate for your' NOT found in preprocessed text")
    
    return "water temperature" in preprocessed and "appropriate for your" in preprocessed

def test_phoneme_conversion():
    """Test the phoneme conversion with the problematic text."""
    logger.info("Testing phoneme conversion")
    
    # Convert text to phonemes
    start_time = time.time()
    phonemes = text_to_phonemes(TEST_TEXT)
    processing_time = time.time() - start_time
    
    # Join phonemes for easier analysis
    phoneme_str = "".join(phonemes)
    logger.info(f"Generated {len(phonemes)} phonemes in {processing_time:.4f}s")
    logger.info(f"First 50 chars: {phoneme_str[:50]}")
    logger.info(f"Last 50 chars: {phoneme_str[-50:]}")
    
    # Check for problematic parts in phoneme output
    # We can't directly search for English words in phonemes, but we can check
    # if the phoneme output is long enough to include the entire text
    expected_min_length = len(TEST_TEXT) * 0.75  # Rough estimate
    
    if len(phonemes) >= expected_min_length:
        logger.info(f"✅ Phoneme output length ({len(phonemes)}) is sufficient")
    else:
        logger.warning(f"⚠️ Phoneme output length ({len(phonemes)}) may be too short")
    
    return len(phonemes) >= expected_min_length

def test_misaki_conversion():
    """Test the Misaki G2P conversion with the problematic text."""
    logger.info("Testing Misaki G2P conversion")
    
    try:
        # Convert text using Misaki
        start_time = time.time()
        phonemes = text_to_phonemes_misaki(TEST_TEXT)
        processing_time = time.time() - start_time
        
        # Join phonemes for easier analysis
        phoneme_str = "".join(phonemes)
        logger.info(f"Generated {len(phonemes)} phonemes in {processing_time:.4f}s")
        logger.info(f"First 50 chars: {phoneme_str[:50]}")
        logger.info(f"Last 50 chars: {phoneme_str[-50:]}")
        
        # Check for problematic parts in phoneme output
        expected_min_length = len(TEST_TEXT) * 0.75  # Rough estimate
        
        if len(phonemes) >= expected_min_length:
            logger.info(f"✅ Misaki phoneme output length ({len(phonemes)}) is sufficient")
        else:
            logger.warning(f"⚠️ Misaki phoneme output length ({len(phonemes)}) may be too short")
        
        return len(phonemes) >= expected_min_length
    except Exception as e:
        logger.error(f"Error testing Misaki conversion: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting verification tests for washing machine instructions text")
    logger.info(f"Text length: {len(TEST_TEXT)} characters")
    logger.info(f"Current DEFAULT_MAX_PHONEME_LENGTH: {DEFAULT_MAX_PHONEME_LENGTH}")
    
    # Run tests
    preprocessing_success = test_preprocessing()
    phoneme_success = test_phoneme_conversion()
    misaki_success = test_misaki_conversion()
    
    # Report results
    logger.info("\nTest Results:")
    logger.info(f"  • Preprocessing: {'✅ PASS' if preprocessing_success else '❌ FAIL'}")
    logger.info(f"  • Phoneme Conversion: {'✅ PASS' if phoneme_success else '❌ FAIL'}")
    logger.info(f"  • Misaki Conversion: {'✅ PASS' if misaki_success else '❌ FAIL'}")
    
    if preprocessing_success and phoneme_success and misaki_success:
        logger.info("✅ All tests passed! The fix appears to be working correctly.")
    else:
        logger.warning("⚠️ Some tests failed. The fix may need additional improvements.")
    
    logger.info("Verification completed.")

if __name__ == "__main__":
    main()

