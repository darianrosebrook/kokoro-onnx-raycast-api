#!/usr/bin/env python3
"""
Debug script to understand what Misaki is returning.

This script tests Misaki directly to see what format it returns.

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

def test_misaki_directly():
    """Test Misaki directly to see what it returns."""
    try:
        from misaki import en
        
        # Create G2P instance
        g2p = en.G2P(trf=False, british=False, fallback=None)
        
        # Test with simple text
        test_text = "hello world"
        logger.info(f"Testing with text: '{test_text}'")
        
        result = g2p(test_text)
        logger.info(f"Raw result: {result}")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result length: {len(result) if hasattr(result, '__len__') else 'N/A'}")
        
        if hasattr(result, '__iter__'):
            for i, item in enumerate(result):
                logger.info(f"  Item {i}: {item} (type: {type(item)})")
        
        return result
        
    except ImportError as e:
        logger.error(f"Misaki not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error testing Misaki: {e}")
        return None

def main():
    """Run the debug test."""
    logger.info("Starting Misaki debug test")
    
    result = test_misaki_directly()
    
    if result is not None:
        logger.info("✅ Misaki test completed successfully")
    else:
        logger.warning("⚠️ Misaki test failed")
    
    logger.info("Debug test completed.")

if __name__ == "__main__":
    main()

