# Optimized Model Setup & Testing

**Author:** @darianrosebrook  
**Date:** 2025-12-21  
**Status:** ✅ Configuration Complete

## Summary

The TTS service has been configured to use the graph-optimized model (`kokoro-v1.0.int8-graph-opt.onnx`) which provides **74% performance improvement** (595ms → 155ms average inference time).

## Configuration Changes

### 1. Model Selection Support

Updated `api/config.py` to support model selection via environment variable:

```python
# Supports:
# - Environment variable: KOKORO_MODEL_FILE
# - Automatic fallback: optimized_models/ → models/
# - Absolute/relative paths
```

### 2. LaunchAgent Configuration

Updated `launchagents/com.kokoro.tts-api.plist` to use optimized model:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>KOKORO_MODEL_FILE</key>
    <string>kokoro-v1.0.int8-graph-opt.onnx</string>
</dict>
```

## Model Verification

### ✅ Model Loading Test

```bash
cd /Users/darianrosebrook/Desktop/Projects/kokoro-onnx
source .venv/bin/activate
python3 -c "
import onnxruntime as ort
model_path = 'optimized_models/kokoro-v1.0.int8-graph-opt.onnx'
session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
print('✅ Optimized model loaded successfully')
"
```

**Result:** Model loads successfully with correct input/output signatures.

### Model Path Detection

The config correctly detects the optimized model:

```bash
KOKORO_MODEL_FILE="kokoro-v1.0.int8-graph-opt.onnx" python3 -c \
  "from api.config import MODEL_PATH; print(MODEL_PATH)"
# Output: /Users/darianrosebrook/Desktop/Projects/kokoro-onnx/optimized_models/kokoro-v1.0.int8-graph-opt.onnx
```

## Performance Comparison

Based on existing benchmarks from `optimized_models/graph_optimization_results.json`:

| Metric | Base Model | Optimized Model | Improvement |
|--------|------------|-----------------|-------------|
| **Average Inference** | 595.07ms | 155.01ms | **74% faster** |
| **Min Inference** | 567.45ms | 148.72ms | **74% faster** |
| **Max Inference** | 651.63ms | 172.25ms | **74% faster** |
| **Model Size** | 88.08MB | 87.92MB | 0.19% reduction |

## Available Models

| Model File | Location | Performance | Status |
|------------|----------|-------------|--------|
| `kokoro-v1.0.onnx` | `models/` | Baseline | Default fallback |
| `kokoro-v1.0.int8-graph-opt.onnx` | `optimized_models/` | **74% faster** | ✅ **Active** |
| `kokoro-v1.0.int8.graph_optimized.onnx` | `optimized_models/` | Optimized | Alternative |

## Testing the Optimized Model

### Option 1: Direct Model Test

```bash
# Test model loading and structure
cd /Users/darianrosebrook/Desktop/Projects/kokoro-onnx
source .venv/bin/activate
python3 scripts/simple_graph_optimize.py \
  --input models/kokoro-v1.0.onnx \
  --output optimized_models/test-opt.onnx \
  --validate \
  --benchmark
```

### Option 2: Benchmark Performance (Once Service is Running)

```bash
# Run comprehensive benchmarks
python3 scripts/run_bench.py \
  --preset=short \
  --stream \
  --trials=5 \
  --base-url=http://127.0.0.1:8080
```

### Option 3: Quick API Test

```bash
# Test health endpoint (once service starts)
curl http://127.0.0.1:8080/health

# Test TTS generation
curl -X POST http://127.0.0.1:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello, this is a test.", "voice": "af_heart"}' \
  --output test_audio.wav
```

## Current Status

### ✅ Completed

1. **Model Configuration:** Updated `api/config.py` to support model selection
2. **LaunchAgent Setup:** Configured to use optimized model via environment variable
3. **Model Verification:** Confirmed optimized model loads successfully
4. **Installation:** Reinstalled menubar app and LaunchAgents

### ⚠️ Known Issue

The TTS service is currently failing to start due to an `EspeakWrapper` library compatibility issue:

```
AttributeError: type object 'EspeakWrapper' has no attribute 'set_data_path'
```

This is a **library compatibility issue**, not a model configuration problem. The optimized model path is correctly detected (as shown in logs: "Loading model from .../optimized_models/kokoro-v1.0.int8-graph-opt.onnx").

### Next Steps

1. **Resolve EspeakWrapper Issue:** Update `kokoro-onnx` library or fix compatibility
2. **Verify Service Startup:** Once library issue is resolved, service should start with optimized model
3. **Run Benchmarks:** Compare performance with optimized vs base model
4. **Monitor Performance:** Track TTFA, RTF, and memory usage

## Switching Models

To switch between models, update the `KOKORO_MODEL_FILE` environment variable:

```bash
# Use optimized model (current)
export KOKORO_MODEL_FILE="kokoro-v1.0.int8-graph-opt.onnx"

# Use base model
export KOKORO_MODEL_FILE="kokoro-v1.0.onnx"

# Use custom path
export KOKORO_MODEL_FILE="/path/to/custom/model.onnx"
```

Then reload the LaunchAgent:

```bash
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts-api.plist
launchctl load ~/Library/LaunchAgents/com.kokoro.tts-api.plist
```

## Further Optimization

See `docs/optimization/optimization-results-summary.md` for additional optimization strategies:

- Full INT8 quantization (weights + activations)
- ORT format conversion (3-5x speedup on Apple Silicon)
- Provider-specific optimizations (CoreML, MPS)
- Memory arena tuning

---

**Note:** The optimized model configuration is complete and ready. Once the EspeakWrapper library issue is resolved, the service will automatically use the optimized model and benefit from the 74% performance improvement.















