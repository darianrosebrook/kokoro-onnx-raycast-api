"""
Hardware detection and capabilities module.

This module provides comprehensive Apple Silicon hardware detection,
capability analysis, and hardware-specific optimizations.
"""

from .detection import detect_apple_silicon_capabilities, validate_provider, clear_hardware_capabilities_cache
from .capabilities import (
    get_cached_capabilities, 
    clear_capabilities_cache,
    refresh_capabilities_cache,
    is_capabilities_cached,
    get_capabilities_summary
)
from .validators import (
    validate_hardware_requirements,
    validate_provider_compatibility,
    get_optimal_provider_recommendation,
    diagnose_hardware_issues
)

__all__ = [
    # Detection
    'detect_apple_silicon_capabilities',
    'validate_provider',
    'clear_hardware_capabilities_cache',
    
    # Capabilities caching
    'get_cached_capabilities', 
    'clear_capabilities_cache',
    'refresh_capabilities_cache',
    'is_capabilities_cached',
    'get_capabilities_summary',
    
    # Validation
    'validate_hardware_requirements',
    'validate_provider_compatibility', 
    'get_optimal_provider_recommendation',
    'diagnose_hardware_issues'
]