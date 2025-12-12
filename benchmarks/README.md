"""
Consolidated Benchmark Suite README

This directory contains the consolidated benchmark architecture for the Kokoro ONNX TTS system.
"""

# Benchmarks Directory Structure

```
benchmarks/
├── __init__.py                    # Module exports
├── core/                          # Core benchmark infrastructure
│   ├── __init__.py
│   └── benchmark_runner.py       # Unified benchmark execution engine
├── suites/                        # Specialized benchmark suites
│   ├── __init__.py
│   ├── ttfa_suite.py              # TTFA comprehensive tests
│   ├── provider_suite.py          # Provider comparison tests
│   ├── streaming_suite.py        # Streaming performance tests (TODO)
│   ├── m_series_suite.py          # M-series Mac optimization tests
│   └── model_optimization_suite.py # Model optimization comparison tests
└── archive/                       # Archived old benchmarks
    ├── README.md
    └── [archived files]
```

## Usage

### CLI Usage

```bash
# Run comprehensive benchmark suite
python scripts/run_bench_enhanced.py --suite comprehensive

# Run specific suite
python scripts/run_bench_enhanced.py --suite ttfa
python scripts/run_bench_enhanced.py --suite provider
python scripts/run_bench_enhanced.py --suite m-series

# Run model optimization benchmark
python scripts/run_model_optimization_benchmark.py \\
    --original kokoro-v1.0.int8.onnx \\
    --optimized kokoro-v1.0.int8.optimized.onnx \\
    --compare \\
    --trials 5 \\
    --output results.json

# Original comprehensive benchmark (still available)
python scripts/run_bench.py --preset short --stream --trials 5
```

### Programmatic Usage

```python
from benchmarks.suites.ttfa_suite import TTFABenchmarkSuite
from benchmarks.suites.provider_suite import ProviderBenchmarkSuite
from benchmarks.suites.m_series_suite import MSeriesBenchmarkSuite
from benchmarks.suites.model_optimization_suite import ModelOptimizationBenchmarkSuite

# Run TTFA benchmark
ttfa_suite = TTFABenchmarkSuite()
results = await ttfa_suite.run_full_suite()

# Run provider comparison
provider_suite = ProviderBenchmarkSuite()
results = await provider_suite.run_comprehensive_provider_benchmark()

# Run M-series validation
m_series_suite = MSeriesBenchmarkSuite()
results = await m_series_suite.run_comprehensive_m_series_benchmark()

# Run model optimization comparison
model_opt_suite = ModelOptimizationBenchmarkSuite()
results = await model_opt_suite.run_comprehensive_comparison(
    original_model_path="kokoro-v1.0.int8.onnx",
    optimized_model_path="kokoro-v1.0.int8.optimized.onnx",
    trials=5
)
```

### API Usage

The API endpoints use the same consolidated benchmark suites:

````bash
# Run TTFA benchmark via API
curl -X POST http://localhost:8000/benchmarks/run \
  -H "Content-Type: application/json" \
  -d '{"benchmark_type": "ttfa"}'

# Run model optimization benchmark via API
curl -X POST http://localhost:8000/benchmarks/model-optimization \
  -H "Content-Type: application/json" \
  -d '{"trials": 5, "enable_comparison": true}'

# Get benchmark status
curl http://localhost:8000/benchmarks/status

## Benchmark Suites

### TTFA Suite (`ttfa_suite.py`)
- Comprehensive TTFA measurement
- M-series Mac target validation (<10ms)
- Performance categorization
- Bottleneck analysis

### Provider Suite (`provider_suite.py`)
- CoreML vs CPU provider comparison
- Real provider performance testing
- M-series optimization detection
- Provider recommendation

### M-Series Suite (`m_series_suite.py`)
- Neural Engine utilization validation
- CoreML provider performance testing
- Memory arena optimization validation
- Hardware detection and verification

### Streaming Suite (`streaming_suite.py`)
- TODO: Enhance with consolidated architecture
- Current: Basic streaming metrics collection

### Model Optimization Suite (`model_optimization_suite.py`)
- Side-by-side comparison of original vs optimized ONNX models
- Measures TTFA, RTF, memory usage, CPU usage
- Supports both CoreML and CPU providers
- Generates detailed comparison reports with regression detection
- Statistical analysis (mean, median, p95, min, max, std dev)
- Performance improvement percentage calculations
- Automatic recommendation (original vs optimized)

## Configuration

### Model Optimization Testing Flags

Enable model optimization testing via environment variables:

```bash
# Enable model optimization testing
export KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING=true

# Enable side-by-side comparison mode
export KOKORO_MODEL_OPTIMIZATION_COMPARISON=true

# Set optimized model path (default: kokoro-v1.0.int8.optimized.onnx)
export KOKORO_OPTIMIZED_MODEL_PATH=kokoro-v1.0.int8.optimized.onnx

# Override default model path
export KOKORO_MODEL_PATH=kokoro-v1.0.int8.onnx
````

### Model Optimization Benchmark Usage

**CLI:**

```bash
python scripts/run_model_optimization_benchmark.py \\
    --original kokoro-v1.0.int8.onnx \\
    --optimized kokoro-v1.0.int8.optimized.onnx \\
    --compare \\
    --trials 5 \\
    --output results.json \\
    --output-markdown report.md
```

**API:**

```bash
curl -X POST http://localhost:8000/benchmarks/model-optimization \\
  -H "Content-Type: application/json" \\
  -d '{
    "trials": 5,
    "enable_comparison": true,
    "custom_text": "Test text for comparison"
  }'
```

**Programmatic:**

```python
from benchmarks.suites.model_optimization_suite import ModelOptimizationBenchmarkSuite

suite = ModelOptimizationBenchmarkSuite(server_url="http://localhost:8000")
results = await suite.run_comprehensive_comparison(
    original_model_path="kokoro-v1.0.int8.onnx",
    optimized_model_path="kokoro-v1.0.int8.optimized.onnx",
    test_texts=["Test text"],
    trials=5
)

print(results.generate_report())
```

### Metrics Collected

- **TTFA (Time to First Audio)**: Milliseconds to first audio chunk
- **RTF (Real-Time Factor)**: Inference time / audio duration
- **Memory Usage**: RSS memory in MB
- **CPU Usage**: CPU percentage utilization
- **Success Rate**: Percentage of successful trials
- **Provider Used**: CoreML or CPU execution provider

### Report Format

The benchmark generates:

- **JSON Results**: Detailed metrics with statistical analysis
- **Markdown Report**: Human-readable comparison report
- **Recommendations**: Original vs optimized model recommendation
- **Regression Detection**: Automatic detection of performance regressions

## Architecture Benefits

1. **Unified Core**: All benchmarks use the same core execution engine
2. **Consistent Metrics**: Standardized metric collection across all suites
3. **M-series Optimized**: Specific tests for M-series Mac optimizations
4. **API/CLI Compatible**: Same benchmarks work for both API and CLI
5. **Extensible**: Easy to add new benchmark suites

## Migration Notes

- Old benchmarks archived in `benchmarks/archive/`
- API modules now import from consolidated benchmarks
- Original `run_bench.py` still available for backward compatibility
- New `run_bench_enhanced.py` uses consolidated architecture
