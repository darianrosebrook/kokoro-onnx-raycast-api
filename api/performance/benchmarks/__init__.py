"""
Comprehensive benchmarking system for TTS performance optimization.

This module provides a complete benchmarking suite designed to measure and optimize
all aspects of the TTS pipeline, with special focus on TTFA (Time to First Audio) optimization.
"""

from .ttfa_benchmark import TTFABenchmark

__all__ = [
    'TTFABenchmark',
]