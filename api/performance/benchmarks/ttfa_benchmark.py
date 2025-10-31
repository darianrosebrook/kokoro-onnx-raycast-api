"""
TTFA (Time to First Audio) Benchmark System

This module re-exports the consolidated TTFA benchmark suite for API use.
"""

import sys
import os
from pathlib import Path

# Add benchmarks directory to path
project_root = Path(__file__).parent.parent.parent.parent
benchmarks_path = project_root / "benchmarks"
if str(benchmarks_path) not in sys.path:
    sys.path.insert(0, str(benchmarks_path))

# Import from consolidated benchmarks
from benchmarks.suites.ttfa_suite import (
    TTFABenchmark,
    TTFABenchmarkSuite,
    TTFAMeasurement,
    TTFABenchmarkResult,
    TTFACategory
)

import logging
logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "TTFABenchmark",
    "TTFABenchmarkSuite",
    "TTFAMeasurement",
    "TTFABenchmarkResult",
    "TTFACategory",
]

# Convenience functions for API use
async def run_ttfa_benchmark(quick: bool = False):
    """Run TTFA benchmark - convenience function for API"""
    suite = TTFABenchmarkSuite()
    if quick:
        result = await suite.benchmark.run_quick_ttfa_benchmark()
        suite.comprehensive_result = result
        return suite
    else:
        return await suite.run_full_suite()
