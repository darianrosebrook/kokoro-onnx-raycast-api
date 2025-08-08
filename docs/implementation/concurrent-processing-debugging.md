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

### Remaining Issues
- [ ] Dual session manager integration needs debugging
- [ ] Concurrent processing not working as expected
- [ ] Performance gaps between segments
- [ ] Audio corruption in final chunks
- [ ] Phonemizer language support (`en` → `en-us`)

## Next Steps

### Immediate (High Priority)
1. **Debug Dual Session Manager**
   - Test `process_segment_concurrent` method independently
   - Verify session routing logic
   - Check for deadlocks or race conditions

2. **Fix Phonemizer Language Support**
   - Update language code mapping (`en` → `en-us`)
   - Test with corrected language codes
   - Validate phonemizer backend configuration

3. **Investigate Audio Corruption**
   - Debug final chunk processing
   - Check audio buffer handling
   - Verify memory management

### Medium Priority
1. **Simplify Concurrent Processing**
   - Consider reverting to simpler async approach
   - Test with basic `run_in_threadpool` without dual session manager
   - Validate performance improvements

2. **Performance Profiling**
   - Add detailed timing logs for each processing stage
   - Identify bottlenecks in segment processing
   - Measure actual vs expected concurrency benefits

## Code References

- **Main streaming function**: `api/tts/core.py` → `stream_tts_audio`
- **Dual session manager**: `api/model/loader.py` → `DualSessionManager`
- **Fast processing**: `api/tts/core.py` → `_fast_generate_audio_segment`
- **Standard processing**: `api/tts/core.py` → `_generate_audio_segment`

## Testing Strategy

### 1. Isolated Testing
```bash
# Test dual session manager independently
python -c "from api.model.loader import get_dual_session_manager; print(get_dual_session_manager())"

# Test simple TTS request without streaming
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test.", "voice": "af_alloy", "stream": false}'
```

### 2. Performance Testing
```bash
# Test with timing information
time curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world.", "voice": "af_alloy", "stream": true}' \
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

## Related Documents

- [Optimization Gap Analysis](./optimization-gap-analysis.md)
- [Optimization Progress Tracker](./optimization-progress-tracker.md)
- [Comprehensive Optimization Plan](../comprehensive-optimization-plan-for-kokoro-backend.md)
