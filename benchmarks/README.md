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
│   └── m_series_suite.py          # M-series Mac optimization tests
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

# Original comprehensive benchmark (still available)
python scripts/run_bench.py --preset short --stream --trials 5
```

### Programmatic Usage

```python
from benchmarks.suites.ttfa_suite import TTFABenchmarkSuite
from benchmarks.suites.provider_suite import ProviderBenchmarkSuite
from benchmarks.suites.m_series_suite import MSeriesBenchmarkSuite

# Run TTFA benchmark
ttfa_suite = TTFABenchmarkSuite()
results = await ttfa_suite.run_full_suite()

# Run provider comparison
provider_suite = ProviderBenchmarkSuite()
results = await provider_suite.run_comprehensive_provider_benchmark()

# Run M-series validation
m_series_suite = MSeriesBenchmarkSuite()
results = await m_series_suite.run_comprehensive_m_series_benchmark()
```

### API Usage

The API endpoints use the same consolidated benchmark suites:

```bash
# Run TTFA benchmark via API
curl -X POST http://localhost:8000/benchmarks/run \
  -H "Content-Type: application/json" \
  -d '{"benchmark_type": "ttfa"}'

# Get benchmark status
curl http://localhost:8000/benchmarks/status
```

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




