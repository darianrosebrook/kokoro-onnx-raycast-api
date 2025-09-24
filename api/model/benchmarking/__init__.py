"""
Benchmarking module.

This module provides performance testing, benchmark result caching,
and performance reporting capabilities.
"""

from .performance import benchmark_providers
from .caching import get_cached_benchmark_results, save_benchmark_results, clear_benchmark_cache
from .reporting import generate_performance_report

__all__ = [
    'benchmark_providers',
    'get_cached_benchmark_results',
    'save_benchmark_results',
    'clear_benchmark_cache',
    'generate_performance_report'
]