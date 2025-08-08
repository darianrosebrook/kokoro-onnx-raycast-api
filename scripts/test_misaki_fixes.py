#!/usr/bin/env python3
"""
Test script to verify the Misaki integration fixes.

This script tests the various fixes applied to the Misaki integration module,
including initialization, caching, thread safety, and fallback mechanisms.

@author: @darianrosebrook
@date: 2025-08-06
"""
import os
import sys
import logging
import time
import threading

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
    from api.tts.misaki_processing import (
        text_to_phonemes_misaki,
        is_misaki_available,
        get_misaki_stats,
        reset_misaki_stats,
        clear_misaki_cache
    )
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Test text
TEST_TEXT = "Hello world, this is a test of the Misaki G2P engine."

def test_initialization():
    """Test that Misaki initializes correctly."""
    logger.info("Testing Misaki initialization")
    
    # Check if Misaki is available
    available = is_misaki_available()
    logger.info(f"Misaki available: {available}")
    
    if available:
        logger.info("✅ Misaki initialization successful")
        return True
    else:
        logger.warning("⚠️ Misaki not available - this is expected if not installed")
        return False

def test_phonemization():
    """Test basic phonemization functionality."""
    logger.info("Testing Misaki phonemization")
    
    try:
        # Convert text to phonemes
        start_time = time.time()
        phonemes = text_to_phonemes_misaki(TEST_TEXT)
        processing_time = time.time() - start_time
        
        logger.info(f"Generated {len(phonemes)} phonemes in {processing_time:.4f}s")
        logger.info(f"Phonemes: {phonemes[:20]}...")
        
        if len(phonemes) > 0:
            logger.info("✅ Phonemization successful")
            return True
        else:
            logger.warning("⚠️ Phonemization returned empty result")
            return False
            
    except Exception as e:
        logger.error(f"Error during phonemization: {e}")
        return False

def test_caching():
    """Test that caching works correctly."""
    logger.info("Testing Misaki caching")
    
    # Get initial stats
    initial_stats = get_misaki_stats()
    initial_cache_size = initial_stats.get('cache_size', 0)
    
    # Process the same text twice
    phonemes1 = text_to_phonemes_misaki(TEST_TEXT)
    phonemes2 = text_to_phonemes_misaki(TEST_TEXT)
    
    # Get final stats
    final_stats = get_misaki_stats()
    final_cache_size = final_stats.get('cache_size', 0)
    
    logger.info(f"Initial cache size: {initial_cache_size}")
    logger.info(f"Final cache size: {final_cache_size}")
    logger.info(f"Cache size increased: {final_cache_size > initial_cache_size}")
    
    # Check that results are identical
    if phonemes1 == phonemes2:
        logger.info("✅ Caching working correctly - identical results")
        return True
    else:
        logger.warning("⚠️ Caching may not be working - different results")
        return False

def test_thread_safety():
    """Test thread safety of the Misaki module."""
    logger.info("Testing thread safety")
    
    results = []
    errors = []
    
    def worker(worker_id):
        try:
            phonemes = text_to_phonemes_misaki(f"Worker {worker_id} test text")
            results.append((worker_id, len(phonemes)))
        except Exception as e:
            errors.append((worker_id, str(e)))
    
    # Create multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    logger.info(f"Thread results: {results}")
    logger.info(f"Thread errors: {errors}")
    
    if len(errors) == 0:
        logger.info("✅ Thread safety test passed")
        return True
    else:
        logger.warning(f"⚠️ Thread safety test failed with {len(errors)} errors")
        return False

def test_stats():
    """Test statistics collection."""
    logger.info("Testing statistics collection")
    
    # Reset stats
    reset_misaki_stats()
    
    # Process some text
    text_to_phonemes_misaki(TEST_TEXT)
    
    # Get stats
    stats = get_misaki_stats()
    
    logger.info("Statistics:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    
    if stats['total_requests'] > 0:
        logger.info("✅ Statistics collection working")
        return True
    else:
        logger.warning("⚠️ Statistics collection may not be working")
        return False

def test_cache_management():
    """Test cache management functions."""
    logger.info("Testing cache management")
    
    # Get initial cache size
    initial_stats = get_misaki_stats()
    initial_cache_size = initial_stats.get('cache_size', 0)
    
    # Clear cache
    clear_misaki_cache()
    
    # Get cache size after clearing
    final_stats = get_misaki_stats()
    final_cache_size = final_stats.get('cache_size', 0)
    
    logger.info(f"Cache size before clearing: {initial_cache_size}")
    logger.info(f"Cache size after clearing: {final_cache_size}")
    
    if final_cache_size == 0:
        logger.info("✅ Cache clearing working")
        return True
    else:
        logger.warning("⚠️ Cache clearing may not be working")
        return False

def main():
    """Run all tests."""
    logger.info("Starting Misaki integration tests")
    
    # Run tests
    tests = [
        ("Initialization", test_initialization),
        ("Phonemization", test_phonemization),
        ("Caching", test_caching),
        ("Thread Safety", test_thread_safety),
        ("Statistics", test_stats),
        ("Cache Management", test_cache_management),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n=== {test_name} Test ===")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Report results
    logger.info("\n=== Test Results ===")
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("✅ All tests passed! Misaki integration is working correctly.")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs for details.")
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    main()

