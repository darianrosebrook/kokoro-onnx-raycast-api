# Environment Toggles for Kokoro ONNX TTS

> Author: @darianrosebrook  
> Status: Active – comprehensive environment variable documentation

## Overview

This document provides a complete reference for all `KOKORO_` environment variables that control the behavior of the Kokoro ONNX TTS system. These toggles allow fine-grained control over performance, development experience, and production deployment.

## Quick Reference

### Development Mode
```bash
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true
export KOKORO_FAST_STARTUP=true
```

### Production Mode
```bash
export KOKORO_PRODUCTION=true
export KOKORO_BENCHMARK_FREQUENCY=daily
export KOKORO_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

## Environment Variables by Category

### 🚀 **Performance & Optimization**

#### `KOKORO_ORT_OPTIMIZATION`
- **Purpose**: Controls ONNX Runtime optimization level
- **Values**: `auto` (default), `true`, `false`
- **Development**: `auto` (automatic detection)
- **Production**: `true` (force optimization)
- **Example**: `export KOKORO_ORT_OPTIMIZATION=true`

#### `KOKORO_GRAPH_OPT_LEVEL`
- **Purpose**: ONNX Runtime graph optimization level
- **Values**: `BASIC` (default), `EXTENDED`, `ALL`
- **Development**: `BASIC` (faster startup)
- **Production**: `ALL` (maximum optimization)
- **Example**: `export KOKORO_GRAPH_OPT_LEVEL=ALL`

#### `KOKORO_MEMORY_ARENA_SIZE_MB`
- **Purpose**: Memory arena size for performance optimization
- **Values**: `512` (default), `1024`, `2048`
- **Development**: `512` (balanced)
- **Production**: `1024` or `2048` (high performance)
- **Example**: `export KOKORO_MEMORY_ARENA_SIZE_MB=1024`

#### `KOKORO_DISABLE_MEM_PATTERN`
- **Purpose**: Disable memory pattern optimization
- **Values**: `false` (default), `true`
- **Development**: `false` (use optimization)
- **Production**: `false` (use optimization)
- **Example**: `export KOKORO_DISABLE_MEM_PATTERN=false`

### 🍎 **Apple Silicon (CoreML) Optimization**

#### `KOKORO_COREML_MODEL_FORMAT`
- **Purpose**: CoreML model format for Apple Silicon
- **Values**: `MLProgram` (default), `NeuralNetwork`
- **Development**: `MLProgram` (optimal)
- **Production**: `MLProgram` (optimal)
- **Example**: `export KOKORO_COREML_MODEL_FORMAT=MLProgram`

#### `KOKORO_COREML_COMPUTE_UNITS`
- **Purpose**: CoreML compute units configuration
- **Values**: `CPUAndGPU` (default), `CPUAndNeuralEngine`, `CPUOnly`, `ALL`
- **Development**: `CPUAndGPU` (balanced)
- **Production**: `CPUAndNeuralEngine` (optimal performance)
- **Example**: `export KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine`

#### `KOKORO_COREML_SPECIALIZATION`
- **Purpose**: CoreML specialization mode
- **Values**: `FastPrediction` (default), `Balanced`, `Accuracy`
- **Development**: `FastPrediction` (fastest)
- **Production**: `FastPrediction` (optimal for TTS)
- **Example**: `export KOKORO_COREML_SPECIALIZATION=FastPrediction`

### 📊 **Benchmarking & Monitoring**

#### `KOKORO_BENCHMARK_FREQUENCY`
- **Purpose**: Controls automatic benchmark frequency
- **Values**: `daily` (default), `weekly`, `monthly`, `manually`
- **Development**: `manually` (skip automatic)
- **Production**: `daily` or `weekly` (regular monitoring)
- **Example**: `export KOKORO_BENCHMARK_FREQUENCY=weekly`

#### `KOKORO_SKIP_BENCHMARKING`
- **Purpose**: Completely disable automatic benchmarking
- **Values**: `false` (default), `true`
- **Development**: `true` (faster startup)
- **Production**: `false` (enable monitoring)
- **Example**: `export KOKORO_SKIP_BENCHMARKING=true`

#### `KOKORO_MIN_IMPROVEMENT_PERCENT`
- **Purpose**: Minimum improvement required for provider change
- **Values**: `5.0` (default), `10.0`, `15.0`
- **Development**: `5.0` (sensitive to changes)
- **Production**: `10.0` (stable performance)
- **Example**: `export KOKORO_MIN_IMPROVEMENT_PERCENT=10.0`

### 🔧 **Development Experience**

#### `KOKORO_DEVELOPMENT_MODE`
- **Purpose**: Enable development-specific optimizations
- **Values**: `false` (default), `true`
- **Development**: `true` (faster startup, more logging)
- **Production**: `false` (optimized for production)
- **Example**: `export KOKORO_DEVELOPMENT_MODE=true`

#### `KOKORO_FAST_STARTUP`
- **Purpose**: Skip non-essential initialization for faster startup
- **Values**: `false` (default), `true`
- **Development**: `true` (faster iteration)
- **Production**: `false` (complete initialization)
- **Example**: `export KOKORO_FAST_STARTUP=true`

### 🗣️ **Text Processing (Misaki G2P)**

#### `KOKORO_MISAKI_ENABLED`
- **Purpose**: Enable/disable Misaki G2P phonemization
- **Values**: `true` (default), `false`
- **Development**: `true` (use advanced features)
- **Production**: `true` (use advanced features)
- **Example**: `export KOKORO_MISAKI_ENABLED=true`

#### `KOKORO_MISAKI_FALLBACK`
- **Purpose**: Enable phonemizer fallback when Misaki fails
- **Values**: `true` (default), `false`
- **Development**: `true` (robust processing)
- **Production**: `true` (robust processing)
- **Example**: `export KOKORO_MISAKI_FALLBACK=true`

#### `KOKORO_MISAKI_CACHE_SIZE`
- **Purpose**: Phoneme cache size for performance
- **Values**: `1000` (default), `500`, `2000`
- **Development**: `1000` (balanced)
- **Production**: `2000` (higher performance)
- **Example**: `export KOKORO_MISAKI_CACHE_SIZE=2000`

#### `KOKORO_MISAKI_QUALITY_THRESHOLD`
- **Purpose**: Quality threshold for fallback decisions
- **Values**: `0.8` (default), `0.7`, `0.9`
- **Development**: `0.8` (balanced)
- **Production**: `0.9` (higher quality)
- **Example**: `export KOKORO_MISAKI_QUALITY_THRESHOLD=0.9`

### 🔒 **Security & Production**

#### `KOKORO_PRODUCTION`
- **Purpose**: Enable production mode optimizations
- **Values**: `false` (default), `true`
- **Development**: `false` (development features)
- **Production**: `true` (security, performance)
- **Example**: `export KOKORO_PRODUCTION=true`

#### `KOKORO_ALLOWED_HOSTS`
- **Purpose**: Comma-separated list of allowed hosts
- **Values**: `*` (default), `yourdomain.com,api.yourdomain.com`
- **Development**: `*` (allow all)
- **Production**: Specific domains only
- **Example**: `export KOKORO_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com`

### 📁 **File Paths & Cache**

#### `KOKORO_ORT_MODEL_PATH`
- **Purpose**: Path to optimized ONNX Runtime model
- **Values**: `.cache/ort/kokoro-v1.0.int8.ort` (default)
- **Development**: Default path
- **Production**: Default path
- **Example**: `export KOKORO_ORT_MODEL_PATH=.cache/ort/kokoro-v1.0.int8.ort`

#### `KOKORO_ORT_CACHE_DIR`
- **Purpose**: ONNX Runtime cache directory
- **Values**: `.cache/ort` (default)
- **Development**: Default path
- **Production**: Default path
- **Example**: `export KOKORO_ORT_CACHE_DIR=.cache/ort`

## Environment Setup Scripts

### Development Environment
```bash
# Quick development setup
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true
export KOKORO_FAST_STARTUP=true
export KOKORO_MISAKI_ENABLED=true
export KOKORO_MISAKI_FALLBACK=true

# Save to .env file
echo "KOKORO_DEVELOPMENT_MODE=true" >> .env
echo "KOKORO_SKIP_BENCHMARKING=true" >> .env
echo "KOKORO_FAST_STARTUP=true" >> .env
echo "KOKORO_MISAKI_ENABLED=true" >> .env
echo "KOKORO_MISAKI_FALLBACK=true" >> .env
```

### Production Environment
```bash
# Production optimization setup
export KOKORO_PRODUCTION=true
export KOKORO_BENCHMARK_FREQUENCY=daily
export KOKORO_GRAPH_OPT_LEVEL=ALL
export KOKORO_MEMORY_ARENA_SIZE_MB=1024
export KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine
export KOKORO_COREML_SPECIALIZATION=FastPrediction
export KOKORO_MISAKI_ENABLED=true
export KOKORO_MISAKI_CACHE_SIZE=2000
export KOKORO_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Save to .env file
echo "KOKORO_PRODUCTION=true" >> .env
echo "KOKORO_BENCHMARK_FREQUENCY=daily" >> .env
echo "KOKORO_GRAPH_OPT_LEVEL=ALL" >> .env
echo "KOKORO_MEMORY_ARENA_SIZE_MB=1024" >> .env
echo "KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine" >> .env
echo "KOKORO_COREML_SPECIALIZATION=FastPrediction" >> .env
echo "KOKORO_MISAKI_ENABLED=true" >> .env
echo "KOKORO_MISAKI_CACHE_SIZE=2000" >> .env
echo "KOKORO_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com" >> .env
```

## Usage Examples

### Local Development
```bash
# Start with development optimizations
./start_development.sh

# Or manually set environment
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true
python -m api.main
```

### Production Deployment
```bash
# Start with production optimizations
./start_production.sh

# Or manually set environment
export KOKORO_PRODUCTION=true
export KOKORO_BENCHMARK_FREQUENCY=daily
python -m api.main
```

### Docker Deployment
```bash
# Use production Docker image with environment variables
docker run -e KOKORO_PRODUCTION=true \
           -e KOKORO_BENCHMARK_FREQUENCY=daily \
           -e KOKORO_ALLOWED_HOSTS=yourdomain.com \
           kokoro-tts:latest
```

## Performance Impact

### Development Mode Benefits
- **Faster Startup**: 30-50% faster startup time
- **Reduced Benchmarking**: Skip automatic benchmarks
- **More Logging**: Detailed debug information
- **Flexible Configuration**: Easy to modify settings

### Production Mode Benefits
- **Security**: Host restrictions, production headers
- **Performance**: Maximum optimization levels
- **Monitoring**: Regular benchmark scheduling
- **Stability**: Conservative settings for reliability

## Troubleshooting

### Common Issues

1. **Slow Startup in Development**
   ```bash
   export KOKORO_SKIP_BENCHMARKING=true
   export KOKORO_FAST_STARTUP=true
   ```

2. **Memory Issues**
   ```bash
   export KOKORO_MEMORY_ARENA_SIZE_MB=512
   export KOKORO_DISABLE_MEM_PATTERN=false
   ```

3. **CoreML Performance Issues**
   ```bash
   export KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine
   export KOKORO_COREML_SPECIALIZATION=FastPrediction
   ```

4. **Security Warnings**
   ```bash
   export KOKORO_PRODUCTION=true
   export KOKORO_ALLOWED_HOSTS=yourdomain.com
   ```

## References

- [Development Guide](development.md)
- [Production Setup](production-patches.md)
- [ORT Optimization Guide](ORT-optimization-guide.md)
- [Benchmarking Guide](benchmarking.md)

