# Kokoro TTS Startup & Priming Optimizations

## Executive Summary

This document outlines optimizations to improve Kokoro TTS startup performance and maintain a primed, ready state for optimal request handling. With 64GB RAM available, we can be more aggressive about keeping models and sessions warm in memory.

**Current State**:
- Fast init: ~17.3s
- Background warming: ~32s (optimized to skip if models cached)
- Service ready: ~17.3s (after fast init)
- Memory footprint: Minimal (~142MB baseline, ~300MB steady-state)

**Target State**:
- Fast init: <10s
- Service ready: <10s
- Memory footprint: ~500-800MB (acceptable with 64GB available)
- Always primed: Periodic keep-alive prevents cold starts

## Critical Issues Identified

### 1. Missing Function Import (FIXED)

**Problem**: `detect_apple_silicon` doesn't exist in `scripts/simple_graph_optimize.py`

**Impact**: Auto-optimization fails on startup, falls back to original model

**Fix**: Use `detect_apple_silicon_capabilities` from `api.model.hardware`

**Status**: ✅ Fixed

### 7. Emergency Cleanup Triggered by Hardcoded CPU Provider (FIXED)

**Problem**: `_fast_generate_audio_segment` was hardcoded to use `CPUExecutionProvider` for all segments, causing severe performance degradation (13.4s TTFA) for long text segments and triggering emergency session cleanup.

**Root Cause**:
- Single-segment requests (common for long documents) always used the "fast path"
- Fast path was hardcoded to CPU provider regardless of text length
- CPU provider is optimal for short text (<200 chars) but very slow for long text (>1000 chars)
- Long text on CPU: 13,495ms TTFA (16.9x the 800ms target) → triggered emergency cleanup

**Impact**: 
- Emergency cleanup triggered unnecessarily for long text requests
- Performance degradation: 13.4s TTFA vs expected <2s with CoreML
- User experience: Very slow response times for document-length text

**Fix**: Replaced hardcoded CPU provider with adaptive provider selection based on text length:
```python
# Before:
provider = "CPUExecutionProvider"  # Hardcoded

# After:
from api.model.sessions.manager import get_adaptive_provider
text_length = len(processed_text)
provider = get_adaptive_provider(text_length)  # Adaptive selection
```

**Expected Improvement**:
- Long text (>1000 chars): Now uses CoreML → ~2-3s TTFA (vs 13.4s)
- Short text (<200 chars): Still uses CPU → ~8-10ms TTFA (optimal)
- Medium text (200-1000 chars): Uses current provider or avoids CoreML ALL if needed
- Emergency cleanup: Only triggers for actual performance issues, not provider selection mistakes

**Status**: ✅ Fixed

### 8. Fast Path Regression for Long Single-Segment Requests (FIXED)

**Problem**: After implementing adaptive provider selection in `_fast_generate_audio_segment`, long single-segment requests were incorrectly routed through the fast path, causing severe audio playback regressions.

**Root Cause**:
- Fast path selection logic: `(j in fast_indices) or (j == 0 and len(segments) == 1)`
- This meant ANY single-segment request (even very long ones) used the fast path
- Fast path was designed for SHORT primer segments (<200 chars), not long text
- Long text in fast path with adaptive provider selection caused performance issues and potential audio corruption

**Impact**:
- Long single-segment requests (common for documents) used inappropriate fast path
- Audio playback regressions: slow, corrupted, or failed playback
- Performance degradation for long text requests

**Fix**: Added text length check to fast path selection:
```python
# Before:
use_fast_local = (j in fast_indices) or (j == 0 and len(segments) == 1)

# After:
is_single_segment = len(segments) == 1
is_short_text = len(seg) < 200
use_fast_local = (j in fast_indices) or (j == 0 and is_single_segment and is_short_text)
```

**Expected Improvement**:
- Long single-segment requests: Now use fallback path → proper handling via dual session manager
- Short single-segment requests: Still use fast path → optimal CPU performance
- Primer segments: Continue using fast path → low TTFA maintained
- Audio playback: Should work correctly for all text lengths

**Status**: ✅ Fixed

### 2. Model Cache Duplication (OPTIMIZED)

**Problem**: Dual session manager creates separate Kokoro model instances instead of reusing cached models

**Evidence**:
```
WARNING - PERFORMANCE ISSUE: Creating new Kokoro model for provider: CPUExecutionProvider (cache miss)
WARNING - Current cache contents: []
```

**Impact**:
- 3x model loading overhead (~21-24s total)
- 3x memory usage for model instances
- Context leak warnings multiply

**Solution**: 
- Added `_ensure_main_model_cached()` method to ensure main model is cached before dual sessions initialize
- CPU session already uses shared model cache (optimized)
- ANE/GPU sessions require separate ONNX Runtime sessions due to different CoreML compute units (CPUAndNeuralEngine vs CPUAndGPU), so they cannot share the same Kokoro model instance
- However, they can use cached CPU model for fallback

**Status**: ✅ Optimized (ANE/GPU sessions inherently need separate sessions, but cache coordination improved)

### 3. Memory Management Too Aggressive

**Problem**: With 64GB RAM available, aggressive cleanup may be unnecessary and counterproductive for keeping things primed

**Current Settings**:
- Aggressive cleanup: True
- Memory threshold: 500MB
- Cleanup frequency: After every operation

**Recommendation**: 
- Increase memory threshold to 2GB (plenty of headroom)
- Reduce cleanup frequency for idle periods
- Keep models in memory longer

**Priority**: MEDIUM

### 4. No Periodic Keep-Alive

**Problem**: After idle periods, models may go "cold" requiring re-warming

**Impact**: First request after idle period may be slow (~1-2s overhead)

**Solution**: Implement periodic keep-alive warmup every 5-10 minutes during idle periods

**Priority**: MEDIUM

### 5. Overlapping Warmup Operations

**Problem**: Multiple warmup systems run concurrently with overlapping responsibilities

**Phases**:
1. Fast init minimal warmup
2. Background extended warming
3. Dual session pre-warming
4. Aggressive session warming
5. Pipeline warmer

**Impact**: Redundant work, wasted CPU cycles

**Solution**: Coordinate warmup through single coordinator

**Priority**: LOW (nice to have)

## Optimization Plan

### Phase 1: Critical Fixes (COMPLETED)

#### 1.1 Fix Model Cache Sharing ✅

**File**: `api/model/sessions/dual_session.py`

**Changes**:
- Added `_ensure_main_model_cached()` method to ensure main model is cached before dual sessions initialize
- CPU session already uses `get_or_create_cached_model("CPUExecutionProvider")` (optimized)
- ANE/GPU sessions require separate ONNX Runtime sessions due to different CoreML compute units, so they cannot share the same Kokoro model instance
- Added proper documentation explaining why ANE/GPU need separate sessions

**Expected Impact**: Prevents cache misses, ensures CPU model is available for fallback

**Status**: ✅ Completed (ANE/GPU sessions inherently need separate sessions, but cache coordination improved)

#### 1.2 Optimize Memory Management for Priming

**File**: `api/model/memory/coreml_leak_mitigation.py`

**Changes**:
- Increase `MEMORY_THRESHOLD_MB` from 200MB to 2000MB (2GB)
- Add environment variable `KOKORO_MEMORY_THRESHOLD_MB` for configuration
- Reduce cleanup frequency during idle periods
- Add "priming mode" that keeps models warm longer

**Expected Impact**: Better priming, fewer unnecessary cleanups

**Risk**: Low (with 64GB RAM, 2GB threshold is safe)

### Phase 2: Keep-Alive & Priming (COMPLETED)

#### 2.1 Periodic Keep-Alive Warmup ✅

**New File**: `api/model/initialization/keep_alive.py`

**Features**:
- Background task that runs every 5-10 minutes during idle periods
- Performs minimal warmup inference to keep models primed
- Configurable interval via `KOKORO_KEEP_ALIVE_INTERVAL_SECONDS` (default: 300s)
- Only runs if no requests in last 2 minutes

**Status**: ✅ Completed

#### 2.2 Optimize Background Extended Warming ✅

**File**: `api/model/initialization/fast_init.py`

**Optimizations**:
- Skip adaptive provider cache warming if models already cached (saves ~14-16s)
- Limit extended warming patterns to 2 max
- Only warmup existing models (don't create new ones)
- Add `KOKORO_SKIP_EXTENDED_WARMING=true` to disable entirely

**Expected Impact**: Reduce background warming from ~32s to <5s when models cached

**Status**: ✅ Completed

#### 2.2 Enhanced Memory Threshold Detection

**File**: `api/model/memory/coreml_leak_mitigation.py`

**Changes**:
- Detect available system RAM
- Auto-adjust threshold based on available memory
- For systems with >32GB RAM, use more aggressive thresholds

**Expected Impact**: Better memory management for high-RAM systems

**Risk**: Low

### Phase 3: Warmup Coordination (Medium-term)

#### 3.1 Unified Warmup Coordinator

**File**: `api/model/initialization/warmup_coordinator.py` (enhance existing)

**Features**:
- Single coordinator for all warmup operations
- Eliminates duplicate warmup inferences
- Coordinates timing to avoid conflicts

**Expected Impact**: Save ~2-3s startup time, reduce redundant work

**Risk**: Medium (requires careful coordination)

## Implementation Details

### Memory Management Configuration

```python
# Environment variables for priming optimization
KOKORO_MEMORY_THRESHOLD_MB=2000  # 2GB threshold (was 200MB)
KOKORO_KEEP_ALIVE_INTERVAL_SECONDS=300  # 5 minutes
KOKORO_KEEP_ALIVE_ENABLED=true
KOKORO_PRIMING_MODE=true  # Keep models warm longer
```

### Keep-Alive Implementation

```python
async def periodic_keep_alive():
    """Periodic warmup to keep models primed during idle periods."""
    while True:
        await asyncio.sleep(KOKORO_KEEP_ALIVE_INTERVAL_SECONDS)
        
        # Check if we've had recent requests
        if time.time() - last_request_time < 120:
            continue  # Skip if recent activity
        
        # Perform minimal warmup
        try:
            model = get_model()
            if model:
                model.create("Hi", "af_heart", 1.0, "en-us")
                logger.debug("Keep-alive warmup completed")
        except Exception as e:
            logger.debug(f"Keep-alive warmup failed: {e}")
```

### Model Cache Sharing

```python
# In dual_session.py __init__()
def _ensure_main_model_cached(self):
    """Ensure main model is cached before initializing dual sessions."""
    # Ensures CPU model is cached (used for fallback)
    cpu_model = get_or_create_cached_model("CPUExecutionProvider")
    
    # Ensures CoreML model is cached if main model uses it
    if active_provider == "CoreMLExecutionProvider":
        coreml_model = get_or_create_cached_model("CoreMLExecutionProvider")

# For CPU session (already optimized)
cpu_model = get_or_create_cached_model("CPUExecutionProvider")
self.sessions["cpu"] = cpu_model

# For ANE/GPU sessions: These require separate ONNX Runtime sessions
# due to different CoreML compute units (CPUAndNeuralEngine vs CPUAndGPU)
# They cannot share the same Kokoro model instance, but can use cached CPU for fallback
```

## Expected Results

### Startup Performance

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Fast init | 17.3s | <10s | 42% faster |
| Service ready | 17.3s | <10s | 42% faster |
| Full optimization | 35.7s | <20s | 44% faster |

### Memory Usage

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Baseline | 142MB | 142MB | No change |
| Steady-state | 300MB | 500-800MB | Acceptable with 64GB |
| Peak (3 models) | ~900MB | ~500MB | 44% reduction |

### Priming Effectiveness

| Metric | Current | Target |
|--------|---------|--------|
| Cold start after idle | 1-2s | <100ms |
| Keep-alive overhead | N/A | <50ms |
| Memory efficiency | Good | Excellent |

## Testing Checklist

- [x] Model cache sharing works correctly (CPU session uses cache)
- [x] Main model cache ensured before dual sessions initialize
- [x] Memory threshold respects available RAM (auto-detected)
- [x] Keep-alive runs during idle periods
- [ ] Keep-alive doesn't interfere with requests (needs testing)
- [ ] Startup time < 10s (needs benchmarking)
- [ ] Memory usage acceptable (needs monitoring)
- [ ] No regressions in performance benchmarks (needs testing)

## Rollback Plan

If issues occur:

1. **Disable keep-alive**: Set `KOKORO_KEEP_ALIVE_ENABLED=false`
2. **Restore memory threshold**: Set `KOKORO_MEMORY_THRESHOLD_MB=200`
3. **Disable priming mode**: Set `KOKORO_PRIMING_MODE=false`
4. **Revert model cache changes**: Dual session manager can fall back to creating new models

## Monitoring

Track these metrics:
- Startup time (fast init, service ready, full optimization)
- Memory usage (baseline, steady-state, peak)
- Model cache hit/miss ratio
- Keep-alive execution frequency
- Cold start occurrences after idle periods

## References

- `docs/optimization/startup_analysis.md` - Detailed startup analysis
- `api/model/sessions/dual_session.py` - Dual session manager
- `api/tts/core.py` - Model cache implementation
- `api/model/memory/coreml_leak_mitigation.py` - Memory management

