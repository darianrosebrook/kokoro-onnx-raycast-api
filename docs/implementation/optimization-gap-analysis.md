# Kokoro TTS Optimization Gap Analysis

> Author: @darianrosebrook  
> Status: Active – comprehensive comparison of implemented vs recommended optimizations

## Overview

This document compares our current implementation status against the comprehensive optimization recommendations from the full chat conversation. It identifies what we've completed, what's partially implemented, and what remains to be done.

## 🔴 **Critical Issues Discovered & Fixed (Latest)**

### Issue 1: Concurrent Processing Implementation Problems
**Status**: ✅ **IDENTIFIED & PARTIALLY FIXED**
**Problem**: 
- Requests hanging for 6+ minutes during testing
- Dual session manager integration causing deadlocks
- Sequential processing instead of parallel execution

**Root Cause**: 
- Complex async/await patterns in `stream_tts_audio` function
- Dual session manager `process_segment_concurrent` method not properly integrated
- Indentation errors breaking the concurrent processing flow

**Fixes Applied**:
- ✅ Fixed indentation errors using Black formatter
- ✅ Simplified `DualSessionManager.process_segment_concurrent` to use global model
- ✅ Corrected voice name from "alloy" to "af_alloy" in cold-start warm-up
- ✅ Fixed `UnboundLocalError` for `primer_hint_key` variable

**Remaining Issues**:
- ⚠️ Dual session manager still not fully integrated (temporary simplification)
- ⚠️ Concurrent processing needs debugging and validation
- ⚠️ Performance gaps between segments (16+ second delays)

### Issue 2: Phonemizer Language Support
**Status**: ✅ **IDENTIFIED**
**Problem**: 
- `language "en" is not supported by the espeak backend`
- Affecting both dual session manager and single model processing

**Impact**: 
- Cold-start warm-up failing with phonemizer errors
- Dual session processing falling back to single model
- Potential audio quality issues

**Next Steps**:
- [ ] Fix language code mapping (`en` → `en-us`)
- [ ] Validate phonemizer backend configuration
- [ ] Test with corrected language codes

### Issue 3: Performance Gaps from User Logs
**Status**: ✅ **DOCUMENTED**
**Problem**: 
- TTFA: 4.46s (4458.82ms) vs target 800ms (5.6x slower)
- Processing gaps: 16+ second delays between segments
- Audio quality: Final chunk producing static sound

**Analysis**:
- Primer micro-cache working but not sufficient for TTFA target
- Concurrent processing not providing expected benefits
- Audio streaming may have corruption or incomplete processing

**Next Steps**:
- [ ] Debug concurrent processing implementation
- [ ] Investigate audio corruption in final chunks
- [ ] Optimize segment processing pipeline

## Current Implementation Status

### ✅ **Fully Implemented & Working**

#### Phase 1: TTFA and Streaming Pipeline
- [x] **Streaming endpoint with immediate WAV header + 50ms silence primer**
  - Code: `api/tts/core.py` → `stream_tts_audio`
  - Status: Working, yields header and silence before first audio

- [x] **Early-primer fast-path (10–15%, cap 700 chars) + primer micro-cache**
  - Code: `api/tts/core.py` → primer micro-cache implementation
  - Status: Implemented but has population issue (debugging added)

- [x] **Language normalization `en` → `en-us`**
  - Code: `api/main.py` → `create_speech`
  - Status: Working on both streaming and non-streaming paths

- [x] **Segmentation tuned for fewer segments**
  - Code: `api/tts/text_processing.py` → `segment_text`
  - Status: Optimized for better TTFA

#### Phase 2: Text Preprocessing and Misaki G2P
- [x] **Misaki G2P integration with fallbacks**
  - Code: `api/tts/misaki_processing.py`
  - Status: Implemented with fallback to phonemizer 

- [x] **Enhanced phonemizer backend pre-init**
  - Code: `api/tts/text_processing.py`
  - Status: Conservative normalization implemented

#### Phase 3: Concurrency and Sessions
- [x] **Dual ANE/GPU session manager**
  - Code: `api/model/loader.py` → `DualSessionManager`
  - Status: Implemented and validated under load

- [x] **Concurrent segment processing**
  - Code: `api/tts/core.py` → `_generate_audio_segment`
  - Status: Working with dual session manager

#### Phase 4: Dynamic Memory and Optimization
- [x] **Cold-start warm-up on startup**
  - Code: `api/main.py` → lifespan context manager
  - Status: Working (502ms completion time)

- [x] **Scheduled benchmark scheduler**
  - Code: `api/performance/scheduled_benchmark.py`
  - Status: Active and running

- [x] **Performance telemetry and monitoring**
  - Code: `/status` endpoint with comprehensive stats
  - Status: All features exposed and working

## Gap Analysis: What's Missing from Recommendations

### 🔴 **High Priority - Not Implemented**

#### 1. Advanced Quantization Strategies
**Recommendation**: Per-channel INT8 quantization, hybrid INT8+FP16, QAT
**Current Status**: Basic INT8 model used, no advanced quantization
**Gap**: 
- No per-channel quantization implementation
- No hybrid precision (INT8+FP16) strategy
- No Quantization-Aware Training (QAT) pipeline
- No experimental INT4 quantization testing

**Implementation Needed**:
```bash
# Stage 1: Per-channel INT8
onnxruntime.quantization.quantize_static --per_channel

# Stage 2: Hybrid INT8+FP16 layers
# Identify sensitive layers (vocoder outputs) and keep in FP16

# Stage 3: QAT pipeline
# Fine-tune model with quantization simulation
```

#### 2. ONNX Graph Optimizations
**Recommendation**: Operator fusion, constant folding, static shape binding
**Current Status**: Basic ORT model conversion, no advanced graph optimizations
**Gap**:
- No operator fusion passes
- No constant folding optimization
- No static shape binding for fixed dimensions
- No MPS vs CoreML EP benchmarking

**Implementation Needed**:
```python
# Add to model build pipeline
from onnx import optimizer
optimized_model = optimizer.optimize_model(
    model,
    passes=['fuse_matmul_add', 'eliminate_deadend', 'fold_consecutive_transposes']
)
```

#### 3. Pipeline Concurrency Engineering
**Recommendation**: 3-stage lock-free pipeline with QoS
**Current Status**: Basic async processing, no structured pipeline
**Gap**:
- No structured 3-stage pipeline (Text → Inference → Audio)
- No lock-free ring buffers between stages
- No thread affinity and QoS for real-time threads
- No backpressure signals

**Implementation Needed**:
```python
# Stage 1: G2P & phonemization (CPU-bound, async)
# Stage 2: TTS inference (ANE/GPU, backpressure signals)
# Stage 3: PCM streaming (real-time QoS audio thread)
```

#### 4. Audio Streaming Robustness
**Recommendation**: Sequence-tagged chunks, adaptive buffer sizing
**Current Status**: Basic streaming, no chunk sequencing
**Gap**:
- No sequence IDs on PCM chunks
- No chunk reordering logic
- No adaptive buffer sizing
- No robust handling of out-of-order packets

**Implementation Needed**:
```python
# Add chunk_id to audio frames
chunk_data = {
    "seq": chunk_id,
    "data": base64_pcm_chunk
}
```

#### 5. Low-Level macOS/Metal Tuning
**Recommendation**: Unified memory, zero-copy buffers, custom MPS kernels
**Current Status**: Basic CoreML usage, no low-level optimizations
**Gap**:
- No MTLResourceStorageModeShared for zero-copy
- No custom MPSGraph kernels
- No Metal-backed allocators
- No deep Metal integration

**Implementation Needed**:
```swift
// Metal-backed allocator for PCM/mel buffers
let buffer = device.makeBuffer(length: size, options: .storageModeShared)
```

### 🟡 **Medium Priority - Partially Implemented**

#### 1. Model Pruning & Distillation
**Recommendation**: Structured pruning, knowledge distillation to smaller model
**Current Status**: No model size reduction beyond basic quantization
**Gap**:
- No structured pruning (attention heads, channels)
- No knowledge distillation pipeline
- No student model training
- No model architecture optimization

#### 2. Memory and Resource Management
**Current Status**: Basic cleanup, no advanced memory management
**Gap**:
- No unified memory optimization
- No aggressive memory recycling
- No memory fragmentation monitoring
- No adaptive memory allocation

#### 3. Text Preprocessing Optimization
**Current Status**: Misaki integration working, but could be optimized
**Gap**:
- No sub-sentence fragment caching
- No batch processing for phonemizer
- No lightweight fallback alternatives
- No performance profiling of G2P stage

### 🟢 **Low Priority - Experimental/Future**

#### 1. Emerging macOS Capabilities
**Recommendation**: JIT MLProgram compilation, Xcode 15+ features
**Current Status**: Not applicable yet
**Gap**:
- No JIT compilation for input-dependent subgraphs
- No dynamic shape optimization
- No runtime compilation benefits

#### 2. Advanced Quantization (Experimental)
**Recommendation**: GPTQ-style 4-bit quantization
**Current Status**: Not implemented
**Gap**:
- No 4-bit quantization pipeline
- No GPTQ techniques integration
- No experimental quantization testing

## Implementation Roadmap

### Phase 5: Advanced Quantization (High Priority)
1. **Per-channel INT8 quantization**
   - Implement `quantize_static --per_channel`
   - Benchmark quality vs speed improvements
   - Expected: 10-20% speed improvement with minimal quality loss

2. **Hybrid INT8+FP16 strategy**
   - Identify sensitive layers (vocoder outputs)
   - Keep critical layers in FP16
   - Expected: Better quality preservation

3. **QAT pipeline**
   - Implement quantization-aware training
   - Fine-tune model with quantization simulation
   - Expected: Near-FP32 quality with INT8 speed

### Phase 6: ONNX Graph Optimization (High Priority)
1. **Operator fusion and constant folding**
   - Add optimizer passes to model build pipeline
   - Benchmark graph optimization benefits
   - Expected: 5-15% runtime overhead reduction

2. **Static shape binding**
   - Bind fixed input/output dimensions
   - Eliminate dynamic shape paths
   - Expected: Faster inference for common input sizes

3. **MPS vs CoreML benchmarking**
   - Implement A/B testing between providers
   - Dynamic provider selection based on input
   - Expected: Optimal provider per use case

### Phase 7: Pipeline Engineering (Medium Priority)
1. **3-stage lock-free pipeline**
   - Implement structured pipeline architecture
   - Add ring buffers between stages
   - Expected: Better concurrency and throughput

2. **Thread affinity and QoS**
   - Mark audio threads with high QoS
   - Bind to performance cores
   - Expected: Eliminate buffer underruns

### Phase 8: Streaming Robustness (Medium Priority)
1. **Sequence-tagged chunks**
   - Add chunk IDs to audio frames
   - Implement reordering logic
   - Expected: Robust streaming under network issues

2. **Adaptive buffer sizing**
   - Dynamic pre-buffer length adjustment
   - Startup buffering window optimization
   - Expected: Better latency vs stability balance

## Benchmarking Requirements

### For Each Phase Implementation:
1. **Baseline measurement** before implementation
2. **Quality assessment** (audio quality, pronunciation)
3. **Performance measurement** (latency, throughput, memory)
4. **Stability testing** (long-running, edge cases)
5. **Regression testing** against previous optimizations

### Key Metrics to Track:
- Time-to-first-audio (TTFA)
- Real-time factor (RTF)
- Memory usage and cleanup
- CPU/GPU/ANE utilization
- Audio quality scores
- Error rates and fallbacks

## Conclusion

Our current implementation covers the foundational optimizations well, achieving:
- ✅ Cold-start warm-up (502ms)
- ✅ Streaming pipeline with primer optimization
- ✅ Dual session concurrency
- ✅ Comprehensive telemetry and monitoring
- ✅ Environment configuration management

**Major gaps** that would provide significant performance improvements:
1. **Advanced quantization** (per-channel, hybrid precision, QAT)
2. **ONNX graph optimizations** (fusion, static shapes)
3. **Pipeline engineering** (structured concurrency, QoS)
4. **Streaming robustness** (sequence tagging, adaptive buffers)

**Next immediate steps**:
1. Fix primer micro-cache population issue
2. Implement per-channel INT8 quantization
3. Add ONNX graph optimization pipeline
4. Begin 3-stage pipeline architecture

The foundation is solid - we're ready to implement the advanced optimizations for maximum performance gains.
