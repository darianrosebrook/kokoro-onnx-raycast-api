"""
Benchmark Module Initialization

Consolidated benchmark architecture exports.
"""

from benchmarks.core.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkMetrics
)

from benchmarks.suites.ttfa_suite import (
    TTFABenchmark,
    TTFABenchmarkSuite,
    TTFAMeasurement,
    TTFABenchmarkResult,
    TTFACategory
)

from benchmarks.suites.provider_suite import (
    ProviderBenchmark,
    ProviderBenchmarkSuite,
    ProviderComparison
)

from benchmarks.suites.m_series_suite import (
    MSeriesBenchmarkSuite,
    MSeriesOptimizationResult
)

__all__ = [
    # Core
    "BenchmarkRunner",
    "BenchmarkConfig",
    "BenchmarkResult",
    "BenchmarkMetrics",
    
    # TTFA Suite
    "TTFABenchmark",
    "TTFABenchmarkSuite",
    "TTFAMeasurement",
    "TTFABenchmarkResult",
    "TTFACategory",
    
    # Provider Suite
    "ProviderBenchmark",
    "ProviderBenchmarkSuite",
    "ProviderComparison",
    
    # M-series Suite
    "MSeriesBenchmarkSuite",
    "MSeriesOptimizationResult",
]




