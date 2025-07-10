# Development Guide

This guide covers the development workflow, including setup, testing, debugging, and optimization.

## Development Optimization Guide

For developers who want to understand and manually configure the optimization features that `setup.sh` provides automatically, here's a detailed guide:

### 1. Environment Diagnostics

Run comprehensive environment checks to ensure your setup is optimal:

```bash
# Check Python environment, packages, and system compatibility
python scripts/check_environment.py

# Run detailed CoreML and hardware diagnostics (Apple Silicon)
python scripts/troubleshoot_coreml.py

# Quick performance test
python scripts/quick_benchmark.py
```

### 2. ORT (ONNX Runtime) Optimization

For details on ORT Optimization, see [ORT_OPTIMIZATION_GUIDE.md](./ORT_OPTIMIZATION_GUIDE.md).

### 3. Benchmark Frequency Configuration

For details on Benchmark Frequency Configuration, see [benchmarking.md](./benchmarking.md).

### 4. Cache Management

For details on Cache Management, see [benchmarking.md](./benchmarking.md).

### 5. Development Mode Optimization

For faster development iteration, use these environment variables:

```bash
# Skip benchmarking for faster startup
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true

# Use extended cache duration for faster iteration
export KOKORO_FAST_STARTUP=true

# Add to .env for persistence
echo "KOKORO_DEVELOPMENT_MODE=true" >> .env
echo "KOKORO_SKIP_BENCHMARKING=true" >> .env
echo "KOKORO_FAST_STARTUP=true" >> .env
```

### 6. Performance Monitoring

For details on Performance Monitoring, see [benchmarking.md](./benchmarking.md).

### 7. Troubleshooting Optimization Issues

If optimization isn't working as expected:

```bash
# Check if ORT optimization is enabled
python scripts/convert_to_ort.py --validate .cache/ort/kokoro-v1.0.int8.ort

# Compare ORT vs ONNX performance
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx --benchmark --compare-original

# Diagnose CoreML issues
python scripts/troubleshoot_coreml.py

# Check environment setup
python scripts/check_environment.py

# Clear all caches and re-benchmark
python scripts/manage_benchmark_cache.py --clear
python scripts/cleanup_cache.py --aggressive
```

### 8. Production Optimization Checklist

Before deploying to production, ensure these optimizations are in place:

```bash
# ✅ Environment diagnostics pass
python scripts/check_environment.py

# ✅ ORT optimization enabled (Apple Silicon)
ls -la .cache/ort/kokoro-v1.0.int8.ort

# ✅ Benchmark frequency configured
python scripts/configure_benchmark_frequency.py --show-current

# ✅ Cache management working
python scripts/manage_benchmark_cache.py --status

# ✅ Performance benchmark passes
python run_benchmark.py --quick

# ✅ System validation complete
python scripts/troubleshoot_coreml.py
```

### 9. Development Workflow

Recommended development workflow with optimizations:

```bash
# 1. Initial setup with optimizations
./setup.sh

# 2. Development mode for faster iteration
export KOKORO_DEVELOPMENT_MODE=true
./start_development.sh

# 3. Monitor performance during development
curl -s http://localhost:8000/status | jq '.performance'

# 4. Test optimizations before production
python run_benchmark.py --verbose

# 5. Production deployment with full optimizations
export KOKORO_DEVELOPMENT_MODE=false
./start_production.sh
```

##  Development

### Development Setup

1. **Enable Development Mode**:
   ```bash
   export DEVELOPMENT_MODE="true"
   ./start_development.sh
   ```

2. **Access API Documentation**:
   ```
   http://localhost:8000/docs
   ```

3. **Monitor Performance**:
   ```
   http://localhost:8000/status
   ```

## Testing

```bash
# Validate application startup
python test_application_startup.py --verbose

# Test benchmark features
python test_benchmark_features.py

# Run comprehensive performance benchmark
python run_benchmark.py --warmup-runs 5 --consistency-runs 5
 
```

## Debugging

#### Enable Debug Logging
```bash
export LOG_LEVEL="DEBUG"
./start_development.sh
```

#### Performance Profiling
```bash
# Monitor inference times
curl -s http://localhost:8000/status | jq '.performance.average_inference_time'

# Check memory usage
curl -s http://localhost:8000/status | jq '.performance.memory_cleanup_count'

# Analyze provider performance
curl -s http://localhost:8000/status | jq '.performance.coreml_usage_percent'

# Check patch status
curl -s http://localhost:8000/status | jq '.patch_status'
``` 