# ORT Optimization Guide

This guide provides a deep dive into ORT (ONNX Runtime) optimization for the Kokoro-ONNX TTS API, particularly for Apple Silicon devices.

## ORT (ONNX Runtime) Optimization

ORT optimization provides significant performance improvements on Apple Silicon:

```bash
# Create cache directories
mkdir -p .cache/ort

# Convert ONNX model to optimized ORT format
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx -o .cache/ort/kokoro-v1.0.int8.ort

# Enable ORT optimization in environment
export KOKORO_ORT_OPTIMIZATION=auto
echo "export KOKORO_ORT_OPTIMIZATION=auto" >> .env

# Optional: Set specific ORT model path
export KOKORO_ORT_MODEL_PATH=.cache/ort/kokoro-v1.0.int8.ort
echo "KOKORO_ORT_MODEL_PATH=.cache/ort/kokoro-v1.0.int8.ort" >> .env
```

**Benefits of ORT Optimization:**
- **3-5x faster inference** on Apple Silicon with Neural Engine
- **2-3x faster inference** on Apple Silicon without Neural Engine
- **Fewer temporary file issues** - ORT models require less runtime compilation
- **Better CoreML compatibility** - optimized for Apple's ML frameworks

## Automatic ORT Optimization

**How it works:**
1. **Hardware Detection**: Automatically detects Apple Silicon and Neural Engine
2. **Smart Decision Making**: Determines if ORT optimization will improve performance
3. **On-Demand Conversion**: Creates optimized models automatically on first run
4. **Intelligent Caching**: Caches optimized models for faster subsequent startups

**Configuration:**
```bash
# Enable automatic ORT optimization (default on Apple Silicon)
export KOKORO_ORT_OPTIMIZATION=auto

# Force enable ORT optimization
export KOKORO_ORT_OPTIMIZATION=true

# Disable ORT optimization
export KOKORO_ORT_OPTIMIZATION=false

# Custom ORT cache directory
export KOKORO_ORT_CACHE_DIR=.cache/ort
```

## Benefits of ORT Optimization

#### **Performance Improvements:**
- **3-5x faster inference** on Apple Silicon with Neural Engine
- **2-3x faster inference** on Apple Silicon without Neural Engine
- **Reduced memory usage** through optimized graph structure
- **Faster startup times** after initial conversion

#### **Reliability Improvements:**
- **Fewer temporary file issues** - ORT models require less runtime compilation
- **Better CoreML compatibility** - optimized for Apple's ML frameworks
- **Reduced permission issues** - fewer system temp directory dependencies

#### **Developer Experience:**
-  **Automatic optimization** - no manual intervention required
-  **Transparent fallback** - graceful degradation if ORT fails
-  **Comprehensive logging** - detailed optimization information
-  **Pre-deployment tools** - manual conversion for CI/CD pipelines

## ORT Optimization Logic

The system uses intelligent device-based logic to determine when to use ORT optimization:

```python
# Apple Silicon with Neural Engine
if device.has_neural_engine:
    return "ORT_STRONGLY_RECOMMENDED"  # 3-5x performance boost

# Apple Silicon without Neural Engine  
elif device.is_apple_silicon:
    return "ORT_RECOMMENDED"          # 2-3x performance boost

# Other devices
else:
    return "ORT_OPTIONAL"             # Minimal benefit
```

## ORT File Structure

```
.cache/ort/
├── kokoro-v1.0.int8.ort              # Optimized model file
├── optimization_metadata.json        # Conversion metadata
└── performance_profile.json          # Performance benchmarks
```

## Manual ORT Optimization

For CI/CD pipelines or manual optimization:

```bash
#!/usr/bin/env bash
# Run provider benchmark and persist reports
python scripts/run_benchmark.py --verbose

# Validate optimization state via status endpoint
curl -s http://localhost:8000/status | jq '{provider: .performance.provider_used, ort: .performance.ort_optimization}'
``` 