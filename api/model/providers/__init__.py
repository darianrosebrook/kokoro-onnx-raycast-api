"""
Provider management module.

This module provides comprehensive ONNX Runtime provider management,
including CoreML and CPU provider optimization, benchmarking, and configuration.
"""

# ONNX Runtime providers
from .ort import (
    create_optimized_session_options,
    get_cached_provider_options,
    should_use_ort_optimization,
    get_or_create_ort_model,
    configure_ort_providers,
    clear_provider_cache,
    get_provider_info
)

# CoreML-specific providers
from .coreml import (
    setup_coreml_temp_directory,
    cleanup_coreml_temp_directory,
    create_coreml_provider_options,
    test_mlcompute_units_configuration,
    benchmark_mlcompute_units_if_needed,
    clear_provider_options_cache
)

__all__ = [
    # ONNX Runtime
    'create_optimized_session_options',
    'get_cached_provider_options', 
    'should_use_ort_optimization',
    'get_or_create_ort_model',
    'configure_ort_providers',
    'clear_provider_cache',
    'get_provider_info',
    
    # CoreML
    'setup_coreml_temp_directory',
    'cleanup_coreml_temp_directory',
    'create_coreml_provider_options',
    'test_mlcompute_units_configuration',
    'benchmark_mlcompute_units_if_needed',
    'verify_neural_engine_utilization',
    'clear_provider_options_cache'
]
