# Performance Logging Rebuild Plan

**Author:** @darianrosebrook  
**Date:** 2025-08-18  
**Status:** In Progress  
**Priority:** P0 (Critical)

## 🚨 **Current Problems Identified**

### **1. Misleading Metrics**
- **TTFA calculation is wrong**: Measuring from chunk processing start, not request start
- **Streaming efficiency shows 100%**: When it should be 25.2% (6.89s audio / 27.39s streaming)
- **Performance monitoring validation failures**: Broken metrics collection
- **Inconsistent timing measurements**: Across client and server components

### **2. Fragmented Logging**
- **Multiple logging systems**: PerformanceMonitor, AdaptiveBufferManager, AudioStreamer, etc.
- **No clear request flow tracking**: Can't trace a request end-to-end
- **Missing critical timing points**: Server processing time, inference time, etc.
- **Inconsistent log formats**: Different components use different logging patterns

### **3. Hidden Performance Issues**
- **1836ms server response time**: Hidden in logs, not surfaced in metrics
- **29+ second chunk processing delays**: Not properly tracked or reported
- **0% cache hit rate**: Caching system completely ineffective
- **Broken performance validation**: System can't validate its own metrics

## 🎯 **New Performance Logging Architecture**

### **Phase 1: Core Request Flow Tracking**

#### **1.1 Unified Performance Tracker**
- **File**: `raycast/src/utils/core/performance-tracker.ts`
- **Purpose**: Centralized client-side performance tracking
- **Features**:
  - Consistent event logging format
  - End-to-end request flow tracking
  - Accurate TTFA calculation (request start to first audio)
  - Proper streaming efficiency calculation
  - Error and warning collection

#### **1.2 Server Performance Tracker**
- **File**: `api/performance/request_tracker.py`
- **Purpose**: Server-side performance tracking coordination
- **Features**:
  - Server processing time tracking
  - Inference timing breakdown
  - Provider usage tracking
  - Cache hit/miss tracking
  - Error and warning collection

#### **1.3 Standardized Event Stages**
```
CLIENT SIDE:
REQUEST_START → REQUEST_SENT → FIRST_BYTE_RECEIVED → FIRST_AUDIO_CHUNK → 
AUDIO_CHUNK_RECEIVED (multiple) → LAST_AUDIO_CHUNK → REQUEST_COMPLETE

SERVER SIDE:
REQUEST_RECEIVED → PROCESSING_START → TEXT_PROCESSING_COMPLETE → 
PHONEME_GENERATION_COMPLETE → INFERENCE_START → INFERENCE_COMPLETE → 
FIRST_CHUNK_GENERATED → AUDIO_CHUNK_GENERATED (multiple) → 
AUDIO_GENERATION_COMPLETE → REQUEST_COMPLETE
```

### **Phase 2: Component Integration**

#### **2.1 Replace Existing Logging Systems**

**Files to Update:**

1. **AudioStreamer** (`raycast/src/utils/tts/streaming/audio-streamer.ts`)
   - Remove all `console.log` statements
   - Replace with `PerformanceTracker.logEvent()` calls
   - Track: chunk reception, streaming progress, audio completion

2. **TTSProcessor** (`raycast/src/utils/tts/tts-processor.ts`)
   - Remove performance monitoring integration
   - Replace with `PerformanceTracker` integration
   - Track: request start, streaming start/end, errors

3. **PerformanceMonitor** (`raycast/src/utils/performance/performance-monitor.ts`)
   - **DEPRECATE** - Replace with new PerformanceTracker
   - Remove all console.log statements
   - Keep only for backward compatibility during transition

4. **Server TTS Core** (`api/tts/core.py`)
   - Add `server_tracker` integration
   - Track: request received, processing start, inference, chunk generation

5. **Server Routes** (`api/routes/performance.py`)
   - Update to use new server tracker
   - Provide metrics from new tracking system

#### **2.2 Migration Strategy**

**Step 1: Deploy New Trackers**
```bash
# Deploy new tracking systems
# - performance-tracker.ts (client)
# - request_tracker.py (server)
```

**Step 2: Add Integration Points**
```typescript
// In each component, replace console.log with:
import { PerformanceTracker } from '@/utils/core/performance-tracker';

const tracker = PerformanceTracker.getInstance();
tracker.logEvent(requestId, 'STAGE_NAME', { metadata });
```

**Step 3: Remove Old Logging**
```bash
# Remove all old performance logging
# - PerformanceMonitor console.log statements
# - AudioStreamer progress reports
# - TTSProcessor performance tracking
```

**Step 4: Validate New System**
```bash
# Test with sample requests
# Verify accurate TTFA calculation
# Verify proper streaming efficiency
# Verify error tracking
```

### **Phase 3: Enhanced Metrics and Analysis**

#### **3.1 Accurate Performance Metrics**

**TTFA Calculation:**
```typescript
// OLD (WRONG):
const ttfa = chunkProcessingTime - chunkStartTime; // 0ms

// NEW (CORRECT):
const ttfa = firstAudioChunk.timestamp - requestStart.timestamp; // 1841ms
```

**Streaming Efficiency Calculation:**
```typescript
// OLD (WRONG):
const efficiency = 100.0; // Always 100%

// NEW (CORRECT):
const efficiency = audioDuration / (streamingTime / 1000); // 25.2%
```

#### **3.2 Performance Thresholds**

**Target Metrics:**
- **TTFA**: ≤ 800ms (request start to first audio)
- **Server Response**: ≤ 500ms (request received to first byte)
- **Streaming Efficiency**: ≥ 90% (audio duration / streaming time)
- **Cache Hit Rate**: ≥ 50% (for repeated requests)

**Alert Thresholds:**
- **TTFA**: > 1000ms (warning), > 2000ms (error)
- **Server Response**: > 1000ms (warning), > 3000ms (error)
- **Streaming Efficiency**: < 80% (warning), < 60% (error)
- **Cache Hit Rate**: < 20% (warning)

#### **3.3 Performance Analysis Dashboard**

**Real-time Metrics:**
- Current TTFA (rolling average)
- Server response time trends
- Streaming efficiency over time
- Cache hit rate
- Error rate

**Historical Analysis:**
- Performance trends over time
- Bottleneck identification
- Provider performance comparison
- Cache effectiveness analysis

## 🔧 **Implementation Steps**

### **Step 1: Deploy New Tracking Systems**
1. ✅ Create `performance-tracker.ts` (client-side)
2. ✅ Create `request_tracker.py` (server-side)
3. Test basic functionality
4. Validate event logging

### **Step 2: Integrate with Core Components**
1. Update `AudioStreamer` to use new tracker
2. Update `TTSProcessor` to use new tracker
3. Update server TTS core to use new tracker
4. Test end-to-end tracking

### **Step 3: Remove Old Logging**
1. Remove `PerformanceMonitor` console.log statements
2. Remove `AudioStreamer` progress reports
3. Remove `TTSProcessor` performance tracking
4. Remove server-side old logging

### **Step 4: Validate and Optimize**
1. Test with various text lengths
2. Verify accurate metrics calculation
3. Test error scenarios
4. Optimize logging performance

### **Step 5: Deploy and Monitor**
1. Deploy to production
2. Monitor for 24 hours
3. Analyze performance data
4. Identify remaining issues

## 📊 **Expected Outcomes**

### **Immediate Benefits:**
- **Accurate TTFA measurement**: Will show real 1841ms instead of 0ms
- **Proper streaming efficiency**: Will show 25.2% instead of 100%
- **Clear performance bottlenecks**: Server response time, chunk processing delays
- **Consistent error tracking**: All errors properly categorized and reported

### **Long-term Benefits:**
- **Performance trend analysis**: Historical data for optimization
- **Automated alerting**: Proactive performance monitoring
- **Bottleneck identification**: Clear data on where time is spent
- **Provider comparison**: Accurate data on CoreML vs CPU performance

## 🚨 **Risk Mitigation**

### **Rollback Plan:**
1. Keep old logging systems during transition
2. Feature flag to switch between old/new systems
3. Gradual rollout with monitoring
4. Quick rollback capability

### **Performance Impact:**
1. Minimal overhead from new tracking
2. Async logging to avoid blocking
3. Configurable log levels
4. Memory management for completed flows

## 📋 **Success Criteria**

### **Phase 1 Success:**
- [ ] New tracking systems deployed and functional
- [ ] Accurate TTFA calculation (showing real values)
- [ ] Proper streaming efficiency calculation
- [ ] End-to-end request flow tracking

### **Phase 2 Success:**
- [ ] All old logging systems removed
- [ ] Consistent log format across all components
- [ ] No performance degradation
- [ ] All errors properly tracked

### **Phase 3 Success:**
- [ ] Performance dashboard operational
- [ ] Automated alerting working
- [ ] Historical analysis capabilities
- [ ] Clear bottleneck identification

## 🎯 **Next Steps**

1. **Immediate**: Deploy new tracking systems
2. **Week 1**: Integrate with core components
3. **Week 2**: Remove old logging systems
4. **Week 3**: Deploy performance dashboard
5. **Week 4**: Analyze results and optimize

This rebuild will provide the foundation for accurate performance monitoring and enable data-driven optimization of the TTS system.
