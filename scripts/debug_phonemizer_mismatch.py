#!/usr/bin/env python3
"""
Debug script to investigate phonemizer word count mismatch issues.

This script analyzes the washing machine instructions text to understand
why the phonemizer is reporting word count mismatches and how this might
be causing truncation in TTS output.

@author: @darianrosebrook
@date: 2025-08-06
"""
import os
import sys
import logging
import re

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
        normalize_for_tts,
        clean_text,
        _preprocess_for_phonemizer,
        _get_phonemizer_backend
    )
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

def count_words(text):
    """Count words in text using a simple space-based approach."""
    return len(text.split())

def count_words_advanced(text):
    """Count words using a more advanced regex approach."""
    # This regex matches words more accurately by handling punctuation
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text)
    return len(words)

def analyze_text_structure(text):
    """Analyze the structure of the text for potential issues."""
    lines = text.split('\n')
    logger.info(f"Text has {len(lines)} lines:")
    
    for i, line in enumerate(lines):
        word_count = count_words(line)
        logger.info(f"  Line {i+1}: {word_count} words, {len(line)} chars: '{line}'")
    
    # Check for special characters that might cause issues
    special_chars = re.findall(r'[^a-zA-Z0-9\s.,!?;:\'\"\n]', text)
    if special_chars:
        unique_special = set(special_chars)
        logger.info(f"Special characters found: {', '.join(unique_special)}")
    
    # Check for unusual whitespace
    unusual_whitespace = re.findall(r'[^\S\n]+', text)
    if unusual_whitespace:
        logger.info(f"Unusual whitespace found: {len(unusual_whitespace)} instances")

def test_phonemizer_directly():
    """Test the phonemizer directly to see how it handles the text."""
    # Clean and normalize the text first
    normalized = normalize_for_tts(TEST_TEXT)
    cleaned = clean_text(normalized)
    preprocessed = _preprocess_for_phonemizer(cleaned)
    
    logger.info("Testing phonemizer with different text preparations:")
    
    # Test with original text
    logger.info("\nTesting with original text:")
    word_count_original = count_words(TEST_TEXT)
    logger.info(f"Original text word count: {word_count_original}")
    
    try:
        # Use the internal text_to_phonemes function
        phonemes = text_to_phonemes(TEST_TEXT)
        logger.info(f"Phoneme count: {len(phonemes)}")
        logger.info(f"First 20 phonemes: {phonemes[:20]}")
        logger.info(f"Last 20 phonemes: {phonemes[-20:] if len(phonemes) >= 20 else phonemes}")
    except Exception as e:
        logger.error(f"Error testing phonemizer: {e}")
    
    # Test with preprocessed text
    logger.info("\nTesting with preprocessed text:")
    word_count_preprocessed = count_words(preprocessed)
    logger.info(f"Preprocessed text word count: {word_count_preprocessed}")
    
    try:
        # Use the internal text_to_phonemes function
        phonemes = text_to_phonemes(preprocessed)
        logger.info(f"Phoneme count: {len(phonemes)}")
        logger.info(f"First 20 phonemes: {phonemes[:20]}")
        logger.info(f"Last 20 phonemes: {phonemes[-20:] if len(phonemes) >= 20 else phonemes}")
        
        # Check if the phonemes include the end of the text
        last_words = " ".join(preprocessed.split()[-10:])  # Last 10 words
        logger.info(f"Last 10 words of preprocessed text: '{last_words}'")
        
        # Convert phonemes back to a string representation for comparison
        phoneme_str = "".join(phonemes)
        logger.info(f"Last 50 characters of phoneme string: '{phoneme_str[-50:]}'")
    except Exception as e:
        logger.error(f"Error testing phonemizer: {e}")

def test_line_by_line():
    """Test phonemizer line by line to identify problematic lines."""
    lines = TEST_TEXT.split('\n')
    
    logger.info("\nTesting phonemizer line by line:")
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
            
        word_count = count_words(line)
        
        try:
            # Use the internal text_to_phonemes function
            phonemes = text_to_phonemes(line)
            
            logger.info(f"Line {i+1}: Words: {word_count}, Phonemes: {len(phonemes)}")
            logger.info(f"  Original: '{line}'")
            logger.info(f"  First phonemes: {phonemes[:10]}")
            logger.info(f"  Last phonemes: {phonemes[-10:] if len(phonemes) >= 10 else phonemes}")
            
            # Check for specific lines that might be causing issues
            if i == 5:  # Line 6 with "Warm or Hot water temperature"
                logger.info(f"  DETAILED ANALYSIS OF LINE 6: '{line}'")
                # Check each word
                words = line.split()
                for j, word in enumerate(words):
                    word_phonemes = text_to_phonemes(word)
                    logger.info(f"    Word {j+1} '{word}': {len(word_phonemes)} phonemes: {word_phonemes}")
            
            if i == 6:  # Line 7 with "selection as appropriate for your"
                logger.info(f"  DETAILED ANALYSIS OF LINE 7: '{line}'")
                # Check each word
                words = line.split()
                for j, word in enumerate(words):
                    word_phonemes = text_to_phonemes(word)
                    logger.info(f"    Word {j+1} '{word}': {len(word_phonemes)} phonemes: {word_phonemes}")
        except Exception as e:
            logger.error(f"Error processing line {i+1}: {e}")

def test_modified_text():
    """Test with modified versions of the text to find workarounds."""
    # Try with newlines replaced by spaces
    modified_text = TEST_TEXT.replace('\n', ' ')
    
    logger.info("\nTesting with newlines replaced by spaces:")
    word_count = count_words(modified_text)
    logger.info(f"Modified text word count: {word_count}")
    
    try:
        backend = _get_phonemizer_backend()
        from phonemizer_fork import phonemize
        phonemized = phonemize(modified_text, backend=backend)
        phoneme_words = count_words(phonemized)
        logger.info(f"Phonemized text word count: {phoneme_words}")
        logger.info(f"Word count match: {word_count == phoneme_words}")
    except Exception as e:
        logger.error(f"Error testing modified text: {e}")

def main():
    """Run all debug tests."""
    logger.info("Starting phonemizer word count mismatch debug")
    
    # Analyze text structure
    logger.info("\n=== Text Structure Analysis ===")
    analyze_text_structure(TEST_TEXT)
    
    # Test phonemizer directly
    logger.info("\n=== Direct Phonemizer Testing ===")
    test_phonemizer_directly()
    
    # Test line by line
    logger.info("\n=== Line-by-Line Testing ===")
    test_line_by_line()
    
    # Test with modified text
    logger.info("\n=== Modified Text Testing ===")
    test_modified_text()
    
    logger.info("\nDebug completed.")

if __name__ == "__main__":
    main()
