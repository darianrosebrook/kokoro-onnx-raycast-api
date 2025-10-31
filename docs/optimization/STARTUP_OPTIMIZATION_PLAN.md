# Startup Optimization Plan

**Current Startup Time:** ~40+ seconds  
**Target Startup Time:** <10 seconds for basic readiness  
**Goal:** Prioritize critical path, defer non-essential initialization

---

## Current Startup Sequence Analysis

### Step 1: Validation (~1-2 seconds)
- ✅ Validate dependencies
- ✅ Validate model files
- ✅ Validate environment
- ✅ Apply patches
- **Status:** Fast, keep synchronous

### Step 2: Model Initialization (~30-35 seconds) ⚠️ BOTTLENECK
**Current blocking operations:**

1. **Cache Cleanup** (lines 722-731) - ~2-5 seconds
   - **Impact:** High
   - **Criticality:** LOW - can be deferred
   - **Action:** Move to background

2. **CoreML Temp Cleanup** (lines 733-795) - ~3-8 seconds
   - **Impact:** High
   - **Criticality:** LOW - can be deferred
   - **Action:** Move to background or skip entirely

3. **Model Initialization** (lines 819-836) - ~15-20 seconds
   - **Impact:** CRITICAL
   - **Criticality:** HIGH - required for service
   - **Action:** Optimize, but keep synchronous

4. **Session Warming** (fast_init.py lines 318-370) - ~5-10 seconds
   - **Impact:** Medium
   - **Criticality:** MEDIUM - improves first request, but not blocking
   - **Action:** Reduce to minimal warmup (1 inference), defer rest

### Step 3: Background Services (~1-2 seconds)
- ✅ Benchmark scheduler
- **Status:** Fast, can stay

### Step 4: Warmup Processes (~5-10 seconds) ⚠️ REDUNDANT
- **Issue:** `delayed_cold_start_warmup()` waits 5 seconds then does redundant warmup
- **Criticality:** LOW - fast_init already does warming
- **Action:** Remove or make optional

---

## Optimized Startup Sequence

### Phase 1: Critical Path (Target: <8 seconds)
1. **Hardware Detection** (~0.5s)
   - Quick capability detection
   - Cached provider selection

2. **Model Initialization** (~5-7s)
   - Provider initialization
   - Session creation
   - **Minimal warmup:** 1 inference to verify readiness

3. **Service Ready** ✅
   - API accepts requests
   - Model responds (may be slower first request)

### Phase 2: Background Optimization (Non-blocking)
1. **Cache Cleanup** (async)
   - Run in background thread
   - Don't block startup

2. **CoreML Temp Cleanup** (async)
   - Run in background thread  
   - Or skip entirely if not needed

3. **Extended Warming** (async)
   - Additional inference warmup
   - Adaptive provider cache warming
   - Pipeline warmer initialization

4. **Heavy Components** (async)
   - Dual session manager
   - Dynamic memory manager
   - Real-time optimizer

5. **Background Services** (async)
   - Benchmark scheduler
   - Provider benchmarking

---

## Implementation Plan

### 1. Defer Cache Cleanup
**Current:** Lines 722-731 in `initialize_model()`
**Change:** Move to background task after model ready

```python
# Defer cache cleanup to background
async def background_cache_cleanup():
    await asyncio.sleep(1)  # Wait for model ready
    try:
        cache_info = get_cache_info()
        if cache_info.get('needs_cleanup', False):
            cleanup_result = cleanup_cache(aggressive=False)
            logger.info(f"Background cache cleanup: freed {cleanup_result.get('total_freed_mb', 0):.1f}MB")
    except Exception as e:
        logger.debug(f"Background cache cleanup failed: {e}")
```

### 2. Defer CoreML Temp Cleanup
**Current:** Lines 733-795 in `initialize_model()`
**Change:** Move to background or make optional

```python
# Defer CoreML temp cleanup to background
async def background_coreml_cleanup():
    await asyncio.sleep(2)  # After model ready
    # ... cleanup logic ...
```

### 3. Minimize Initial Session Warming
**Current:** fast_init.py lines 318-370 does multiple warmups
**Change:** Reduce to 1 minimal warmup, defer rest

```python
# Minimal warmup: 1 inference to verify readiness
with step_timer("minimal_session_warming"):
    model = get_model()
    if model:
        model.create("Hi", "af_heart", 1.0, "en-us")
        logger.info("✅ Minimal warmup complete - service ready")

# Defer extended warming to background
async def background_extended_warming():
    # Additional warmup inferences
    # Adaptive provider cache warming
    # etc.
```

### 4. Remove Redundant Cold Start Warmup
**Current:** `delayed_cold_start_warmup()` waits 5 seconds then warms up
**Change:** Remove or make optional via env var

```python
# Only run if explicitly enabled
if os.environ.get('KOKORO_ENABLE_COLD_START_WARMUP', 'false').lower() == 'true':
    asyncio.create_task(delayed_cold_start_warmup())
```

### 5. Parallelize Heavy Components
**Current:** Sequential initialization
**Change:** Start all heavy components in parallel threads

---

## Expected Improvements

### Before Optimization
- **Total Startup:** ~40-45 seconds
- **Service Ready:** ~40 seconds
- **First Request:** Fast (due to warmup)

### After Optimization
- **Total Startup:** ~8-10 seconds
- **Service Ready:** ~8 seconds ⚡
- **First Request:** May be slower (~5s), but subsequent requests fast
- **Background Optimization:** Completes in background

---

## Configuration Options

Add environment variables for control:

```bash
# Skip cache cleanup during startup (faster startup)
KOKORO_SKIP_STARTUP_CACHE_CLEANUP=true

# Skip CoreML temp cleanup during startup
KOKORO_SKIP_STARTUP_COREML_CLEANUP=true

# Enable minimal warmup only (faster startup)
KOKORO_MINIMAL_WARMUP=true

# Disable cold start warmup (redundant)
KOKORO_ENABLE_COLD_START_WARMUP=false

# Defer heavy components initialization
KOKORO_DEFER_BACKGROUND_INIT=true
```

---

## Testing Plan

1. **Measure current startup time**
2. **Implement optimizations incrementally**
3. **Measure after each optimization**
4. **Verify service functionality**
5. **Benchmark first request performance**

---

## Priority Order

1. ✅ **Defer cache cleanup** (Biggest impact)
2. ✅ **Defer CoreML temp cleanup** (High impact)
3. ✅ **Minimize initial warming** (Medium impact)
4. ✅ **Remove redundant warmup** (Low impact, easy win)
5. ✅ **Parallelize heavy components** (Optimization)
