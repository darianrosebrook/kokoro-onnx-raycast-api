# Startup Performance Analysis

## Executive Summary

**Total Startup Time**: ~28.6 seconds (from application start to ready)

### Key Timing Breakdown

| Phase                         | Duration | Blocking | Notes                         |
| ----------------------------- | -------- | -------- | ----------------------------- |
| Application initialization    | ~0.1s    | Yes      | Environment setup, validation |
| Fast initialization           | 8.87s    | Yes      | Model loading, minimal warmup |
| Model initialization complete | 28.19s   | Yes      | Includes all phases           |
| Background extended warming   | 19.0s    | No       | Runs in parallel thread       |
| Dual session pre-warming      | 4.4s     | No       | Runs in parallel thread       |

**Service Ready Time**: ~8.9s (after fast init completes)
**Full Optimization Time**: ~28.6s (all background tasks complete)

## Critical Duplication Issues

### 1. Model Cache Duplication ⚠️ HIGH PRIORITY

**Problem**: Dual session manager creates separate Kokoro model instances that don't share the main model cache.

**Evidence**:

```
Line 117: WARNING - PERFORMANCE ISSUE: Creating new Kokoro model for provider: CPUExecutionProvider (cache miss)
Line 118: WARNING - Current cache contents: []
Line 124: WARNING - PERFORMANCE ISSUE: Creating new Kokoro model for provider: CoreMLExecutionProvider (cache miss)
Line 125: WARNING - Current cache contents: ['CPUExecutionProvider']
```

**Root Cause**:

- `api/tts/core.py` maintains `_model_cache` dictionary
- `api/model/sessions/dual_session.py` creates separate Kokoro instances in `DualSessionManager._initialize_sessions()`
- These are completely independent caches

**Impact**:

- **3x model loading overhead**: Separate models for ANE, GPU, and CPU
- Each model initialization takes ~7-8 seconds
- Memory overhead: ~3x memory usage for model instances
- Context leak warnings multiply (6+ context leaks per session)

**Recommendation**:

1. Create a shared model factory that reuses instances from `_model_cache`
2. Allow dual session manager to reference existing cached models
3. Use session-level separation instead of model-level duplication

### 2. Multiple Cache Cleanup Operations

**Problem**: Cache cleanup runs multiple times with zero results.

**Evidence**:

```
Line 94: Startup Progress (10%): Cleaning up cache files (background)...
Line 97: Starting comprehensive cache cleanup...
Line 98: Age cleanup: removed 0 files, 0 dirs, freed 0.0MB
Line 99: Temp dir cleanup: removed 0 dirs, freed 0.0MB
Line 127: Pattern cleanup: removed 0 files, freed 0.0MB
Line 129: Cache cleanup completed: freed 0.0MB
Line 130: Background cache cleanup completed: freed 0.0MB
```

**Impact**:

- Unnecessary CPU cycles (~100-200ms overhead)
- Log noise obscuring real issues

**Recommendation**:

- Consolidate cache cleanup into single operation
- Skip cleanup if cache is empty
- Run cleanup only once per startup

### 3. Overlapping Initialization Phases

**Problem**: Multiple initialization systems run concurrently with overlapping responsibilities.

**Phases**:

1. Fast init minimal warmup (line 100)
2. Background extended warming (line 101)
3. Dual session manager initialization (line 105)
4. Aggressive session warming (line 487)
5. Dual session pre-warming (line 123)

**Overlap**:

- Fast init does minimal warmup: `model.create("Hi", ...)`
- Background extended warming does: `model.create("Hello world", ...)` and `model.create("This is a test sentence...", ...)`
- Dual session pre-warming does: `dsm.process_segment_concurrent("Hi", ...)` and `dsm.process_segment_concurrent("This is a more complex sentence...", ...)`
- Pipeline warmer caches common patterns (line 503)

**Impact**:

- Multiple inferences on same/similar text
- Redundant warmup work
- Context leak warnings multiply

**Recommendation**:

- Coordinate warmup across all systems
- Single warmup coordinator that feeds all systems
- Avoid duplicate inference patterns

### 4. Context Leak Mitigation Redundancy

**Problem**: Context leak mitigation runs multiple times per session creation.

**Evidence**:

- Pre-session cleanup (lines 456-459, 509-513)
- Post-session cleanup (lines 468-475, 522-527)
- Each session type (ANE, GPU, CPU) runs both

**Impact**:

- Still seeing 6+ context leak warnings despite mitigation
- Mitigation overhead (~100-200ms per session)

**Recommendation**:

- Single context leak mitigation per startup
- Verify if mitigation is actually working
- Consider if warnings are harmless (they may be)

## Optimization Opportunities

### Immediate Wins (Low Risk, High Impact)

1. **Share Model Cache** ⭐⭐⭐

   - **Impact**: Save ~14-16 seconds (2x model loads)
   - **Risk**: Low (shared cache already exists)
   - **Effort**: Medium (refactor dual session manager)

2. **Consolidate Cache Cleanup** ⭐⭐

   - **Impact**: Save ~200ms, reduce log noise
   - **Risk**: Low
   - **Effort**: Low

3. **Coordinate Warmup** ⭐⭐
   - **Impact**: Save ~2-3 seconds, reduce redundant work
   - **Risk**: Low
   - **Effort**: Medium

### Medium-Term Improvements

4. **Lazy Dual Session Initialization** ⭐

   - **Impact**: Save ~16 seconds on startup (move to background)
   - **Risk**: Medium (requires careful testing)
   - **Effort**: Medium

5. **Eliminate Context Leak Mitigation Overhead** ⭐
   - **Impact**: Save ~300-600ms
   - **Risk**: Low if warnings are harmless
   - **Effort**: Low

### Long-Term Architectural Changes

6. **Unified Model Management**
   - Single model factory/singleton
   - Session-level separation without model duplication
   - Shared initialization state

## Recommended Action Plan

### Phase 1: Quick Wins (1-2 days)

1. Consolidate cache cleanup operations
2. Verify context leak warnings are harmless
3. Reduce log verbosity for redundant operations

### Phase 2: Model Cache Sharing (3-5 days)

1. Refactor dual session manager to use shared model cache
2. Create model factory that enforces singleton per provider
3. Test thoroughly to ensure no regressions

### Phase 3: Warmup Coordination (2-3 days)

1. Create warmup coordinator
2. Eliminate duplicate inference patterns
3. Optimize warmup sequence

### Phase 4: Lazy Initialization (5-7 days)

1. Move dual session manager to lazy initialization
2. Initialize on first use instead of startup
3. Add health check for dual session readiness

## Expected Results

**Current State**:

- Service ready: ~8.9s
- Fully optimized: ~28.6s

**After Phase 1**:

- Service ready: ~8.7s (save 200ms)
- Fully optimized: ~26.4s (save 2.2s)

**After Phase 2**:

- Service ready: ~8.7s (no change)
- Fully optimized: ~14.4s (save 14.2s) ⭐ **BIG WIN**

**After Phase 3**:

- Service ready: ~8.4s (save 500ms)
- Fully optimized: ~12.0s (save 2.4s)

**After Phase 4**:

- Service ready: ~8.4s (no change)
- Fully optimized: ~12.0s (no change, but dual sessions ready on first use)

## Metrics to Track

- Total startup time
- Service ready time (first request capable)
- Memory usage at startup
- Number of context leak warnings
- Cache hit/miss ratios
- Model initialization count

## Testing Checklist

- [ ] Service ready time < 10s
- [ ] No duplicate model instances
- [ ] Memory usage reduced by ~50%
- [ ] Context leak warnings < 3 per startup
- [ ] All warmup systems operational
- [ ] No regressions in performance benchmarks
