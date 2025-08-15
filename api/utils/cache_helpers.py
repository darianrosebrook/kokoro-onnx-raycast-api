"""
Cache Helpers - Persistent Caching with System Fingerprinting

This module provides utilities for persistent caching across process restarts,
system fingerprinting, and file locking to prevent redundant expensive operations.

@author: @darianrosebrook
@date: 2025-08-08
@version: 1.0.0
"""

import hashlib
import json
import os
import time
import platform
import subprocess
import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache directory setup
CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def _file_sha256(path: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.debug(f"Could not compute SHA256 for {path}: {e}")
        return "unknown"


def compute_system_fingerprint(model_path: str, voices_path: str) -> str:
    """
    Compute a stable system fingerprint for caching.
    
    The fingerprint includes hardware, software, and configuration factors
    that affect model initialization and performance.
    
    @param model_path: Path to the ONNX model file
    @param voices_path: Path to the voices directory
    @returns: SHA1 hash of the system fingerprint
    """
    try:
        # Hardware detection
        chip = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                            capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
        ram = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                           capture_output=True, text=True, timeout=5).stdout.strip() or "0"
        
        # Software versions
        os_ver = platform.mac_ver()[0] if platform.system() == "Darwin" else platform.platform()
        
        # Import ONNX Runtime version
        try:
            import onnxruntime as ort
            ort_ver = getattr(ort, "__version__", "unknown")
        except ImportError:
            ort_ver = "unknown"
        
        # Import Kokoro version
        try:
            import kokoro_onnx as _k
            kokoro_ver = getattr(_k, "__version__", "unknown")
        except ImportError:
            kokoro_ver = "unknown"
        
        # Model signature (path + mtime + hash)
        model_sig = f"{model_path}:{os.path.getmtime(model_path)}"
        try:
            model_sig += f":{_file_sha256(model_path)}"
        except Exception:
            pass
        
        # Environment variables that affect graph compilation
        env_affecting = {
            k: os.environ.get(k)
            for k in [
                "KOKORO_COREML_MODEL_FORMAT",
                "KOKORO_COREML_COMPUTE_UNITS", 
                "KOKORO_COREML_SPECIALIZATION",
                "KOKORO_COREML_LOW_PRECISION_GPU",
                "KOKORO_CPU_INTRA_THREADS",
                "KOKORO_CPU_INTER_THREADS",
                "KOKORO_ORT_OPTIMIZATION_ENABLED",
                "KOKORO_BENCHMARK_FREQUENCY",
            ]
            if os.environ.get(k) is not None
        }
        
        # Build fingerprint basis
        basis = {
            "chip": chip,
            "ram": ram,
            "os": os_ver,
            "ort": ort_ver,
            "kokoro": kokoro_ver,
            "model": model_sig,
            "voices_path": voices_path,
            "env": env_affecting,
        }
        
        # Compute SHA1 hash
        fingerprint = hashlib.sha1(json.dumps(basis, sort_keys=True).encode()).hexdigest()
        logger.debug(f"System fingerprint: {fingerprint[:8]}...")
        return fingerprint
        
    except Exception as e:
        logger.warning(f"Could not compute system fingerprint: {e}")
        # Fallback to basic fingerprint
        fallback = {
            "platform": platform.platform(),
            "model_path": model_path,
            "voices_path": voices_path,
        }
        return hashlib.sha1(json.dumps(fallback, sort_keys=True).encode()).hexdigest()


def _resolve_cache_path(name: str) -> str:
    """Resolve a cache file name to an absolute path under CACHE_DIR.
    - Strips any leading slashes
    - Strips an accidental leading '.cache/' prefix to avoid double nesting
    - Joins with CACHE_DIR
    """
    cleaned = (name or "").strip().lstrip("/\\")
    cache_prefix = f"{CACHE_DIR}{os.sep}"
    if cleaned.startswith(cache_prefix):
        cleaned = cleaned[len(cache_prefix):]
    return os.path.join(CACHE_DIR, cleaned)


def load_json_cache(name: str) -> Optional[Dict[str, Any]]:
    """
    Load JSON data from cache file.
    
    @param name: Cache file name (relative to '.cache'). Accepts paths with or without a leading '.cache/'.
    @returns: Cached data or None if not found/invalid
    """
    path = _resolve_cache_path(name)
    try:
        with open(path, "r") as f:
            data = json.load(f)
            logger.debug(f"Loaded cache: {name}")
            return data
    except Exception as e:
        logger.debug(f"Could not load cache {name}: {e}")
        return None


def save_json_cache_atomic(name: str, data: Dict[str, Any]) -> bool:
    """
    Save JSON data to cache file atomically.
    
    @param name: Cache file name (relative to '.cache'). Accepts paths with or without a leading '.cache/'.
    @param data: Data to cache
    @returns: True if successful, False otherwise
    """
    try:
        path = _resolve_cache_path(name)
        # Ensure parent directory exists
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        tmp = path + ".tmp"
        
        # Write to temporary file first
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        
        # Atomic rename
        os.replace(tmp, path)
        logger.debug(f"Saved cache: {name}")
        return True
        
    except Exception as e:
        logger.warning(f"Could not save cache {name}: {e}")
        return False


@contextmanager
def file_lock(name: str, timeout: float = 30.0):
    """
    File-based lock for cross-process synchronization.
    
    Uses directory creation as atomic lock mechanism.
    
    @param name: Lock name
    @param timeout: Timeout in seconds
    @raises TimeoutError: If lock cannot be acquired within timeout
    """
    lock_path = os.path.join(CACHE_DIR, f"{name}.lock")
    start_time = time.time()
    
    while True:
        try:
            os.mkdir(lock_path)
            break
        except FileExistsError:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timed out acquiring lock {name}")
            time.sleep(0.05)
    
    try:
        yield
    finally:
        try:
            os.rmdir(lock_path)
        except Exception as e:
            logger.debug(f"Could not remove lock {name}: {e}")


def clear_expired_caches(max_age_hours: int = 24) -> int:
    """
    Clear expired cache files.
    
    @param max_age_hours: Maximum age in hours before cache is considered expired
    @returns: Number of files removed
    """
    removed = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.json') or filename.endswith('.ort'):
                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        removed += 1
                        logger.debug(f"Removed expired cache: {filename}")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Error clearing expired caches: {e}")
    
    return removed

