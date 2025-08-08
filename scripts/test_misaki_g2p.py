#!/usr/bin/env python3
"""
Test script to verify Misaki G2P output with example text.

This script tests the Misaki G2P engine with the example text to check
if we're getting the expected output, which might help diagnose the
truncation issue.

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
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Test if Misaki is available
try:
    from api.tts.misaki_processing import text_to_phonemes_misaki
    misaki_available = True
    logger.info("Misaki module available from api.tts.misaki_processing")
except ImportError:
    misaki_available = False
    logger.warning("Misaki module not available in api.tts.misaki_processing")

# Example text from Misaki documentation
EXAMPLE_TEXT = '[Misaki](/misˈɑki/) is a G2P engine designed for [Kokoro](/kˈOkəɹO/) models.'
EXPECTED_OUTPUT = "misˈɑki ɪz ə ʤˈitəpˈi ˈɛnʤən dəzˈInd fɔɹ kˈOkəɹO mˈɑdᵊlz."

# Washing machine instructions text that was truncated
WASHING_TEXT = """Cycle for normal, regular, or typical
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

def test_misaki_example():
    """Test Misaki with the example text from documentation."""
    logger.info("Testing Misaki with example text from documentation")
    
    if not misaki_available:
        try:
            # Try to import directly
            from misaki import en
            logger.info("Imported misaki.en directly")
            
            # Create G2P instance
            g2p = en.G2P(trf=False, british=False, fallback=None)
            logger.info("Created G2P instance")
            
            # Process the example text
            phonemes, tokens = g2p(EXAMPLE_TEXT)
            logger.info(f"Generated phonemes: {phonemes}")
            logger.info(f"Expected phonemes: {EXPECTED_OUTPUT}")
            logger.info(f"Match: {phonemes == EXPECTED_OUTPUT}")
            
            # Process the washing text
            logger.info("\nTesting with washing machine instructions:")
            phonemes, tokens = g2p(WASHING_TEXT)
            logger.info(f"Generated {len(phonemes)} characters of phonemes")
            logger.info(f"First 50 chars: {phonemes[:50]}")
            logger.info(f"Last 50 chars: {phonemes[-50:]}")
            
            # Check if it includes the problematic part
            if "water temperature" in WASHING_TEXT and "water temperature" not in phonemes:
                logger.warning("⚠️ 'water temperature' not found in phonemes!")
            
            if "appropriate for your" in WASHING_TEXT and "appropriate for your" not in phonemes:
                logger.warning("⚠️ 'appropriate for your' not found in phonemes!")
                
        except ImportError:
            logger.error("Misaki not available for direct import")
            return False
        except Exception as e:
            logger.error(f"Error testing Misaki directly: {e}")
            return False
    else:
        try:
            # Use the internal function
            phonemes = text_to_phonemes_misaki(EXAMPLE_TEXT)
            phoneme_str = "".join(phonemes)
            logger.info(f"Generated phonemes: {phoneme_str}")
            logger.info(f"Expected phonemes: {EXPECTED_OUTPUT}")
            
            # Process the washing text
            logger.info("\nTesting with washing machine instructions:")
            phonemes = text_to_phonemes_misaki(WASHING_TEXT)
            phoneme_str = "".join(phonemes)
            logger.info(f"Generated {len(phoneme_str)} characters of phonemes")
            logger.info(f"First 50 chars: {phoneme_str[:50]}")
            logger.info(f"Last 50 chars: {phoneme_str[-50:]}")
            
            # Check if it includes the problematic part
            if "water temperature" in WASHING_TEXT and "water temperature" not in phoneme_str:
                logger.warning("⚠️ 'water temperature' not found in phonemes!")
            
            if "appropriate for your" in WASHING_TEXT and "appropriate for your" not in phoneme_str:
                logger.warning("⚠️ 'appropriate for your' not found in phonemes!")
                
        except Exception as e:
            logger.error(f"Error testing Misaki via internal function: {e}")
            return False
    
    return True

def test_with_line_breaks_removed():
    """Test Misaki with line breaks removed from the washing text."""
    logger.info("\nTesting with line breaks removed:")
    
    # Remove line breaks
    modified_text = WASHING_TEXT.replace("\n", " ")
    logger.info(f"Modified text: {modified_text}")
    
    try:
        if not misaki_available:
            from misaki import en
            g2p = en.G2P(trf=False, british=False, fallback=None)
            phonemes, tokens = g2p(modified_text)
            logger.info(f"Generated {len(phonemes)} characters of phonemes")
            logger.info(f"First 50 chars: {phonemes[:50]}")
            logger.info(f"Last 50 chars: {phonemes[-50:]}")
        else:
            phonemes = text_to_phonemes_misaki(modified_text)
            phoneme_str = "".join(phonemes)
            logger.info(f"Generated {len(phoneme_str)} characters of phonemes")
            logger.info(f"First 50 chars: {phoneme_str[:50]}")
            logger.info(f"Last 50 chars: {phoneme_str[-50:]}")
            
        return True
    except Exception as e:
        logger.error(f"Error testing with modified text: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting Misaki G2P tests")
    
    # Test with example text
    example_success = test_misaki_example()
    
    # Test with modified text
    modified_success = test_with_line_breaks_removed()
    
    # Report results
    if example_success and modified_success:
        logger.info("✅ All tests completed successfully")
    else:
        logger.warning("⚠️ Some tests failed")
    
    logger.info("Tests completed")

if __name__ == "__main__":
    main()

