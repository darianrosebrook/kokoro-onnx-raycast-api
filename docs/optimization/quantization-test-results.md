# Kokoro TTS Quantization Test Results

**Date:** 2025-08-16  
**Author:** @darianrosebrook  
**Model:** kokoro.onnx (original) → kokoro-v1.0.int8w-working.onnx (quantized)

## Summary

Successfully implemented and tested weights-only INT8 quantization for the Kokoro TTS model. The quantization achieved a **11.3% size reduction** while maintaining compatibility with both CoreML and CPU execution providers.

## Key Achievements

✅ **Fixed Python 3.13 compatibility issues** - Resolved `InterruptedError` from ONNX shape inference reload path  
✅ **Avoided ConvInteger operations** - Used dynamic quantization for Gemm/MatMul only, excluded Conv to maintain provider compatibility  
✅ **Implemented safe input generation** - Fixed vocab bounds detection to prevent out-of-bounds Gather errors  
✅ **Added comprehensive benchmarking** - Pre-benchmark smoke tests and detailed performance comparison  

## Model Size Comparison

| Model | Size | Reduction |
|-------|------|-----------|
| Original (kokoro.onnx) | 310.5 MB | - |
| Quantized (kokoro-v1.0.int8w-working.onnx) | 275.5 MB | **11.3%** |

## Performance Results (5 trials each)

### CoreML Execution Provider

| Metric | Original | Quantized | Change |
|--------|----------|-----------|--------|
| Average (ms) | 940.3 | 1568.7 | +66.8% |
| P50 (ms) | 903.6 | 971.1 | +7.5% |
| P95 (ms) | 1046.6 | 3120.9 | +198.1% |
| Throughput (QPS) | 1.06 | 0.64 | -39.6% |

### CPU Execution Provider

| Metric | Original | Quantized | Change |
|--------|----------|-----------|--------|
| Average (ms) | 1957.2 | 918.8 | **-53.1%** |
| P50 (ms) | 1134.6 | 894.8 | **-21.1%** |
| P95 (ms) | 3473.3 | 978.2 | **-71.8%** |
| Throughput (QPS) | 0.51 | 1.09 | **+113.7%** |

## Technical Implementation

### Quantization Strategy
- **Method:** Weights-only INT8 dynamic quantization
- **Target Operations:** Gemm, MatMul (excluded Conv to avoid ConvInteger)
- **Excluded Operations:** postnet, layernorm, rmsnorm, out_proj, vocoder, final
- **Activation Precision:** Kept as FP32 (no activation quantization)

### Provider Compatibility
- **CoreML:** ✅ Compatible (no ConvInteger operations)
- **CPU:** ✅ Compatible with significant performance improvement
- **MPS:** Not tested (not available in current environment)

### Input Handling
- **Vocab Size:** 178 tokens (detected from model structure)
- **Input Types:** 
  - `tokens`: int64 [1, sequence_length]
  - `style`: float32 [1, 256]
  - `speed`: float32 [1]

## Issues Resolved

1. **Python 3.13 Compatibility**
   - Fixed `InterruptedError` from ONNX shape inference reload
   - Added `DisableShapeInference=True` to quantization options

2. **Provider Compatibility**
   - Avoided ConvInteger operations that CoreML doesn't support
   - Used dynamic quantization for Gemm/MatMul operations only

3. **Input Validation**
   - Implemented vocab bounds detection (178 tokens)
   - Added pre-benchmark smoke tests to catch invalid inputs early

## Performance Analysis

### CPU Performance Improvement
The quantized model shows **significant performance improvement on CPU**:
- **53.1% faster average inference time**
- **71.8% better P95 latency**
- **113.7% higher throughput**

This suggests that the INT8 quantization is particularly effective for CPU execution, likely due to better memory bandwidth utilization and optimized INT8 kernels.

### CoreML Performance Impact
The quantized model shows **degraded performance on CoreML**:
- Higher latency and lower throughput
- This may be due to:
  - Reduced CoreML partition coverage (1048 vs 1346 nodes)
  - Suboptimal quantization for CoreML's optimized FP32 paths
  - Mixed precision overhead

## Recommendations

1. **For CPU Deployment:** Use the quantized model for significant performance gains
2. **For CoreML Deployment:** Consider keeping the original model or testing different quantization strategies
3. **Further Optimization:** Explore activation quantization for additional size reduction
4. **Quality Validation:** Test audio quality to ensure quantization doesn't impact TTS output

## Files Generated

- `kokoro-v1.0.int8w-working.onnx` - Quantized model (275.5 MB)
- `quantization_comparison_results.json` - Detailed benchmark results
- `scripts/quantize_model.py` - Updated quantization script with fixes

## Next Steps

1. **Audio Quality Testing** - Validate that quantization doesn't impact TTS output quality
2. **Activation Quantization** - Test full INT8 quantization for additional size reduction
3. **CoreML Optimization** - Investigate why CoreML performance degraded
4. **Production Integration** - Integrate quantized model into production pipeline
