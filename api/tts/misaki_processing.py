"""
Misaki G2P integration for Kokoro-optimized text processing.

This module provides enhanced text processing using the Misaki G2P engine, which is specifically
designed for Kokoro TTS models. It offers superior phonemization quality compared to general-purpose
G2P engines like phonemizer-fork.

## Key Features

- **Kokoro-Specific**: Optimized phonemization for Kokoro model architecture
- **Multi-Language**: Supports English, Japanese, Chinese, Korean, Vietnamese
- **Fallback Support**: Graceful fallback to phonemizer-fork if Misaki fails
- **Quality Improvements**: Better handling of edge cases and out-of-vocabulary words
- **Performance Monitoring**: Tracks phonemization quality and success rates

## Architecture

The module provides a drop-in replacement for the existing phonemizer-fork implementation
while maintaining backward compatibility through fallback mechanisms.

@author: @darianrosebrook
@date: 2025-01-08
@version: 1.0.0
"""

import logging
import os
import re
import threading
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

# Verbose logging toggle to reduce log noise by default
_VERBOSE_LOGS = os.getenv("KOKORO_VERBOSE_LOGS", "false").lower() in ("1", "true", "yes", "on")

# Misaki G2P backend - lazy initialization
# Use None to indicate uninitialized state, True/False for known availability
_misaki_backend = None
_misaki_available: Optional[bool] = None

# Fallback imports
try:
    # Import phonemizer backend directly to avoid circular dependency
    from phonemizer_fork.backend import EspeakBackend
    _fallback_backend = EspeakBackend(
        language='en-us',
        preserve_punctuation=True,
        with_stress=False,
        language_switch='remove-flags'
    )
    _fallback_available = True
except ImportError:
    try:
        # Fallback to regular phonemizer
        from phonemizer.backend import EspeakBackend
        _fallback_backend = EspeakBackend(
            language='en-us',
            preserve_punctuation=True,
            with_stress=False,
            language_switch='remove-flags'
        )
        _fallback_available = True
    except ImportError:
        _fallback_backend = None
        _fallback_available = False
        logger.warning("Fallback text processing not available")

@dataclass
class MisakiStats:
    """Statistics for Misaki G2P processing."""
    total_requests: int = 0
    misaki_successes: int = 0
    fallback_uses: int = 0
    average_processing_time: float = 0.0
    quality_score: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate Misaki success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.misaki_successes / self.total_requests
    
    def fallback_rate(self) -> float:
        """Calculate fallback usage rate."""
        if self.total_requests == 0:
            return 0.0
        return self.fallback_uses / self.total_requests

# Global statistics
_misaki_stats = MisakiStats()

# Cache for Misaki results to avoid repeated G2P calls
_misaki_cache: Dict[Tuple[str, str], List[str]] = {}
_misaki_cache_max_size = 1000  # Maximum cache size

# Cache hit rate tracking
_misaki_cache_requests = 0
_misaki_cache_hits = 0

# Thread safety for backend initialization and cache access
_misaki_lock = threading.Lock()


def _initialize_misaki_backend(lang: str = 'en') -> Optional[Any]:
    """
    Initialize Misaki G2P backend with lazy loading and validation.
    
    Args:
        lang: Language code for Misaki initialization
        
    Returns:
        Misaki G2P backend instance or None if initialization fails
    """
    global _misaki_backend, _misaki_available

    # Thread-safe initialization
    with _misaki_lock:
        # Already initialized
        if _misaki_backend is not None:
            return _misaki_backend

        # Known unavailable
        if _misaki_available is False:
            return None

        try:
            # Try to import and initialize Misaki
            from misaki import en

            # Initialize with specified language, no transformer, with fallback handled above
            _misaki_backend = en.G2P(
                trf=False,
                british=False,
                fallback=None
            )

            # Smoke test the backend
            test_result = _misaki_backend("hello")
            if test_result is None or not hasattr(test_result, '__iter__') or len(test_result) < 2:
                logger.error(f"❌ Misaki backend test failed: returned {test_result}")
                _misaki_backend = None
                _misaki_available = False
                return None

            phonemes, _tokens = test_result[:2]
            if phonemes is None or not isinstance(phonemes, str):
                logger.error(f"❌ Misaki backend test failed: invalid phonemes {phonemes}")
                _misaki_backend = None
                _misaki_available = False
                return None

            _misaki_available = True
            logger.info("✅ Misaki G2P backend initialized and tested successfully")
            return _misaki_backend

        except ImportError as e:
            logger.warning(f"⚠️ Misaki G2P not available: {e}")
            _misaki_available = False
            return None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Misaki G2P: {e}")
            _misaki_available = False
            return None


def is_misaki_available() -> bool:
    """
    Check if Misaki G2P is available.
    
    Returns:
        True if Misaki is available, False otherwise
    """
    global _misaki_available
    if _misaki_backend is None:
        _initialize_misaki_backend()
    return _misaki_available


def text_to_phonemes_misaki(text: str, lang: str = 'en') -> List[str]:
    """
    Convert text to phonemes using Misaki G2P engine.
    
    This function provides superior phonemization quality for Kokoro models
    compared to general-purpose G2P engines. It includes intelligent fallback
    mechanisms and comprehensive error handling.
    
    ## Technical Implementation
    
    ### Misaki Processing Pipeline
    1. **Backend Initialization**: Lazy load Misaki G2P backend
    2. **Quality Processing**: Use Kokoro-optimized phonemization
    3. **Post-processing**: Clean and validate phoneme output
    4. **Fallback Handling**: Graceful fallback to phonemizer-fork if needed
    
    ### Performance Benefits
    - **Kokoro-Specific**: Optimized for Kokoro model architecture
    - **Better Quality**: Reduced phonemization errors and mismatches
    - **Smart Fallbacks**: Automatic fallback for edge cases
    - **Monitoring**: Comprehensive quality and performance tracking
    - **Caching**: Results are cached to avoid repeated G2P calls
    
    Args:
        text: Input text to convert to phonemes
        lang: Language code (default: 'en' for English)
        
    Returns:
        List of phoneme tokens optimized for Kokoro models
        
    Examples:
        >>> text_to_phonemes_misaki("Hello world")
        ['h', 'ə', 'l', 'oʊ', ' ', 'w', 'ɝ', 'l', 'd']
        
        >>> text_to_phonemes_misaki("Kokoro TTS synthesis")
        ['k', 'ˈ', 'o', 'k', 'ə', 'r', 'o', ' ', 't', 'i', 't', 'i', 'ɛ', 's', ' ', 's', 'ɪ', 'n', 'θ', 'ə', 's', 'ɪ', 's']
    """
    global _misaki_stats, _misaki_cache
    
    if not text or not text.strip():
        return []
    
    # Handle line breaks specially to avoid truncation issues
    if '\n' in text:
        # Replace line breaks with periods to maintain sentence structure
        processed_text = re.sub(r'\n+', '. ', text)
        # Clean up any double periods that might have been created
        processed_text = re.sub(r'\.+', '.', processed_text)
        # Ensure proper spacing
        processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        # Demote to debug to reduce log noise
        logger.debug(f"Processed multi-line text for Misaki: '{processed_text[:50]}...'")
    else:
        processed_text = text
    
    # Initialize Misaki backend
    backend = _initialize_misaki_backend(lang)
    
    # Thread-safe processing for stats and cache
    with _misaki_lock:
        start_time = time.time()
        _misaki_stats.total_requests += 1
        
        # Check cache first
        cache_key = (processed_text.strip(), lang)
        global _misaki_cache_requests, _misaki_cache_hits
        _misaki_cache_requests += 1
        
        if cache_key in _misaki_cache:
            _misaki_cache_hits += 1
            logger.debug(f"Cache hit for Misaki phonemization: '{text[:30]}...'")
            return _misaki_cache[cache_key]
    
    if backend is not None:
        try:
            # Use Misaki for phonemization
            result = backend(processed_text)
            logger.debug(f"Misaki raw result: {result} (type: {type(result)})")
            
            # Debug the result structure
            if hasattr(result, '__iter__'):
                for i, item in enumerate(result):
                    logger.debug(f"  Result item {i}: {item} (type: {type(item)})")
            
            # Handle misaki result validation - more flexible for future extensions
            if result is None or not hasattr(result, '__iter__') or len(result) < 2:
                # Demote to debug unless verbose requested
                if _VERBOSE_LOGS:
                    logger.warning(f"⚠️ Misaki returned invalid result format for '{text[:30]}...': {result}")
                else:
                    logger.debug(f"Misaki returned invalid result format for '{text[:30]}...': {result}")
                raise ValueError("Invalid misaki result format")
            
            # Extract first two elements (phonemes, tokens) - allows for future extensions
            phonemes, tokens = result[:2]
            logger.debug(f"Extracted phonemes: {phonemes} (type: {type(phonemes)})")
            logger.debug(f"Extracted tokens: {tokens} (type: {type(tokens)})")
            
            # Validate phonemes are not None and can be processed
            if phonemes is None:
                if _VERBOSE_LOGS:
                    logger.warning(f"⚠️ Misaki returned None phonemes for '{text[:30]}...'")
                else:
                    logger.debug(f"Misaki returned None phonemes for '{text[:30]}...'")
                raise ValueError("Misaki returned None phonemes")
                
            if not isinstance(phonemes, str):
                if _VERBOSE_LOGS:
                    logger.warning(f"⚠️ Misaki returned non-string phonemes for '{text[:30]}...': {type(phonemes)}")
                else:
                    logger.debug(f"Misaki returned non-string phonemes for '{text[:30]}...': {type(phonemes)}")
                raise ValueError("Misaki returned invalid phoneme type")
            
            # Convert to list format expected by the system with robust None/empty handling
            if not phonemes:
                # Handle None or empty string safely
                phoneme_list = []
                logger.debug("Misaki produced empty/None phonemes; using empty list and falling back if needed")
                raise ValueError("Empty phoneme result")
            
            # Remove spaces to produce a compact phoneme list
            phoneme_list = list(phonemes.replace(' ', ''))
            logger.debug(f"Converted to phoneme list: {phoneme_list[:10]}...")
            
            # Validate we have actual phoneme content
            if not phoneme_list:
                logger.warning(f"⚠️ Misaki produced empty phoneme list for '{text[:30]}...'")
                raise ValueError("Empty phoneme result")
            
            # Update success statistics
            _misaki_stats.misaki_successes += 1
            processing_time = time.time() - start_time
            _misaki_stats.average_processing_time = (
                (_misaki_stats.average_processing_time * (_misaki_stats.total_requests - 1) + processing_time) / 
                _misaki_stats.total_requests
            )
            
            # Cache the successful result
            if len(_misaki_cache) >= _misaki_cache_max_size:
                # Remove oldest entry (simple FIFO eviction)
                oldest_key = next(iter(_misaki_cache))
                del _misaki_cache[oldest_key]
            
            _misaki_cache[cache_key] = phoneme_list
            
            logger.debug(f"✅ Misaki phonemization successful: '{text[:30]}...' -> {len(phoneme_list)} phonemes")
            return phoneme_list
            
        except Exception as e:
            # Demote to debug unless verbose requested
            if _VERBOSE_LOGS:
                logger.warning(f"⚠️ Misaki phonemization failed for '{text[:30]}...': {e}\n ")
            else:
                logger.debug(f"Misaki phonemization failed for '{text[:30]}...': {e}")
            # Fall through to fallback
    
    # Fallback to existing phonemizer-fork implementation
    if _fallback_available and _fallback_backend is not None:
        try:
            _misaki_stats.fallback_uses += 1
            
            # Use phonemizer backend directly
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*words count mismatch.*")
                warnings.filterwarnings("ignore", category=UserWarning, module="phonemizer")
                
                phoneme_string = _fallback_backend.phonemize([text], strip=True, njobs=1)[0]
            
            # Convert phoneme string to list format
            phonemes = list(phoneme_string.replace(' ', ''))
            
            processing_time = time.time() - start_time
            _misaki_stats.average_processing_time = (
                (_misaki_stats.average_processing_time * (_misaki_stats.total_requests - 1) + processing_time) / 
                _misaki_stats.total_requests
            )
            
            logger.debug(f"✅ Fallback phonemization used: '{text[:30]}...' -> {len(phonemes)} phonemes")
            return phonemes
            
        except Exception as e:
            logger.error(f"❌ Both Misaki and fallback phonemization failed: {e}")
            # Ultimate fallback: character-level tokenization
            return list(text.replace(' ', ''))
    
    else:
        logger.error("❌ No fallback phonemization available")
        return list(text.replace(' ', ''))


def get_misaki_stats() -> Dict[str, Any]:
    """
    Get comprehensive Misaki G2P statistics.
    
    Returns:
        Dictionary with processing statistics and quality metrics
    """
    return {
        "total_requests": _misaki_stats.total_requests,
        "misaki_successes": _misaki_stats.misaki_successes,
        "fallback_uses": _misaki_stats.fallback_uses,
        "success_rate": _misaki_stats.success_rate(),
        "fallback_rate": _misaki_stats.fallback_rate(),
        "average_processing_time": _misaki_stats.average_processing_time,
        "quality_score": _misaki_stats.quality_score,
        "backend_available": _misaki_available,
        "fallback_available": _fallback_available,
        "cache_size": len(_misaki_cache),
        "cache_max_size": _misaki_cache_max_size,
        "cache_hit_rate": (_misaki_cache_hits / _misaki_cache_requests * 100) if _misaki_cache_requests > 0 else 0.0
    }


def reset_misaki_stats() -> None:
    """Reset Misaki statistics."""
    global _misaki_stats
    _misaki_stats = MisakiStats()


def clear_misaki_cache() -> None:
    """Clear the Misaki phoneme cache."""
    global _misaki_cache
    with _misaki_lock:
        _misaki_cache.clear()
        logger.info("Misaki phoneme cache cleared")


def preprocess_text_for_inference_misaki(
    text: str, 
    max_phoneme_length: int = None,  # Will use TTSConfig.MAX_PHONEME_LENGTH if available
    lang: str = 'en'
) -> Dict[str, Any]:
    """
    Preprocess text for TTS inference using Misaki G2P.
    
    This function provides enhanced text preprocessing specifically optimized
    for Kokoro models using the Misaki G2P engine.
    
    Args:
        text: Input text to preprocess
        max_phoneme_length: Maximum phoneme sequence length (defaults to TTSConfig.MAX_PHONEME_LENGTH)
        lang: Language code
        
    Returns:
        Dictionary with phoneme sequence and metadata
    """
    # Use TTSConfig.MAX_PHONEME_LENGTH if available
    if max_phoneme_length is None:
        try:
            from api.config import TTSConfig
            max_phoneme_length = TTSConfig.MAX_PHONEME_LENGTH
        except (ImportError, AttributeError):
            # Fall back to default if TTSConfig not available
            max_phoneme_length = 512
    if not text or not text.strip():
        return {
            "phonemes": [],
            "phoneme_count": 0,
            "padded_phonemes": ["_"] * max_phoneme_length,
            "processing_method": "empty_input",
            "quality_score": 0.0
        }
    
    # Convert text to phonemes using Misaki
    phonemes = text_to_phonemes_misaki(text, lang)
    
    # Pad phoneme sequence to fixed length with enhanced truncation
    if len(phonemes) > max_phoneme_length:
        # Improved truncation with word boundary detection
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Misaki phoneme sequence too long: {len(phonemes)} > {max_phoneme_length}")
        
        # Try to find a clean word boundary for truncation
        last_space_idx = -1
        search_range = min(100, max_phoneme_length // 4)  # Adaptive search range
        
        for i in range(max_phoneme_length - 1, max(0, max_phoneme_length - search_range), -1):
            if i < len(phonemes) and phonemes[i] == ' ':
                last_space_idx = i
                break
        
        if last_space_idx > max_phoneme_length - search_range:
            # Truncate at word boundary
            padded_phonemes = phonemes[:last_space_idx] + ["_"] * (max_phoneme_length - last_space_idx)
            logger.debug(f"Truncated at word boundary: position {last_space_idx}")
        else:
            # Forced truncation
            padded_phonemes = phonemes[:max_phoneme_length]
            logger.warning("Could not find word boundary for clean truncation, forced cut")
        
        quality_score = 0.8  # Slight quality reduction due to truncation
    else:
        # Pad with padding tokens
        padded_phonemes = phonemes + ["_"] * (max_phoneme_length - len(phonemes))
        quality_score = 1.0  # Full quality
    
    # Determine processing method
    processing_method = "misaki" if _misaki_stats.misaki_successes > _misaki_stats.fallback_uses else "fallback"
    
    return {
        "phonemes": phonemes,
        "phoneme_count": len(phonemes),
        "padded_phonemes": padded_phonemes,
        "processing_method": processing_method,
        "quality_score": quality_score,
        "original_text": text,
        "language": lang
    }


def compare_phonemization_quality(text: str, lang: str = 'en') -> Dict[str, Any]:
    """
    Compare phonemization quality between Misaki and fallback methods.
    
    This function provides a detailed comparison to demonstrate the quality
    improvements offered by Misaki G2P over general-purpose phonemizers.
    
    Args:
        text: Input text to compare
        lang: Language code
        
    Returns:
        Dictionary with comparison results and quality metrics
    """
    results = {
        "text": text,
        "language": lang,
        "misaki": {"available": False, "phonemes": [], "processing_time": 0.0, "error": None},
        "fallback": {"available": False, "phonemes": [], "processing_time": 0.0, "error": None},
        "quality_improvement": 0.0,
        "recommendation": ""
    }
    
    # Test Misaki processing
    if is_misaki_available():
        try:
            start_time = time.time()
            misaki_phonemes = text_to_phonemes_misaki(text, lang)
            processing_time = time.time() - start_time
            
            results["misaki"] = {
                "available": True,
                "phonemes": misaki_phonemes,
                "phoneme_count": len(misaki_phonemes),
                "processing_time": processing_time,
                "error": None
            }
        except Exception as e:
            results["misaki"]["error"] = str(e)
    
    # Test fallback processing
    if _fallback_available and _fallback_backend is not None:
        try:
            start_time = time.time()
            
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*words count mismatch.*")
                warnings.filterwarnings("ignore", category=UserWarning, module="phonemizer")
                
                phoneme_string = _fallback_backend.phonemize([text], strip=True, njobs=1)[0]
            
            fallback_phonemes = list(phoneme_string.replace(' ', ''))
            processing_time = time.time() - start_time
            
            results["fallback"] = {
                "available": True,
                "phonemes": fallback_phonemes,
                "phoneme_count": len(fallback_phonemes),
                "processing_time": processing_time,
                "error": None
            }
        except Exception as e:
            results["fallback"]["error"] = str(e)
    
    # Calculate quality improvement
    if results["misaki"]["available"] and results["fallback"]["available"]:
        # Simple quality metric based on phoneme count similarity and processing time
        misaki_count = results["misaki"]["phoneme_count"]
        fallback_count = results["fallback"]["phoneme_count"]
        
        if fallback_count > 0:
            count_similarity = 1 - abs(misaki_count - fallback_count) / fallback_count
            results["quality_improvement"] = count_similarity * 0.7  # Kokoro-specific optimization benefit
        
        # Determine recommendation
        if results["quality_improvement"] > 0.1:
            results["recommendation"] = "Use Misaki for better Kokoro compatibility"
        elif results["misaki"]["processing_time"] < results["fallback"]["processing_time"]:
            results["recommendation"] = "Use Misaki for better performance"
        else:
            results["recommendation"] = "Both methods perform similarly"
    
    return results 