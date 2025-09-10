"""
Dependency injection module for the TTS API.

This module provides cached dependency injection functions for optimal performance
and resource management across the FastAPI application.
"""

import asyncio
from functools import lru_cache, wraps
from typing import Callable
import logging

logger = logging.getLogger(__name__)


# Enhanced dependency injection caching for optimal performance
# Reference: DEPENDENCY_RESEARCH.md section 2.2

@lru_cache(maxsize=1)
def get_tts_config():
    """
    Cached TTS configuration dependency.
    
    Returns cached TTSConfig instance to avoid repeated instantiation.
    Cache size limited to 1 since configuration is static.
    """
    from api.config import TTSConfig
    return TTSConfig()


@lru_cache(maxsize=1)
def get_model_capabilities():
    """
    Cached hardware capabilities dependency.
    
    Returns cached system capabilities to avoid repeated detection.
    Cache size limited to 1 since hardware doesn't change during runtime.
    """
    from api.model.loader import detect_apple_silicon_capabilities
    return detect_apple_silicon_capabilities()


@lru_cache(maxsize=10)
def get_cached_model_status():
    """
    Cached model status dependency with TTL-like behavior.
    
    Returns cached model status for performance optimization.
    Cache size limited to 10 to handle different status states.
    """
    from api.model.loader import get_model_status
    return get_model_status()


@lru_cache(maxsize=1)
def get_performance_tracker():
    """
    Cached performance tracker dependency.
    
    Returns cached performance tracking instance.
    Cache size limited to 1 since tracker is singleton.
    """
    from api.performance.stats import PerformanceTracker
    return PerformanceTracker()


# Async cached dependencies for better performance

def async_lru_cache(maxsize=128):
    """
    Async LRU cache decorator for expensive async operations.
    
    Provides caching for async functions with automatic cleanup and
    memory management for improved performance.
    
    @param maxsize: Maximum number of cached results
    @returns: Decorated async function with caching
    """
    def decorator(func: Callable):
        cache = {}
        cache_order = []
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key = str(args) + str(sorted(kwargs.items()))
            
            # Check if result is cached
            if key in cache:
                return cache[key]
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            # Manage cache size
            if len(cache) >= maxsize:
                # Remove oldest entry
                oldest_key = cache_order.pop(0)
                del cache[oldest_key]
            
            # Store new result
            cache[key] = result
            cache_order.append(key)
            
            return result
        
        return wrapper
    return decorator


@async_lru_cache(maxsize=1)
async def get_async_model_status():
    """
    Async cached model status for non-blocking operations.
    
    Returns model status asynchronously to avoid blocking the event loop
    during status checks.
    """
    from api.model.loader import get_model_status
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_model_status)


@async_lru_cache(maxsize=5)
async def get_async_performance_stats():
    """
    Async cached performance statistics.
    
    Returns performance statistics asynchronously for better request handling
    in high-traffic scenarios.
    """
    from api.performance.stats import get_performance_stats
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_performance_stats)


def clear_dependency_caches():
    """
    Clear all dependency caches for testing or state reset.
    
    This function clears all LRU caches to ensure fresh data
    during testing or when configuration changes.
    """
    get_tts_config.cache_clear()
    get_model_capabilities.cache_clear() 
    get_cached_model_status.cache_clear()
    get_performance_tracker.cache_clear()
    
    logger.info("All dependency caches cleared")


# Dependency validation functions

def validate_dependencies():
    """
    Validate that all required dependencies are available.
    
    This function checks that all critical dependencies can be
    loaded and are functioning correctly.
    """
    try:
        # Test core dependencies
        config = get_tts_config()
        capabilities = get_model_capabilities()
        
        # Validate that we have required attributes
        if not hasattr(config, 'MODEL_PATH'):
            raise ValueError("TTSConfig missing MODEL_PATH")
        
        if not isinstance(capabilities, dict):
            raise ValueError("Hardware capabilities should be dict")
        
        logger.info("✅ All dependencies validated successfully")
        
    except Exception as e:
        logger.error(f" Dependency validation failed: {e}")
        raise

