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
from api.performance.request_tracker import server_tracker
from api.tts.text_processing import (
    get_phoneme_cache_stats,
    preprocess_text_for_inference,
    segment_text as split_segments,   # avoid name shadowing with local identifiers
    normalize_for_tts as _normalize_for_tts,
    clean_text as _clean_text,
)
from api.tts.audio_variation_handler import get_variation_handler

logger = logging.getLogger(__name__)

# Thread-safe cache for Kokoro model instances
_model_cache: Dict[str, Kokoro] = {}
_model_cache_lock = threading.Lock()

# TTL-aligned refresh tracking (aligns to benchmarking cadence)
_model_cache_last_refresh: float = time.time()
_model_cache_refresh_in_progress: bool = False

# Inference result cache (audio -> (samples, ts, provider))
_inference_cache: Dict[str, Tuple[np.ndarray, float, str]] = {}
_inference_cache_lock = threading.Lock()
_inference_cache_max_size = 1000
_inference_cache_ttl = 3600  # seconds

# Cache hit/miss tracking
_inference_cache_hits = 0
_inference_cache_misses = 0

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
    """Thread-safe retrieval of the properly initialized Kokoro model."""
    # First, try to use the model that was properly initialized at startup
    try:
        from api.model.sessions import get_model
        startup_model = get_model()
        if startup_model is not None:
            logger.info(f"✅ TTFA OPTIMIZATION: Using startup-initialized model for provider: {provider}")
            return startup_model
    except Exception as e:
        logger.warning(f"Could not get startup model: {e}")
    
    # Fallback: use the legacy cache system (but this should rarely happen)
    logger.error(f"🚫 TTFA ISSUE: FALLBACK to legacy model cache for provider: {provider}")
    logger.error(f" This indicates startup model initialization failed or model was not properly set!")
    
    # Trigger background refresh if TTL expired (non-blocking and no cold start)
    try:
        ttl_seconds = int(TTSConfig.get_benchmark_cache_duration())
    except Exception:
        ttl_seconds = 86400
    now = time.time()
    if (now - _model_cache_last_refresh) > max(3600, ttl_seconds):
        # Avoid spamming refresh attempts
        _trigger_background_model_cache_refresh()

    with _model_cache_lock:
        if provider not in _model_cache:
            logger.error(f"🚫 CRITICAL: Creating new Kokoro model for provider: {provider} (cache miss)")
            logger.error(f" This indicates startup model initialization failed!")
            logger.error(f" Current cache contents: {list(_model_cache.keys())}")
            _model_cache[provider] = Kokoro(
                model_path=TTSConfig.MODEL_PATH,
                voices_path=TTSConfig.VOICES_PATH,
                providers=[provider],
            )
            # Initialize last refresh time on first creation
            _set_model_cache_last_refresh(now)
        else:
            logger.debug(f"✅ Using cached Kokoro model for provider: {provider}")
        return _model_cache[provider]


def _set_model_cache_last_refresh(ts: float) -> None:
    global _model_cache_last_refresh
    _model_cache_last_refresh = ts


def _trigger_background_model_cache_refresh() -> None:
    """Kick off a non-blocking model cache refresh aligned to benchmark TTL.
    Does not clear existing cache to avoid cold starts; rebuilt models are hot-swapped when ready.
    """
    global _model_cache_refresh_in_progress
    if _model_cache_refresh_in_progress:
        return

    def _refresh_worker() -> None:
        global _model_cache_refresh_in_progress
        _model_cache_refresh_in_progress = True
        try:
            providers: List[str]
            with _model_cache_lock:
                providers = list(_model_cache.keys()) or [
                    "CPUExecutionProvider",
                    "CoreMLExecutionProvider",
                ]
            logger.info(f" Refreshing model cache in background for providers: {providers}")
            for p in providers:
                try:
                    new_model = Kokoro(
                        model_path=TTSConfig.MODEL_PATH,
                        voices_path=TTSConfig.VOICES_PATH,
                        providers=[p],
                    )
                    with _model_cache_lock:
                        _model_cache[p] = new_model
                    logger.debug(f"✅ Refreshed model for provider: {p}")
                except Exception as e:
                    logger.warning(f" Model cache refresh failed for provider {p}: {e}")
            _set_model_cache_last_refresh(time.time())
            logger.info("✅ Model cache refresh completed")
        finally:
            _model_cache_refresh_in_progress = False

    try:
        t = threading.Thread(target=_refresh_worker, daemon=True)
        t.start()
    except Exception as e:
        logger.debug(f" Could not start background model cache refresh: {e}")


def refresh_model_cache_now(providers: Optional[List[str]] = None, non_blocking: bool = True) -> None:
    """Public API: Refresh model cache now, aligning with benchmark cadence.
    If non_blocking=True, runs in a background thread; otherwise blocks.
    """
    def _run() -> None:
        try:
            target_providers: List[str]
            if providers is not None and len(providers) > 0:
                target_providers = providers
            else:
                with _model_cache_lock:
                    target_providers = list(_model_cache.keys()) or [
                        "CPUExecutionProvider",
                        "CoreMLExecutionProvider",
                    ]
            logger.info(f" Refreshing model cache now for providers: {target_providers}")
            for p in target_providers:
                try:
                    new_model = Kokoro(
                        model_path=TTSConfig.MODEL_PATH,
                        voices_path=TTSConfig.VOICES_PATH,
                        providers=[p],
                    )
                    with _model_cache_lock:
                        _model_cache[p] = new_model
                    logger.debug(f"✅ Refreshed model for provider: {p}")
                except Exception as e:
                    logger.warning(f" Model cache refresh failed for provider {p}: {e}")
            _set_model_cache_last_refresh(time.time())
            logger.info("✅ Model cache refresh completed")
        except Exception as e:
            logger.warning(f" Model cache refresh encountered an error: {e}")

    if non_blocking:
        try:
            t = threading.Thread(target=_run, daemon=True)
            t.start()
        except Exception as e:
            logger.debug(f" Could not start non-blocking model cache refresh: {e}")
            _run()
    else:
        _run()


def _create_inference_cache_key(text: str, voice: str, speed: float, lang: str) -> str:
    """Create cache key for inference results using normalized text.
    This ensures identical text hits cache even when phoneme preprocessing is skipped.
    """
    try:
        normalized = _clean_text(_normalize_for_tts(text))
    except Exception:
        normalized = text.strip()
    return hashlib.md5(f"{normalized}|{voice}|{speed:.3f}|{lang}".encode("utf-8")).hexdigest()


def _get_cached_inference(cache_key: str) -> Optional[Tuple[np.ndarray, str]]:
    """Retrieve cached inference result if valid."""
    global _inference_cache_hits, _inference_cache_misses
    
    with _inference_cache_lock:
        item = _inference_cache.get(cache_key)
        if not item:
            _inference_cache_misses += 1
            logger.debug(f"Cache miss {cache_key[:8]}…")
            return None
        
        samples, ts, provider = item
        if (time.time() - ts) < _inference_cache_ttl:
            _inference_cache_hits += 1
            logger.debug(f"Cache hit {cache_key[:8]}…")
            return samples, provider
        
        _inference_cache.pop(cache_key, None)
        _inference_cache_misses += 1
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
    global _inference_cache_hits, _inference_cache_misses
    
    with _inference_cache_lock:
        now = time.time()
        valid = sum(1 for _, (__, ts, ___) in _inference_cache.items() if (now - ts) < _inference_cache_ttl)
        expired = len(_inference_cache) - valid
        
        # Calculate real hit rates
        total_requests = _inference_cache_hits + _inference_cache_misses
        hit_rate = (_inference_cache_hits / total_requests * 100) if total_requests > 0 else 0.0
        miss_rate = (_inference_cache_misses / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "total_entries": len(_inference_cache),
            "valid_entries": valid,
            "expired_entries": expired,
            "cache_size_mb": len(_inference_cache) * 0.1,  # heuristic
            "hits": _inference_cache_hits,
            "misses": _inference_cache_misses,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
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
                                  request_id: str, no_cache: bool = False) -> Tuple[int, Optional[np.ndarray], str, str]:
    """
    Generate audio with corruption detection and fallback mechanisms.
    Combines full-fidelity path with CoreML corruption handling.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short", "none"

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
                return idx, samples, info, "cached"

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
                    return idx, validated_samples, info, "dual-session"
                
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
            return idx, None, "All generation paths corrupted", "corrupted"
        
        dur = time.perf_counter() - start
        update_inference_stats(dur, provider)
        
        if not no_cache:
            _cache_inference_result(cache_key, validated_samples, provider)
        
        info = provider + (f" [{preprocessing_info}]" if preprocessing_info else "")
        return idx, validated_samples, info, processing_method

    except Exception as e:
        logger.error(f"[{idx}] TTS generation failed: {e}", exc_info=True)
        return idx, None, str(e), "error"


def _fast_generate_audio_segment(idx: int, text: str, voice: str, speed: float, lang: str, 
                                 request_id: str, no_cache: bool = False) -> Tuple[int, Optional[np.ndarray], str, str]:
    """
    Latency-optimized path for primer segments with corruption detection.
    Uses adaptive provider selection (CoreML for most cases) for optimal performance.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short", "none"

    try:
        processed_text = text.strip()
        cache_key = _create_inference_cache_key(processed_text, voice, speed, lang)

        # Check cache (unless bypassed)
        if not no_cache:
            cached = _get_cached_inference(cache_key)
            if cached:
                samples, provider = cached
                logger.debug(f"[{idx}] Fast path cache hit")
                return idx, samples, f"{provider} (fast-cached)", "fast-cached"

        # Primer-fast path: use adaptive provider for optimal performance (CoreML for most cases)
        from api.model.sessions.manager import get_adaptive_provider
        provider = get_adaptive_provider(len(processed_text))
        model = _get_cached_model(provider)
        
        start = time.perf_counter()
        
        # Apply memory management if available
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
            return idx, None, "Fast generation corrupted", "corrupted"
        
        dur = time.perf_counter() - start
        update_inference_stats(dur, provider)
        
        if not no_cache:
            _cache_inference_result(cache_key, validated_samples, provider)
        
        logger.info(f"[{idx}] Fast segment in {dur:.4f}s via {provider}")
        return idx, validated_samples, provider, "fast"

    except Exception as e:
        logger.error(f"[{idx}] Fast TTS generation failed: {e}", exc_info=True)
        return idx, None, str(e), "error"


async def stream_tts_audio(
    text: str, voice: str, speed: float, lang: str, format: str, request: Request, no_cache: bool = False
) -> AsyncGenerator[bytes, None]:
    """
    Generate and stream TTS audio with CoreML variation handling and self-optimization.
    
    This combines the clean architecture with adaptive threshold management and
    corruption detection for robust streaming.
    """
    request_id = request.headers.get("x-request-id", "no-id")

    # Initialize WAV tracking variables
    header_size = 44  # Standard WAV header size
    total_audio_size = 0

    # Start server-side performance tracking
    server_tracker.start_request(request_id, text, voice, speed)
    server_tracker.log_event(request_id, "PROCESSING_START", {
        "text_length": len(text),
        "voice": voice,
        "speed": speed,
        "format": format,
        "no_cache": no_cache
    })
    
    logger.info(
        f"[{request_id}] Stream start: voice='{voice}', speed={speed}, format='{format}', "
        f"no_cache={no_cache}, text='{text[:30]}…'"
    )

    start_time = time.perf_counter()
    stream_success = True
    error_details = None
    
    # Add detailed timing diagnostics for streaming performance analysis
    timing_checkpoints = {
        "start": start_time,
        "text_processing_start": None,
        "text_processing_end": None,
        "first_segment_start": None,
        "first_segment_end": None,
        "first_chunk_yield": None,
    }

    # Get variation handler for CoreML precision tracking
    variation_handler = get_variation_handler()
    full_text_hash = variation_handler.get_text_hash(text, voice, speed, lang)

    if not get_model_status():
        logger.error(f"[{request_id}] Model not ready")
        raise HTTPException(status_code=503, detail="TTS model not ready.")
    
    # Log model status for debugging
    try:
        from api.model.sessions import get_model, get_active_provider
        startup_model = get_model()
        active_provider = get_active_provider()
        logger.info(f"[{request_id}] ✅ TTFA CHECK: Model status: loaded={startup_model is not None}, provider={active_provider}")
        if startup_model is None:
            logger.error(f"[{request_id}] 🚫 TTFA ISSUE: Startup model is None - this will cause 10+ second delays!")
    except Exception as e:
        logger.error(f"[{request_id}] 🚫 TTFA ISSUE: Could not check model status: {e}")

    # Segment the text (use aliased import to avoid shadowing)
    timing_checkpoints["text_processing_start"] = time.perf_counter()
    segments = split_segments(text, TTSConfig.MAX_SEGMENT_LENGTH)
    timing_checkpoints["text_processing_end"] = time.perf_counter()
    
    if not segments:
        raise HTTPException(status_code=400, detail="No valid text segments found")

    text_processing_time = (timing_checkpoints["text_processing_end"] - timing_checkpoints["text_processing_start"]) * 1000
    logger.info(f"[{request_id}] 📊 STREAMING DIAGNOSTICS: Text processing took {text_processing_time:.1f}ms")
    logger.info(f"[{request_id}] Text segmented into {len(segments)} parts")
    
    # Log text processing completion
    server_tracker.log_event(request_id, "TEXT_PROCESSING_COMPLETE", {
        "segment_count": len(segments),
        "total_text_length": len(text)
    })

    # Enhanced streaming state tracking with adaptive optimization
    chunk_state = {
        "chunk_count": 0,
        "first_chunk_time": None,
        "stream_start_time": time.monotonic(),
        "total_audio_duration_ms": 0.0,
        "ttfa_target_ms": 500,  # Reduced from 800ms for better responsiveness
        "efficiency_target": 0.95,  # Increased from 0.90 for better performance
        "adaptive_chunk_size": TTSConfig.get_adaptive_chunk_size_bytes(len(text)),
        "content_length_category": "short" if len(text) < 200 else ("medium" if len(text) <= 800 else "long"),
        "memory_cleanup_counter": 0,  # Track cleanup cycles
    }

    # Gap tracking for gapless audio streaming
    max_gap_ms = None  # Will be calculated during streaming if gaps are detected

    try:
        # Primer optimization for TTFA
        fast_indices: Set[int] = set()
        primer_hint_key: Optional[str] = None
        segments_override: Optional[List[str]] = None  # holds [early, rest, ...] if we split the primer

        def _split_segment_for_early_ttfa(seg: str) -> Tuple[str, str]:
            """Split first segment for faster TTFA with punctuation-aware guardrails.
            Respect config to disable primer splitting entirely.
            """
            if not getattr(TTSConfig, "ENABLE_PRIMER_SPLIT", False):
                return seg, ""

            length = len(seg)
            min_chars = getattr(TTSConfig, "FIRST_SEGMENT_MIN_CHARS", 120)
            require_punct = getattr(TTSConfig, "FIRST_SEGMENT_REQUIRE_PUNCT", True)

            # Do not split if below minimum threshold
            if length <= max(80, min_chars):
                return seg, ""

            # Candidate split target around 15% with bounds
            split_percentage = min(0.18, max(0.12, 120.0 / length))
            cut = int(length * split_percentage)

            # Search for punctuation boundary first, then fallback to space
            punct_found = False
            for i in range(max(0, cut - 40), min(length, cut + 60)):
                ch = seg[i]
                if ch in ".!?;:" or (i + 1 < length and seg[i:i+2] in [". ", "! ", "? ", "; ", ": "]):
                    cut = i + 1
                    punct_found = True
                    break
            if not punct_found:
                # Fallback to nearest whitespace
                for i in range(max(0, cut - 30), min(length, cut + 50)):
                    if seg[i].isspace():
                        cut = i
                        break

            early = seg[:cut].strip()
            rest = seg[cut:].strip()

            # Enforce minimum and punctuation requirement if configured
            if (len(early) < min_chars) or (require_punct and not any(p in early for p in ".!?;:")):
                return seg, ""

            return early, rest

        # Handle primer segment for immediate TTFA (optionally disabled)
        if segments:
            early, rest = _split_segment_for_early_ttfa(segments[0])
            if early and rest:
                primer_key = _get_primer_cache_key(early, voice, speed, lang)
                cached_primer = None if no_cache else _get_cached_primer(primer_key)

                if cached_primer is not None and cached_primer.size > 0:
                    try:
                        scaled = np.int16(np.asarray(cached_primer, dtype=np.float32) * 32767)
                        primer_bytes = scaled.tobytes()

                        # Track primer bytes for WAV size calculation
                        primer_yield_size = 0
                        first_chunk = primer_bytes[:max(1024, len(primer_bytes) // 4)]
                        primer_yield_size += len(first_chunk)
                        yield first_chunk

                        if len(primer_bytes) > 2048:
                            second_chunk = primer_bytes[max(1024, len(primer_bytes) // 4):max(2048, len(primer_bytes) // 2)]
                            primer_yield_size += len(second_chunk)
                            yield second_chunk

                        # Update WAV size tracking
                        if format.lower() == "wav":
                            total_audio_size += primer_yield_size

                        logger.info(f"[{request_id}] Primer emitted from cache ({len(primer_bytes)} bytes)")
                    except Exception as e:
                        logger.debug(f"[{request_id}] Primer emit failed: {e}")
                else:
                    segments_override = [early, rest] + segments[1:]
                    fast_indices.add(0)
                    primer_hint_key = primer_key

        # WAV header (if requested) - optimized for gapless streaming
        if format.lower() == "wav":
            try:
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

                # Track total audio size for WAV header correction
                # For streaming WAV, we initially send placeholder sizes (0xFFFFFFFF)
                # and send a correction header at the end if possible
                struct.pack_into("<4sI", wav_header, 36, b"data", 0xFFFFFFFF - header_size)
                yield bytes(wav_header)

                # Add optimized silence for playback kickstart - reduced from 50ms to 25ms for faster startup
                # This provides just enough buffer for audio pipeline initialization without noticeable delay
                silence_ms = 25  # Reduced for faster TTFA
                silence_samples = int(TTSConfig.SAMPLE_RATE * (silence_ms / 1000))
                silence_bytes = np.int16(np.zeros(silence_samples)).tobytes()
                if format.lower() == "wav":
                    total_audio_size += len(silence_bytes)
                yield silence_bytes

            except Exception as e:
                logger.error(f"[{request_id}] WAV header generation failed: {e}; falling back to PCM")
                format = "pcm"

        # Process segments with adaptive generation and lookahead prefetch to avoid inter-segment gaps
        processed_count = 0
        total_audio_bytes = 0
        
        # Use overridden segments if primer split was applied; otherwise use original segments
        segments_to_process: List[str] = segments_override if segments_override is not None else segments

        async def _generate_segment_async(j: int):
            seg = segments_to_process[j]
            use_fast_local = (j in fast_indices) or (j == 0 and len(segments) == 1)
            start_local = time.perf_counter()
            if use_fast_local:
                return await run_in_threadpool(_fast_generate_audio_segment, j, seg, voice, speed, lang, request_id, no_cache), time.perf_counter() - start_local, use_fast_local
            else:
                return await run_in_threadpool(_generate_audio_with_fallback, j, seg, voice, speed, lang, request_id, no_cache), time.perf_counter() - start_local, use_fast_local

        n = len(segments_to_process)
        if n == 0:
            logger.error(f"[{request_id}] No segments to process after preprocessing")
            raise HTTPException(status_code=400, detail="No valid text segments found")

        # Prefetch current and next
        current_index = 0
        current_future = asyncio.create_task(_generate_segment_async(current_index))
        next_future = asyncio.create_task(_generate_segment_async(1)) if n > 1 else None

        while current_index < n:
            try:
                if current_index == 0:
                    timing_checkpoints["first_segment_start"] = time.perf_counter()
                
                (idx, audio_np, provider, method), gen_time, use_fast = await current_future
                
                if current_index == 0:
                    timing_checkpoints["first_segment_end"] = time.perf_counter()
                    first_segment_time = (timing_checkpoints["first_segment_end"] - timing_checkpoints["first_segment_start"]) * 1000
                    logger.info(f"[{request_id}] 📊 STREAMING DIAGNOSTICS: First segment generation took {first_segment_time:.1f}ms")
                
                logger.debug(f"[{request_id}] Segment {current_index} generated in {gen_time:.3f}s via {provider}")

                if audio_np is None:
                    logger.error(f"[{request_id}] Segment {current_index} produced no audio, skipping")
                    current_index += 1
                    current_future = next_future if next_future is not None else None
                    if (current_index + 1) < n and next_future is None:
                        next_future = asyncio.create_task(_generate_segment_async(current_index + 1))
                    continue

                processed_count += 1

                # Store primer if applicable
                if (current_index in fast_indices) and primer_hint_key and (not no_cache):
                    try:
                        _put_cached_primer(primer_hint_key, audio_np)
                        logger.debug(f"[{request_id}] Primer stored in micro-cache")
                    except Exception as e:
                        logger.debug(f"[{request_id}] Primer cache store failed: {e}")

                # Convert to streaming format
                scaled = np.clip(audio_np * 32767.0, -32768, 32767).astype(np.int16)
                segment_bytes = scaled.tobytes()
                total_audio_bytes += len(segment_bytes)

                # Track audio size for WAV header correction
                if format.lower() == "wav":
                    total_audio_size += len(segment_bytes)

                # Use adaptive chunk sizing based on total text length for optimal streaming performance
                # This balances responsiveness with stability for gapless audio
                adaptive_chunk_size = TTSConfig.get_adaptive_chunk_size_bytes(len(text))
                chunk_size = max(1024, adaptive_chunk_size // 2) if use_fast else adaptive_chunk_size
                offset = 0

                # Ensure next is prefetching
                if (current_index + 1) < n and next_future is None:
                    next_future = asyncio.create_task(_generate_segment_async(current_index + 1))

                while offset < len(segment_bytes):
                    chunk = segment_bytes[offset:offset + chunk_size]
                    current_time = time.monotonic()
                    chunk_state["chunk_count"] += 1

                    if chunk_state["first_chunk_time"] is None:
                        chunk_state["first_chunk_time"] = current_time
                        timing_checkpoints["first_chunk_yield"] = current_time
                        ttfa_ms = (current_time - chunk_state["stream_start_time"]) * 1000.0
                        logger.info(f"[{request_id}] 📊 STREAMING DIAGNOSTICS: First chunk yielded in {ttfa_ms:.2f}ms")
                        logger.info(f"[{request_id}] First chunk in {ttfa_ms:.2f} ms")
                        server_tracker.log_event(request_id, "FIRST_CHUNK_GENERATED", {"ttfa_ms": ttfa_ms, "chunk_size": len(chunk)})

                    # Track audio duration
                    chunk_state["total_audio_duration_ms"] += (
                        len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE
                    ) * 1000.0

                    if (chunk_state["chunk_count"] % 10) == 0:
                        elapsed = current_time - chunk_state["stream_start_time"]
                        expected = chunk_state["total_audio_duration_ms"] / 1000.0
                        efficiency = (expected / elapsed) if elapsed > 0 else 0.0
                        logger.debug(f"[{request_id}] Chunk {chunk_state['chunk_count']}: efficiency {efficiency*100:.1f}%")

                    # Track gaps between chunks for gapless audio analysis
                    if chunk_state["chunk_count"] > 1:  # Skip first chunk (no previous gap)
                        chunk_duration_ms = (len(chunk) / TTSConfig.BYTES_PER_SAMPLE / TTSConfig.SAMPLE_RATE) * 1000.0
                        expected_gap_ms = chunk_duration_ms  # Expected gap should match chunk duration for gapless

                        # Update max_gap_ms if this gap is larger
                        if max_gap_ms is None or expected_gap_ms > max_gap_ms:
                            max_gap_ms = expected_gap_ms

                    yield chunk
                    offset += chunk_size

                # Optimized memory cleanup with garbage collection hints for sustained streaming
                del audio_np, scaled, segment_bytes

                # Force garbage collection periodically to prevent memory buildup during long streams
                # Only on every 5th segment to balance performance and memory management
                if current_index % 5 == 0:
                    import gc
                    gc.collect()

                # Move to next
                current_index += 1
                current_future = next_future if next_future is not None else None
                next_future = asyncio.create_task(_generate_segment_async(current_index + 1)) if (current_index + 1) < n else None

                # Track audio size variation only at the very end
                if current_index == n:
                    variation_analysis = variation_handler.record_audio_size(full_text_hash, total_audio_bytes)
                    if not variation_analysis['is_consistent']:
                        logger.info(
                            f"[{request_id}]  Audio size variation detected: {variation_analysis['variation_pct']:.1f}% "
                            f"(current: {total_audio_bytes}, baseline: {variation_analysis['baseline_size']}, "
                            f"threshold: {variation_analysis['threshold_used']:.1f}%)"
                        )

            except Exception as e:
                logger.error(f"[{request_id}] Error processing segment {current_index}: {e}", exc_info=True)
                error_details = str(e)
                current_index += 1
                current_future = next_future if next_future is not None else None
                next_future = asyncio.create_task(_generate_segment_async(current_index + 1)) if (current_index + 1) < n else None
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

        # Adaptive performance compliance check based on content length
        content_length = len(text)
        adaptive_ttfa_target = (
            300 if content_length < 200 else  # Short content: very fast target
            500 if content_length <= 800 else  # Medium content: standard target
            700  # Long content: relaxed target for stability
        )

        compliant = bool(
            (ttfa_ms is not None and ttfa_ms < adaptive_ttfa_target) and
            (rtf < 1.0) and
            (efficiency >= chunk_state["efficiency_target"]) and
            (max_gap_ms is None or max_gap_ms < 50)  # Gapless audio requirement
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

        # Session cleanup - DISABLED to prevent audio gaps
        # This was causing 8+ second delays after every request
        # dual_session_manager = get_dual_session_manager()
        # if dual_session_manager:
        #     try:
        #         dual_session_manager.cleanup_sessions()
        #         logger.debug(f"[{request_id}] Session cleanup completed")
        #     except Exception as e:
        #         logger.warning(f"[{request_id}] Session cleanup failed: {e}")
        #         if not error_details:
        #             error_details = f"Session cleanup failed: {e}"

        # Record stream health for optimization
        variation_handler.record_stream_health(
            text_hash=full_text_hash,
            stream_success=stream_success and processed_count > 0,
            error_details=error_details,
            latency_ms=stream_time * 1000,
            chunk_count=chunk_state["chunk_count"]
        )

        # Log audio generation completion with performance tracker
        server_tracker.log_event(request_id, "AUDIO_GENERATION_COMPLETE", {
            "processing_time_ms": total_time * 1000,
            "total_chunks": chunk_state["chunk_count"],
            "audio_duration_ms": chunk_state["total_audio_duration_ms"],
            "streaming_efficiency": efficiency
        })
        
        # Complete server-side performance tracking
        server_tracker.complete_request(request_id)
        
        # Enhanced final logging with optimization details
        adaptive_chunk_duration = TTSConfig.get_adaptive_chunk_duration_ms(len(text))
        # Send WAV header correction if applicable
        # For streaming WAV, we send a metadata chunk with correct file sizes
        # This allows clients to reconstruct proper WAV files from streams
        if format.lower() == "wav" and total_audio_size > 0:
            try:
                # Create a correction metadata chunk
                # Format: "WAVC" (WAV Correction) + total_file_size + data_size
                total_file_size = header_size + total_audio_size
                correction_data = struct.pack("<4sII", b"WAVC", total_file_size, total_audio_size)
                yield correction_data
                logger.debug(f"[{request_id}] Sent WAV header correction: file_size={total_file_size}, data_size={total_audio_size}")
            except Exception as e:
                logger.debug(f"[{request_id}] WAV correction failed: {e}")

        logger.info(f"[{request_id}] Streaming completed successfully")
        logger.info(f"[{request_id}] Optimization: content_length={len(text)}, "
                   f"category={chunk_state['content_length_category']}, "
                   f"adaptive_chunk_duration={adaptive_chunk_duration}ms")
        # Null-safe formatting for metrics that may be None
        ttfa_str = f"{ttfa_ms:.1f}" if ttfa_ms is not None else "N/A"
        rtf_str = f"{rtf:.2f}" if rtf is not None else "N/A"
        efficiency_str = f"{efficiency:.1f}" if efficiency is not None else "N/A"
        max_gap_str = f"{max_gap_ms:.1f}" if max_gap_ms is not None else "N/A"
        
        logger.info(f"[{request_id}] Performance: segments={processed_count}/{len(segments_to_process)}, "
                   f"chunks={chunk_state['chunk_count']}, TTFA={ttfa_str}ms, RTF={rtf_str}, "
                   f"efficiency={efficiency_str}%, max_gap={max_gap_str}ms, compliant={compliant}")
        
        # Log detailed streaming diagnostics
        if timing_checkpoints["first_chunk_yield"]:
            total_to_first_chunk = (timing_checkpoints["first_chunk_yield"] - timing_checkpoints["start"]) * 1000
            logger.info(f"[{request_id}] 📊 STREAMING DIAGNOSTICS SUMMARY:")
            logger.info(f"[{request_id}]   • Total time to first chunk: {total_to_first_chunk:.1f}ms")
            if timing_checkpoints["text_processing_end"]:
                text_time = (timing_checkpoints["text_processing_end"] - timing_checkpoints["text_processing_start"]) * 1000
                logger.info(f"[{request_id}]   • Text processing: {text_time:.1f}ms")
            if timing_checkpoints["first_segment_end"]:
                segment_time = (timing_checkpoints["first_segment_end"] - timing_checkpoints["first_segment_start"]) * 1000
                logger.info(f"[{request_id}]   • First segment generation: {segment_time:.1f}ms")
                chunk_yield_time = (timing_checkpoints["first_chunk_yield"] - timing_checkpoints["first_segment_end"]) * 1000
                logger.info(f"[{request_id}]   • Chunk processing & yield: {chunk_yield_time:.1f}ms")

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
        
        # Session cleanup on error - DISABLED to prevent audio gaps
        # This was causing 8+ second delays during error conditions
        # try:
        #     dual_session_manager = get_dual_session_manager()
        #     if dual_session_manager:
        #         dual_session_manager.cleanup_sessions()
        # except Exception as cleanup_err:
        #     logger.warning(f"[{request_id}] Error cleanup failed: {cleanup_err}")
        
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
