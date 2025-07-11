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
from typing import AsyncGenerator, Dict, Optional, Tuple

import numpy as np
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from kokoro_onnx import Kokoro

from api.config import TTSConfig
from api.model.loader import get_model, get_model_status, get_active_provider, get_dual_session_manager
from api.performance.stats import update_performance_stats
from api.tts.text_processing import (
    segment_text,
    preprocess_text_for_inference,
    get_phoneme_cache_stats,
    clear_phoneme_cache,
)
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
                providers=[provider]
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
    return hashlib.md5(cache_input.encode('utf-8')).hexdigest()

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
            'total_entries': len(_inference_cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'cache_size_mb': len(_inference_cache) * 0.1,  # Rough estimate
            'hit_rate': getattr(get_inference_cache_stats, '_hit_rate', 0.0),
            'miss_rate': getattr(get_inference_cache_stats, '_miss_rate', 0.0)
        }


def should_use_phoneme_preprocessing() -> bool:
    """
    Determine whether to use phoneme preprocessing for optimization.
    
    This function checks if phoneme preprocessing should be enabled based on:
    1. Active provider (CoreML benefits most from consistent tensor shapes)
    2. Configuration settings
    3. Hardware capabilities
    
    Returns:
        bool: True if phoneme preprocessing should be used
    """
    try:
        # Check if CoreML provider is active (benefits most from consistent tensor shapes)
        active_provider = get_active_provider()
        if active_provider == "CoreMLExecutionProvider":
            logger.debug("✅ Phoneme preprocessing enabled for CoreML optimization")
            return True
        
        # Check for environment variable override
        if os.environ.get('KOKORO_ENABLE_PHONEME_PREPROCESSING', '').lower() == 'true':
            logger.debug("✅ Phoneme preprocessing enabled via environment variable")
            return True
        
        # Default: disabled for other providers (can be enabled in future)
        logger.debug("ℹ️ Phoneme preprocessing disabled (not using CoreML)")
        return False
        
    except Exception as e:
        logger.warning(f"Could not determine phoneme preprocessing status: {e}")
        return False


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
            'inference_cache': inference_stats,
            'phoneme_cache': phoneme_stats,
            'phoneme_preprocessing_enabled': should_use_phoneme_preprocessing(),
            'active_provider': get_active_provider()
        }
        
        return combined_stats
        
    except Exception as e:
        logger.warning(f"Could not get TTS processing stats: {e}")
        return {
            'inference_cache': {},
            'phoneme_cache': {},
            'phoneme_preprocessing_enabled': False,
            'active_provider': 'Unknown',
            'error': str(e)
        }


def _generate_audio_segment(
    idx: int, text: str, voice: str, speed: float, lang: str
) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Generates a single audio segment with enhanced caching and thread safety.
    
    This function implements inference pipeline caching for common requests
    to avoid redundant processing and improve performance.
    
    ## PHASE 2 OPTIMIZATION: Phoneme Preprocessing Integration
    
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
        # PHASE 2 OPTIMIZATION: Phoneme preprocessing for CoreML optimization
        processed_text = text
        preprocessing_info = ""
        
        if should_use_phoneme_preprocessing():
            try:
                # Preprocess text for optimal inference with consistent tensor shapes
                preprocessing_result = preprocess_text_for_inference(text)
                processed_text = preprocessing_result['normalized_text']
                
                # Log preprocessing stats for monitoring
                original_length = preprocessing_result['original_length']
                padded_length = preprocessing_result['padded_length']
                cache_hit = preprocessing_result['cache_hit']
                truncated = preprocessing_result['truncated']
                
                preprocessing_info = f"phonemes:{original_length}→{padded_length}"
                if cache_hit:
                    preprocessing_info += " (cached)"
                if truncated:
                    preprocessing_info += " (truncated)"
                    
                logger.debug(f"[{idx}] Phoneme preprocessing: {preprocessing_info}")
                
            except Exception as e:
                logger.warning(f"[{idx}] Phoneme preprocessing failed: {e}, falling back to original text")
                processed_text = text
                preprocessing_info = "fallback"
        
        # Create cache key for this inference (using processed text for better cache efficiency)
        cache_key = _create_inference_cache_key(processed_text, voice, speed, lang)
        
        # Check cache first
        cached_result = _get_cached_inference(cache_key)
        if cached_result is not None:
            samples, provider = cached_result
            logger.debug(f"[{idx}] Using cached audio for: {processed_text[:50]}...")
            # Update cache hit statistics
            update_performance_stats(0.001, provider)  # Minimal time for cache hit
            cache_info = f"{provider} (cached)"
            if preprocessing_info:
                cache_info += f" [{preprocessing_info}]"
            return idx, samples, cache_info
        
        # Cache miss - generate new audio
        # PHASE 3 OPTIMIZATION: Use dual session manager for concurrent processing
        dual_session_manager = get_dual_session_manager()
        
        if dual_session_manager:
            # Use dual session manager for optimal concurrent processing
            logger.debug(f"[{idx}] Generating audio using dual session manager for: {processed_text[:50]}...")
            start_time = time.perf_counter()
            
            try:
                samples, _ = dual_session_manager.process_segment_concurrent(
                    processed_text, voice, speed, lang
                )
                
                inference_time = time.perf_counter() - start_time
                
                # Get session utilization stats for logging
                utilization_stats = dual_session_manager.get_utilization_stats()
                active_sessions = utilization_stats.get('concurrent_segments_active', 0)
                
                # Determine which session was likely used based on complexity
                complexity = dual_session_manager.calculate_segment_complexity(processed_text)
                if complexity > 0.7:
                    likely_session = "ANE" if utilization_stats['sessions_available']['ane'] else "GPU"
                else:
                    likely_session = "GPU" if utilization_stats['sessions_available']['gpu'] else "ANE"
                
                update_performance_stats(inference_time, f"DualSession-{likely_session}")
                
                if samples is not None and samples.size > 0:
                    # Cache the successful result
                    _cache_inference_result(cache_key, samples, f"DualSession-{likely_session}")
                    
                    result_info = f"DualSession-{likely_session} (concurrent:{active_sessions})"
                    if preprocessing_info:
                        result_info += f" [{preprocessing_info}]"
                    
                    logger.info(f"[{idx}] Segment processed in {inference_time:.4f}s using {result_info}")
                    return idx, samples, result_info
                else:
                    logger.warning(f"[{idx}] Dual session manager returned empty audio for text: {processed_text[:50]}...")
                    return idx, None, "Empty audio returned"
                    
            except Exception as e:
                logger.warning(f"[{idx}] Dual session processing failed: {e}, falling back to single model")
                # Fall back to single model processing
                pass
        
        # Fallback to single model processing
        provider = get_active_provider()
        local_model = _get_cached_model(provider)

        logger.debug(f"[{idx}] Generating audio using single model for: {processed_text[:50]}...")
        start_time = time.perf_counter()

        samples, _ = local_model.create(processed_text, voice, speed, lang)
        
        inference_time = time.perf_counter() - start_time
        update_performance_stats(inference_time, provider)
        
        if samples is not None and samples.size > 0:
            # Cache the successful result
            _cache_inference_result(cache_key, samples, provider)
            
            result_info = f"{provider}"
            if preprocessing_info:
                result_info += f" [{preprocessing_info}]"
            
            logger.info(f"[{idx}] Segment processed in {inference_time:.4f}s using {result_info}")
            return idx, samples, result_info
        else:
            logger.warning(f"[{idx}] TTS model returned empty audio for text: {processed_text[:50]}...")
            return idx, None, "Empty audio returned"

    except Exception as e:
        logger.error(f"[{idx}] TTS generation failed for text '{text[:50]}...': {e}", exc_info=True)
        return idx, None, str(e)


async def stream_tts_audio(
    text: str, voice: str, speed: float, lang: str, format: str, request: Request
) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously generates and streams TTS audio.
    This function processes text in segments, generates audio for each in parallel,
    and streams the resulting audio bytes back to the client as they become available.
    """
    request_id = request.headers.get("x-request-id", "no-id")
    logger.info(
        f"[{request_id}] Starting stream request: voice='{voice}', speed={speed}, format='{format}', text='{text[:30]}...'"
    )
    
    # PHASE 1 OPTIMIZATION: Record request for workload analysis
    start_time = time.perf_counter()
    concurrent_requests = 1  # TODO: Implement actual concurrent request tracking

    model_loaded = get_model_status()
    if not model_loaded:
        logger.error(f"[{request_id}] TTS model not ready, raising 503 error.")
        raise HTTPException(status_code=503, detail="TTS model not ready.")

    segments = segment_text(text, TTSConfig.MAX_SEGMENT_LENGTH)
    if not segments:
        logger.warning(f"[{request_id}] No segments generated from text, ending stream early.")
        return

    total_segments = len(segments)
    logger.info(f"[{request_id}] Text split into {total_segments} segments.")

    if format == "wav":
        try:
            # PHASE 1 OPTIMIZATION: Enhanced WAV header streaming with proper chunking
            # This implements the optimization plan's requirement for streaming WAV header support
            header_size = 44
            
            # PHASE 1 OPTIMIZATION: Create streaming-optimized WAV header
            # Use placeholder for data size, will be handled by streaming response
            estimated_data_size = 0xFFFFFFFF - header_size  # Maximum size for streaming
            
            wav_header = bytearray(header_size)
            
            # RIFF header with streaming optimization
            struct.pack_into(
                "<4sI4s", wav_header, 0, 
                b"RIFF", 
                estimated_data_size + 36,  # File size - 8 bytes
                b"WAVE"
            )
            
            # Format chunk with Kokoro-optimized parameters
            struct.pack_into(
                "<4sIHHIIHH",
                wav_header, 12,
                b"fmt ",
                16,  # Format chunk size
                1,   # PCM format
                1,   # Mono channel (Kokoro default)
                TTSConfig.SAMPLE_RATE,  # 24kHz sample rate
                TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE * 1,  # Byte rate
                TTSConfig.BYTES_PER_SAMPLE * 1,  # Block align
                TTSConfig.BYTES_PER_SAMPLE * 8,  # Bits per sample (16-bit)
            )
            
            # Data chunk header with streaming placeholder
            struct.pack_into(
                "<4sI", wav_header, 36, 
                b"data", 
                estimated_data_size  # Data chunk size
            )
            
            # PHASE 1 OPTIMIZATION: Immediate header yield for faster TTFA
            # This ensures the client receives the WAV header immediately
            logger.debug(f"[{request_id}] Yielding optimized WAV header ({header_size} bytes) for streaming")
            yield bytes(wav_header)
            
        except Exception as e:
            logger.error(f"[{request_id}] WAV header generation failed: {e}")
            # PHASE 1 OPTIMIZATION: Graceful fallback to PCM format
            logger.info(f"[{request_id}] Falling back to PCM format for streaming")
            format = "pcm"

    # PHASE 1 OPTIMIZATION: True streaming - process segments one by one
    # This is the key fix: instead of creating all tasks upfront and waiting,
    # we process each segment immediately and yield chunks as they complete
    
    successful_segments = 0
    chunk_timing_state = {
        'chunk_count': 0,
        'first_chunk_time': None,
        'request_start_time': start_time,
        'stream_start_time': time.monotonic(),
        'total_audio_duration_ms': 0,
        'phase1_ttfa_target_ms': 800,
        'phase1_efficiency_target': 0.90,
    }

    try:
        # PHASE 1 OPTIMIZATION: Process segments sequentially for immediate streaming
        for i, seg_text in enumerate(segments):
            logger.debug(f"[{request_id}] Processing segment {i+1}/{total_segments}: '{seg_text[:30]}...'")
            
            # Generate audio for this segment immediately
            try:
                segment_start_time = time.perf_counter()
                idx, audio_np, provider = await run_in_threadpool(
                    _generate_audio_segment, i, seg_text, voice, speed, lang
                )
                segment_duration = time.perf_counter() - segment_start_time
                
                logger.debug(f"[{request_id}] Segment {idx} completed in {segment_duration:.2f}s by {provider}")
                
                if audio_np is not None and audio_np.size > 0:
                    # Convert audio to bytes immediately
                    scaled_audio = np.int16(audio_np * 32767)
                    segment_bytes = scaled_audio.tobytes()
                    
                    # PHASE 1 OPTIMIZATION: Yield chunks immediately in smaller pieces
                    # This ensures faster TTFA by not waiting for complete segments
                    chunk_size = TTSConfig.CHUNK_SIZE_BYTES
                    offset = 0
                    
                    while offset < len(segment_bytes):
                        chunk = segment_bytes[offset:offset + chunk_size]
                        current_time = time.monotonic()
                        chunk_timing_state['chunk_count'] += 1
                        
                        # PHASE 1 OPTIMIZATION: Track first chunk for TTFA calculation
                        if chunk_timing_state['first_chunk_time'] is None:
                            chunk_timing_state['first_chunk_time'] = current_time
                            ttfa_ms = (current_time - chunk_timing_state['stream_start_time']) * 1000
                            logger.info(f"[{request_id}] PHASE 1 OPTIMIZATION: First chunk yielded in {ttfa_ms:.2f}ms")
                            
                            if ttfa_ms < chunk_timing_state['phase1_ttfa_target_ms']:
                                logger.info(f"[{request_id}] ✅ PHASE 1 TARGET ACHIEVED: TTFA < {chunk_timing_state['phase1_ttfa_target_ms']}ms")
                            else:
                                logger.warning(f"[{request_id}] ⚠️ PHASE 1 TARGET MISSED: TTFA {ttfa_ms:.2f}ms > {chunk_timing_state['phase1_ttfa_target_ms']}ms")
                        
                        # Calculate actual audio duration represented by this chunk
                        actual_audio_duration_ms = (len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE) * 1000
                        chunk_timing_state['total_audio_duration_ms'] += actual_audio_duration_ms
                        
                        # Log progress every 10 chunks
                        if chunk_timing_state['chunk_count'] % 10 == 0:
                            elapsed_time = current_time - chunk_timing_state['stream_start_time']
                            expected_time = chunk_timing_state['total_audio_duration_ms'] / 1000
                            current_efficiency = expected_time / elapsed_time if elapsed_time > 0 else 0
                            logger.debug(f"[{request_id}] Chunk {chunk_timing_state['chunk_count']}: Efficiency {current_efficiency*100:.1f}%")
                        
                        # Yield the chunk immediately
                        logger.debug(f"[{request_id}] Yielding chunk {chunk_timing_state['chunk_count']} of {len(chunk)} bytes from segment {i+1}")
                        yield chunk
                        
                        offset += chunk_size
                    
                    successful_segments += 1
                    
                    # Clear the numpy array to free memory immediately
                    del audio_np, scaled_audio
                    
                else:
                    logger.warning(f"[{request_id}] Segment {i} ('{seg_text[:30]}...') produced no audio and will be skipped.")
                    
            except Exception as e:
                logger.error(f"[{request_id}] Failed to process segment {i}: {e}", exc_info=True)
                continue

        # PHASE 1 OPTIMIZATION: Final streaming statistics
        total_time = time.perf_counter() - start_time
        total_stream_time = time.monotonic() - chunk_timing_state['stream_start_time']
        
        logger.info(f"[{request_id}] PHASE 1 OPTIMIZATION: Streaming completed")
        logger.info(f"[{request_id}] Final statistics:")
        logger.info(f"[{request_id}]   • Total time: {total_time:.2f}s")
        logger.info(f"[{request_id}]   • Stream time: {total_stream_time:.2f}s")
        logger.info(f"[{request_id}]   • Segments processed: {successful_segments}/{total_segments}")
        logger.info(f"[{request_id}]   • Chunks yielded: {chunk_timing_state['chunk_count']}")
        logger.info(f"[{request_id}]   • Audio duration: {chunk_timing_state['total_audio_duration_ms']:.1f}ms")
        
        if chunk_timing_state['first_chunk_time']:
            ttfa_ms = (chunk_timing_state['first_chunk_time'] - chunk_timing_state['stream_start_time']) * 1000
            logger.info(f"[{request_id}]   • TTFA: {ttfa_ms:.2f}ms")
            
            if ttfa_ms < chunk_timing_state['phase1_ttfa_target_ms']:
                logger.info(f"[{request_id}] ✅ PHASE 1 SUCCESS: TTFA target achieved")
            else:
                logger.warning(f"[{request_id}] ⚠️ PHASE 1 NEEDS IMPROVEMENT: TTFA target not met")

    except Exception as e:
        logger.error(f"[{request_id}] Streaming error: {e}", exc_info=True)
        raise

    if successful_segments == 0:
        logger.error(f"[{request_id}] No segments were successfully processed")
        raise HTTPException(status_code=500, detail="Audio generation failed for all segments") 