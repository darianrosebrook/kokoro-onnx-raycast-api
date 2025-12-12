"""Benchmark suites module"""

from benchmarks.suites.model_optimization_suite import ModelOptimizationBenchmarkSuite
from benchmarks.suites.provider_suite import ProviderBenchmarkSuite
from benchmarks.suites.ttfa_suite import TTFABenchmarkSuite

__all__ = [
    "ProviderBenchmarkSuite",
    "TTFABenchmarkSuite",
    "ModelOptimizationBenchmarkSuite",
]
