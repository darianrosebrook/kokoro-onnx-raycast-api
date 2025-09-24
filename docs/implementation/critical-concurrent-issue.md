# CRITICAL: Concurrent Request Handling Issue

> **Status:**  **CRITICAL BUG** - Second request takes 26.8s vs 3.8s for first request
> 
> **Impact:** System unusable for concurrent/sequential requests

## Problem Analysis

### Observed Behavior
1. **First request:** ~3.8s TTFA, produces full audio
2. **Second request:** ~26.8s TTFA, produces minimal audio  
3. **Monitoring:** Only tracks 1 request successfully
4. **Text coverage:** Losing 4+ characters during segmentation

### Detailed Symptoms

**From User's Report:**
```
First request:  TTFA: 2164.77ms, 7 segments, 1501 chunks, 25663.7ms audio
Second request: TTFA: 3726.31ms, 6 segments, 305 chunks, 15082.4ms audio
```

**From Test Results:**
```
Request 1: Time to first byte: 3.821494s
Request 2: Time to first byte: 26.814007s (7x slower!)
```

## Root Cause Analysis

### 1. Session Contention Issue 
**Hypothesis:** Dual session manager has resource contention
**Evidence:**
- First request uses sessions normally
- Second request waits for session availability
- 26.8s delay suggests timeout or retry behavior

### 2. Model Session Locking 
**Hypothesis:** Model sessions not properly released
**Evidence:**
- Huge delay between requests
- Only one request tracked in monitoring
- Suggests session blocking/deadlock

### 3. Memory/Resource Exhaustion   
**Hypothesis:** First request exhausts system resources
**Evidence:**
- Different audio duration (25.6s vs 15.0s)
- Fewer chunks produced (1501 vs 305)
- Performance degradation pattern

### 4. Request ID Collision 🆔
**Hypothesis:** Request tracking collision
**Evidence:**
- Both requests logged as "no-id"
- Monitoring only shows 1 request
- Possible ID generation issue

## Technical Investigation

### Session Manager State
From logs: "Dual session stats" shows sessions being used but not properly tracked
```
'total_requests': 7, 'ane_requests': 0, 'gpu_requests': 5, 'cpu_requests': 2
```

### Request Processing Pattern
```
First request:  Fast → Normal processing
Second request: Slow → Degraded processing
```

### Audio Generation Analysis
```
First:  7 segments → 1501 chunks → 25.6s audio  (normal)
Second: 6 segments → 305 chunks → 15.0s audio   (truncated!)
```

## Immediate Fixes Applied

### 1. Text Coverage Recovery ✅
```python
# Recover missing text during segmentation
if original_text_length > current_text_length:
    missing_text = text[current_text_length:].strip()
    if missing_text:
        logger.info(f"Recovering missing text: '{missing_text[:20]}...'")
        # Append to last segment or create new segment
```

### 2. Request ID Generation ✅
```python
# Generate unique request ID for proper tracking
import uuid
request_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex[:8]}")
```

### 3. Enhanced Logging ✅
```python
# Better tracking of chunk generation and streaming
logger.debug(f"Yielded chunk {chunk_count} (size: {len(chunk)}) from segment {i}")
```

## Critical Fixes Needed

### 1. Session Manager Resource Management
**Problem:** Sessions not properly released between requests
**Solution:** 
- Add explicit session cleanup after each request
- Implement session timeout and recovery
- Add session pool management

### 2. Concurrent Request Handling
**Problem:** Blocking behavior between sequential requests  
**Solution:**
- Implement proper async session management
- Add request queuing with timeout
- Fix session contention issues

### 3. Memory Management
**Problem:** First request may be exhausting resources
**Solution:**
- Add memory cleanup between requests
- Implement proper resource disposal
- Monitor memory usage patterns

## Recommended Immediate Actions

### 1. Session Cleanup Investigation
```python
# Add explicit session cleanup
try:
    # Process request
    pass
finally:
    # Force session cleanup
    if dual_session_manager:
        dual_session_manager.cleanup_session()
```

### 2. Request Isolation
```python
# Ensure proper request isolation
with request_context_manager() as ctx:
    # Process request in isolated context
    pass
```

### 3. Resource Monitoring
```python
# Add resource monitoring
before_memory = get_memory_usage()
# Process request
after_memory = get_memory_usage()
if after_memory - before_memory > threshold:
    force_cleanup()
```

## Testing Strategy

### 1. Sequential Request Test
```bash
# Test multiple sequential requests
for i in {1..5}; do
  echo "Request $i:"
  time curl -X POST http://localhost:8000/v1/audio/speech \
    -H "Content-Type: application/json" \
    -d '{"text":"Test request '$i'", "voice":"af_heart", "speed":1.0}' \
    -o /dev/null -w "TTFA: %{time_starttransfer}s\n"
  sleep 1
done
```

### 2. Concurrent Request Test
```bash
# Test truly concurrent requests
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"text":"Concurrent test 1", "voice":"af_heart", "speed":1.0}' \
  -o /dev/null &
  
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"text":"Concurrent test 2", "voice":"af_heart", "speed":1.0}' \
  -o /dev/null &
  
wait
```

### 3. Session State Monitoring
```bash
# Monitor session state between requests
curl http://localhost:8000/status
# Make request
curl -X POST http://localhost:8000/v1/audio/speech ...
# Check session state again
curl http://localhost:8000/status
```

## Success Criteria

### Immediate (Critical)
- ✅ Fix text coverage loss
-  Sequential requests should have consistent TTFA (<5s difference)
-  All requests should be tracked in monitoring
-  Audio quality consistent between requests

### Medium Term
-  TTFA should improve, not degrade, on subsequent requests (caching benefit)
-  Concurrent requests should work without blocking
-  Memory usage stable across multiple requests

## Risk Assessment

### High Risk 
- **System unusable for real usage** - 26s delay makes system impractical
- **Data loss** - Missing text characters affect audio quality
- **Resource exhaustion** - May lead to system crashes under load

### Medium Risk 🟡  
- **Performance unpredictability** - Users can't rely on consistent performance
- **Session deadlocks** - System may become completely unresponsive

## Next Steps Priority

1. **IMMEDIATE:** Investigate session manager state and cleanup
2. **URGENT:** Implement proper request isolation
3. **HIGH:** Add comprehensive resource monitoring
4. **MEDIUM:** Optimize session pool management

---

**This is a production-blocking issue that needs immediate resolution before the TTFA optimization work can continue effectively.**
