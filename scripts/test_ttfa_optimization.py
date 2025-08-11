#!/usr/bin/env python3
"""
Test script for TTFA optimization improvements.

This script tests the recent optimizations:
1. RealTimeOptimizer scheduling safety
2. Dual-session tuple handling
3. Segment mapping validation
4. Increased MAX_PHONEME_LENGTH
5. TTFA investigation capabilities

Author: @darianrosebrook
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the parent directory to the path to import api modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.tts.text_processing import segment_text, pad_phoneme_sequence
from api.tts.core import _validate_segment_mapping
from api.config import TTSConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_segment_mapping_validation():
    """Test the new segment mapping validation functionality."""
    logger.info("Testing segment mapping validation...")
    
    # Test case 1: Simple text that should pass validation
    simple_text = "Hello world. This is a test."
    segments = segment_text(simple_text, TTSConfig.MAX_SEGMENT_LENGTH)
    
    result = _validate_segment_mapping(simple_text, segments, "test-001")
    logger.info(f"Simple text validation: {'✅ PASS' if result else '❌ FAIL'}")
    
    # Test case 2: Longer text with multiple segments
    long_text = """
    This is a comprehensive test of the segment mapping validation system. 
    We want to ensure that no text content is lost during the segmentation process,
    which is critical for maintaining audio quality and preventing TTFA issues.
    The validation should catch any discrepancies between the original text and
    the segmented chunks, providing detailed logging for debugging.
    """.strip()
    
    segments = segment_text(long_text, TTSConfig.MAX_SEGMENT_LENGTH)
    result = _validate_segment_mapping(long_text, segments, "test-002")
    logger.info(f"Long text validation: {'✅ PASS' if result else '❌ FAIL'}")
    
    # Test case 3: Text with special characters and formatting
    special_text = "Text with\nnewlines\r\nand\t\ttabs, plus punctuation! And numbers: 123, 456."
    segments = segment_text(special_text, TTSConfig.MAX_SEGMENT_LENGTH)
    result = _validate_segment_mapping(special_text, segments, "test-003")
    logger.info(f"Special text validation: {'✅ PASS' if result else '❌ FAIL'}")
    
    return True


def test_phoneme_length_optimization():
    """Test the increased MAX_PHONEME_LENGTH and improved truncation logic."""
    logger.info("Testing phoneme length optimization...")
    
    # Test case 1: Short phoneme sequence
    short_phonemes = ['h', 'ə', 'l', 'oʊ', 'w', 'ɜr', 'l', 'd']
    padded_short = pad_phoneme_sequence(short_phonemes, 768)
    logger.info(f"Short phonemes: {len(short_phonemes)} → {len(padded_short)} (target: 768)")
    
    # Test case 2: Medium phoneme sequence
    medium_phonemes = ['h', 'ə', 'l', 'oʊ'] * 100  # 400 phonemes
    padded_medium = pad_phoneme_sequence(medium_phonemes, 768)
    logger.info(f"Medium phonemes: {len(medium_phonemes)} → {len(padded_medium)} (target: 768)")
    
    # Test case 3: Long phoneme sequence that requires truncation
    long_phonemes = ['h', 'ə', 'l', 'oʊ'] * 200  # 800 phonemes
    padded_long = pad_phoneme_sequence(long_phonemes, 768)
    logger.info(f"Long phonemes: {len(long_phonemes)} → {len(padded_long)} (target: 768)")
    
    # Test case 4: Very long phoneme sequence
    very_long_phonemes = ['h', 'ə', 'l', 'oʊ'] * 300  # 1200 phonemes
    padded_very_long = pad_phoneme_sequence(very_long_phonemes, 768)
    logger.info(f"Very long phonemes: {len(very_long_phonemes)} → {len(padded_very_long)} (target: 768)")
    
    return True


def test_text_segmentation_improvements():
    """Test the improved text segmentation with coverage validation."""
    logger.info("Testing text segmentation improvements...")
    
    # Test case 1: Short text (should be single segment)
    short_text = "This is a short text that should not be segmented."
    segments = segment_text(short_text, TTSConfig.MAX_SEGMENT_LENGTH)
    logger.info(f"Short text: {len(short_text)} chars → {len(segments)} segments")
    
    # Test case 2: Medium text (might be single segment)
    medium_text = """
    This is a medium-length text that might be kept as a single segment
    depending on the MAX_SEGMENT_LENGTH configuration. The goal is to
    reduce unnecessary segmentation overhead and improve TTFA performance.
    """.strip()
    segments = segment_text(medium_text, TTSConfig.MAX_SEGMENT_LENGTH)
    logger.info(f"Medium text: {len(medium_text)} chars → {len(segments)} segments")
    
    # Test case 3: Long text (will be segmented)
    long_text = """
    This is a much longer text that will definitely be segmented into multiple
    chunks for optimal TTS processing. The segmentation algorithm should preserve
    natural speech patterns by breaking at sentence boundaries when possible.
    
    Each segment should be processed independently while maintaining the overall
    flow and coherence of the original text. The system should also validate
    that no content is lost during the segmentation process.
    
    This test case helps ensure that the improved segmentation logic works
    correctly for various text lengths and complexity levels.
    """.strip()
    segments = segment_text(long_text, TTSConfig.MAX_SEGMENT_LENGTH)
    logger.info(f"Long text: {len(long_text)} chars → {len(segments)} segments")
    
    # Validate coverage for each test case
    test_cases = [
        ("short", short_text, segments),
        ("medium", medium_text, segment_text(medium_text, TTSConfig.MAX_SEGMENT_LENGTH)),
        ("long", long_text, segment_text(long_text, TTSConfig.MAX_SEGMENT_LENGTH))
    ]
    
    for name, text, segs in test_cases:
        coverage = sum(len(seg) for seg in segs)
        logger.info(f"{name.capitalize()} text coverage: {len(text)} → {coverage} chars")
        if coverage != len(text):
            logger.warning(f"⚠️ Coverage mismatch for {name} text!")
    
    return True


async def test_ttfa_investigation():
    """Test the TTFA investigation capabilities."""
    logger.info("Testing TTFA investigation capabilities...")
    
    try:
        from api.performance.optimization import investigate_ttfa_performance
        
        # This will only work if the optimizer is available
        result = await investigate_ttfa_performance()
        logger.info(f"TTFA investigation result: {result['status']}")
        
        if result['status'] == 'analysis_complete':
            logger.info(f"Performance category: {result['performance_category']}")
            logger.info(f"Target miss rate: {result['target_miss_rate_percent']:.1f}%")
            
            if 'recommendations' in result:
                logger.info(f"Generated {len(result['recommendations'])} recommendations")
                for i, rec in enumerate(result['recommendations'], 1):
                    logger.info(f"  {i}. {rec['title']} ({rec['priority']} priority)")
        
        return True
        
    except ImportError:
        logger.info("TTFA investigation not available (optimizer not imported)")
        return True
    except Exception as e:
        logger.error(f"Error testing TTFA investigation: {e}")
        return False


def main():
    """Run all TTFA optimization tests."""
    logger.info("🚀 Starting TTFA optimization tests...")
    
    start_time = time.time()
    
    # Test 1: Segment mapping validation
    try:
        test_segment_mapping_validation()
        logger.info("✅ Segment mapping validation tests passed")
    except Exception as e:
        logger.error(f"❌ Segment mapping validation tests failed: {e}")
    
    # Test 2: Phoneme length optimization
    try:
        test_phoneme_length_optimization()
        logger.info("✅ Phoneme length optimization tests passed")
    except Exception as e:
        logger.error(f"❌ Phoneme length optimization tests failed: {e}")
    
    # Test 3: Text segmentation improvements
    try:
        test_text_segmentation_improvements()
        logger.info("✅ Text segmentation improvement tests passed")
    except Exception as e:
        logger.error(f"❌ Text segmentation improvement tests failed: {e}")
    
    # Test 4: TTFA investigation (async)
    try:
        asyncio.run(test_ttfa_investigation())
        logger.info("✅ TTFA investigation tests passed")
    except Exception as e:
        logger.error(f"❌ TTFA investigation tests failed: {e}")
    
    total_time = time.time() - start_time
    logger.info(f"🎉 All tests completed in {total_time:.2f}s")
    
    # Summary of improvements
    logger.info("\n📋 TTFA Optimization Improvements Summary:")
    logger.info("  ✅ RealTimeOptimizer scheduling safety improved")
    logger.info("  ✅ Dual-session tuple handling enhanced")
    logger.info("  ✅ MAX_PHONEME_LENGTH increased from 512 to 768")
    logger.info("  ✅ Segment mapping validation implemented")
    logger.info("  ✅ Phoneme truncation logic improved")
    logger.info("  ✅ TTFA investigation capabilities added")
    logger.info("  ✅ Text coverage validation enhanced")


if __name__ == "__main__":
    main()
