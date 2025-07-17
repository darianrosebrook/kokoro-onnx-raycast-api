# Scripts Directory - Production Tools and Utilities

This directory contains production-ready scripts for the kokoro-onnx TTS system, focusing on performance optimization, validation, and system maintenance.

## Overview

The scripts in this directory support the current **Phase 4** optimization level of the TTS system, providing tools for:
- Performance benchmarking and validation
- Environment diagnostics and troubleshooting
- Cache management and optimization
- Production deployment validation

## Active Production Scripts

### Performance and Benchmarking

#### `run_benchmark.py` - Comprehensive Performance Benchmarking
**Purpose**: Production performance validation and optimization testing

**Features**:
- Model warmup and consistency testing
- Extended text performance analysis
- Provider comparison (CoreML vs CPU)
- Thermal analysis under sustained load
- Detailed statistical reporting

**Usage**:
```bash
# Full benchmark suite
python scripts/run_benchmark.py

# Quick benchmark
python scripts/run_benchmark.py --quick

# Custom configuration
python scripts/run_benchmark.py --warmup-runs 5 --consistency-runs 5
```

#### `validate_optimization_performance.py` - Optimization Validation
**Purpose**: Validate Phase 4 optimization effectiveness

**Features**:
- Real-time optimization validation
- Performance regression detection
- System resource monitoring
- Optimization effectiveness analysis

**Usage**:
```bash
# Quick validation
python scripts/validate_optimization_performance.py --quick

# Comprehensive validation
python scripts/validate_optimization_performance.py --comprehensive
```

#### `baseline_comparison.py` - Performance Analysis
**Purpose**: Compare performance against baselines and previous versions

**Features**:
- Historical performance comparison
- Regression detection
- Optimization impact analysis
- Statistical performance reporting

**Usage**:
```bash
python scripts/baseline_comparison.py
```

### System Management

#### `check_environment.py` - Environment Diagnostics
**Purpose**: Comprehensive environment validation and troubleshooting

**Features**:
- Python environment analysis
- Package installation validation
- System compatibility checking
- ONNX Runtime provider detection
- Installation recommendations

**Usage**:
```bash
python scripts/check_environment.py
```

#### `cleanup_cache.py` - Cache Management
**Purpose**: System cache cleanup and maintenance

**Features**:
- ONNX Runtime cache cleanup
- Model cache optimization
- Memory cleanup coordination
- Performance optimization

**Usage**:
```bash
# Standard cleanup
python scripts/cleanup_cache.py

# Aggressive cleanup
python scripts/cleanup_cache.py --aggressive
```

#### `manage_benchmark_cache.py` - Benchmark Cache Control
**Purpose**: Benchmark cache management and optimization

**Features**:
- Cache status monitoring
- Cache cleanup and optimization
- Benchmark frequency control
- Performance tuning

**Usage**:
```bash
# Check cache status
python scripts/manage_benchmark_cache.py --status

# Clear cache
python scripts/manage_benchmark_cache.py --clear
```

#### `configure_benchmark_frequency.py` - Performance Tuning
**Purpose**: Configure benchmark frequency and optimization settings

**Features**:
- Benchmark frequency configuration
- Performance optimization settings
- System tuning recommendations
- Production optimization

**Usage**:
```bash
# Show current configuration
python scripts/configure_benchmark_frequency.py --show-current

# Set benchmark frequency
python scripts/configure_benchmark_frequency.py --frequency weekly
```

## Phase 4 Optimization Status

The TTS system is currently implementing **Phase 4** advanced optimizations:

### Current Optimization Features
- **Dynamic Memory Optimization**: Intelligent memory management and arena sizing
- **Pipeline Warming**: Pre-compilation and pattern caching for immediate performance
- **Real-time Optimization**: Automatic performance tuning and bottleneck detection
- **Advanced Performance Monitoring**: Comprehensive metrics and trend analysis

### Performance Targets (Phase 4)
- **TTFA**: <500ms (improved from Phase 1's 800ms target)
- **RTF**: <0.8 (improved from Phase 1's 1.0 target)
- **Streaming Efficiency**: >95% (improved from Phase 1's 90% target)
- **Memory Efficiency**: >90% utilization
- **System Stability**: <5% performance degradation over time

## Development Workflow

### Quick Performance Validation
```bash
# 1. Check environment
python scripts/check_environment.py

# 2. Run quick benchmark
python scripts/run_benchmark.py --quick

# 3. Validate optimizations
python scripts/validate_optimization_performance.py --quick
```

### Production Deployment Validation
```bash
# 1. Comprehensive environment check
python scripts/check_environment.py

# 2. Full performance benchmark
python scripts/run_benchmark.py --comprehensive

# 3. Optimization validation
python scripts/validate_optimization_performance.py --comprehensive

# 4. Baseline comparison
python scripts/baseline_comparison.py
```

### System Maintenance
```bash
# 1. Cache cleanup
python scripts/cleanup_cache.py

# 2. Benchmark cache management
python scripts/manage_benchmark_cache.py --status

# 3. Performance tuning
python scripts/configure_benchmark_frequency.py --show-current
```

## Troubleshooting

### Common Issues

#### Performance Degradation
```bash
# Check for performance regressions
python scripts/baseline_comparison.py

# Validate optimization effectiveness
python scripts/validate_optimization_performance.py --comprehensive
```

#### Environment Issues
```bash
# Comprehensive environment diagnostics
python scripts/check_environment.py

# Cache cleanup
python scripts/cleanup_cache.py --aggressive
```

#### Benchmark Issues
```bash
# Check benchmark cache status
python scripts/manage_benchmark_cache.py --status

# Clear and reconfigure benchmarks
python scripts/manage_benchmark_cache.py --clear
python scripts/configure_benchmark_frequency.py --frequency weekly
```

## Historical Context

### Phase 1 Optimization (Completed)
The Phase 1 optimization focused on:
- 85% latency reduction (17.2s → 2.5s)
- Streaming audio implementation
- Adaptive buffering
- Basic performance monitoring

**Status**: ✅ **Complete** - All Phase 1 optimizations are now baseline performance

### Phase 4 Optimization (Current)
The current Phase 4 optimization focuses on:
- Advanced memory management
- Pipeline warming and pre-compilation
- Real-time optimization
- Comprehensive performance monitoring

**Status**: 🔄 **Active Development** - Advanced optimizations in progress

## Contributing

### Adding New Scripts
1. Follow the existing script structure and documentation patterns
2. Include comprehensive error handling and logging
3. Add usage examples and troubleshooting guidance
4. Update this README with new script documentation

### Script Standards
- Use Python 3.8+ compatible code
- Include comprehensive docstrings
- Implement proper error handling
- Provide clear usage examples
- Follow the project's logging standards

---

For detailed implementation information about Phase 4 optimizations, see the main project documentation in `docs/` and the API status endpoints. 