# Benchmarking and Monitoring Guide

This document provides detailed information on benchmarking, performance monitoring, and cache management for the Kokoro-ONNX TTS API.

##  Performance Monitoring

### Benchmark Reports

The system automatically generates comprehensive benchmark reports:

```bash
# Run comprehensive performance benchmark
python scripts/run_benchmark.py --verbose

# View current benchmark results
cat benchmark_results.md

# Force regenerate benchmark
curl http://localhost:8000/status
```

### Real-Time Metrics

Monitor system performance in real-time:

```bash
# Get comprehensive system status
curl http://localhost:8000/status | jq '.'

# Get performance statistics
curl http://localhost:8000/status | jq '.performance'

# Monitor inference times
curl http://localhost:8000/status | jq '.performance.average_inference_time'

# Check provider usage
curl http://localhost:8000/status | jq '.performance.provider_used'

# View patch status
curl http://localhost:8000/status | jq '.patch_status'

# Check hardware capabilities
curl http://localhost:8000/status | jq '.hardware'
```

### Key Performance Indicators

- **Inference Time**: Average time per TTS generation
- **Provider Usage**: CoreML vs CPU execution distribution
- **Memory Usage**: Memory consumption and cleanup events
- **Phonemizer Fallbacks**: Text processing fallback rate
- **System Stability**: Error rates and warning counts
- **Patch Status**: Applied patches and any errors
- **Hardware Info**: System capabilities and configuration

## Benchmark Frequency Configuration

The system includes configurable benchmark frequency to balance performance optimization with startup speed. Since hardware capabilities don't change frequently, longer cache periods are safe and provide faster startup times.

### Interactive Configuration
```bash
# Interactive setup with explanations and recommendations
python scripts/configure_benchmark_frequency.py

# Show current configuration
python scripts/configure_benchmark_frequency.py --show-current

# Set frequency non-interactively
python scripts/configure_benchmark_frequency.py --frequency weekly
```

### Frequency Options
- **Daily** (24 hours): For development or frequently changing systems
- **Weekly** (7 days):  **Recommended** for most users - balances optimization and convenience
- **Monthly** (30 days): For stable production systems and battery-conscious users  
- **Manual**: Expert mode - only benchmark when explicitly requested

### Environment Variable
```bash
# Set benchmark frequency (persisted in .env file)
export KOKORO_BENCHMARK_FREQUENCY=weekly

# Add to .env file for persistence
echo "KOKORO_BENCHMARK_FREQUENCY=weekly" >> .env
```

### Recommendations by Use Case
- **Developers**: Daily or Weekly (quick iteration, occasional optimization)
- **Most Users**: Weekly (recommended - good balance of speed and optimization)
- **Production**: Monthly (stable systems, minimal startup delays)
- **Experts**: Manual (complete control over when benchmarking occurs)

## Cache Management

Manage benchmark cache and ORT models for optimal performance:

```bash
# Show detailed cache status and expiration
python scripts/manage_benchmark_cache.py --status

# Clear cache to force re-benchmark (e.g., after OS updates)
python scripts/manage_benchmark_cache.py --clear

# Force benchmark regardless of cache status
python scripts/manage_benchmark_cache.py --force-benchmark

# Inspect detailed cache contents
python scripts/manage_benchmark_cache.py --inspect
```

The system uses intelligent caching to avoid re-running expensive operations:
- Provider recommendations are cached based on configured frequency (daily/weekly/monthly/manually)
- Hardware capabilities are cached during runtime
- Cache duration extends automatically in development mode for faster iteration
- Cache is automatically refreshed when used successfully

### Cache Cleanup Utility
Manage cache files and prevent storage bloat:

```bash
# Check cache statistics
python scripts/cleanup_cache.py --stats

# Clean up cache files
python scripts/cleanup_cache.py

# Aggressive cleanup (smaller limits)
python scripts/cleanup_cache.py --aggressive

# API endpoints for cache management
curl http://localhost:8000/cache-status
curl -X POST http://localhost:8000/cache-cleanup
```

**Features:**
-  Intelligent cleanup policies (age, size, pattern-based)
-  Real-time cache statistics and monitoring
-  Preserves important optimized models
-  Automatic cleanup during server startup
-  Configurable cleanup thresholds (500MB max, 10 temp dirs)
-  Performance impact monitoring

## Full System Benchmark
Comprehensive performance analysis:

```bash
# Quick benchmark (recommended)
python scripts/run_benchmark.py --quick

# Full benchmark (detailed analysis)
python scripts/run_benchmark.py
```

**Features:**
-  Provider performance comparison
-  Detailed timing analysis
-  Memory usage tracking
-  Optimization recommendations 