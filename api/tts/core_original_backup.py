"""
Core TTS functionality for the Kokoro-ONNX API.

This module handles the core TTS functionality, including:
- Text processing and segmentation
- Audio generation
- Streaming audio

@author: @darianrosebrook
@date: 2025-07-08
@version: 1.0.0
@license: MIT
@copyright: 2025 Darian Rosebrook
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""

import asyncio
import io
import logging
import re
import struct
import time
from typing import AsyncGenerator, Dict, Optional, Tuple, List, Set

import numpy as np
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from kokoro_onnx import Kokoro

from api.config import TTSConfig
from api.model.loader import (
    get_model,
    get_model_status,
    get_active_provider,
    get_dual_session_manager,
)
from api.performance.stats import update_inference_stats, update_endpoint_performance_stats
from api.tts.text_processing import (
    segment_text,
    preprocess_text_for_inference,
    get_phoneme_cache_stats,
    clear_phoneme_cache,
)
from api.tts.audio_variation_handler import get_variation_handler
import threading
import os

logger = logging.getLogger(__name__)

# Thread-safe cache for Kokoro model instances
_model_cache: Dict[str, Kokoro] = {}
_model_cache_lock = threading.Lock()

# Enhanced inference pipeline caching for common requests
# Reference: DEPENDENCY_RESEARCH.md section 5.2
import hashlib
from functools import lru_cache
from typing import Tuple, Optional, Dict, Any

# Inference result cache with TTL-like behavior
_inference_cache: Dict[str, Tuple[np.ndarray, float, str]] = {}

# Micro-cache for primer phonemes and initial inference to reduce TTFB
_primer_microcache: Dict[str, Tuple[np.ndarray, float]] = {}
_primer_microcache_ttl_s: float = 300.0  # 5 minutes
_primer_microcache_hits: int = 0
_primer_microcache_misses: int = 0


def _get_primer_cache_key(text: str, voice: str, speed: float, lang: str) -> str:
    return hashlib.md5(
        f"primer:{text[:700]}:{voice}:{speed}:{lang}".encode("utf-8")
    ).hexdigest()


def _get_cached_primer(key: str) -> Optional[np.ndarray]:
    entry = _primer_microcache.get(key)
    if not entry:
        try:
            globals()["_primer_microcache_misses"] += 1
        except Exception:
            pass
        return None
    samples, ts = entry
    if (time.time() - ts) > _primer_microcache_ttl_s:
        try:
            del _primer_microcache[key]
        except Exception:
            pass
        try:
            globals()["_primer_microcache_misses"] += 1
        except Exception:
            pass
        return None
    try:
        globals()["_primer_microcache_hits"] += 1
    except Exception:
        pass
    return samples


def _put_cached_primer(key: str, samples: np.ndarray) -> None:
    # Keep micro-cache size bounded
    try:
        if len(_primer_microcache) > 64:
            # remove oldest ~8 entries
            for k in list(_primer_microcache.keys())[:8]:
                _primer_microcache.pop(k, None)
        _primer_microcache[key] = (samples, time.time())
    except Exception:
        pass


def get_primer_microcache_stats() -> Dict[str, Any]:
    """
    Return primer micro-cache telemetry for status endpoints.
    """
    try:
        size = len(_primer_microcache)
    except Exception:
        size = 0
    hits = globals().get("_primer_microcache_hits", 0)
    misses = globals().get("_primer_microcache_misses", 0)
    total = hits + misses
    hit_rate = (hits / total) * 100 if total > 0 else 0.0
    return {
        "entries": size,
        "ttl_seconds": _primer_microcache_ttl_s,
        "hits": hits,
        "misses": misses,
        "hit_rate_percent": hit_rate,
    }


_inference_cache_lock = threading.Lock()
_inference_cache_max_size = 1000  # Maximum number of cached results
_inference_cache_ttl = 3600  # Cache TTL in seconds (1 hour)


def _get_cached_model(provider: str) -> Kokoro:
    """
    Retrieves a cached Kokoro model instance or creates a new one if not available.
    This is thread-safe.
    """
    with _model_cache_lock:
        if provider not in _model_cache:
            logger.info(f"Creating new Kokoro model instance for provider: {provider}")
            _model_cache[provider] = Kokoro(
                model_path=TTSConfig.MODEL_PATH,
                voices_path=TTSConfig.VOICES_PATH,
                providers=[provider],
            )
        return _model_cache[provider]


def _create_inference_cache_key(text: str, voice: str, speed: float, lang: str) -> str:
    """
    Creates a unique cache key for inference results.

    Args:
        text: Input text
        voice: Voice identifier
        speed: Speech speed multiplier
        lang: Language code

    Returns:
        Unique cache key string
    """
    # Create a hash of the input parameters
    cache_input = f"{text}|{voice}|{speed:.3f}|{lang}"
    return hashlib.md5(cache_input.encode("utf-8")).hexdigest()


def _get_cached_inference(cache_key: str) -> Optional[Tuple[np.ndarray, str]]:
    """
    Retrieves cached inference result if available and not expired.

    Args:
        cache_key: Cache key for the inference result

    Returns:
        Tuple of (audio_array, provider) if cached, None otherwise
    """
    with _inference_cache_lock:
        if cache_key in _inference_cache:
            audio_array, timestamp, provider = _inference_cache[cache_key]

            # Check if cache entry is still valid
            if time.time() - timestamp < _inference_cache_ttl:
                logger.debug(f"Cache hit for key: {cache_key[:8]}...")
                return audio_array, provider
            else:
                # Remove expired entry
                del _inference_cache[cache_key]
                logger.debug(f"Cache expired for key: {cache_key[:8]}...")

        return None


def _cache_inference_result(cache_key: str, audio_array: np.ndarray, provider: str):
    """
    Caches inference result with timestamp and memory-efficient storage.

    Args:
        cache_key: Cache key for the inference result
        audio_array: Generated audio array
        provider: Provider used for generation
    """
    with _inference_cache_lock:
        # Check cache size and evict oldest entries if needed
        if len(_inference_cache) >= _inference_cache_max_size:
            # Remove oldest entries (simple FIFO eviction)
            oldest_keys = list(_inference_cache.keys())[:50]  # Remove 50 oldest
            for key in oldest_keys:
                del _inference_cache[key]
            logger.debug(f"Evicted {len(oldest_keys)} old cache entries")

        # Memory-efficient storage: compress audio data if large
        audio_to_cache = audio_array
        if audio_array.size > 10000:  # Compress if > 10k samples
            # Use float32 instead of float64 for memory efficiency
            audio_to_cache = audio_array.astype(np.float32)

        # Cache the result with timestamp
        _inference_cache[cache_key] = (audio_to_cache, time.time(), provider)
        logger.debug(f"Cached inference result for key: {cache_key[:8]}...")


def cleanup_inference_cache():
    """
    Cleans up expired inference cache entries to free memory.

    This function implements memory-efficient cache cleanup to prevent
    memory leaks and optimize performance.
    """
    with _inference_cache_lock:
        current_time = time.time()
        expired_keys = []

        for key, (_, timestamp, _) in _inference_cache.items():
            if current_time - timestamp >= _inference_cache_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del _inference_cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        # Force garbage collection if we cleaned up many entries
        if len(expired_keys) > 100:
            import gc

            gc.collect()
            logger.debug("Forced garbage collection after cache cleanup")


def get_inference_cache_stats() -> Dict[str, Any]:
    """
    Returns statistics about the inference cache.

    Returns:
        Dictionary with cache statistics
    """
    with _inference_cache_lock:
        current_time = time.time()
        valid_entries = 0
        expired_entries = 0

        for _, (_, timestamp, _) in _inference_cache.items():
            if current_time - timestamp < _inference_cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "total_entries": len(_inference_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_size_mb": len(_inference_cache) * 0.1,  # Rough estimate
            "hit_rate": getattr(get_inference_cache_stats, "_hit_rate", 0.0),
            "miss_rate": getattr(get_inference_cache_stats, "_miss_rate", 0.0),
        }


def should_use_phoneme_preprocessing() -> bool:
    """
    Determine if phoneme preprocessing should be enabled.

    Returns:
        bool: True if phoneme preprocessing is enabled and beneficial
    """
    # Disable phoneme preprocessing for streaming requests (lower latency)
    # to reduce first-chunk latency. This check can be extended to consider request context.

    try:
        from api.config import TTSConfig

        # Check if we're in a high-performance mode where we want to skip preprocessing
        # for faster TTFA (this can be controlled via environment variables)
        if hasattr(TTSConfig, "FAST_STREAMING_MODE"):
            return not TTSConfig.FAST_STREAMING_MODE

        # Default behavior: use preprocessing for quality
        return True

    except ImportError:
        return False


# Fast segment processing for simple text
def _is_simple_segment(text: str) -> bool:
    """
    Determine if a text segment is simple enough for fast processing.

    This is used during streaming to identify segments that can bypass
    heavy preprocessing and get audio chunks out faster.
    """
    if not text or len(text.strip()) > 150:
        return False

    # Simple criteria: basic ASCII text without complex patterns
    import re

    # Check for complex patterns
    complex_patterns = [
        r"\d{4}-\d{2}-\d{2}",  # Dates
        r"\d{2}:\d{2}:\d{2}",  # Times
        r"[^\x00-\x7F]",  # Non-ASCII
        r"[{}[\]()@#$%^&*+=<>]",  # Special chars
        r"\d+\.\d+",  # Decimal numbers
    ]

    for pattern in complex_patterns:
        if re.search(pattern, text):
            return False

    return True


def get_tts_processing_stats() -> Dict[str, Any]:
    """
    Get comprehensive TTS processing statistics including phoneme cache performance.

    Returns:
        Dict[str, Any]: Combined statistics from inference cache and phoneme cache
    """
    try:
        # Get inference cache stats
        inference_stats = get_inference_cache_stats()

        # Get phoneme cache stats
        phoneme_stats = get_phoneme_cache_stats()

        # Combine statistics
        combined_stats = {
            "inference_cache": inference_stats,
            "phoneme_cache": phoneme_stats,
            "phoneme_preprocessing_enabled": should_use_phoneme_preprocessing(),
            "active_provider": get_active_provider(),
        }

        return combined_stats

    except Exception as e:
        logger.warning(f"Could not get TTS processing stats: {e}")
        return {
            "inference_cache": {},
            "phoneme_cache": {},
            "phoneme_preprocessing_enabled": False,
            "active_provider": "Unknown",
            "error": str(e),
        }


def _generate_audio_segment(
    idx: int, text: str, voice: str, speed: float, lang: str, no_cache: bool = False
) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Generates a single audio segment with enhanced caching and thread safety.

    This function implements inference pipeline caching for common requests
    to avoid redundant processing and improve performance.

    ## Phoneme Preprocessing Integration

    This function now includes optional phoneme preprocessing for CoreML optimization:
    - **Phoneme Conversion**: Converts text to phoneme sequences for consistency
    - **Tensor Shape Padding**: Ensures consistent tensor shapes for CoreML graph reuse
    - **Cache Integration**: Phoneme preprocessing results are cached for performance
    - **Fallback Strategy**: Falls back to original text if phoneme processing fails

    Reference: DEPENDENCY_RESEARCH.md section 5.2
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short (minimum 3 characters required)"

    try:
        # Phoneme preprocessing for CoreML optimization
        processed_text = text
        preprocessing_info = ""

        if should_use_phoneme_preprocessing():
            try:
                # Preprocess text for optimal inference with consistent tensor shapes
                preprocessing_result = preprocess_text_for_inference(text)
                processed_text = preprocessing_result["normalized_text"]

                # Log preprocessing stats for monitoring
                original_length = preprocessing_result["original_length"]
                padded_length = preprocessing_result["padded_length"]
                cache_hit = preprocessing_result["cache_hit"]
                truncated = preprocessing_result["truncated"]

                preprocessing_info = f"phonemes:{original_length}→{padded_length}"
                if cache_hit:
                    preprocessing_info += " (cached)"
                if truncated:
                    preprocessing_info += " (truncated)"
                    # Log detailed truncation warning for debugging
                    logger.warning(
                        f"[{idx}] Text truncated during phoneme processing: original {original_length} > max {padded_length}"
                    )
                    logger.warning(
                        f"[{idx}] Truncated text may lose content at the end. Consider increasing DEFAULT_MAX_PHONEME_LENGTH"
                    )

                logger.debug(f"[{idx}] Phoneme preprocessing: {preprocessing_info}")

            except Exception as e:
                logger.warning(
                    f"[{idx}] Phoneme preprocessing failed: {e}, falling back to original text"
                )
                processed_text = text
                preprocessing_info = "fallback"

        # Create cache key for this inference (using processed text for better cache efficiency)
        cache_key = _create_inference_cache_key(processed_text, voice, speed, lang)

        # Check cache first (unless bypassed)
        if not no_cache:
            cached_result = _get_cached_inference(cache_key)
            if cached_result is not None:
                samples, provider = cached_result
                logger.debug(f"[{idx}] Using cached audio for: {processed_text[:50]}...")
                # Update cache hit statistics
                from api.performance.stats import update_inference_stats
                update_inference_stats(0.001, provider)  # Minimal time for cache hit
                cache_info = f"{provider} (cached)"
                if preprocessing_info:
                    cache_info += f" [{preprocessing_info}]"
                return idx, samples, cache_info
        else:
            logger.info(f"[{idx}] 🚫 CACHE BYPASS ENABLED - forcing fresh generation for: {processed_text[:50]}...")

        # Cache miss - generate new audio
        # Use dual session manager for concurrent processing
        dual_session_manager = get_dual_session_manager()

        if dual_session_manager:
            # Use dual session manager for optimal concurrent processing
            logger.debug(
                f"[{idx}] Generating audio using dual session manager for: {processed_text[:50]}..."
            )
            start_time = time.perf_counter()

            try:
                samples, _ = dual_session_manager.process_segment_concurrent(
                    processed_text, voice, speed, lang
                )

                inference_time = time.perf_counter() - start_time

                # Get session utilization stats for logging
                utilization_stats = dual_session_manager.get_utilization_stats()
                active_sessions = utilization_stats.get("concurrent_segments_active", 0)

                # Determine which session was likely used based on complexity
                complexity = dual_session_manager.calculate_segment_complexity(
                    processed_text
                )
                if complexity > 0.7:
                    likely_session = (
                        "ANE"
                        if utilization_stats["sessions_available"]["ane"]
                        else "GPU"
                    )
                else:
                    likely_session = (
                        "GPU"
                        if utilization_stats["sessions_available"]["gpu"]
                        else "ANE"
                    )

                from api.performance.stats import update_inference_stats
                update_inference_stats(
                    inference_time, f"DualSession-{likely_session}"
                )

                if samples is not None and samples.size > 0:
                    # Cache the successful result
                    _cache_inference_result(
                        cache_key, samples, f"DualSession-{likely_session}"
                    )

                    result_info = (
                        f"DualSession-{likely_session} (concurrent:{active_sessions})"
                    )
                    if preprocessing_info:
                        result_info += f" [{preprocessing_info}]"

                    logger.info(
                        f"[{idx}] Segment processed in {inference_time:.4f}s using {result_info}"
                    )
                    return idx, samples, result_info
                else:
                    logger.warning(
                        f"[{idx}] Dual session manager returned empty audio for text: {processed_text[:50]}..."
                    )
                    return idx, None, "Empty audio returned"

            except Exception as e:
                logger.warning(
                    f"[{idx}] Dual session processing failed: {e}, falling back to single model"
                )
                # Fall back to single model processing
                pass

        # Fallback to single model processing
        provider = get_active_provider()
        local_model = _get_cached_model(provider)

        logger.debug(
            f"[{idx}] Generating audio using single model for: {processed_text[:50]}..."
        )
        start_time = time.perf_counter()

        result = local_model.create(processed_text, voice, speed, lang)
        
        # Handle different return formats
        if isinstance(result, tuple):
            if len(result) >= 2:
                samples = result[0]  # First element is always samples
            else:
                samples = result[0]  # Single element tuple
        else:
            samples = result  # Direct return

        inference_time = time.perf_counter() - start_time
        from api.performance.stats import update_inference_stats
        update_inference_stats(inference_time, provider)

        if samples is not None and samples.size > 0:
            # Cache the successful result
            _cache_inference_result(cache_key, samples, provider)

            result_info = f"{provider}"
            if preprocessing_info:
                result_info += f" [{preprocessing_info}]"

            logger.info(
                f"[{idx}] Segment processed in {inference_time:.4f}s using {result_info}"
            )
            return idx, samples, result_info
        else:
            logger.warning(
                f"[{idx}] TTS model returned empty audio for text: {processed_text[:50]}..."
            )
            return idx, None, "Empty audio returned"

    except Exception as e:
        logger.error(
            f"[{idx}] TTS generation failed for text '{text[:50]}...': {e}",
            exc_info=True,
        )
        return idx, None, str(e)


def _fast_generate_audio_segment(
    idx: int, text: str, voice: str, speed: float, lang: str, no_cache: bool = False
) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Fast audio segment generation for simple text with minimal preprocessing.

    This bypasses heavy phoneme preprocessing for simple text to achieve
    faster TTFA performance. Used for the first segment in streaming requests.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short (minimum 3 characters required)"

    try:
        # Skip heavy preprocessing for simple text
        processed_text = text.strip()

        # Create simple cache key
        import hashlib

        cache_key = hashlib.md5(
            f"{processed_text}:{voice}:{speed}:{lang}".encode()
        ).hexdigest()[:16]

        # Check inference cache (unless bypassed)
        if not no_cache:
            cached_result = _get_cached_inference(cache_key)
            if cached_result is not None:
                samples, provider = cached_result
                logger.debug(f"[{idx}] Fast path cache hit for: {processed_text[:50]}...")
                return idx, samples, f"{provider} (fast-cached)"
        else:
            logger.info(f"[{idx}] 🚫 CACHE BYPASS ENABLED - forcing fresh generation for: {processed_text[:50]}...")

        # Generate audio directly without preprocessing
        # Use dual session manager if available
        dual_session_manager = get_dual_session_manager()

        if dual_session_manager:
            logger.debug(
                f"[{idx}] Fast generation using dual session manager: {processed_text[:50]}..."
            )
            start_time = time.perf_counter()

            try:
                ds_result = dual_session_manager.process_segment_concurrent(
                    processed_text, voice, speed, lang
                )

                inference_time = time.perf_counter() - start_time

                # DualSessionManager returns (samples, metadata)
                if isinstance(ds_result, tuple) and len(ds_result) >= 1:
                    samples = ds_result[0]
                    metadata = ds_result[1] if len(ds_result) >= 2 else {}
                    logger.debug(f"[{idx}] DualSession returned: samples type={type(samples)}, metadata={metadata}")
                else:
                    samples = ds_result
                    logger.debug(f"[{idx}] DualSession returned direct result: type={type(samples)}")

                # CRITICAL FIX: Ensure samples is a proper numpy array
                if samples is not None:
                    try:
                        # Handle different possible return types from corrupted sessions
                        if isinstance(samples, (int, float)):
                            logger.error(f"[{idx}] DualSession returned scalar ({type(samples)}): {samples} - this indicates session corruption")
                            samples = None
                        elif hasattr(samples, '__len__') and len(samples) == 0:
                            logger.error(f"[{idx}] DualSession returned empty array")
                            samples = None
                        else:
                            samples = np.asarray(samples, dtype=np.float32)
                            if samples.ndim == 0:  # Scalar array
                                logger.error(f"[{idx}] DualSession returned scalar array: {samples} - converting to None")
                                samples = None
                            elif samples.size <= 1:  # Array with only 1 element
                                logger.error(f"[{idx}] DualSession returned array with size {samples.size}: {samples} - this is too small for audio")
                                samples = None
                            else:
                                logger.debug(f"[{idx}] DualSession samples converted successfully: shape={samples.shape}, size={samples.size}")
                    except Exception as e:
                        logger.error(f"[{idx}] Failed to convert DualSession samples to numpy array: {e}")
                        samples = None

                if samples is not None and getattr(samples, "size", 0) > 0:
                    # Cache the successful result
                    _cache_inference_result(cache_key, samples, "DualSession-Fast")

                    logger.info(
                        f"[{idx}] Fast segment processed in {inference_time:.4f}s using DualSession-Fast"
                    )
                    return idx, samples, "DualSession-Fast"
                else:
                    logger.warning(f"[{idx}] Fast dual session returned empty audio")

            except Exception as e:
                logger.warning(f"[{idx}] Fast dual session failed: {e}")
                # Fall through to single model

        # Fallback to single model
        provider = get_active_provider()
        local_model = _get_cached_model(provider)

        logger.debug(
            f"[{idx}] Fast generation using single model: {processed_text[:50]}..."
        )
        start_time = time.perf_counter()

        result = local_model.create(processed_text, voice, speed, lang)
        
        # Handle different return formats
        if isinstance(result, tuple):
            if len(result) >= 2:
                samples = result[0]  # First element is always samples
            else:
                samples = result[0]  # Single element tuple
        else:
            samples = result  # Direct return

        # CRITICAL FIX: Validate single model results too
        logger.debug(f"[{idx}] Single model returned: type={type(samples)}, value={samples if isinstance(samples, (int, float)) else 'array'}")
        
        # Check if the single model is also corrupted
        if isinstance(samples, (int, float)):
            logger.error(f"[{idx}] CRITICAL: Single model returned scalar ({type(samples)}): {samples} - TTS model is completely corrupted!")
            logger.error(f"[{idx}] This indicates fundamental model corruption. Returning empty audio to prevent crash.")
            return idx, None, "Model corrupted - returned scalar"
        
        # Ensure proper numpy array
        if samples is not None:
            try:
                samples = np.asarray(samples, dtype=np.float32)
                if samples.ndim == 0:  # Scalar array
                    logger.error(f"[{idx}] Single model returned scalar array: {samples}")
                    return idx, None, "Model returned scalar array"
                elif samples.size <= 1:
                    logger.error(f"[{idx}] Single model returned array with size {samples.size}: too small for audio")
                    return idx, None, "Audio too small"
                else:
                    logger.debug(f"[{idx}] Single model samples validated: shape={samples.shape}, size={samples.size}")
            except Exception as e:
                logger.error(f"[{idx}] Failed to convert single model samples: {e}")
                return idx, None, "Array conversion failed"

        inference_time = time.perf_counter() - start_time
        from api.performance.stats import update_inference_stats
        update_inference_stats(inference_time, f"{provider}-Fast")

        if samples is not None and samples.size > 0:
            # Cache the result
            _cache_inference_result(cache_key, samples, f"{provider}-Fast")

            logger.info(
                f"[{idx}] Fast segment processed in {inference_time:.4f}s using {provider}-Fast"
            )
            return idx, samples, f"{provider}-Fast"
        else:
            logger.warning(f"[{idx}] Fast processing returned empty audio")
            return idx, None, "Empty audio returned"

    except Exception as e:
        logger.error(f"[{idx}] Fast TTS generation failed: {e}", exc_info=True)
        return idx, None, str(e)


async def stream_tts_audio(
    text: str, voice: str, speed: float, lang: str, format: str, request: Request, no_cache: bool = False
) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously generates and streams TTS audio.
    This function processes text in segments, generates audio for each in parallel,
    and streams the resulting audio bytes back to the client as they become available.
    """
    request_id = request.headers.get("x-request-id", "no-id")
    cache_status = "🚫 BYPASSED" if no_cache else "✅ ENABLED"
    logger.info(
        f"[{request_id}] Starting stream request: voice='{voice}', speed={speed}, format='{format}', cache={cache_status}, text='{text[:30]}...'"
    )

    # Record request for workload analysis
    start_time = time.perf_counter()
    concurrent_requests = 1  # TODO: Implement actual concurrent request tracking

    model_loaded = get_model_status()
    if not model_loaded:
        logger.error(f"[{request_id}] TTS model not ready, raising 503 error.")
        raise HTTPException(status_code=503, detail="TTS model not ready.")

    # Segment text for optimal processing
    segments = segment_text(text, TTSConfig.MAX_SEGMENT_LENGTH)
    total_segments = len(segments)
    
    # Validate segment mapping to ensure full text coverage
    if not _validate_segment_mapping(text, segments, request_id):
        logger.warning(f"[{request_id}] Segment mapping validation failed - this may affect TTFA performance")
    
    if total_segments == 0:
        raise HTTPException(status_code=400, detail="No valid text segments found")

    # Early TTFA primer: split first segment to stream ~5% of text ASAP
    def _split_segment_for_early_ttfa(segment_text: str) -> Tuple[str, str]:
        """
        Split a segment for early TTFA optimization with natural speech boundaries.
        
        This function implements the early-primer strategy by splitting text segments
        at natural punctuation marks or word boundaries to provide immediate audio
        output while maintaining speech comprehension quality.
        
        Strategy:
        1. Look for sentence-ending punctuation (.!?) within first 15-20 words
        2. Fall back to comma/semicolon if no sentence end found
        3. Fall back to word boundary at 15-20 words if no punctuation
        4. Ensure minimum 3 words and maximum 25 words for natural speech
        
        Args:
            segment_text (str): Text segment to split
            
        Returns:
            Tuple[str, str]: (early_text, remaining_text) for optimized TTFA
        """
        words = segment_text.split()
        
        # For very short segments (< 5 words), return as-is to avoid fragmentation
        if len(words) <= 5:
            return segment_text, ""
        
        # Strategy 1: Look for sentence-ending punctuation within first 15-20 words
        max_words_for_sentence = min(20, len(words))
        for i in range(3, max_words_for_sentence):  # Start at word 3, minimum viable sentence
            word = words[i]
            # Check if word ends with sentence-ending punctuation
            if word.rstrip().endswith(('.', '!', '?')):
                early_words = words[:i+1]
                rest_words = words[i+1:]
                early = ' '.join(early_words).strip()
                rest = ' '.join(rest_words).strip() if rest_words else ""
                
                logger.debug(f"TTFA split on sentence boundary at word {i+1}: '{early[:30]}...'")
                return early, rest
        
        # Strategy 2: Look for comma/semicolon within first 15 words for natural pause
        max_words_for_comma = min(15, len(words))
        for i in range(3, max_words_for_comma):
            word = words[i]
            if word.rstrip().endswith((',', ';')):
                early_words = words[:i+1]
                rest_words = words[i+1:]
                early = ' '.join(early_words).strip()
                rest = ' '.join(rest_words).strip() if rest_words else ""
                
                logger.debug(f"TTFA split on comma/semicolon at word {i+1}: '{early[:30]}...'")
                return early, rest
        
        # Strategy 3: Split at 15 words if no natural punctuation found
        # This ensures reasonable TTFA while maintaining comprehension
        if len(words) > 15:
            early_words = words[:15]
            rest_words = words[15:]
            early = ' '.join(early_words).strip()
            rest = ' '.join(rest_words).strip()
            
            logger.debug(f"TTFA split at 15-word boundary: '{early[:30]}...'")
            return early, rest
        
        # If we get here, the segment is 6-15 words with no punctuation
        # Split roughly in half but ensure minimum 3 words in each part
        split_point = max(3, len(words) // 2)
        early_words = words[:split_point]
        rest_words = words[split_point:]
        early = ' '.join(early_words).strip()
        rest = ' '.join(rest_words).strip() if rest_words else ""
        
        logger.debug(f"TTFA split at midpoint ({split_point} words): '{early[:30]}...'")
        return early, rest

    fast_indices: Set[int] = set()
    primer_hint_key: Optional[str] = None  # Initialize to avoid UnboundLocalError

    if segments:
        logger.debug(
            f"[{request_id}] Checking primer split for first segment: '{segments[0][:50]}...' (length: {len(segments[0])})"
        )
        early, rest = _split_segment_for_early_ttfa(segments[0])
        logger.debug(
            f"[{request_id}] Primer split result: early='{early[:30]}...' (length: {len(early)}), rest='{rest[:30]}...' (length: {len(rest)})"
        )

        if early and rest:
            logger.debug(f"[{request_id}] Primer split successful, checking cache")
            # Micro-cache lookup for primer inference
            primer_key = _get_primer_cache_key(early, voice, speed, lang)
            logger.debug(f"[{request_id}] Generated primer key: {primer_key[:8]}...")
            cached_primer = _get_cached_primer(primer_key)
            if cached_primer is not None and cached_primer.size > 0:
                logger.debug(
                    f"[{request_id}] Primer micro-cache hit; yielding cached primer audio"
                )
                try:
                    scaled_audio = np.int16(cached_primer * 32767)
                    segment_bytes = scaled_audio.tobytes()
                    # yield a couple of small chunks to flush
                    yield segment_bytes[: max(1024, len(segment_bytes) // 4)]
                    if len(segment_bytes) > 2048:
                        yield segment_bytes[
                            max(1024, len(segment_bytes) // 4) : max(
                                2048, len(segment_bytes) // 2
                            )
                        ]
                except Exception as e:
                    logger.debug(f"[{request_id}] Primer cached audio emit failed: {e}")
            else:
                logger.debug(
                    f"[{request_id}] No cached primer found, setting up for storage"
                )
                # No cached primer; keep primer as first segment and mark fast-path
                segments = [early, rest] + segments[1:]
                fast_indices.add(0)  # force fast path for the early primer segment
                # Store hint key for later caching after generation
                primer_hint_key = primer_key
                logger.debug(
                    f"[{request_id}] Set primer_hint_key: {primer_hint_key[:8]}..."
                )
        else:
            logger.debug(
                f"[{request_id}] Primer split not triggered (early or rest empty)"
            )
            primer_hint_key = None
    else:
        logger.debug(f"[{request_id}] No segments to process")
        primer_hint_key = None

    total_segments = len(segments)
    logger.info(f"[{request_id}] Text split into {total_segments} segments.")

    if format == "wav":
        try:
            # Enhanced WAV header streaming with proper chunking
            # This implements the optimization plan's requirement for streaming WAV header support
            header_size = 44

            # Create streaming-optimized WAV header
            # Use placeholder for data size, will be handled by streaming response
            estimated_data_size = 0xFFFFFFFF - header_size  # Maximum size for streaming

            wav_header = bytearray(header_size)

            # RIFF header with streaming optimization
            struct.pack_into(
                "<4sI4s",
                wav_header,
                0,
                b"RIFF",
                estimated_data_size + 36,  # File size - 8 bytes
                b"WAVE",
            )

            # Format chunk with Kokoro-optimized parameters
            struct.pack_into(
                "<4sIHHIIHH",
                wav_header,
                12,
                b"fmt ",
                16,  # Format chunk size
                1,  # PCM format
                1,  # Mono channel (Kokoro default)
                TTSConfig.SAMPLE_RATE,  # 24kHz sample rate
                TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE * 1,  # Byte rate
                TTSConfig.BYTES_PER_SAMPLE * 1,  # Block align
                TTSConfig.BYTES_PER_SAMPLE * 8,  # Bits per sample (16-bit)
            )

            # Data chunk header with streaming placeholder
            struct.pack_into(
                "<4sI", wav_header, 36, b"data", estimated_data_size  # Data chunk size
            )

            # Immediate header yield for faster TTFA
            # This ensures the client receives the WAV header immediately
            logger.debug(
                f"[{request_id}] Yielding optimized WAV header ({header_size} bytes) for streaming"
            )
            yield bytes(wav_header)

            # Yield a tiny silence primer to force flush and begin playback immediately
            # 50ms of silence at 24kHz, 16-bit mono → 24000 * 0.05 * 2 = 2400 bytes
            try:
                silence_ms = 50
                silence_samples = int(TTSConfig.SAMPLE_RATE * (silence_ms / 1000))
                silence_bytes = (np.int16(np.zeros(silence_samples)) * 0).tobytes()
                if silence_bytes:
                    logger.debug(
                        f"[{request_id}] Yielding {silence_ms}ms silence primer ({len(silence_bytes)} bytes)"
                    )
                    yield silence_bytes
            except Exception as e:
                logger.debug(f"[{request_id}] Silence primer generation skipped: {e}")

        except Exception as e:
            logger.error(f"[{request_id}] WAV header generation failed: {e}")
            # Graceful fallback to PCM format
            logger.info(f"[{request_id}] Falling back to PCM format for streaming")
            format = "pcm"

    # True streaming - process segments one by one
    # This is the key fix: instead of creating all tasks upfront and waiting,
    # we process each segment immediately and yield chunks as they complete

    logger.info(f"[{request_id}] Starting segment processing loop for format='{format}', total_segments={total_segments}")
    successful_segments = 0
    chunk_timing_state = {
        "chunk_count": 0,
        "first_chunk_time": None,
        "request_start_time": start_time,
        "stream_start_time": time.monotonic(),
        "total_audio_duration_ms": 0,
        "ttfa_target_ms": 800,
        "efficiency_target": 0.90,
    }

    try:
        # Process segments with dual session manager for concurrency
        # Get dual session manager for concurrent processing
        from api.model.loader import get_dual_session_manager

        dual_session_manager = get_dual_session_manager()
        
        logger.info(f"[{request_id}] 🔍 Dual session manager debug: {dual_session_manager is not None}")
        if dual_session_manager:
            logger.info(f"[{request_id}] ✅ Dual session manager available for concurrent processing")
            logger.info(f"[{request_id}] 🎯 Sessions available: {[k for k, v in dual_session_manager.sessions.items() if v is not None]}")
            dual_stats = dual_session_manager.get_utilization_stats()
            logger.info(f"[{request_id}] Dual session stats: {dual_stats}")
        else:
            logger.warning(f"[{request_id}] ❌ Dual session manager not available, falling back to sequential processing")
            # Debug: Try to check what the import actually returns
            try:
                from api.model.sessions.dual_session import get_dual_session_manager as get_dsm_direct
                dsm_direct = get_dsm_direct()
                logger.info(f"[{request_id}] 🔍 Direct import check: {dsm_direct is not None}")
            except Exception as e:
                logger.error(f"[{request_id}] 🔍 Direct import failed: {e}")

        # Create tasks for concurrent processing
        segment_tasks = []
        for i, seg_text in enumerate(segments):
            logger.debug(
                f"[{request_id}] Creating task for segment {i+1}/{total_segments}: '{seg_text[:30]}...'"
            )

            # Use fast processing for first simple segment
            # Force fast-path for primer segment and for first segment regardless of complexity
            use_fast_processing = (i in fast_indices) or (i == 0)

            # Create task for this segment
            if use_fast_processing:
                logger.debug(
                    f"[{request_id}] Using fast processing for segment {i+1} to improve TTFA"
                )
                task = run_in_threadpool(
                    _fast_generate_audio_segment, i, seg_text, voice, speed, lang, no_cache
                )
            else:
                # Use dual session manager for concurrent processing
                if dual_session_manager:
                    logger.debug(
                        f"[{request_id}] Using dual session manager for concurrent processing of segment {i+1}"
                    )
                    task = run_in_threadpool(
                        dual_session_manager.process_segment_concurrent,
                        seg_text,
                        voice,
                        speed,
                        lang,
                    )
                else:
                    logger.debug(
                        f"[{request_id}] Dual session manager not available, using standard processing for segment {i+1}"
                    )
                    task = run_in_threadpool(
                        _generate_audio_segment, i, seg_text, voice, speed, lang, no_cache
                    )

            segment_tasks.append((i, task))

        # Process segments as they complete (maintain order for streaming)
        completed_segments = {}

        # Start all tasks
        for i, task in segment_tasks:
            try:
                segment_start_time = time.perf_counter()

                # Wait for segment to complete
                if dual_session_manager and i not in fast_indices:
                    # Dual session manager returns (samples, sample_rate)
                    audio_data = await task
                    if isinstance(audio_data, tuple):
                        if len(audio_data) >= 2:
                            audio_np = audio_data[0]  # First element is always samples
                            sample_rate = audio_data[1]  # Second element is sample rate
                        else:
                            # Handle single element tuple
                            audio_np = audio_data[0]
                            sample_rate = 24000  # Default sample rate
                            logger.warning(f"[{request_id}] Dual session returned single element tuple, using default sample rate")
                    else:
                        # Handle direct return
                        audio_np = audio_data
                        sample_rate = 24000  # Default sample rate
                        logger.debug(f"[{request_id}] Dual session returned direct audio data")
                    
                    provider = "DualSession"
                    
                    # Validate audio data
                    if audio_np is None or (hasattr(audio_np, 'size') and audio_np.size == 0):
                        logger.error(f"[{request_id}] Dual session returned invalid audio data for segment {i}")
                        continue
                        
                else:
                    # Standard processing returns (idx, audio_np, provider)
                    try:
                        result = await task
                        if isinstance(result, tuple) and len(result) >= 3:
                            idx, audio_np, provider = result
                        elif isinstance(result, tuple) and len(result) == 2:
                            # Handle case where provider might be missing
                            idx, audio_np = result
                            provider = "Standard"
                            logger.debug(f"[{request_id}] Standard processing returned 2-element tuple for segment {i}")
                        else:
                            logger.error(f"[{request_id}] Unexpected result format from standard processing: {type(result)}")
                            continue
                    except Exception as e:
                        logger.error(f"[{request_id}] Error unpacking standard processing result for segment {i}: {e}")
                        continue

                # Final validation before processing
                if audio_np is None or (hasattr(audio_np, 'size') and audio_np.size == 0):
                    logger.error(f"[{request_id}] Segment {i} produced no audio")
                    continue
                
                segment_duration = time.perf_counter() - segment_start_time
                logger.debug(f"[{request_id}] Segment {i} completed in {segment_duration:.3f}s via {provider}")

                completed_segments[i] = (audio_np, provider)

            except Exception as e:
                logger.error(f"[{request_id}] Error processing segment {i}: {e}", exc_info=True)
                continue

        # Get variation handler for consistent audio experience
        variation_handler = get_variation_handler()
        
        # Create text hash for variation tracking
        full_text_hash = variation_handler.get_text_hash(text, voice, speed, lang)
        
        # Process completed segments in order for streaming
        for i in range(len(segments)):
            if i not in completed_segments:
                logger.error(f"[{request_id}] Segment {i} not completed")
                continue

            audio_np, provider = completed_segments[i]

            # If the segment is None, it means the segment failed to generate audio.
            # Check the tuple for any other information that might be useful.
            if audio_np is None:
                logger.error(f"[{request_id}] Segment {i} failed to generate audio")
                continue
            else:
                logger.info(f"[{request_id}] Processing segment {i}: audio_np type={type(audio_np)}, shape={getattr(audio_np, 'shape', 'no shape')}, size={getattr(audio_np, 'size', 'no size')}")
                
                # CRITICAL FIX: Detect corrupted audio and fallback to non-streaming path
                if isinstance(audio_np, (int, float)):
                    logger.error(f"[{request_id}] STREAMING CORRUPTION DETECTED: Segment {i} returned scalar {type(audio_np)}: {audio_np}")
                    logger.info(f"[{request_id}] Falling back to non-streaming TTS for segment: '{segments[i][:50]}...'")
                    
                    # Use the working non-streaming path as fallback
                    try:
                        from api.model.loader import get_model
                        fallback_model = get_model()
                        if fallback_model:
                            fallback_result = fallback_model.create(segments[i], voice, speed, lang)
                            
                            # Handle the non-streaming result format
                            if isinstance(fallback_result, tuple) and len(fallback_result) >= 1:
                                audio_np = fallback_result[0]
                            else:
                                audio_np = fallback_result
                            
                            # Validate the fallback result
                            if audio_np is not None and not isinstance(audio_np, (int, float)):
                                try:
                                    audio_np = np.asarray(audio_np, dtype=np.float32)
                                    if audio_np.size > 100:  # Reasonable size check
                                        logger.info(f"[{request_id}] ✅ Fallback successful: {audio_np.size} samples from non-streaming path")
                                        provider = f"{provider}-Fallback"
                                    else:
                                        logger.error(f"[{request_id}] Fallback returned insufficient audio: {audio_np.size} samples")
                                        continue
                                except Exception as e:
                                    logger.error(f"[{request_id}] Fallback conversion failed: {e}")
                                    continue
                            else:
                                logger.error(f"[{request_id}] Fallback also returned corrupted data: {type(audio_np)}")
                                continue
                        else:
                            logger.error(f"[{request_id}] No fallback model available")
                            continue
                    except Exception as e:
                        logger.error(f"[{request_id}] Fallback to non-streaming failed: {e}")
                        continue
                
                # Normalize and convert audio to bytes immediately
                try:
                    audio_np = np.asarray(audio_np)
                    if audio_np.dtype == object:
                        # Concatenate nested arrays/lists if present
                        audio_np = np.concatenate([
                            np.asarray(x, dtype=np.float32).reshape(-1)
                            for x in audio_np
                        ])
                    else:
                        audio_np = audio_np.astype(np.float32, copy=False)
                    if audio_np.ndim > 1:
                        audio_np = audio_np.reshape(-1)
                    # Guard against NaN/Inf
                    audio_np = np.nan_to_num(audio_np, nan=0.0, posinf=1.0, neginf=-1.0)
                except Exception as norm_err:
                    logger.warning(f"[{request_id}] Audio normalization failed: {norm_err}")
                    audio_np = np.asarray(audio_np, dtype=np.float32).reshape(-1)

                scaled_audio = np.clip(audio_np * 32767.0, -32768, 32767).astype(np.int16)
                segment_bytes = scaled_audio.tobytes()
                
                # Track audio size variation for CoreML precision analysis
                if i == len(segments) - 1:  # Only track on the last segment (total audio size)
                    total_audio_size = len(segment_bytes)
                    variation_analysis = variation_handler.record_audio_size(full_text_hash, total_audio_size)
                    
                    if not variation_analysis['is_consistent']:
                        logger.info(f"[{request_id}] 🎯 Audio size variation detected: {variation_analysis['variation_pct']:.1f}% "
                                  f"(current: {total_audio_size}, baseline: {variation_analysis['baseline_size']})")
                        
                        # For now, just log the variation - normalization can be added later if needed
                        logger.info(f"[{request_id}] 📊 Pattern count: {variation_analysis['pattern_count']}, "
                                  f"all sizes: {variation_analysis.get('all_sizes', [total_audio_size])}")
                
                logger.info(f"[{request_id}] Segment {i} converted to {len(segment_bytes)} bytes (audio samples: {getattr(scaled_audio, 'size', 'scalar')})")

                # If this was the primer segment, put into micro-cache
                try:
                    logger.debug(
                        f"[{request_id}] Checking primer storage conditions: i={i}, fast_indices={fast_indices}, primer_hint_key={primer_hint_key}"
                    )

                    if i in fast_indices and primer_hint_key:
                        logger.debug(
                            f"[{request_id}] Storing primer in micro-cache: key={primer_hint_key[:8]}..., audio_size={audio_np.size}"
                        )
                        _put_cached_primer(primer_hint_key, audio_np)
                        logger.debug(
                            f"[{request_id}] Primer storage completed successfully"
                        )
                    else:
                        logger.debug(
                            f"[{request_id}] Primer storage conditions not met: i={i}, fast_indices={fast_indices}, primer_hint_key={primer_hint_key}"
                        )
                except Exception as e:
                    logger.warning(f"[{request_id}] Primer storage failed: {e}")
                    logger.warning(
                        f"[{request_id}] Exception details: {type(e).__name__}: {str(e)}"
                    )

                # Yield chunks immediately in smaller pieces
                # Smaller initial chunks for primer segment to improve TTFA
                chunk_size = TTSConfig.CHUNK_SIZE_BYTES
                if i in fast_indices:
                    chunk_size = max(1024, TTSConfig.CHUNK_SIZE_BYTES // 2)
                offset = 0

                while offset < len(segment_bytes):
                    chunk = segment_bytes[offset : offset + chunk_size]
                    current_time = time.monotonic()
                    chunk_timing_state["chunk_count"] += 1

                    # Track first chunk for TTFA calculation
                    if chunk_timing_state["first_chunk_time"] is None:
                        chunk_timing_state["first_chunk_time"] = current_time
                        ttfa_ms = (
                            current_time - chunk_timing_state["stream_start_time"]
                        ) * 1000
                        logger.info(
                            f"[{request_id}] First chunk yielded in {ttfa_ms:.2f}ms"
                        )

                        if ttfa_ms < chunk_timing_state["ttfa_target_ms"]:
                            logger.info(
                                f"[{request_id}] ✅ TARGET ACHIEVED: TTFA < {chunk_timing_state['ttfa_target_ms']}ms"
                            )
                        else:
                            logger.warning(
                                f"[{request_id}] ⚠️ TARGET MISSED: TTFA {ttfa_ms:.2f}ms > {chunk_timing_state['ttfa_target_ms']}ms"
                            )

                    # Calculate actual audio duration represented by this chunk
                    actual_audio_duration_ms = (
                        len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE
                    ) * 1000
                    chunk_timing_state[
                        "total_audio_duration_ms"
                    ] += actual_audio_duration_ms

                    # Log progress every 10 chunks
                    if chunk_timing_state["chunk_count"] % 10 == 0:
                        elapsed_time = (
                            current_time - chunk_timing_state["stream_start_time"]
                        )
                        expected_time = (
                            chunk_timing_state["total_audio_duration_ms"] / 1000
                        )
                        current_efficiency = (
                            expected_time / elapsed_time if elapsed_time > 0 else 0
                        )
                        logger.debug(
                            f"[{request_id}] Chunk {chunk_timing_state['chunk_count']}: Efficiency {current_efficiency*100:.1f}%"
                        )

                    # Yield the chunk immediately
                    logger.debug(
                        f"[{request_id}] Yielding chunk {chunk_timing_state['chunk_count']} of {len(chunk)} bytes from segment {i+1}"
                    )
                    yield chunk

                    offset += chunk_size

                successful_segments += 1

                # Clear the numpy array to free memory immediately
                del audio_np, scaled_audio

        # Final streaming statistics
        total_time = time.perf_counter() - start_time
        total_stream_time = time.monotonic() - chunk_timing_state["stream_start_time"]

        # Record stream health for threshold optimization
        stream_success = True
        error_details = None
        
        # CRITICAL FIX: Clean up TTS model sessions after each request
        # This prevents session state corruption that causes silent audio on subsequent requests
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager:
            try:
                dual_session_manager.cleanup_sessions()
                logger.debug(f"[{request_id}] Session cleanup completed after streaming")
            except Exception as e:
                logger.warning(f"[{request_id}] Session cleanup failed: {e}")
                error_details = f"Session cleanup failed: {e}"

        # Record stream health for threshold optimization
        variation_handler.record_stream_health(
            text_hash=full_text_hash,
            stream_success=stream_success,
            error_details=error_details,
            latency_ms=total_stream_time * 1000,
            chunk_count=chunk_timing_state["chunk_count"]
        )

        logger.info(f"[{request_id}] Streaming completed")
        logger.info(f"[{request_id}] Final statistics:")
        logger.info(f"[{request_id}]   • Total time: {total_time:.2f}s")
        logger.info(f"[{request_id}]   • Stream time: {total_stream_time:.2f}s")
        logger.info(
            f"[{request_id}]   • Segments processed: {successful_segments}/{total_segments}"
        )
        logger.info(
            f"[{request_id}]   • Chunks yielded: {chunk_timing_state['chunk_count']}"
        )
        logger.info(
            f"[{request_id}]   • Audio duration: {chunk_timing_state['total_audio_duration_ms']:.1f}ms"
        )

        if chunk_timing_state["first_chunk_time"]:
            ttfa_ms = (
                chunk_timing_state["first_chunk_time"]
                - chunk_timing_state["stream_start_time"]
            ) * 1000
            logger.info(f"[{request_id}]   • TTFA: {ttfa_ms:.2f}ms")

            if ttfa_ms < chunk_timing_state["ttfa_target_ms"]:
                logger.info(f"[{request_id}] ✅ TTFA target achieved")
            else:
                logger.warning(
                    f"[{request_id}] ⚠️ OPTIMAL TIMING NEEDS IMPROVEMENT: TTFA target not met"
                )

        # Update endpoint-level performance metrics
        try:
            from api.performance.stats import update_endpoint_performance_stats

            # Compute RTF and streaming efficiency
            audio_duration_sec = chunk_timing_state["total_audio_duration_ms"] / 1000.0
            rtf = (total_time / audio_duration_sec) if audio_duration_sec > 0 else 0.0
            efficiency = (
                audio_duration_sec / total_stream_time if total_stream_time > 0 else 0.0
            )

            compliant = (
                (ttfa_ms if chunk_timing_state["first_chunk_time"] else 1e9)
                < chunk_timing_state["ttfa_target_ms"]
                and rtf < 1.0
                and efficiency >= chunk_timing_state["efficiency_target"]
            )

            update_endpoint_performance_stats(
                endpoint="stream_tts_audio",
                processing_time=total_time,
                success=True,
                ttfa_ms=float(ttfa_ms) if chunk_timing_state["first_chunk_time"] else 0.0,
                rtf=float(rtf),
                streaming_efficiency=float(efficiency),
                compliant=bool(compliant),
            )
        except Exception as metrics_err:
            logger.debug(f"[{request_id}] Endpoint metrics update failed: {metrics_err}")

    except Exception as e:
        logger.error(f"[{request_id}] Streaming error: {e}", exc_info=True)
        
        # Record failed stream for threshold optimization
        try:
            variation_handler = get_variation_handler()
            if 'full_text_hash' in locals():
                variation_handler.record_stream_health(
                    text_hash=full_text_hash,
                    stream_success=False,
                    error_details=str(e),
                    latency_ms=None,
                    chunk_count=chunk_timing_state.get("chunk_count", 0) if 'chunk_timing_state' in locals() else 0
                )
        except Exception as health_err:
            logger.debug(f"[{request_id}] Failed to record stream health: {health_err}")
        
        raise

    finally:
        # CRITICAL FIX: Clean up TTS model sessions after each request
        # This prevents session state corruption that causes silent audio on subsequent requests
        try:
            from api.model.loader import get_dual_session_manager
            dual_session_manager = get_dual_session_manager()
            if dual_session_manager:
                dual_session_manager.cleanup_sessions()
                logger.debug(f"[{request_id}] Session cleanup completed after streaming")
        except Exception as e:
            logger.warning(f"[{request_id}] Session cleanup failed: {e}")

    if successful_segments == 0:
        logger.error(f"[{request_id}] No segments were successfully processed")
        raise HTTPException(
            status_code=500, detail="Audio generation failed for all segments"
        )


def _validate_segment_mapping(text: str, segments: List[str], request_id: str) -> bool:
    """
    Validate that segment mapping preserves full text coverage.
    
    This function ensures that no text content is lost during segmentation,
    which is critical for maintaining audio quality and preventing TTFA issues.
    
    Args:
        text (str): Original input text
        segments (List[str]): Segmented text chunks
        request_id (str): Request identifier for logging
        
    Returns:
        bool: True if full coverage is maintained, False otherwise
    """
    # Normalize both original and segmented text for comparison
    original_normalized = text.replace('\n', ' ').replace('\r', ' ').strip()
    segmented_normalized = ' '.join(segments).replace('\n', ' ').replace('\r', ' ').strip()
    
    # Remove extra whitespace for comparison
    original_clean = ' '.join(original_normalized.split())
    segmented_clean = ' '.join(segmented_normalized.split())
    
    # Check for exact match
    if original_clean == segmented_clean:
        logger.debug(f"[{request_id}] ✅ Segment mapping validation passed: full text coverage maintained")
        return True
    
    # Check for length-based validation
    original_length = len(original_clean)
    segmented_length = len(segmented_clean)
    
    if abs(original_length - segmented_length) <= 5:  # Allow small differences due to normalization
        logger.debug(f"[{request_id}] ✅ Segment mapping validation passed: length difference within tolerance ({original_length} vs {segmented_length})")
        return True
    
    # Detailed analysis for failures
    logger.warning(f"[{request_id}] ⚠️ Segment mapping validation failed:")
    logger.warning(f"[{request_id}]   Original length: {original_length} chars")
    logger.warning(f"[{request_id}]   Segmented length: {segmented_length} chars")
    logger.warning(f"[{request_id}]   Difference: {abs(original_length - segmented_length)} chars")
    
    # Log sample of differences for debugging
    if original_length > segmented_length:
        missing_chars = original_length - segmented_length
        logger.warning(f"[{request_id}]   Missing approximately {missing_chars} characters")
        
        # Try to identify where the loss occurred
        if len(segments) > 1:
            total_segmented = sum(len(seg) for seg in segments)
            logger.warning(f"[{request_id}]   Total segment lengths: {total_segmented} chars")
            logger.warning(f"[{request_id}]   Segment count: {len(segments)}")
    
    return False