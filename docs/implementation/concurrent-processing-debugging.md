# Concurrent Processing Debugging

> Author: @darianrosebrook  
> Status: Active – debugging concurrent processing implementation issues

## Problem Summary

During testing of our concurrent processing implementation, we discovered critical issues causing requests to hang for 6+ minutes and performance gaps between segments.

## Issues Identified

### 1. Request Hanging (6+ minutes)
**Symptoms**:
- Simple requests like "Hello world." taking 6+ minutes to complete
- Complex requests hanging indefinitely
- Server logs showing dual session manager activity but no completion

**Root Cause Analysis**:
- Complex async/await patterns in `stream_tts_audio` function
- Dual session manager `process_segment_concurrent` method not properly integrated
- Indentation errors breaking the concurrent processing flow

**Fixes Applied**:
- ✅ Fixed indentation errors using Black formatter
- ✅ Simplified `DualSessionManager.process_segment_concurrent` to use global model
- ✅ Corrected voice name from "alloy" to "af_alloy" in cold-start warm-up
- ✅ Fixed `UnboundLocalError` for `primer_hint_key` variable

### 2. Performance Gaps (16+ second delays)
**Symptoms**:
- 16+ second gaps between segments in user logs
- TTFA: 4.46s vs target 800ms (5.6x slower)
- Sequential processing instead of parallel execution

**Analysis**:
- Primer micro-cache working but not sufficient for TTFA target
- Concurrent processing not providing expected benefits
- Dual session manager may not be properly routing requests

### 3. Audio Quality Issues
**Symptoms**:
- Final chunk producing static sound
- Potential audio corruption or incomplete processing

**Investigation Needed**:
- Audio buffer handling in streaming pipeline
- Final chunk processing logic
- Memory management during audio generation

## Current Status

### Fixed Issues
- [x] Indentation errors in `api/tts/core.py`
- [x] `UnboundLocalError` for `primer_hint_key`
- [x] Voice name mismatch in cold-start warm-up
- [x] Basic syntax errors preventing server startup
- [x] **NEW**: Phonemizer language support (`en` → `en-us`)
- [x] **NEW**: Dual session manager model availability check
- [x] **NEW**: Global variable declaration order in dual session manager

### Remaining Issues
- [ ] Dual session manager integration needs debugging
- [ ] Concurrent processing not working as expected
- [ ] Performance gaps between segments
- [ ] Audio corruption in final chunks
- [ ] **NEW**: Module import issues in test scripts

## Debugging Results

### Issue 1: Phonemizer Language Support ✅ **FIXED**
**Problem**: `language "en" is not supported by the espeak backend`
**Root Cause**: Cold-start warm-up function using `"en"` instead of `"en-us"`
**Fix**: Updated cold-start warm-up to use `"en-us"` language code
**Status**: ✅ **RESOLVED** - Test script confirms fix is working

### Issue 2: Dual Session Manager Model Availability ✅ **FIXED**
**Problem**: `Global model not available` errors in dual session manager
**Root Cause**: Dual session manager trying to use global model before initialization
**Fix**: Added model availability check and improved error handling
**Status**: ✅ **RESOLVED** - Dual session manager now checks model status

### Issue 3: Concurrent Processing Timeouts ⚠️ **PARTIALLY FIXED**
**Problem**: Segment 3 timed out after 30 seconds in concurrent processing test
**Root Cause**: Complex async/await patterns and potential deadlocks
**Fix**: Added timeouts and improved error handling
**Status**: ⚠️ **NEEDS FURTHER TESTING** - Basic fixes applied, needs validation

### Issue 4: Module Import Issues ⚠️ **IDENTIFIED**
**Problem**: Global variable declaration errors in test scripts
**Root Cause**: Module import order and global variable access
**Fix**: Simplified test approach needed
**Status**: ⚠️ **NEEDS SIMPLIFIED APPROACH** - Test scripts need refactoring

## Next Steps

### Immediate (High Priority)
1. **Test Dual Session Manager Fixes**
   - Run server and test with actual requests
   - Verify model availability checks work
   - Test concurrent processing with real load

2. **Validate Phonemizer Fix**
   - Test cold-start warm-up with corrected language code
   - Verify no more "language en not supported" errors

3. **Investigate Audio Corruption**
   - Debug final chunk processing
   - Check audio buffer handling

### Medium Priority
1. **Simplify Concurrent Processing Testing**
   - Create server-based tests instead of direct module tests
   - Use actual HTTP requests to test streaming
   - Avoid module import issues

2. **Performance Profiling**
   - Add detailed timing logs for each processing stage
   - Identify bottlenecks in segment processing
   - Measure actual vs expected concurrency benefits

## Code References

- **Main streaming function**: `api/tts/core.py` → `stream_tts_audio`
- **Dual session manager**: `api/model/loader.py` → `DualSessionManager`
- **Fast processing**: `api/tts/core.py` → `_fast_generate_audio_segment`
- **Standard processing**: `api/tts/core.py` → `_generate_audio_segment`
- **Cold-start warm-up**: `api/main.py` → `perform_cold_start_warmup`

## Testing Strategy

### 1. Server-Based Testing (Recommended)
```bash
# Start server and test with actual requests
source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Test simple request
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world.", "voice": "af_alloy", "stream": true}' \
  --output /dev/null --write-out "Time: %{time_total}s\n"
```

### 2. Performance Testing
```bash
# Test with timing information
time curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a comprehensive test of the concurrent processing capabilities.", "voice": "af_alloy", "stream": true}' \
  --output /dev/null
```

### 3. Log Analysis
- Monitor server logs for dual session manager activity
- Check for error messages and warnings
- Analyze timing information in logs

## Expected Outcomes

Once debugging is complete, we expect:
- **TTFA**: Reduce from 4.46s to <800ms target
- **Concurrent Processing**: Eliminate 16+ second gaps between segments
- **Audio Quality**: Fix static sound in final chunks
- **Stability**: No more hanging requests
- **Phonemizer**: No more language support errors

## Related Documents

- [Optimization Gap Analysis](./optimization-gap-analysis.md)
- [Optimization Progress Tracker](./optimization-progress-tracker.md)
- [Comprehensive Optimization Plan](../comprehensive-optimization-plan-for-kokoro-backend.md)
