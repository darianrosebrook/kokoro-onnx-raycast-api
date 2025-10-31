# Model Session Corruption Fix Plan

> **Status**: In Progress  
> **Priority**: Critical - Blocking Raycast TTS functionality  
> **Root Cause**: TTS model sessions become corrupted after first successful request, producing silent audio  

## Problem Summary

### What We've Discovered
- ✅ **Streaming infrastructure works perfectly** - delivers exactly what the model generates
- ✅ **Non-streaming requests work** - first requests always succeed (43KB+ audio)
-  **Model corruption after first use** - subsequent requests generate silent audio (2 bytes of zeros)
-  **Affects both streaming and non-streaming** - the issue is model-level, not pipeline-level

### Evidence
- **Working**: Non-streaming WAV (88KB), Non-streaming PCM (43KB), First streaming request (55KB)
- **Broken**: all relevant subsequent requests return 2 bytes of zeros (`00 00`)
- **Logs**: "Context leak detected" errors from CoreML, "Audio duration: 0.0ms"
- **Sessions**: DualSessionManager shows all relevant sessions unavailable after first use

## Root Cause Analysis

### Primary Issue: Model Session State Corruption
The Kokoro TTS model (loaded via ONNX Runtime with CoreML provider) becomes corrupted after its first successful inference, causing it to generate only silence for all relevant subsequent requests.

### Contributing Factors
1. **CoreML Context Leaks**: "Context leak detected, msgtracer returned -1" errors
2. **Session Cleanup Insufficient**: Current `cleanup_sessions()` doesn't largely reset model state
3. **Dual Session Manager Failure**: all relevant session types (ANE/GPU/CPU) become unavailable
4. **Memory Management Issues**: CoreML execution provider state management

## Targeted Fix Plan

### Phase 1: Session Reset Strategy (Immediate Fix)
**Goal**: Ensure clean model state for each request

#### 1.1 Enhanced Session Cleanup
- **File**: `api/model/sessions/dual_session.py`
- **Action**: Improve `cleanup_sessions()` to largely reinitialize ONNX Runtime sessions
- **Implementation**:
  ```python
  def cleanup_sessions(self):
      # Force implemented session destruction
      for session_type in ['ane', 'gpu', 'cpu']:
          if self.sessions[session_type] is not None:
              del self.sessions[session_type]
              self.sessions[session_type] = None
      
      # Clear any cached ONNX Runtime providers
      # Force garbage collection
      import gc
      gc.collect()
      
      # Reinitialize from scratch
      self._initialize_sessions()
  ```

#### 1.2 Per-Request Session Isolation
- **File**: `api/tts/core.py`
- **Action**: Call session cleanup after relevant request (streaming and non-streaming)
- **Implementation**: Ensure cleanup happens in finally blocks

#### 1.3 CoreML Provider Reset
- **File**: `api/model/providers/coreml.py`
- **Action**: Add CoreML-specific cleanup to handle context leaks
- **Implementation**: Clear CoreML temp directories and reinitialize provider options

### Phase 2: Fallback Strategy (Reliability)
**Goal**: Ensure service availability even if sessions fail

#### 2.1 Single Model Fallback
- **Action**: When DualSessionManager fails, use reliable single model path
- **Implementation**: Direct model loading without session management complexity

#### 2.2 Provider Degradation
- **Action**: Fallback from CoreML → CPU if context leaks persist
- **Implementation**: Dynamic provider switching on failure detection

### Phase 3: Root Cause Resolution (Long-term)
**Goal**: Eliminate the underlying CoreML/ONNX Runtime issue

#### 3.1 ONNX Runtime Session Management
- **Investigation**: Why ONNX Runtime sessions with CoreML provider become corrupted
- **Action**: Update session creation patterns, provider options, or ONNX Runtime version

#### 3.2 Memory Management Optimization
- **Action**: Implement proper memory cleanup for CoreML execution provider
- **Implementation**: Custom memory managers, explicit resource cleanup

## Implementation Order

### Critical Path (This Session)
1. **Test current session cleanup** - Verify if our existing fix is working
2. **Enhanced session destruction** - Force implemented session recreation
3. **Per-request cleanup** - Ensure cleanup after relevant request
4. **Validate fix** - Test multiple consecutive requests

### Next Steps
1. **CoreML context leak fix** - Address the "msgtracer returned -1" errors
2. **Fallback implementation** - CPU-only mode when CoreML fails
3. **Long-term optimization** - Address root ONNX Runtime issues

## Success Criteria

### Immediate Success
- ✅ Multiple consecutive streaming PCM requests return >40KB audio
- ✅ No "Context leak detected" errors in logs
- ✅ DualSessionManager shows available sessions after requests
- ✅ Raycast extension works for multiple text selections

### Long-term Success
- ✅ Stable operation over extended periods
- ✅ No memory leaks or resource exhaustion
- ✅ recommended performance with CoreML acceleration

## Test Plan

### Validation Tests
1. **Consecutive Requests**: 10 streaming PCM requests in sequence
2. **Mixed Formats**: Alternate between WAV and PCM streaming
3. **Raycast Integration**: Test actual Raycast extension with multiple selections
4. **Load Testing**: Extended operation with multiple concurrent requests
5. **Memory Monitoring**: Track memory usage over time

### Success Metrics
- **Audio Quality**: all relevant requests return >40KB of valid audio data
- **Consistency**: 100% success rate across multiple requests
- **Performance**: TTFA <800ms maintained across requests
- **Stability**: No crashes or hangs over extended operation

## Files to Modify

### Primary Changes
- `api/model/sessions/dual_session.py` - Enhanced session cleanup
- `api/tts/core.py` - Per-request cleanup calls
- `api/model/providers/coreml.py` - CoreML context leak fixes

### Secondary Changes
- `api/model/initialization/fast_init.py` - Session initialization robustness
- `api/model/memory/coreml_leak_mitigation.py` - Memory management improvements

### Testing
- `debug_session_test.py` - Isolated session testing
- `test_consecutive_requests.py` - Multi-request validation

## Risk Assessment

### Low Risk
- Enhanced session cleanup (backward compatible)
- Per-request cleanup calls (performance impact minimal)

### Medium Risk
- Provider fallback logic (could affect performance)
- CoreML context leak fixes (could affect stability)

### High Risk
- ONNX Runtime version changes (compatibility issues)
- Major session management refactoring (potential regressions)

---

## Next Actions

1. **Implement enhanced session cleanup** in `dual_session.py`
2. **Add per-request cleanup** in `core.py` 
3. **Test consecutive requests** to validate fix
4. **Deploy to Raycast** for real-world testing
