"""
Hardware capabilities caching and management.

This module provides caching utilities for hardware capabilities
to optimize performance and avoid repeated expensive system calls.
"""

from typing import Optional, Dict, Any
import logging

def get_cached_capabilities() -> Optional[Dict[str, Any]]:
    """
    Get cached hardware capabilities if available.
    
    @returns Optional[Dict[str, Any]]: Cached capabilities or None if not available
    """
    from .detection import _capabilities_cache
    return _capabilities_cache


def clear_capabilities_cache() -> None:
    """
    Clear the cached hardware capabilities.
    
    This forces a fresh detection on the next call to detect_apple_silicon_capabilities().
    """
    from . import detection
    detection._capabilities_cache = None
    
    logger = logging.getLogger(__name__)
    logger.debug(" Cleared hardware capabilities cache")


def refresh_capabilities_cache() -> Dict[str, Any]:
    """
    Force refresh of hardware capabilities cache.
    
    This clears the existing cache and performs fresh hardware detection.
    
    @returns Dict[str, Any]: Freshly detected hardware capabilities
    """
    clear_capabilities_cache()
    from .detection import detect_apple_silicon_capabilities
    return detect_apple_silicon_capabilities()


def is_capabilities_cached() -> bool:
    """
    Check if hardware capabilities are currently cached.
    
    @returns bool: True if capabilities are cached, False otherwise
    """
    return get_cached_capabilities() is not None


def get_capabilities_summary() -> Dict[str, Any]:
    """
    Get a summary of current hardware capabilities.
    
    @returns Dict[str, Any]: Summary of key hardware capabilities
    """
    capabilities = get_cached_capabilities()
    if not capabilities:
        from .detection import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    return {
        'platform': capabilities.get('platform', 'Unknown'),
        'is_apple_silicon': capabilities.get('is_apple_silicon', False),
        'chip_family': capabilities.get('chip_family', 'Unknown'),
        'has_neural_engine': capabilities.get('has_neural_engine', False),
        'neural_engine_cores': capabilities.get('neural_engine_cores', 0),
        'cpu_cores': capabilities.get('cpu_cores', 0),
        'memory_gb': capabilities.get('memory_gb', 0),
        'recommended_provider': capabilities.get('recommended_provider', 'CPUExecutionProvider'),
        'hardware_issues_count': len(capabilities.get('hardware_issues', []))
    }
