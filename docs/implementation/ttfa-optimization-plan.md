# TTFA Optimization & Comprehensive Benchmarking Plan

> **Status:** Planning Complete - Ready for Implementation
> **Goal:** Achieve consistent TTFA <800ms and implement comprehensive system benchmarking
> **Current Issue:** TTFA averaging 2047ms due to chunk_delivery bottlenecks

---

## Current State Analysis

### TTFA Bottlenecks Identified

From the terminal output analysis:
```
[req-df9708c2] TTFA: 2047.45ms - ⚠️ TARGET MISSED (Target: 800.0ms)
Bottlenecks identified: chunk_delivery (2047ms)
```

#### Root Causes
1. **Audio Generation Delay**: Waiting for complete audio segment before streaming
2. **Inefficient Chunking**: Large audio segments being processed before first chunk delivery
3. **Sequential Processing**: Segments processed sequentially rather than with streaming overlap
4. **Conversion Overhead**: Audio conversion happening synchronously before streaming
5. **Daemon Communication Latency**: WebSocket communication delays

### Current Architecture Issues

```
Current Flow (Slow):
Text → Full Segment Generation → Convert to WAV → Stream to Daemon
       ↑ 1.5s inference      ↑ 500ms conversion  ↑ Additional latency

Target Flow (Fast):
Text → Partial Generation → Stream Raw → Convert in Daemon
       ↑ <200ms to first    ↑ Immediate    ↑ Parallel processing
```

---

## Phase 1: Immediate TTFA Optimizations

### 1.1 Streaming Audio Pipeline Overhaul

**Objective**: Stream audio as it's generated, not after completion

#### Implementation Strategy

```python
# Current (Sequential):
audio_segment = generate_complete_audio(text)  # 1.5s
wav_bytes = convert_to_wav(audio_segment)      # 500ms  
stream_to_daemon(wav_bytes)                    # Additional latency

# Target (Streaming):
for chunk in generate_streaming_audio(text):   # 50ms per chunk
    stream_raw_chunk_to_daemon(chunk)          # Immediate
```

#### Key Changes Required

1. **Modify `_fast_generate_audio_segment()`** in `api/tts/core.py`:
   - Implement yielding of partial audio chunks during inference
   - Add chunk-based streaming instead of waiting for complete segment

2. **Update Audio Streamer** in `raycast/src/utils/tts/streaming/audio-streamer.ts`:
   - Process smaller chunks (50ms instead of complete segments)
   - Implement buffer management for smooth playback

3. **Enhance Audio Daemon** in `raycast/bin/audio-daemon.js`:
   - Accept raw PCM chunks for immediate playback
   - Handle format conversion in daemon (parallel to generation)

### 1.2 Fast-Path Audio Generation

**Objective**: <200ms to first audio chunk for simple text

#### Implementation Details

```python
def _ultra_fast_generate_first_chunk(text: str, voice: str) -> np.ndarray:
    """
    Generate first 50ms of audio using optimized pipeline
    - Skip heavy preprocessing
    - Use cached phonemes where possible
    - Direct model access
    - Minimal validation
    """
    # Implementation in api/tts/core.py
```

### 1.3 Parallel Processing Pipeline

**Objective**: Process subsequent segments while streaming first chunk

```python
async def parallel_streaming_pipeline(segments: List[str]):
    """
    Process first segment with ultra-fast path while 
    preparing subsequent segments in parallel
    """
    # Start first segment (fast path)
    first_chunk_task = asyncio.create_task(
        _ultra_fast_generate_first_chunk(segments[0])
    )
    
    # Start subsequent segments (parallel)
    subsequent_tasks = [
        asyncio.create_task(_generate_audio_segment(i, seg))
        for i, seg in enumerate(segments[1:], 1)
    ]
    
    # Stream first chunk immediately when ready
    first_chunk = await first_chunk_task
    yield first_chunk
    
    # Stream subsequent chunks as they complete
    for task in subsequent_tasks:
        chunk = await task
        yield chunk
```

---

## Phase 2: Comprehensive Benchmarking System

### 2.1 Full-Spectrum Performance Monitoring

#### Metrics to Track

**Primary Performance Metrics:**
- **TTFA (Time to First Audio)**: <800ms target
- **RTF (Real-Time Factor)**: <1.0 for real-time processing
- **Streaming Efficiency**: >90% smooth playback
- **Memory Usage**: Track memory leaks and optimization
- **Provider Performance**: CoreML vs CPU benchmarking

**Pipeline Stage Metrics:**
- Text processing time
- Phonemization time  
- Model inference time
- Audio generation time
- Format conversion time
- Network/daemon communication time
- Audio playback latency

**System Health Metrics:**
- CPU utilization
- Memory usage patterns
- CoreML context leak frequency
- Cache hit rates
- Error rates and fallback usage

#### Implementation: Enhanced Performance Dashboard

```typescript
// raycast/src/utils/performance/performance-dashboard.ts
interface PerformanceDashboard {
  ttfa: {
    current: number;
    target: number;
    trend: 'improving' | 'stable' | 'degrading';
    achievementRate: number;
  };
  pipeline: {
    textProcessing: number;
    inference: number;
    streaming: number;
    communication: number;
  };
  system: {
    memoryUsage: number;
    cpuUsage: number;
    cacheEfficiency: number;
  };
  recommendations: Recommendation[];
}
```

### 2.2 Automated Benchmark Suite

#### Benchmark Test Categories

**1. TTFA Benchmarks**
```python
# api/performance/benchmarks/ttfa_benchmark.py
class TTFABenchmark:
    """Comprehensive TTFA testing across different scenarios"""
    
    async def run_ttfa_benchmark_suite(self):
        scenarios = [
            ("short_text", "Hello world", 400),      # <400ms target
            ("medium_text", paragraph_text, 800),    # <800ms target  
            ("long_text", article_text, 1200),       # <1200ms target
            ("complex_text", technical_text, 1000),  # <1000ms target
        ]
        
        for name, text, target in scenarios:
            result = await self.measure_ttfa(text, target)
            self.report_ttfa_result(name, result)
```

**2. Streaming Performance Benchmarks**
```python
class StreamingBenchmark:
    """Test streaming efficiency and buffer management"""
    
    def test_chunk_delivery_timing(self):
        # Measure time between chunks
        # Identify gaps or delays in streaming
        
    def test_buffer_underruns(self):
        # Monitor audio playback continuity
        # Detect stuttering or gaps
```

**3. Provider Comparison Benchmarks**
```python
class ProviderBenchmark:
    """Compare CoreML vs CPU performance"""
    
    def benchmark_providers(self):
        # Same text through both providers
        # Compare inference times, memory usage
        # Identify optimal routing decisions
```

### 2.3 Real-Time Performance Integration

#### Integration Points

**1. API Endpoint Enhancement**
```python
# api/routes/performance.py
@router.get("/performance/ttfa")
async def get_ttfa_metrics():
    monitor = get_ttfa_monitor()
    return monitor.get_performance_summary()

@router.post("/performance/benchmark")
async def trigger_benchmark():
    results = await run_comprehensive_benchmark()
    return results
```

**2. Raycast Extension Integration**
```typescript
// raycast/src/components/performance-monitor.tsx
export function PerformanceMonitor() {
  const [metrics, setMetrics] = useState<PerformanceMetrics>();
  
  // Real-time updates from TTS API
  useEffect(() => {
    const interval = setInterval(async () => {
      const data = await fetchPerformanceMetrics();
      setMetrics(data);
    }, 1000);
    
    return () => clearInterval(interval);
  }, []);
  
  return (
    <View>
      <TTFAIndicator metrics={metrics?.ttfa} />
      <PipelineBreakdown metrics={metrics?.pipeline} />
      <SystemHealth metrics={metrics?.system} />
    </View>
  );
}
```

---

## Phase 3: Advanced Optimizations

### 3.1 Predictive Streaming

**Concept**: Start processing likely next segments based on text analysis

```python
class PredictiveProcessor:
    """Predict and pre-process likely segments"""
    
    def analyze_text_segments(self, text: str) -> List[PredictedSegment]:
        # Analyze sentence structure
        # Predict natural break points  
        # Pre-process high-confidence segments
        
    async def warm_cache_for_prediction(self, segments: List[str]):
        # Pre-generate phonemes for likely segments
        # Warm model cache for expected voice/speed combinations
```

### 3.2 Adaptive Quality Modes

**Concept**: Automatically adjust quality vs speed based on performance targets

```python
class AdaptiveQualityManager:
    """Dynamically adjust processing quality based on TTFA targets"""
    
    def select_processing_mode(self, ttfa_history: List[float]) -> ProcessingMode:
        if average(ttfa_history[-5:]) > 1000:
            return ProcessingMode.FAST  # Sacrifice quality for speed
        elif average(ttfa_history[-5:]) < 400:
            return ProcessingMode.HIGH_QUALITY  # Can afford better quality
        else:
            return ProcessingMode.BALANCED
```

### 3.3 Smart Caching Strategies

**Multi-Level Caching System:**
1. **Phoneme Cache**: Cache phonemization results
2. **Segment Cache**: Cache complete audio segments  
3. **Chunk Cache**: Cache first-chunk results for common phrases
4. **Model State Cache**: Cache model states for voice switching

---

## Implementation Priority

### Phase 1 (Critical - Week 1)
- [ ] Implement streaming audio generation in `_fast_generate_audio_segment`
- [ ] Update audio daemon to handle raw PCM streaming
- [ ] Add parallel processing for subsequent segments
- [ ] Test and validate <800ms TTFA achievement

### Phase 2 (High Priority - Week 2)  
- [ ] Implement comprehensive TTFA monitoring dashboard
- [ ] Create automated benchmark suite
- [ ] Add real-time performance tracking to Raycast extension
- [ ] Set up performance alerts and recommendations

### Phase 3 (Enhancement - Week 3)
- [ ] Implement predictive streaming
- [ ] Add adaptive quality modes
- [ ] Create smart multi-level caching
- [ ] Performance optimization based on collected metrics

---

## Success Metrics

### Primary Targets
- **TTFA**: <800ms for 95% of requests
- **Streaming Efficiency**: >90% smooth playback
- **Memory Stability**: No memory leaks or significant growth
- **Error Rate**: <1% for all requests

### Benchmark Coverage
- **Text Variety**: Short, medium, long, complex texts
- **Voice Coverage**: All available voices
- **Speed Variations**: 0.5x to 2.0x speed ranges
- **Provider Scenarios**: CoreML and CPU comparison
- **Load Testing**: Concurrent request handling

### Monitoring & Alerting
- **Real-Time Dashboards**: Performance trends and bottlenecks
- **Automated Alerts**: TTFA target misses and system issues
- **Historical Analysis**: Performance degradation detection
- **Optimization Recommendations**: Actionable improvement suggestions

---

## Technical Implementation Details

### Key Files to Modify

**API (Python):**
- `api/tts/core.py` - Streaming audio generation
- `api/performance/ttfa_monitor.py` - Enhanced monitoring  
- `api/performance/benchmarks/` - New benchmark suite
- `api/routes/performance.py` - Performance endpoints

**Raycast Extension (TypeScript):**
- `raycast/src/utils/tts/streaming/audio-streamer.ts` - Chunk processing
- `raycast/bin/audio-daemon.js` - Raw PCM handling
- `raycast/src/components/performance-monitor.tsx` - Real-time dashboard
- `raycast/src/utils/performance/` - Performance utilities

### Integration Strategy

1. **Backward Compatibility**: Maintain existing API while adding optimizations
2. **Gradual Rollout**: Feature flags for testing new optimizations
3. **Monitoring First**: Establish baseline metrics before optimizations
4. **A/B Testing**: Compare old vs new approaches with real metrics

This comprehensive plan addresses both the immediate TTFA issues and establishes a robust benchmarking foundation for continuous optimization.
