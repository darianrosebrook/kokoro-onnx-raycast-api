"""
Cache Management Utilities

This module provides utilities for caching provider strategies, hardware capabilities,
and other performance-related data.
"""
import os
import json
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Create .cache directory
_cache_dir = ".cache"
os.makedirs(_cache_dir, exist_ok=True)


def read_cached_provider_strategy() -> Optional[Dict[str, Any]]:
    """
    Read cached provider strategy if available.

    @returns: Dictionary with keys 'provider' and 'bench_results' or None if missing
    """
    try:
        from api.utils.cache_helpers import compute_system_fingerprint, load_json_cache
        from api.config import TTSConfig

        fp = compute_system_fingerprint(TTSConfig.MODEL_PATH, TTSConfig.VOICES_PATH)
        cache_name = f"provider_strategy_{fp}.json"
        cached = load_json_cache(cache_name)
        if cached and isinstance(cached, dict) and cached.get("provider"):
            return cached
    except Exception as e:
        logger.debug(f"Failed to read cached provider strategy: {e}")
    return None


def save_cached_provider_strategy(strategy: Dict[str, Any]) -> bool:
    """
    Save provider strategy to cache.
    
    @param strategy: Strategy data to cache
    @returns: True if save was successful, False otherwise
    """
    try:
        from api.utils.cache_helpers import compute_system_fingerprint, save_json_cache
        from api.config import TTSConfig

        fp = compute_system_fingerprint(TTSConfig.MODEL_PATH, TTSConfig.VOICES_PATH)
        cache_name = f"provider_strategy_{fp}.json"
        save_json_cache(cache_name, strategy)
        return True
    except Exception as e:
        logger.error(f"Failed to save cached provider strategy: {e}")
        return False


def get_cache_file_path(cache_name: str) -> str:
    """
    Get the full path for a cache file.
    
    @param cache_name: Name of the cache file
    @returns: Full path to the cache file
    """
    return os.path.join(_cache_dir, cache_name)


def is_cache_valid(cache_file: str, max_age_hours: int = 24) -> bool:
    """
    Check if a cache file exists and is within the maximum age.
    
    @param cache_file: Path to the cache file
    @param max_age_hours: Maximum age in hours before cache is considered stale
    @returns: True if cache is valid, False otherwise
    """
    if not os.path.exists(cache_file):
        return False
    
    try:
        cache_age = time.time() - os.path.getmtime(cache_file)
        return cache_age < (max_age_hours * 3600)
    except Exception:
        return False


def clear_cache_file(cache_file: str) -> bool:
    """
    Remove a specific cache file.
    
    @param cache_file: Path to the cache file to remove
    @returns: True if removal was successful, False otherwise
    """
    try:
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info(f"Cleared cache file: {cache_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear cache file {cache_file}: {e}")
        return False


def clear_all_caches() -> bool:
    """
    Clear all cache files in the cache directory.
    
    @returns: True if clearing was successful, False otherwise
    """
    try:
        if os.path.exists(_cache_dir):
            for file in os.listdir(_cache_dir):
                file_path = os.path.join(_cache_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logger.info("Cleared all cache files")
        return True
    except Exception as e:
        logger.error(f"Failed to clear all caches: {e}")
        return False
