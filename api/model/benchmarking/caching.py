"""
Benchmark result caching module.

This module provides caching functionality for benchmark results to avoid
repeating expensive performance tests.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = os.path.join(os.getcwd(), ".cache")
BENCHMARK_CACHE_FILE = os.path.join(CACHE_DIR, "benchmark_cache.json")

def _get_cache_expiry_seconds() -> int:
    """Get cache expiry duration from unified config"""
    try:
        from api.config import TTSConfig
        return TTSConfig.get_benchmark_cache_duration()
    except ImportError:
        # Fallback to 24 hours if config not available
        return 86400


def get_cached_benchmark_results(provider_name: str, capabilities: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get cached benchmark results based on hardware capabilities.
    
    @param provider_name: Name of the provider
    @param capabilities: Hardware capabilities dictionary
    @returns: Cached benchmark results or None if not found/expired
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if not os.path.exists(BENCHMARK_CACHE_FILE):
        return None
    
    try:
        with open(BENCHMARK_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        # Create cache key from provider and hardware capabilities
        cache_key = _create_cache_key(provider_name, capabilities)
        
        if cache_key not in cache_data:
            return None
        
        cached_entry = cache_data[cache_key]
        
        # Check if cache is expired using unified config
        cache_age_seconds = time.time() - cached_entry.get('timestamp', 0)
        cache_expiry_seconds = _get_cache_expiry_seconds()
        if cache_age_seconds > cache_expiry_seconds:
            cache_age_hours = cache_age_seconds / 3600
            logger.debug(f"Cache expired for {provider_name} (age: {cache_age_hours:.1f}h, expiry: {cache_expiry_seconds/3600:.1f}h)")
            return None
        
        logger.debug(f"Using cached benchmark results for {provider_name}")
        return cached_entry
        
    except Exception as e:
        logger.warning(f"Error reading benchmark cache: {e}")
        return None


def save_benchmark_results(provider_name: str, capabilities: Dict[str, Any], 
                         provider_options: Dict[str, Any], benchmark_time: float):
    """
    Save benchmark results to cache.
    
    @param provider_name: Name of the provider
    @param capabilities: Hardware capabilities dictionary  
    @param provider_options: Provider configuration options
    @param benchmark_time: Benchmark time in seconds
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Load existing cache
    cache_data = {}
    if os.path.exists(BENCHMARK_CACHE_FILE):
        try:
            with open(BENCHMARK_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading existing cache: {e}")
    
    # Create cache entry
    cache_key = _create_cache_key(provider_name, capabilities)
    cache_data[cache_key] = {
        'provider_name': provider_name,
        'provider_options': provider_options,
        'benchmark_time': benchmark_time,
        'timestamp': time.time(),
        'hardware_info': {
            'is_apple_silicon': capabilities.get('is_apple_silicon', False),
            'neural_engine_cores': capabilities.get('neural_engine_cores', 0),
            'memory_gb': capabilities.get('memory_gb', 8),
            'cpu_cores': capabilities.get('cpu_cores', 4)
        }
    }
    
    # Save cache
    try:
        with open(BENCHMARK_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        logger.debug(f"Saved benchmark results for {provider_name}")
    except Exception as e:
        logger.warning(f"Error saving benchmark cache: {e}")


def clear_benchmark_cache():
    """Clear all cached benchmark results."""
    try:
        if os.path.exists(BENCHMARK_CACHE_FILE):
            os.remove(BENCHMARK_CACHE_FILE)
        logger.info("Benchmark cache cleared")
    except Exception as e:
        logger.warning(f"Error clearing benchmark cache: {e}")


def _create_cache_key(provider_name: str, capabilities: Dict[str, Any]) -> str:
    """Create a unique cache key from provider name and capabilities."""
    key_parts = [
        provider_name,
        str(capabilities.get('is_apple_silicon', False)),
        str(capabilities.get('neural_engine_cores', 0)),
        str(capabilities.get('memory_gb', 8)),
        str(capabilities.get('cpu_cores', 4))
    ]
    return "_".join(key_parts)

