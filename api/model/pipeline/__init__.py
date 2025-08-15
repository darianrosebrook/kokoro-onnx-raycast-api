"""
Pipeline optimization module.

This module handles inference pipeline warming, text complexity analysis,
and pattern-based optimizations.
"""

from .warmer import (
    InferencePipelineWarmer, 
    get_pipeline_warmer, 
    initialize_pipeline_warmer
)
from .complexity_analyzer import (
    TextComplexityAnalyzer
)
from .patterns import (
    get_common_text_patterns,
    get_common_voice_patterns,
    get_phoneme_test_patterns,
    get_complexity_test_patterns,
    get_language_specific_patterns,
    get_voice_optimization_patterns,
    get_performance_test_patterns,
    optimize_patterns_for_session,
    get_cache_optimization_patterns,
    generate_benchmark_patterns
)

__all__ = [
    # Pipeline Warming
    'InferencePipelineWarmer',
    'get_pipeline_warmer',
    'initialize_pipeline_warmer',
    
    # Complexity Analysis
    'TextComplexityAnalyzer',
    
    # Pattern Optimization
    'get_common_text_patterns',
    'get_common_voice_patterns',
    'get_phoneme_test_patterns',
    'get_complexity_test_patterns',
    'get_language_specific_patterns',
    'get_voice_optimization_patterns',
    'get_performance_test_patterns',
    'optimize_patterns_for_session',
    'get_cache_optimization_patterns',
    'generate_benchmark_patterns'
]