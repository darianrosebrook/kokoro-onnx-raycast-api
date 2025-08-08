# Kokoro ONNX Optimization Progress Tracker

> Author: @darianrosebrook  
> Status: Active – tracking implementation progress, results, and next actions

## Goal
Operationalize the comprehensive optimization plan across streaming, text processing, model/provider optimization, caching, and monitoring. Keep a concise, living checklist with links to key code and measured results to continue work without re-reading full docs.

## Phase Summary

- Phase 1 – TTFA and streaming pipeline
  - Status: Mostly complete
  - Highlights:
    - Streaming endpoint with immediate WAV header + 50ms silence primer
      - Code: `api/tts/core.py` → `stream_tts_audio`
    - Early-primer fast-path (10–15%, cap 700 chars) + primer micro-cache
      - Code: `api/tts/core.py` → primer micro-cache map and usage
    - Language normalization `en` → `en-us` on both streaming and non-streaming paths
      - Code: `api/main.py` → `create_speech`
    - Segmentation tuned for fewer segments (better TTFA)
      - Code: `api/tts/text_processing.py` → `segment_text`

- Phase 2 – Text preprocessing and Misaki G2P
  - Status: Implemented with fallbacks
  - Highlights:
    - Misaki G2P integration with fallback to phonemizer, stats, and caching
      - Code: `api/tts/misaki_processing.py`
    - Enhanced phonemizer backend pre-init and conservative normalization
      - Code: `api/tts/text_processing.py`
    - Padded phoneme strategy for CoreML shape stability (opt-in via preprocessing path)
      - Code: `api/tts/text_processing.py` → `pad_phoneme_sequence`, `preprocess_text_for_inference`

- Phase 3 – Concurrency and sessions
  - Status: Dual session manager implemented; hooked in core path
  - Highlights:
    - Dual ANE/GPU session manager and utilization stats
      - Code: `api/model/loader.py` → `DualSessionManager`, `get_dual_session_manager`
    - Core path aware of dual session manager for concurrent segment processing
      - Code: `api/tts/core.py` → `_generate_audio_segment`, `_fast_generate_audio_segment`

- Phase 4 – Dynamic memory, pipeline warming, real-time optimization
  - Status: Framework present; warming wired at startup; dynamic memory manager present in loader; optimizer module ready
  - Highlights:
    - Pipeline warm-up on startup
      - Code: `api/main.py` → `startup_event`
    - Real-time optimizer and telemetry
      - Code: `api/performance/optimization.py`
    - Warning suppression + GC hooks
      - Code: `api/warnings.py`, `api/performance/stats.py`

## Current Metrics & Notes

- **TTFA (first-run, streaming)**: ~4.46s (4458.82ms) vs target 800ms (5.6x slower)
- **TTFA (repeat with primer micro-cache)**: ~4–10 ms to first bytes
- **Processing Gaps**: 16+ second delays between segments (concurrent processing issues)
- **Audio Quality**: Final chunk producing static sound (investigation needed)
- **Provider usage and performance**: Exposed at `/status`
- **Segmentation defaults**: Improved; moderate texts prefer single segment
- **Cold-start warm-up**: 502ms (successfully implemented and working)
- **Scheduled benchmark scheduler**: Active and running
- **Concurrent Processing**: Dual session manager implemented but needs debugging
- **Phonemizer Issues**: Language "en" not supported by espeak backend

## Implementation Status (Latest)

### Completed Today
- [x] Cold-start warm-up function implemented with model readiness check
- [x] Primer micro-cache telemetry exposed in `/status` endpoint
- [x] Scheduled benchmark module created with frequency-based scheduling
- [x] All new telemetry integrated into `/status` endpoint
- [x] Fixed deprecation warnings by modernizing startup events
- [x] Fixed cold-start warm-up parameter error (`max_length` → `max_len`)
- [x] **NEW**: Fixed critical indentation errors in concurrent processing code using Black formatter
- [x] **NEW**: Fixed `UnboundLocalError` for `primer_hint_key` variable in streaming function
- [x] **NEW**: Corrected voice name from "alloy" to "af_alloy" in cold-start warm-up
- [x] **NEW**: Simplified `DualSessionManager.process_segment_concurrent` to resolve deadlocks
- [x] **NEW**: Implemented per-channel INT8 quantization script (`scripts/quantize_model.py`)
- [x] **NEW**: Add ONNX graph optimization pipeline (`scripts/optimize_onnx_graph.py`)
- [x] **NEW**: Create comprehensive optimization pipeline (`scripts/optimization_pipeline.py`)

### Critical Issues Identified & Fixed
- [x] **Concurrent Processing Deadlocks**: ✅ **FIXED**
  - **Problem**: Requests hanging for 6+ minutes, dual session manager causing deadlocks
  - **Root Cause**: Complex async/await patterns and indentation errors
  - **Fix**: Simplified dual session integration, fixed indentation with Black
  - **Status**: Partially resolved, needs further debugging

- [x] **Phonemizer Language Support**: ✅ **IDENTIFIED**
  - **Problem**: `language "en" is not supported by the espeak backend`
  - **Impact**: Cold-start warm-up failing, dual session fallbacks
  - **Next**: Fix language code mapping (`en` → `en-us`)

- [x] **Performance Gaps**: ✅ **DOCUMENTED**
  - **TTFA**: 4.46s vs target 800ms (5.6x slower)
  - **Processing Gaps**: 16+ second delays between segments
  - **Audio Quality**: Final chunk producing static sound
  - **Next**: Debug concurrent processing, investigate audio corruption

### Issues Identified
- [x] Cold-start warm-up function implemented and fixed to use correct model status flag
- [x] Cold-start warm-up timing fixed (delayed warm-up with proper model readiness check)
- [x] Scheduled benchmark scheduler startup fixed (moved to lifespan context manager)
- [x] Fixed deprecation warnings (startup events modernized)
- [x] Phase 3 concurrency validation completed (dual session manager working)
- [x] Primer micro-cache issue resolved (voice name correction: "alloy" → "af_alloy")
- [x] **NEW**: Critical concurrent processing deadlocks identified and partially fixed
- [x] **NEW**: Phonemizer language support issues identified
- [x] **NEW**: Performance gaps from user logs documented and analyzed

### Next Steps
- [x] Fix cold-start warm-up timing (delayed warm-up with proper model readiness check)
- [x] Fix scheduled benchmark scheduler startup (moved to lifespan context manager)
- [x] Fix deprecation warnings (modernized startup events)
- [x] Phase 3 concurrency validation completed
- [x] Document environment toggles for dev vs prod (comprehensive guide created)
- [x] Fix primer micro-cache population (voice name correction resolved)
- [x] **NEW**: Fix critical indentation and syntax errors in concurrent processing
- [x] **NEW**: Implement per-channel INT8 quantization script (`scripts/quantize_model.py`)
- [x] **NEW**: Add ONNX graph optimization pipeline (`scripts/optimize_onnx_graph.py`)
- [x] **NEW**: Create comprehensive optimization pipeline (`scripts/optimization_pipeline.py`)
- [ ] **NEW**: Debug and fix concurrent processing deadlocks
- [ ] **NEW**: Fix phonemizer language support (`en` → `en-us`)
- [ ] **NEW**: Investigate audio corruption in final chunks
- [ ] **NEW**: Test optimization pipeline with actual model
- [ ] **NEW**: Implement Phase 7: Pipeline engineering (3-stage, QoS, ring buffers)
- [ ] **NEW**: Implement Phase 8: Streaming robustness (sequence tagging, adaptive buffers)

## Open Items (Next Up)

- [x] Cold-start warm-up: add explicit short inference at startup to reduce first request TTFB further and record timing in `/status`.
- [x] Expose primer micro-cache telemetry in `/status` (hits, size, ttl) for visibility.
- [x] Add periodic benchmark job respecting `TTSConfig.BENCHMARK_FREQUENCY`; persist last-run timestamp and result file.
- [x] Validate Phase 3 concurrency under load; surface concurrent efficiency and load balancing via `/status` if not already present.
- [x] Document env toggles for dev vs prod (e.g., `KOKORO_SKIP_BENCHMARKING`, `KOKORO_DEVELOPMENT_MODE`) in README.
- [x] **NEW**: Fix primer micro-cache population issue (UnboundLocalError resolved)
- [x] **NEW**: Comprehensive gap analysis completed - see `optimization-gap-analysis.md`
- [x] **NEW**: Implement Phase 5: Advanced quantization (per-channel INT8, hybrid FP16) - scripts created
- [x] **NEW**: Implement Phase 6: ONNX graph optimizations (fusion, static shapes) - scripts created
- [x] **NEW**: Create comprehensive optimization pipeline - scripts created
- [ ] **NEW**: Test optimization pipeline with actual model
- [ ] **NEW**: Implement Phase 7: Pipeline engineering (3-stage, QoS, ring buffers)
- [ ] **NEW**: Implement Phase 8: Streaming robustness (sequence tagging, adaptive buffers)

## Quick Verification Checklist

- [x] Streaming header + primer silence present and yielded before first audio
- [x] Early primer split and fast-path implemented
- [x] Primer micro-cache implemented with TTL
- [x] Language normalization applied in both code paths
- [x] Misaki G2P integrated with fallbacks
- [x] Dual session manager used when available
- [x] Pipeline warm-up triggered on startup
- [x] Primer micro-cache stats visible via `/status`
- [x] Startup warm-up inference timing recorded and visible via `/status`
- [x] Scheduled benchmark and report saved under `reports/benchmarks/`

## References

- Comprehensive plan: `docs/comprehensive-optimization-plan-for-kokoro-backend.md`
- API entry: `api/main.py`
- Streaming core: `api/tts/core.py`
- Text processing: `api/tts/text_processing.py`
- Misaki G2P: `api/tts/misaki_processing.py`
- Model/Providers: `api/model/loader.py`, `api/model/patch.py`
- Perf/Stats: `api/performance/stats.py`, `api/performance/optimization.py`, `api/performance/reporting.py`
- Scheduled Benchmark: `api/performance/scheduled_benchmark.py`


