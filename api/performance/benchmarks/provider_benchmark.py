"""
Provider Performance Benchmark System

This module re-exports the consolidated provider benchmark suite for API use.
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
from benchmarks.suites.provider_suite import (
    ProviderBenchmark,
    ProviderBenchmarkSuite,
    ProviderComparison
)

import logging
logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "ProviderBenchmark",
    "ProviderBenchmarkSuite",
    "ProviderComparison",
]