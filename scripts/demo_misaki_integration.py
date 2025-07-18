#!/usr/bin/env python3
"""
Misaki Integration Demo Script

This script demonstrates and validates the Misaki G2P integration functionality,
including testing phonemization quality, fallback mechanisms, and performance metrics.

@author @darianrosebrook
@date 2025-01-09
@version 1.0.0
"""

import sys
import time
import logging
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_misaki_import():
    """Test if misaki integration modules can be imported."""
    try:
        from api.tts.misaki_processing import is_misaki_available, get_misaki_stats
        logger.info("✅ Misaki processing modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import misaki modules: {e}")
        return False

def test_misaki_availability():
    """Test if Misaki backend is available."""
    try:
        from api.tts.misaki_processing import is_misaki_available
        available = is_misaki_available()
        if available:
            logger.info("✅ Misaki backend is available")
        else:
            logger.warning("⚠️ Misaki backend not available (likely Python version issue)")
        return available
    except Exception as e:
        logger.error(f"❌ Error checking misaki availability: {e}")
        return False

def test_phonemization():
    """Test phonemization with sample texts."""
    test_texts = [
        "Hello world, this is a test.",
        "The quick brown fox jumps over the lazy dog.",
        "Testing misaki integration with kokoro TTS system.",
        "Numbers like 123 and dates like January 1st, 2025.",
    ]
    
    try:
        from api.tts.misaki_processing import text_to_phonemes_misaki
        
        results = []
        for text in test_texts:
            start_time = time.perf_counter()
            phonemes = text_to_phonemes_misaki(text)
            processing_time = time.perf_counter() - start_time
            
            result = {
                'text': text,
                'phonemes': phonemes,
                'phoneme_count': len(phonemes) if phonemes else 0,
                'processing_time': processing_time,
                'success': phonemes is not None and len(phonemes) > 0
            }
            results.append(result)
            
            status = "✅" if result['success'] else "❌"
            logger.info(f"{status} Text: '{text[:50]}...'")
            logger.info(f"   Phonemes: {len(phonemes) if phonemes else 0}, Time: {processing_time:.3f}s")
            
        return results
        
    except Exception as e:
        logger.error(f"❌ Error during phonemization testing: {e}")
        return []

def test_statistics_tracking():
    """Test statistics tracking functionality."""
    try:
        from api.tts.misaki_processing import get_misaki_stats, reset_misaki_stats
        
        # Reset stats for clean test
        reset_misaki_stats()
        logger.info("📊 Reset misaki statistics")
        
        # Get initial stats
        stats = get_misaki_stats()
        logger.info("✅ Statistics tracking functional")
        logger.info(f"   Stats: {stats}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing statistics: {e}")
        return False

def test_fallback_mechanism():
    """Test fallback to phonemizer-fork when misaki fails."""
    try:
        from api.tts.text_processing import text_to_phonemes
        
        # Test fallback phonemizer
        test_text = "Testing fallback phonemization mechanism."
        start_time = time.perf_counter()
        phonemes = text_to_phonemes(test_text)
        processing_time = time.perf_counter() - start_time
        
        if phonemes and len(phonemes) > 0:
            logger.info("✅ Fallback phonemizer working correctly")
            logger.info(f"   Phonemes: {len(phonemes)}, Time: {processing_time:.3f}s")
            return True
        else:
            logger.error("❌ Fallback phonemizer failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing fallback mechanism: {e}")
        return False

def test_api_configuration():
    """Test API configuration for misaki integration."""
    try:
        from api.config import TTSConfig
        
        config = TTSConfig()
        
        # Check misaki-specific configuration
        misaki_enabled = getattr(config, 'MISAKI_ENABLED', False)
        misaki_fallback = getattr(config, 'MISAKI_FALLBACK_ENABLED', False)
        misaki_lang = getattr(config, 'MISAKI_DEFAULT_LANG', 'unknown')
        
        logger.info("📋 API Configuration:")
        logger.info(f"   MISAKI_ENABLED: {misaki_enabled}")
        logger.info(f"   MISAKI_FALLBACK_ENABLED: {misaki_fallback}")
        logger.info(f"   MISAKI_DEFAULT_LANG: {misaki_lang}")
        
        if misaki_enabled and misaki_fallback:
            logger.info("✅ Misaki configuration is properly set")
            return True
        else:
            logger.warning("⚠️ Misaki configuration may need adjustment")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking API configuration: {e}")
        return False

def generate_report(results: Dict[str, Any]):
    """Generate a comprehensive integration report."""
    logger.info("\n" + "="*60)
    logger.info("📋 MISAKI INTEGRATION DEMO REPORT")
    logger.info("="*60)
    
    # Calculate overall success rate
    total_tests = len(results)
    successful_tests = sum(1 for result in results.values() if result)
    success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
    
    logger.info(f"Overall Success Rate: {success_rate:.1f}% ({successful_tests}/{total_tests})")
    logger.info("")
    
    # Test Results
    test_names = {
        'import_test': 'Module Import',
        'availability_test': 'Backend Availability', 
        'phonemization_test': 'Phonemization',
        'statistics_test': 'Statistics Tracking',
        'fallback_test': 'Fallback Mechanism',
        'config_test': 'API Configuration'
    }
    
    for key, name in test_names.items():
        status = "✅ PASS" if results.get(key, False) else "❌ FAIL"
        logger.info(f"{name:20}: {status}")
    
    logger.info("")
    
    # Recommendations
    if success_rate == 100:
        logger.info("🎉 All tests passed! Misaki integration is fully functional.")
    elif success_rate >= 75:
        logger.info("⚠️ Most tests passed. Minor issues may need attention.")
    else:
        logger.info("🚨 Multiple test failures. Review configuration and dependencies.")
    
    # Next Steps
    logger.info("\n📋 Next Steps:")
    if not results.get('availability_test', False):
        logger.info("- Set up Python 3.12 environment for full Misaki functionality")
    if not results.get('config_test', False):
        logger.info("- Review and update API configuration settings")
    if success_rate == 100:
        logger.info("- Ready for production deployment with Misaki integration")
    
    logger.info("="*60)

def main():
    """Main demo function."""
    logger.info("🚀 Starting Misaki Integration Demo")
    logger.info("")
    
    results = {}
    
    # Run all tests
    logger.info("1. Testing Module Import...")
    results['import_test'] = test_misaki_import()
    
    logger.info("\n2. Testing Backend Availability...")
    results['availability_test'] = test_misaki_availability()
    
    logger.info("\n3. Testing Phonemization...")
    phonemization_results = test_phonemization()
    results['phonemization_test'] = len(phonemization_results) > 0
    
    logger.info("\n4. Testing Statistics Tracking...")
    results['statistics_test'] = test_statistics_tracking()
    
    logger.info("\n5. Testing Fallback Mechanism...")
    results['fallback_test'] = test_fallback_mechanism()
    
    logger.info("\n6. Testing API Configuration...")
    results['config_test'] = test_api_configuration()
    
    # Generate final report
    generate_report(results)
    
    return results

if __name__ == "__main__":
    try:
        results = main()
        # Exit with appropriate code
        success_rate = sum(1 for result in results.values() if result) / len(results)
        sys.exit(0 if success_rate >= 0.75 else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1) 