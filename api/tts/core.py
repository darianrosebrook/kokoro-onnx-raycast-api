"""
Core TTS functionality for the Kokoro-ONNX API.

This module handles the core TTS functionality, including:
- Text processing and segmentation
- Audio generation with CoreML variation handling
- Streaming audio with adaptive optimization
- Self-optimizing threshold management

Merged version combining clean architecture with CoreML precision handling.

@author: @darianrosebrook
@date: 2025-08-15
@version: 2.0.0
@license: MIT
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""

import asyncio
import hashlib
import logging
import struct
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

import numpy as np
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from kokoro_onnx import Kokoro

from api.config import TTSConfig
from api.model.loader import (
    get_active_provider,
    get_dual_session_manager,
    get_model_status,
)
from api.performance.stats import (
    update_endpoint_performance_stats,
    update_inference_stats,
)
from api.tts.text_processing import (
    get_phoneme_cache_stats,
    preprocess_text_for_inference,
    segment_text as split_segments,   # avoid name shadowing with local identifiers
)
from api.tts.audio_variation_handler import get_variation_handler

logger = logging.getLogger(__name__)

# Thread-safe cache for Kokoro model instances
_model_cache: Dict[str, Kokoro] = {}
_model_cache_lock = threading.Lock()

# Inference result cache (audio -> (samples, ts, provider))
_inference_cache: Dict[str, Tuple[np.ndarray, float, str]] = {}
_inference_cache_lock = threading.Lock()
_inference_cache_max_size = 1000
_inference_cache_ttl = 3600  # seconds

# Primer micro-cache for the very first tiny segment (TTFA boost)
_primer_microcache: Dict[str, Tuple[np.ndarray, float]] = {}
_primer_microcache_ttl_s: float = 300.0  # 5 minutes
_primer_microcache_hits: int = 0
_primer_microcache_misses: int = 0


def _get_primer_cache_key(text: str, voice: str, speed: float, lang: str) -> str:
    """Generate cache key for primer segments."""
    return hashlib.md5(f"primer:{text[:700]}:{voice}:{speed}:{lang}".encode("utf-8")).hexdigest()


def _get_cached_primer(key: str) -> Optional[np.ndarray]:
    """Retrieve cached primer if valid."""
    entry = _primer_microcache.get(key)
    if not entry:
        globals()["_primer_microcache_misses"] = globals().get("_primer_microcache_misses", 0) + 1
        return None
    
    samples, ts = entry
    if (time.time() - ts) > _primer_microcache_ttl_s:
        _primer_microcache.pop(key, None)
        globals()["_primer_microcache_misses"] = globals().get("_primer_microcache_misses", 0) + 1
        return None
    
    globals()["_primer_microcache_hits"] = globals().get("_primer_microcache_hits", 0) + 1
    return samples


def _put_cached_primer(key: str, samples: np.ndarray) -> None:
    """Store primer in micro-cache with size bounds."""
    # Keep micro-cache bounded
    if len(_primer_microcache) > 64:
        for k in list(_primer_microcache.keys())[:8]:
            _primer_microcache.pop(k, None)
    _primer_microcache[key] = (samples, time.time())


def get_primer_microcache_stats() -> Dict[str, Any]:
    """Get primer cache statistics."""
    size = len(_primer_microcache)
    hits = globals().get("_primer_microcache_hits", 0)
    misses = globals().get("_primer_microcache_misses", 0)
    total = hits + misses
    return {
        "entries": size,
        "ttl_seconds": _primer_microcache_ttl_s,
        "hits": hits,
        "misses": misses,
        "hit_rate_percent": (hits / total) * 100 if total > 0 else 0.0,
    }


def _get_cached_model(provider: str) -> Kokoro:
    """Thread-safe retrieval/creation of a Kokoro model bound to a provider."""
    with _model_cache_lock:
        if provider not in _model_cache:
            logger.warning(f"🔄 PERFORMANCE ISSUE: Creating new Kokoro model for provider: {provider} (cache miss)")
            logger.warning(f"🔄 Current cache contents: {list(_model_cache.keys())}")
            _model_cache[provider] = Kokoro(
                model_path=TTSConfig.MODEL_PATH,
                voices_path=TTSConfig.VOICES_PATH,
                providers=[provider],
            )
        else:
            logger.debug(f"✅ Using cached Kokoro model for provider: {provider}")
        return _model_cache[provider]


def _create_inference_cache_key(text: str, voice: str, speed: float, lang: str) -> str:
    """Create cache key for inference results."""
    return hashlib.md5(f"{text}|{voice}|{speed:.3f}|{lang}".encode("utf-8")).hexdigest()


def _get_cached_inference(cache_key: str) -> Optional[Tuple[np.ndarray, str]]:
    """Retrieve cached inference result if valid."""
    with _inference_cache_lock:
        item = _inference_cache.get(cache_key)
        if not item:
            return None
        
        samples, ts, provider = item
        if (time.time() - ts) < _inference_cache_ttl:
            logger.debug(f"Cache hit {cache_key[:8]}…")
            return samples, provider
        
        _inference_cache.pop(cache_key, None)
        logger.debug(f"Cache expired {cache_key[:8]}…")
        return None


def _cache_inference_result(cache_key: str, audio_array: np.ndarray, provider: str) -> None:
    """Cache inference result with size management."""
    with _inference_cache_lock:
        if len(_inference_cache) >= _inference_cache_max_size:
            # Evict oldest entries
            for k in list(_inference_cache.keys())[:50]:
                _inference_cache.pop(k, None)
            logger.debug("Evicted 50 old cache entries")
        
        # Store as float32 for large arrays to save memory
        audio_to_cache = audio_array.astype(np.float32, copy=False) if audio_array.size > 10000 else audio_array
        _inference_cache[cache_key] = (audio_to_cache, time.time(), provider)


def cleanup_inference_cache() -> None:
    """Clean up expired cache entries."""
    with _inference_cache_lock:
        now = time.time()
        expired = [k for k, (_, ts, _) in _inference_cache.items() if (now - ts) >= _inference_cache_ttl]
        for k in expired:
            _inference_cache.pop(k, None)
        if expired:
            import gc
            gc.collect()
            logger.debug(f"Cleaned {len(expired)} cache entries")


def get_inference_cache_stats() -> Dict[str, Any]:
    """Get inference cache statistics."""
    with _inference_cache_lock:
        now = time.time()
        valid = sum(1 for _, (__, ts, ___) in _inference_cache.items() if (now - ts) < _inference_cache_ttl)
        expired = len(_inference_cache) - valid
        return {
            "total_entries": len(_inference_cache),
            "valid_entries": valid,
            "expired_entries": expired,
            "cache_size_mb": len(_inference_cache) * 0.1,  # heuristic
            "hit_rate": 0.0,
            "miss_rate": 0.0,
        }


def should_use_phoneme_preprocessing() -> bool:
    """Skip heavier preprocessing when FAST_STREAMING_MODE is set."""
    try:
        return not getattr(TTSConfig, "FAST_STREAMING_MODE", False)
    except Exception:
        return True


def _is_simple_segment(text: str) -> bool:
    """Check if segment is simple enough to skip heavy preprocessing."""
    if not text:
        return False
    s = text.strip()
    if len(s) > 150:
        return False
    
    import re as _re
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}:\d{2}:\d{2}",
        r"[^\x00-\x7F]",
        r"[{}[\]()@#$%^&*+=<>]",
        r"\d+\.\d+",
    ]
    return not any(_re.search(p, s) for p in patterns)


def get_tts_processing_stats() -> Dict[str, Any]:
    """Get comprehensive TTS processing statistics."""
    try:
        return {
            "inference_cache": get_inference_cache_stats(),
            "phoneme_cache": get_phoneme_cache_stats(),
            "primer_cache": get_primer_microcache_stats(),
            "phoneme_preprocessing_enabled": should_use_phoneme_preprocessing(),
            "active_provider": get_active_provider(),
            "variation_handler": get_variation_handler().get_statistics(),
        }
    except Exception as e:
        logger.warning(f"Could not get TTS processing stats: {e}")
        return {
            "inference_cache": {},
            "phoneme_cache": {},
            "primer_cache": {},
            "phoneme_preprocessing_enabled": False,
            "active_provider": "Unknown",
            "error": str(e),
        }


def _validate_and_handle_audio_corruption(audio_np: Any, segment_idx: int, request_id: str) -> Optional[np.ndarray]:
    """
    Validate audio output and handle CoreML corruption cases.
    
    This is the critical fix for CoreML precision variations that return scalar values
    instead of proper audio arrays.
    """
    if audio_np is None:
        return None
    
    # CRITICAL: Check for scalar corruption (CoreML precision issue)
    if isinstance(audio_np, (int, float)):
        logger.error(f"[{request_id}] CORRUPTION DETECTED: Segment {segment_idx} returned scalar {type(audio_np)}: {audio_np}")
        return None
    
    # Convert to numpy array and validate
    try:
        audio_array = np.asarray(audio_np, dtype=np.float32)
        
        # Check for scalar arrays
        if audio_array.ndim == 0:
            logger.error(f"[{request_id}] CORRUPTION: Segment {segment_idx} returned scalar array: {audio_array}")
            return None
        
        # Check for insufficient audio data
        if audio_array.size <= 1:
            logger.error(f"[{request_id}] CORRUPTION: Segment {segment_idx} returned array with size {audio_array.size}")
            return None
        
        # Reshape to 1D and handle NaN/Inf
        audio_array = audio_array.reshape(-1)
        audio_array = np.nan_to_num(audio_array, nan=0.0, posinf=1.0, neginf=-1.0)
        
        logger.debug(f"[{request_id}] Segment {segment_idx} validated: shape={audio_array.shape}, size={audio_array.size}")
        return audio_array
        
    except Exception as e:
        logger.error(f"[{request_id}] Audio validation failed for segment {segment_idx}: {e}")
        return None


def _generate_audio_with_fallback(idx: int, text: str, voice: str, speed: float, lang: str, 
                                  request_id: str, no_cache: bool = False) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Generate audio with corruption detection and fallback mechanisms.
    Combines full-fidelity path with CoreML corruption handling.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short"

    try:
        processed_text = text
        preprocessing_info = ""

        # Phoneme preprocessing for complex text
        processing_method = "unknown"
        if should_use_phoneme_preprocessing() and not _is_simple_segment(text):
            try:
                prep = preprocess_text_for_inference(text)
                processed_text = prep["normalized_text"]
                processing_method = prep.get("processing_method", "unknown")
                preprocessing_info = f"phonemes:{prep.get('original_length')}→{prep.get('padded_length')}"
                if prep.get("cache_hit"):
                    preprocessing_info += " (cached)"
                if prep.get("truncated"):
                    preprocessing_info += " (truncated)"
                    logger.warning(f"[{idx}] Text truncated during phoneme processing")
            except Exception as e:
                logger.warning(f"[{idx}] Phoneme preprocessing failed: {e}; fallback to raw text")
                processed_text = text
                preprocessing_info = "fallback"
                processing_method = "fallback"

        # Check cache (unless bypassed)
        cache_key = _create_inference_cache_key(processed_text, voice, speed, lang)
        if not no_cache:
            cached = _get_cached_inference(cache_key)
            if cached:
                samples, provider = cached
                update_inference_stats(0.001, provider)
                info = f"{provider} (cached)"
                if preprocessing_info:
                    info += f" [{preprocessing_info}]"
                return idx, samples, info

        # Primary path: Dual-session processing with corruption detection
        dsm = get_dual_session_manager()
        if dsm:
            start = time.perf_counter()
            try:
                result = dsm.process_segment_concurrent(processed_text, voice, speed, lang)
                samples = result[0] if isinstance(result, tuple) else result
                
                # CRITICAL: Validate for CoreML corruption
                validated_samples = _validate_and_handle_audio_corruption(samples, idx, request_id)
                
                if validated_samples is not None:
                    dur = time.perf_counter() - start
                    likely = "ANE" if dsm.get_utilization_stats().get("sessions_available", {}).get("ane") else "GPU"
                    provider = f"DualSession-{likely}"
                    
                    update_inference_stats(dur, provider)
                    if not no_cache:
                        _cache_inference_result(cache_key, validated_samples, provider)
                    
                    info = provider
                    if preprocessing_info:
                        info += f" [{preprocessing_info}]"
                    return idx, validated_samples, info
                
                logger.warning(f"[{idx}] DualSession returned corrupted audio, falling back to single model")
                
            except Exception as e:
                logger.warning(f"[{idx}] Dual session failed: {e}; falling back to single model")

        # Fallback path: Single model with corruption detection
        from api.model.sessions.manager import get_adaptive_provider
        provider = get_adaptive_provider(len(processed_text))
        model = _get_cached_model(provider)
        
        start = time.perf_counter()
        
        # Apply CoreML memory management for single model inference
        try:
            from api.model.memory.coreml_leak_mitigation import get_memory_manager
            manager = get_memory_manager()
            
            with manager.managed_operation(f"single_inference_{processed_text[:20]}"):
                result = model.create(processed_text, voice, speed, lang)
                
        except ImportError:
            # Fallback without memory management if not available
            result = model.create(processed_text, voice, speed, lang)
        
        samples = result[0] if isinstance(result, tuple) else result
        
        # CRITICAL: Validate single model output too
        validated_samples = _validate_and_handle_audio_corruption(samples, idx, request_id)
        
        if validated_samples is None:
            logger.error(f"[{idx}] CRITICAL: Both DualSession and single model returned corrupted audio")
            return idx, None, "All generation paths corrupted"
        
        dur = time.perf_counter() - start
        update_inference_stats(dur, provider)
        
        if not no_cache:
            _cache_inference_result(cache_key, validated_samples, provider)
        
        info = provider + (f" [{preprocessing_info}]" if preprocessing_info else "")
        return idx, validated_samples, info, processing_method

    except Exception as e:
        logger.error(f"[{idx}] TTS generation failed: {e}", exc_info=True)
        return idx, None, str(e)


def _fast_generate_audio_segment(idx: int, text: str, voice: str, speed: float, lang: str, 
                                 request_id: str, no_cache: bool = False) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Latency-optimized path for primer segments with corruption detection.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short"

    try:
        processed_text = text.strip()
        cache_key = _create_inference_cache_key(processed_text, voice, speed, lang)

        # Check cache (unless bypassed)
        if not no_cache:
            cached = _get_cached_inference(cache_key)
            if cached:
                samples, provider = cached
                logger.debug(f"[{idx}] Fast path cache hit")
                return idx, samples, f"{provider} (fast-cached)"

        # Fast dual-session path with corruption detection
        dsm = get_dual_session_manager()
        if dsm:
            start = time.perf_counter()
            try:
                result = dsm.process_segment_concurrent(processed_text, voice, speed, lang)
                samples = result[0] if isinstance(result, tuple) else result
                
                # CRITICAL: Validate for corruption
                validated_samples = _validate_and_handle_audio_corruption(samples, idx, request_id)
                
                if validated_samples is not None:
                    dur = time.perf_counter() - start
                    provider = "DualSession-Fast"
                    
                    if not no_cache:
                        _cache_inference_result(cache_key, validated_samples, provider)
                    
                    logger.info(f"[{idx}] Fast segment in {dur:.4f}s via {provider}")
                    return idx, validated_samples, provider
                
                logger.warning(f"[{idx}] Fast DualSession corrupted, falling back")
                
            except Exception as e:
                logger.warning(f"[{idx}] Fast dual session failed: {e}")

        # Fast single model fallback  
        from api.model.sessions.manager import get_adaptive_provider
        provider = get_adaptive_provider(len(processed_text))
        model = _get_cached_model(provider)
        
        start = time.perf_counter()
        
        # Apply CoreML memory management for fast path inference
        try:
            from api.model.memory.coreml_leak_mitigation import get_memory_manager
            manager = get_memory_manager()
            
            with manager.managed_operation(f"fast_inference_{processed_text[:20]}"):
                result = model.create(processed_text, voice, speed, lang)
                
        except ImportError:
            # Fallback without memory management if not available
            result = model.create(processed_text, voice, speed, lang)
        
        samples = result[0] if isinstance(result, tuple) else result
        
        # CRITICAL: Validate single model output
        validated_samples = _validate_and_handle_audio_corruption(samples, idx, request_id)
        
        if validated_samples is None:
            logger.error(f"[{idx}] CRITICAL: Fast path completely corrupted")
            return idx, None, "Fast generation corrupted"
        
        dur = time.perf_counter() - start
        fast_provider = f"{provider}-Fast"
        update_inference_stats(dur, fast_provider)
        
        if not no_cache:
            _cache_inference_result(cache_key, validated_samples, fast_provider)
        
        logger.info(f"[{idx}] Fast segment in {dur:.4f}s via {fast_provider}")
        return idx, validated_samples, fast_provider, "fast_path"

    except Exception as e:
        logger.error(f"[{idx}] Fast TTS generation failed: {e}", exc_info=True)
        return idx, None, str(e)


async def stream_tts_audio(
    text: str, voice: str, speed: float, lang: str, format: str, request: Request, no_cache: bool = False
) -> AsyncGenerator[bytes, None]:
    """
    Generate and stream TTS audio with CoreML variation handling and self-optimization.
    
    This combines the clean architecture with adaptive threshold management and
    corruption detection for robust streaming.
    """
    request_id = request.headers.get("x-request-id", "no-id")
    logger.info(
        f"[{request_id}] Stream start: voice='{voice}', speed={speed}, format='{format}', "
        f"no_cache={no_cache}, text='{text[:30]}…'"
    )

    start_time = time.perf_counter()
    stream_success = True
    error_details = None

    # Get variation handler for CoreML precision tracking
    variation_handler = get_variation_handler()
    full_text_hash = variation_handler.get_text_hash(text, voice, speed, lang)

    if not get_model_status():
        logger.error(f"[{request_id}] Model not ready")
        raise HTTPException(status_code=503, detail="TTS model not ready.")

    # Segment the text (use aliased import to avoid shadowing)
    segments = split_segments(text, TTSConfig.MAX_SEGMENT_LENGTH)
    if not segments:
        raise HTTPException(status_code=400, detail="No valid text segments found")

    logger.info(f"[{request_id}] Text segmented into {len(segments)} parts")

    # Streaming state tracking
    chunk_state = {
        "chunk_count": 0,
        "first_chunk_time": None,
        "stream_start_time": time.monotonic(),
        "total_audio_duration_ms": 0.0,
        "ttfa_target_ms": 800,
        "efficiency_target": 0.90,
    }

    try:
        # Primer optimization for TTFA
        fast_indices: Set[int] = set()
        primer_hint_key: Optional[str] = None
        segments_override: Optional[List[str]] = None  # holds [early, rest, ...] if we split the primer

        def _split_segment_for_early_ttfa(seg: str) -> Tuple[str, str]:
            """Split first segment for faster TTFA."""
            length = len(seg)
            if length <= 50:
                return seg, ""
            
            split_percentage = min(0.15, max(0.10, 50.0 / length))
            cut = int(length * split_percentage)
            
            # Find word boundary
            for i in range(cut, min(length, cut + 50)):
                if seg[i].isspace():
                    cut = i
                    break
            
            early = seg[:cut].strip()
            rest = seg[cut:].strip()
            
            if not early or len(early) < 10:
                return seg, ""
            
            return early, rest

        # Handle primer segment for immediate TTFA
        if segments:
            early, rest = _split_segment_for_early_ttfa(segments[0])
            if early and rest:
                primer_key = _get_primer_cache_key(early, voice, speed, lang)
                cached_primer = None if no_cache else _get_cached_primer(primer_key)
                
                if cached_primer is not None and cached_primer.size > 0:
                    # Emit cached primer immediately
                    try:
                        scaled = np.int16(np.asarray(cached_primer, dtype=np.float32) * 32767)
                        primer_bytes = scaled.tobytes()
                        
                        # Yield in small chunks for immediate playback
                        yield primer_bytes[:max(1024, len(primer_bytes) // 4)]
                        if len(primer_bytes) > 2048:
                            yield primer_bytes[max(1024, len(primer_bytes) // 4):max(2048, len(primer_bytes) // 2)]
                        
                        logger.info(f"[{request_id}] Primer emitted from cache ({len(primer_bytes)} bytes)")
                        
                    except Exception as e:
                        logger.debug(f"[{request_id}] Primer emit failed: {e}")
                else:
                    # Split segment and mark first for fast processing
                    segments_override = [early, rest] + segments[1:]
                    fast_indices.add(0)
                    primer_hint_key = primer_key

        # WAV header (if requested)
        if format.lower() == "wav":
            try:
                header_size = 44
                wav_header = bytearray(header_size)
                
                # RIFF header
                struct.pack_into("<4sI4s", wav_header, 0, b"RIFF", 0xFFFFFFFF - 8, b"WAVE")
                
                # fmt chunk (PCM, mono, 16-bit)
                struct.pack_into(
                    "<4sIHHIIHH",
                    wav_header, 12,
                    b"fmt ", 16, 1, 1,
                    TTSConfig.SAMPLE_RATE,
                    TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE,
                    TTSConfig.BYTES_PER_SAMPLE,
                    TTSConfig.BYTES_PER_SAMPLE * 8,
                )
                
                # data chunk with placeholder size
                struct.pack_into("<4sI", wav_header, 36, b"data", 0xFFFFFFFF - header_size)
                yield bytes(wav_header)

                # Add tiny silence for playback kickstart
                silence_ms = 50
                silence_samples = int(TTSConfig.SAMPLE_RATE * (silence_ms / 1000))
                yield np.int16(np.zeros(silence_samples)).tobytes()
                
            except Exception as e:
                logger.error(f"[{request_id}] WAV header generation failed: {e}; falling back to PCM")
                format = "pcm"

        # Process segments with adaptive generation
        processed_count = 0
        total_audio_bytes = 0
        
        # Use overridden segments if primer split was applied; otherwise use original segments
        segments_to_process: List[str] = segments_override if segments_override is not None else segments

        for i, seg_text in enumerate(segments_to_process):
            segment_start = time.perf_counter()
            
            try:
                # Choose processing path
                use_fast = (i in fast_indices) or (i == 0 and len(segments) == 1)
                
                if use_fast:
                    idx, audio_np, provider = await run_in_threadpool(
                        _fast_generate_audio_segment, i, seg_text, voice, speed, lang, request_id, no_cache
                    )
                else:
                    idx, audio_np, provider = await run_in_threadpool(
                        _generate_audio_with_fallback, i, seg_text, voice, speed, lang, request_id, no_cache
                    )

                segment_duration = time.perf_counter() - segment_start
                logger.debug(f"[{request_id}] Segment {i} completed in {segment_duration:.3f}s via {provider}")

                # Handle failed segments gracefully
                if audio_np is None:
                    logger.error(f"[{request_id}] Segment {i} produced no audio, skipping")
                    continue

                processed_count += 1

                # Store primer if applicable
                if (i in fast_indices) and primer_hint_key and (not no_cache):
                    try:
                        _put_cached_primer(primer_hint_key, audio_np)
                        logger.debug(f"[{request_id}] Primer stored in micro-cache")
                    except Exception as e:
                        logger.debug(f"[{request_id}] Primer cache store failed: {e}")

                # Convert to streaming format
                scaled = np.clip(audio_np * 32767.0, -32768, 32767).astype(np.int16)
                segment_bytes = scaled.tobytes()
                total_audio_bytes += len(segment_bytes)

                # Track audio size variation for optimization (use the *actual* list being processed)
                if i == len(segments_to_process) - 1:
                    variation_analysis = variation_handler.record_audio_size(full_text_hash, total_audio_bytes)
                    
                    if not variation_analysis['is_consistent']:
                        logger.info(
                            f"[{request_id}] 🎯 Audio size variation detected: {variation_analysis['variation_pct']:.1f}% "
                            f"(current: {total_audio_bytes}, baseline: {variation_analysis['baseline_size']}, "
                            f"threshold: {variation_analysis['threshold_used']:.1f}%)"
                        )

                # Stream in optimized chunks
                chunk_size = max(1024, TTSConfig.CHUNK_SIZE_BYTES // 2) if use_fast else TTSConfig.CHUNK_SIZE_BYTES
                offset = 0

                while offset < len(segment_bytes):
                    chunk = segment_bytes[offset:offset + chunk_size]
                    current_time = time.monotonic()
                    chunk_state["chunk_count"] += 1

                    # Track TTFA
                    if chunk_state["first_chunk_time"] is None:
                        chunk_state["first_chunk_time"] = current_time
                        ttfa_ms = (current_time - chunk_state["stream_start_time"]) * 1000.0
                        logger.info(f"[{request_id}] First chunk in {ttfa_ms:.2f} ms")

                    # Track audio duration
                    chunk_state["total_audio_duration_ms"] += (
                        len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE
                    ) * 1000.0

                    # Periodic efficiency logging
                    if (chunk_state["chunk_count"] % 10) == 0:
                        elapsed = current_time - chunk_state["stream_start_time"]
                        expected = chunk_state["total_audio_duration_ms"] / 1000.0
                        efficiency = (expected / elapsed) if elapsed > 0 else 0.0
                        logger.debug(f"[{request_id}] Chunk {chunk_state['chunk_count']}: efficiency {efficiency*100:.1f}%")

                    yield chunk
                    offset += chunk_size

                # Clean up segment memory
                del audio_np, scaled, segment_bytes

            except Exception as e:
                logger.error(f"[{request_id}] Error processing segment {i}: {e}", exc_info=True)
                error_details = str(e)
                continue

        # Final statistics and cleanup
        total_time = time.perf_counter() - start_time
        stream_time = time.monotonic() - chunk_state["stream_start_time"]
        
        # Calculate performance metrics
        first_chunk_time = chunk_state["first_chunk_time"]
        ttfa_ms = ((first_chunk_time - chunk_state["stream_start_time"]) * 1000.0) if first_chunk_time else None
        audio_seconds = chunk_state["total_audio_duration_ms"] / 1000.0
        rtf = (total_time / audio_seconds) if audio_seconds > 0 else 0.0
        efficiency = (audio_seconds / stream_time) if stream_time > 0 else 0.0

        # Performance compliance check
        compliant = bool(
            (ttfa_ms is not None and ttfa_ms < chunk_state["ttfa_target_ms"]) and
            (rtf < 1.0) and
            (efficiency >= chunk_state["efficiency_target"])
        )

        # Update performance stats
        try:
            update_endpoint_performance_stats(
                endpoint="stream_tts_audio",
                processing_time=total_time,
                success=True,
                ttfa_ms=float(ttfa_ms) if ttfa_ms is not None else 0.0,
                rtf=float(rtf),
                streaming_efficiency=float(efficiency),
                compliant=compliant,
            )
        except Exception as e:
            logger.debug(f"[{request_id}] Metrics update failed: {e}")

        # Session cleanup
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager:
            try:
                dual_session_manager.cleanup_sessions()
                logger.debug(f"[{request_id}] Session cleanup completed")
            except Exception as e:
                logger.warning(f"[{request_id}] Session cleanup failed: {e}")
                if not error_details:
                    error_details = f"Session cleanup failed: {e}"

        # Record stream health for optimization
        variation_handler.record_stream_health(
            text_hash=full_text_hash,
            stream_success=stream_success and processed_count > 0,
            error_details=error_details,
            latency_ms=stream_time * 1000,
            chunk_count=chunk_state["chunk_count"]
        )

        # Final logging
        logger.info(f"[{request_id}] Streaming completed successfully")
        logger.info(f"[{request_id}] Stats: segments={processed_count}/{len(segments_to_process)}, "
                   f"chunks={chunk_state['chunk_count']}, TTFA={ttfa_ms:.1f}ms, RTF={rtf:.2f}, "
                   f"efficiency={efficiency:.1f}%, compliant={compliant}")

        if processed_count == 0:
            logger.error(f"[{request_id}] No segments processed successfully")
            raise HTTPException(status_code=500, detail="Audio generation failed")

    except Exception as e:
        logger.error(f"[{request_id}] Streaming error: {e}", exc_info=True)
        
        # Record failed stream for optimization
        try:
            variation_handler.record_stream_health(
                text_hash=full_text_hash,
                stream_success=False,
                error_details=str(e),
                latency_ms=None,
                chunk_count=chunk_state.get("chunk_count", 0)
            )
        except Exception as health_err:
            logger.debug(f"[{request_id}] Failed to record stream health: {health_err}")
        
        # Session cleanup on error
        try:
            dual_session_manager = get_dual_session_manager()
            if dual_session_manager:
                dual_session_manager.cleanup_sessions()
        except Exception as cleanup_err:
            logger.warning(f"[{request_id}] Error cleanup failed: {cleanup_err}")
        
        raise


def _validate_segment_mapping(text: str, segments: List[str], request_id: str) -> bool:
    """Ensure segmentation preserved content (lenient whitespace normalization)."""
    original = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    seg_joined = " ".join(" ".join(segments).replace("\r", " ").replace("\n", " ").split())
    
    if original == seg_joined:
        logger.debug(f"[{request_id}] Segment mapping OK (exact match)")
        return True
    
    if abs(len(original) - len(seg_joined)) <= 5:
        logger.debug(f"[{request_id}] Segment mapping OK (length tolerance)")
        return True

    logger.warning(f"[{request_id}] Segment mapping mismatch: {len(original)} vs {len(seg_joined)}")
    return False


# Compatibility aliases for existing imports
def _generate_audio_segment(idx: int, text: str, voice: str, speed: float, lang: str) -> Tuple[int, Optional[np.ndarray], str, str]:
    """Compatibility wrapper for the legacy function name."""
    result = _generate_audio_with_fallback(idx, text, voice, speed, lang, f"legacy-{idx}", no_cache=False)
    # Extract processing method from the result
    if len(result) >= 4:
        return result
    else:
        # Handle legacy return format
        idx, audio_np, info = result
        return idx, audio_np, info, "unknown"
