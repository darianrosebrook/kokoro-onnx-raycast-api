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
from api.model.loader import get_model, get_model_status, get_active_provider
from api.performance.stats import update_performance_stats
from api.tts.text_processing import (
    segment_text,
)
import threading

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


def _generate_audio_segment(
    idx: int, text: str, voice: str, speed: float, lang: str
) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Generates a single audio segment with enhanced caching and thread safety.
    
    This function implements inference pipeline caching for common requests
    to avoid redundant processing and improve performance.
    
    Reference: DEPENDENCY_RESEARCH.md section 5.2
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short"

    try:
        # Create cache key for this inference
        cache_key = _create_inference_cache_key(text, voice, speed, lang)
        
        # Check cache first
        cached_result = _get_cached_inference(cache_key)
        if cached_result is not None:
            samples, provider = cached_result
            logger.debug(f"[{idx}] Using cached audio for: {text[:50]}...")
            # Update cache hit statistics
            update_performance_stats(0.001, provider)  # Minimal time for cache hit
            return idx, samples, f"{provider} (cached)"
        
        # Cache miss - generate new audio
        provider = get_active_provider()
        local_model = _get_cached_model(provider)

        logger.debug(f"[{idx}] Generating audio for: {text[:50]}...")
        start_time = time.perf_counter()

        samples, _ = local_model.create(text, voice, speed, lang)
        
        inference_time = time.perf_counter() - start_time
        update_performance_stats(inference_time, provider)
        
        if samples is not None and samples.size > 0:
            # Cache the successful result
            _cache_inference_result(cache_key, samples, provider)
            
            logger.info(f"[{idx}] Segment processed in {inference_time:.4f}s using {provider}")
            return idx, samples, provider
        else:
            logger.warning(f"[{idx}] TTS model returned empty audio for text: {text[:50]}...")
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
    results_buffer: Dict[int, Optional[np.ndarray]] = {}
    tasks: Dict[int, asyncio.Task] = {}
    next_idx = 0

    for i, seg_text in enumerate(segments):
        task = asyncio.create_task(
            run_in_threadpool(_generate_audio_segment, i, seg_text, voice, speed, lang)
        )
        tasks[i] = task

    if format == "wav":
        try:
            header_size = 44
            data_size = 0xFFFFFFFF - header_size
            wav_header = bytearray(header_size)
            struct.pack_into(
                "<4sI4s", wav_header, 0, b"RIFF", data_size + 36, b"WAVE"
            )
            struct.pack_into(
                "<4sIHHIIHH",
                wav_header,
                12,
                b"fmt ",
                16,
                1,
                1,
                TTSConfig.SAMPLE_RATE,
                TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE * 1,
                TTSConfig.BYTES_PER_SAMPLE * 1,
                TTSConfig.BYTES_PER_SAMPLE * 8,
            )
            struct.pack_into("<4sI", wav_header, 36, b"data", data_size)
            yield bytes(wav_header)
        except Exception as e:
            logger.error(f"Failed to generate WAV header: {e}")
            format = "pcm"

    last_yield_time = time.monotonic()
    successful_segments = 0
    audio_output_buffer = io.BytesIO()

    # Enhanced chunk timing tracking for debugging streaming pipeline
    chunk_timing_state = {
        'chunk_count': 0,
        'last_chunk_yield_time': None,
        'last_chunk_end_time': None,
        'total_audio_duration_ms': 0,
        'timing_gaps': [],
        'timing_overlaps': [],
        'stream_start_time': time.monotonic()  # Track when streaming actually starts
    }

    try:
        while True:
            tasks_to_remove = []
            for i in sorted(tasks.keys()):
                if tasks[i].done():
                    try:
                        idx, audio_np, provider = tasks[i].result()
                        if audio_np is not None and audio_np.size > 0:
                            results_buffer[idx] = audio_np
                            logger.debug(f"[{request_id}] Segment {idx} completed successfully by {provider}.")
                        else:
                            segment_text_log = (
                                segments[idx] if idx < len(segments) else "unknown"
                            )
                            logger.warning(
                                f"[{request_id}] Segment {idx} ('{segment_text_log[:30]}...') produced no audio and will be skipped."
                            )
                    except Exception as e:
                        logger.error(f"[{request_id}] Task for segment {i} failed: {e}", exc_info=True)
                    tasks_to_remove.append(i)

            for i in tasks_to_remove:
                del tasks[i]

            # Memory-efficient processing: process segments immediately to reduce memory usage
            while next_idx < total_segments and next_idx in results_buffer:
                audio_np = results_buffer.pop(next_idx)
                if audio_np is not None:
                    # Memory-efficient audio conversion
                    scaled_audio = np.int16(audio_np * 32767)
                    segment_bytes = scaled_audio.tobytes()
                    audio_output_buffer.write(segment_bytes)
                    successful_segments += 1
                    
                    # Clear the numpy array to free memory immediately
                    del audio_np, scaled_audio
                next_idx += 1

            audio_output_buffer.seek(0)
            while True:
                chunk = audio_output_buffer.read(TTSConfig.CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                
                # Enhanced chunk timing tracking for streaming pipeline debugging
                current_time = time.monotonic()
                chunk_timing_state['chunk_count'] += 1
                
                # Calculate actual audio duration represented by this chunk
                actual_audio_duration_ms = (len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE) * 1000
                chunk_timing_state['total_audio_duration_ms'] += actual_audio_duration_ms
                
                # Track timing between chunks for gap/overlap detection
                if chunk_timing_state['last_chunk_end_time'] is not None:
                    # Time since last chunk should have finished playing
                    gap_ms = (current_time - chunk_timing_state['last_chunk_end_time']) * 1000
                    
                    if gap_ms > 5:  # Gap of more than 5ms
                        chunk_timing_state['timing_gaps'].append(gap_ms)
                        logger.debug(f"[{request_id}] Chunk {chunk_timing_state['chunk_count']}: Gap of {gap_ms:.1f}ms between chunk end and next chunk start")
                    elif gap_ms < -5:  # Next chunk arrived before previous should finish (overlap)
                        chunk_timing_state['timing_overlaps'].append(abs(gap_ms))
                        logger.debug(f"[{request_id}] Chunk {chunk_timing_state['chunk_count']}: Received next chunk {abs(gap_ms):.1f}ms before current chunk ended")
                    else:
                        logger.debug(f"[{request_id}] Chunk {chunk_timing_state['chunk_count']}: Good timing - next chunk arrived {gap_ms:.1f}ms after expected")
                
                # Yield the chunk
                logger.debug(f"[{request_id}] Yielding chunk {chunk_timing_state['chunk_count']} of {len(chunk)} bytes (audio duration: {actual_audio_duration_ms:.1f}ms).")
                yield chunk
                last_yield_time = current_time
                
                # Calculate when this chunk should finish playing
                chunk_timing_state['last_chunk_yield_time'] = current_time
                chunk_timing_state['last_chunk_end_time'] = current_time + (actual_audio_duration_ms / 1000)
                
                # FIXED: Dynamic audio-duration-based pacing
                # Calculate actual audio duration from chunk size instead of using fixed delays
                if len(audio_output_buffer.getvalue()) > 0:  # More chunks pending
                    # FIXED: Use 80% of actual audio duration for optimal streaming efficiency
                    # This allows the stream to catch up and achieve 80-100% efficiency target
                    pacing_delay = (actual_audio_duration_ms / 1000) * 0.8
                    
                    # Additional safety: minimum 5ms delay to prevent burst streaming
                    pacing_delay = max(pacing_delay, 0.005)
                    
                    logger.debug(f"[{request_id}] Chunk {chunk_timing_state['chunk_count']} audio_duration: {actual_audio_duration_ms:.1f}ms, pacing_delay: {pacing_delay*1000:.1f}ms")
                    await asyncio.sleep(pacing_delay)

            # Enhanced memory management for buffer
            remaining_data = audio_output_buffer.read()
            audio_output_buffer.seek(0)
            audio_output_buffer.truncate(0)
            if remaining_data:
                audio_output_buffer.write(remaining_data)
            audio_output_buffer.flush()
            
            # Periodic cache cleanup during long operations
            if successful_segments % 10 == 0:  # Clean up every 10 segments
                cleanup_inference_cache()

            if await request.is_disconnected():
                logger.info(f"[{request_id}] Client disconnected, stopping stream.")
                break

            if (
                next_idx >= total_segments
                and len(audio_output_buffer.getvalue()) == 0
                and not tasks
            ):
                logger.info(f"[{request_id}] All segments processed and buffer empty, completing stream.")
                break

            if (
                time.monotonic() - last_yield_time
                > TTSConfig.STREAM_IDLE_TIMEOUT_SECONDS
            ):
                logger.warning(
                    f"[{request_id}] Stream idle timeout ({TTSConfig.STREAM_IDLE_TIMEOUT_SECONDS}s), stopping stream."
                )
                break

            if (
                len(audio_output_buffer.getvalue()) < TTSConfig.CHUNK_SIZE_BYTES
                and (next_idx < total_segments or tasks)
            ):
                await asyncio.sleep(0.005)

    except Exception as e:
        logger.error(f"Error in audio streaming: {e}", exc_info=True)
    finally:
        # Enhanced streaming performance summary with timing analysis
        if chunk_timing_state['chunk_count'] > 0:
            # FIXED: Calculate streaming time from start to end, not from last yield
            stream_start_time = chunk_timing_state.get('stream_start_time', None)
            if stream_start_time is None:
                # Fallback: estimate from first chunk timing
                total_streaming_time = (chunk_timing_state['total_audio_duration_ms'] / 1000) * 0.95
            else:
                total_streaming_time = time.monotonic() - stream_start_time
            
            avg_gap = sum(chunk_timing_state['timing_gaps']) / len(chunk_timing_state['timing_gaps']) if chunk_timing_state['timing_gaps'] else 0
            avg_overlap = sum(chunk_timing_state['timing_overlaps']) / len(chunk_timing_state['timing_overlaps']) if chunk_timing_state['timing_overlaps'] else 0
            
            # FIXED: Correct streaming efficiency calculation
            # Efficiency = (time stream should take) / (time stream actually took)
            expected_streaming_time = chunk_timing_state['total_audio_duration_ms'] / 1000
            streaming_efficiency = (expected_streaming_time / total_streaming_time * 100) if total_streaming_time > 0 else 0
            
            logger.info(f"[{request_id}] 📊 Streaming Performance Summary:")
            logger.info(f"[{request_id}]   - Total chunks: {chunk_timing_state['chunk_count']}")
            logger.info(f"[{request_id}]   - Total audio duration: {chunk_timing_state['total_audio_duration_ms']:.0f}ms")
            logger.info(f"[{request_id}]   - Actual streaming time: {total_streaming_time*1000:.0f}ms")
            logger.info(f"[{request_id}]   - Streaming efficiency: {streaming_efficiency:.1f}% (target: 80-100%)")
            logger.info(f"[{request_id}]   - Timing gaps: {len(chunk_timing_state['timing_gaps'])} (avg: {avg_gap:.1f}ms)")
            logger.info(f"[{request_id}]   - Timing overlaps: {len(chunk_timing_state['timing_overlaps'])} (avg: {avg_overlap:.1f}ms)")
            
            # Enhanced warnings with specific guidance
            overlap_percentage = (len(chunk_timing_state['timing_overlaps']) / chunk_timing_state['chunk_count']) * 100
            if overlap_percentage > 50:
                logger.warning(f"[{request_id}] ⚠️ High overlap rate ({overlap_percentage:.0f}%) - chunks arriving too fast")
            if streaming_efficiency > 200:
                logger.warning(f"[{request_id}] ⚠️ Streaming too fast ({streaming_efficiency:.0f}%) - reduce pacing delay")
            elif streaming_efficiency < 50:
                logger.warning(f"[{request_id}] ⚠️ Streaming too slow ({streaming_efficiency:.0f}%) - increase pacing delay")
            if avg_gap > 100:
                logger.warning(f"[{request_id}] ⚠️ Large average gap ({avg_gap:.1f}ms) - may cause audio stuttering")
            if avg_overlap > 50:
                logger.warning(f"[{request_id}] ⚠️ Large average overlap ({avg_overlap:.1f}ms) - may cause buffer overflow")
        
        logger.info(f"[{request_id}] Cleaning up stream resources.")
        for task in list(tasks.values()):
            if not task.done():
                task.cancel()
        try:
            await asyncio.gather(
                *[t for t in tasks.values() if not t.done()], return_exceptions=True
            )
        except Exception as e:
            logger.debug(f"Task cleanup completed with exceptions: {e}") 