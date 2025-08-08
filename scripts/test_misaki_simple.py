#!/usr/bin/env python3
"""
Simple test to isolate the Misaki issue.

@author: @darianrosebrook
@date: 2025-08-06
"""
import os
import sys
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_misaki_direct():
    """Test Misaki directly without the wrapper."""
    try:
        from misaki import en
        
        # Create G2P instance
        g2p = en.G2P(trf=False, british=False, fallback=None)
        
        # Test with the problematic text
        test_text = "Hello world, this is a test of the Misaki G2P engine."
        logger.info(f"Testing with text: '{test_text}'")
        
        result = g2p(test_text)
        logger.info(f"Raw result: {result}")
        logger.info(f"Result type: {type(result)}")
        
        if hasattr(result, '__iter__'):
            for i, item in enumerate(result):
                logger.info(f"  Item {i}: {item} (type: {type(item)})")
        
        # Extract phonemes
        phonemes, tokens = result[:2]
        logger.info(f"Extracted phonemes: {phonemes}")
        
        # Convert to list
        phoneme_list = list(phonemes.replace(' ', ''))
        logger.info(f"Phoneme list: {phoneme_list}")
        
        return phoneme_list
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_misaki_wrapper():
    """Test the Misaki wrapper function."""
    try:
        from api.tts.misaki_processing import text_to_phonemes_misaki
        
        test_text = "Hello world, this is a test of the Misaki G2P engine."
        logger.info(f"Testing wrapper with text: '{test_text}'")
        
        result = text_to_phonemes_misaki(test_text)
        logger.info(f"Wrapper result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Run the tests."""
    logger.info("Starting simple Misaki tests")
    
    # Test direct Misaki
    logger.info("\n=== Direct Misaki Test ===")
    direct_result = test_misaki_direct()
    
    # Test wrapper
    logger.info("\n=== Wrapper Test ===")
    wrapper_result = test_misaki_wrapper()
    
    # Compare results
    logger.info("\n=== Results ===")
    logger.info(f"Direct result: {direct_result}")
    logger.info(f"Wrapper result: {wrapper_result}")
    
    if direct_result and wrapper_result:
        logger.info("✅ Both tests completed successfully")
    else:
        logger.warning("⚠️ Some tests failed")
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    main()

