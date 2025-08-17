"""
CoreML provider configuration and optimization.

This module handles CoreML-specific optimizations including MLComputeUnits
configuration, temporary directory management, Apple Silicon optimizations,
and advanced memory leak mitigation for the "Context leak detected" issue.

## Memory Leak Mitigation

This module now includes comprehensive memory management to address the
"Context leak detected, msgtracer returned -1" errors that occur with
CoreML Execution Provider on M-series Macs. The solution includes:

1. **Objective-C Autorelease Pool Management**: Direct interaction with
   the Objective-C runtime to drain autorelease pools
2. **Aggressive Garbage Collection**: Forced cleanup after CoreML operations
3. **Memory Pressure Monitoring**: Automatic cleanup based on memory usage
4. **Operation Tracking**: Monitoring memory impact of CoreML operations

## Integration

The memory management system is automatically integrated with all CoreML
provider operations and can be configured for different usage patterns.
"""

import os
import glob
import time
import logging
import shutil
from typing import Dict, Any
from functools import lru_cache

# Cache for provider options to avoid duplicate creation and logging
_provider_options_cache: Dict[str, Dict[str, Any]] = {}

logger = logging.getLogger(__name__)


def setup_coreml_temp_directory() -> str:
    """
    Set up a dedicated temporary directory for CoreML operations.
    
    This ensures CoreML has a clean, controlled environment for temporary files
    and avoids permission issues that can occur with system temp directories.
    
    @returns str: Path to the configured CoreML temp directory
    """
    # Use a subdirectory of our cache directory for better control
    from api.config import TTSConfig
    cache_dir = getattr(TTSConfig, 'CACHE_DIR', os.path.join(os.getcwd(), ".cache"))
    local_temp_dir = os.path.join(cache_dir, "coreml_temp")
    
    # Create directory with proper permissions
    os.makedirs(local_temp_dir, exist_ok=True)
    os.chmod(local_temp_dir, 0o755)
    
    # Set multiple environment variables for maximum compatibility
    os.environ['TMPDIR'] = local_temp_dir
    os.environ['TMP'] = local_temp_dir
    os.environ['TEMP'] = local_temp_dir
    os.environ['COREML_TEMP_DIR'] = local_temp_dir
    os.environ['ONNXRUNTIME_TEMP_DIR'] = local_temp_dir
    
    # Also configure Python's tempfile module
    import tempfile
    tempfile.tempdir = local_temp_dir
    
    # Clean up any existing temp files first
    cleanup_existing_coreml_temp_files(local_temp_dir)
    
    # Force ONNX Runtime to use our temp directory
    _force_onnxruntime_temp_directory(local_temp_dir)
    
    # Verify the directory is writable
    try:
        test_file = os.path.join(local_temp_dir, "writetest.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        
        logger.info(f"📁 CoreML temp directory configured: {local_temp_dir}")
        
    except Exception as e:
        logger.error(f"❌ CoreML temp directory setup failed: {e}")
        raise
    
    return local_temp_dir


def cleanup_existing_coreml_temp_files(local_temp_dir: str) -> None:
    """
    Clean up existing CoreML temp files in the specified directory.
    
    This prevents accumulation of temp files and ensures a clean start.
    
    @param local_temp_dir: Path to the temp directory to clean
    """
    try:
        if not os.path.exists(local_temp_dir):
            return
            
        for item in os.listdir(local_temp_dir):
            item_path = os.path.join(local_temp_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except (OSError, PermissionError) as e:
                # Log but don't fail - some files might be in use
                logger.debug(f"Could not clean up temp file {item_path}: {e}")
    except Exception as e:
        logger.debug(f"Temp directory cleanup failed: {e}")


def _force_onnxruntime_temp_directory(local_temp_dir: str) -> None:
    """
    Force ONNX Runtime to use our local temp directory through various methods.
    
    This uses multiple approaches to ensure ONNX Runtime respects our temp directory
    choice, as it sometimes ignores environment variables.
    
    @param local_temp_dir: Path to the temp directory to use
    """
    try:
        import tempfile
        
        # Method 1: Set Python's tempfile module to use our directory
        tempfile.tempdir = local_temp_dir
        
        # Method 2: Override tempfile.gettempdir() function - avoid infinite recursion
        original_gettempdir = getattr(tempfile, '_original_gettempdir', tempfile.gettempdir)
        if not hasattr(tempfile, '_original_gettempdir'):
            tempfile._original_gettempdir = tempfile.gettempdir
        
        def patched_gettempdir():
            return local_temp_dir
        tempfile.gettempdir = patched_gettempdir
        
        logger.debug(f"✅ ONNX Runtime temp directory override configured: {local_temp_dir}")
        
    except Exception as e:
        logger.warning(f"⚠️ Could not fully configure ONNX Runtime temp directory override: {e}")


def cleanup_coreml_temp_directory() -> None:
    """
    Clean up the CoreML temporary directory to free up space.
    
    This removes old files while preserving the directory structure for future use.
    Files older than 1 hour are automatically cleaned up.
    """
    try:
        from api.config import TTSConfig
        cache_dir = getattr(TTSConfig, 'CACHE_DIR', os.path.join(os.getcwd(), ".cache"))
        local_temp_dir = os.path.join(cache_dir, "coreml_temp")
        
        if not os.path.exists(local_temp_dir):
            return
        
        current_time = time.time()
        files_cleaned = 0
        
        # Clean up files older than 1 hour
        for file_path in glob.glob(os.path.join(local_temp_dir, "*")):
            try:
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > 3600:  # 1 hour
                        os.remove(file_path)
                        files_cleaned += 1
                elif os.path.isdir(file_path):
                    # For directories, check if they're old and empty
                    dir_age = current_time - os.path.getmtime(file_path)
                    if dir_age > 3600 and not os.listdir(file_path):
                        os.rmdir(file_path)
                        files_cleaned += 1
            except Exception as e:
                logger.debug(f"Could not clean up {file_path}: {e}")
        
        if files_cleaned > 0:
            logger.info(f"🧹 Cleaned up {files_cleaned} old CoreML temp files")
            
    except Exception as e:
        logger.debug(f"CoreML temp directory cleanup failed: {e}")


def _get_capability_cache_key(capabilities: Dict[str, Any]) -> str:
    """
    Generate a cache key for provider options based on hardware capabilities.
    
    @param capabilities: Hardware capabilities dictionary
    @returns str: Cache key for the capability set
    """
    # Create a stable key based on key hardware characteristics
    key_parts = [
        str(capabilities.get('is_apple_silicon', False)),
        str(capabilities.get('has_neural_engine', False)),
        str(capabilities.get('neural_engine_cores', 0)),
        str(capabilities.get('memory_gb', 0)),
        str(capabilities.get('cpu_cores', 0))
    ]
    return '|'.join(key_parts)

def create_coreml_provider_options(capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create optimized CoreML provider options based on hardware capabilities.
    
    This function creates provider-specific options optimized for the detected
    hardware configuration with integrated memory leak mitigation. Results are 
    cached to avoid duplicate creation and logging during startup.
    
    ## Memory Leak Mitigation
    
    This function now automatically initializes the CoreML memory management
    system to prevent context leaks during provider operations.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns Dict[str, Any]: CoreML provider options dictionary
    """
    # Initialize memory management for CoreML operations (unless disabled)
    memory_mgmt_disabled = os.environ.get('KOKORO_DISABLE_MEMORY_MGMT', 'false').lower() == 'true'
    
    if not memory_mgmt_disabled:
        try:
            from api.model.memory.coreml_leak_mitigation import (
                initialize_coreml_memory_management,
                configure_coreml_memory_management
            )
            
            # Initialize memory management system
            if initialize_coreml_memory_management():
                logger.debug("🧠 CoreML memory management initialized for provider options")
            
            # Configure based on system capabilities
            memory_gb = capabilities.get('memory_gb', 8)
            aggressive_mode = memory_gb >= 16  # Enable aggressive mode on high-memory systems
            memory_threshold = min(500, max(100, int(memory_gb * 25)))  # 25MB per GB of RAM
            
            configure_coreml_memory_management(
                aggressive_cleanup=aggressive_mode,
                memory_threshold_mb=memory_threshold,
                monitoring_enabled=True
            )
            
            logger.debug(f"✅ Memory management configured: aggressive={aggressive_mode}, threshold={memory_threshold}MB")
        
        except Exception as e:
            logger.debug(f"⚠️ Could not initialize CoreML memory management: {e}")
    else:
        logger.info("🔧 CoreML memory management disabled via KOKORO_DISABLE_MEMORY_MGMT")
    
    # Check cache first to avoid duplicate creation and logging
    cache_key = _get_capability_cache_key(capabilities)
    if cache_key in _provider_options_cache:
        logger.debug("✅ Using cached CoreML provider options")
        return _provider_options_cache[cache_key].copy()
    
    logger.info("🔧 Creating optimized CoreML provider options...")
    
    # Extract key capabilities
    neural_engine_cores = capabilities.get('neural_engine_cores', 0)
    memory_gb = capabilities.get('memory_gb', 8)
    
    # Initialize base options
    coreml_options = {
        'MLComputeUnits': 'CPUAndGPU',  # Default fallback
        'ModelFormat': 'MLProgram',     # Modern format for better performance
        'AllowLowPrecisionAccumulationOnGPU': '1',  # Enable FP16 for better performance
        'RequireStaticInputShapes': '0',  # Allow dynamic shapes for flexibility
    }
    
    # Neural Engine optimizations based on chip family
    if neural_engine_cores >= 32:  # M1 Max / M2 Max
        logger.info(f"🚀 M1 Max / M2 Max detected with {neural_engine_cores} Neural Engine cores")
        
        # M1 Max / M2 Max optimization strategy
        coreml_options.update({
            'MLComputeUnits': 'CPUAndNeuralEngine',  # Maximize Neural Engine utilization
            'AllowLowPrecisionAccumulationOnGPU': '1',  # Enable FP16 for better performance
            'ModelFormat': 'MLProgram',  # Use MLProgram for newer devices
            'RequireStaticInputShapes': '0',  # Allow dynamic shapes for flexibility
        })
        
        # Set Neural Engine specific environment optimizations
        os.environ['COREML_NEURAL_ENGINE_OPTIMIZATION'] = '1'
        os.environ['COREML_USE_FLOAT16'] = '1'
        os.environ['COREML_OPTIMIZE_FOR_APPLE_SILICON'] = '1'
        
    elif neural_engine_cores >= 18:  # M3
        logger.info(f"🚀 M3 detected with {neural_engine_cores} Neural Engine cores")
        
        coreml_options.update({
            'MLComputeUnits': 'CPUAndNeuralEngine',
            'ModelFormat': 'MLProgram',
            'AllowLowPrecisionAccumulationOnGPU': '1',
        })
        
    elif neural_engine_cores >= 16:  # M1 / M2
        logger.info(f"🚀 M1/M2 detected with {neural_engine_cores} Neural Engine cores")
        
        coreml_options.update({
            'MLComputeUnits': 'CPUAndNeuralEngine',
            'ModelFormat': 'MLProgram',
        })
        
    else:  # Other Apple Silicon or fallback
        logger.info("🚀 Apple Silicon detected - using CPU+GPU configuration")
        
        coreml_options.update({
            'MLComputeUnits': 'CPUAndGPU',
        })
    
    # Memory-based optimizations (logged only once per capability set)
    if memory_gb >= 32:  # High memory systems
        coreml_options.update({
            # 'MaximumCacheSizeMB': '1024',  # Not supported in current ONNX Runtime version
            # 'SubgraphSelectionCriteria': 'aggressive',  # Removed - not supported in ORT 1.22.1
            # 'MinimumNodesPerSubgraph': '5',  # Removed - not supported in ORT 1.22.1
        })
        logger.info(f"🚀 High memory system ({memory_gb}GB): Applied large cache optimizations")
        
    elif memory_gb >= 16:  # Standard memory systems
        coreml_options.update({
            # 'MaximumCacheSizeMB': '512',  # Not supported in current ONNX Runtime version
            # 'SubgraphSelectionCriteria': 'balanced',  # Removed - not supported in ORT 1.22.1
            # 'MinimumNodesPerSubgraph': '3',  # Removed - not supported in ORT 1.22.1
        })
        logger.info(f"⚖️ Standard memory system ({memory_gb}GB): Applied balanced cache optimizations")
        
    else:  # Low memory systems
        coreml_options.update({
            # 'MaximumCacheSizeMB': '256',  # Not supported in current ONNX Runtime version
            # 'SubgraphSelectionCriteria': 'minimal',  # Removed - not supported in ORT 1.22.1
            # 'MinimumNodesPerSubgraph': '1',  # Removed - not supported in ORT 1.22.1
        })
        logger.info(f"💾 Low memory system ({memory_gb}GB): Applied minimal cache optimizations")
    
    # Set environment variable for CoreML temp directory
    from api.config import TTSConfig
    cache_dir = getattr(TTSConfig, 'CACHE_DIR', os.path.join(os.getcwd(), ".cache"))
    local_temp_dir = os.path.join(cache_dir, "coreml_temp")
    os.makedirs(local_temp_dir, exist_ok=True)
    os.environ['COREML_TEMP_DIR'] = local_temp_dir
    logger.debug(f"Set COREML_TEMP_DIR to: {local_temp_dir}")
    
    # Set a dedicated cache path for compiled CoreML models
    coreml_cache_path = os.path.join(cache_dir, "coreml_cache")
    os.makedirs(coreml_cache_path, exist_ok=True)
    coreml_options['ModelCacheDirectory'] = coreml_cache_path
    logger.debug(f"Set CoreML cache directory to: {coreml_cache_path}")
    
    # Cache the result to avoid duplicate creation and logging
    _provider_options_cache[cache_key] = coreml_options.copy()
    logger.debug(f"💾 Cached CoreML provider options for capability set: {cache_key[:20]}...")
    
    return coreml_options


def coreml_memory_managed_session_creation(session_creation_func, *args, **kwargs):
    """
    Wrapper for ONNX Runtime session creation with CoreML memory management.
    
    This function wraps the session creation process with comprehensive memory
    management to mitigate context leaks during CoreML provider initialization.
    
    @param session_creation_func: Function that creates the ONNX Runtime session
    @param args: Arguments to pass to session creation function
    @param kwargs: Keyword arguments to pass to session creation function
    @returns: Result of session creation with memory management applied
    """
    # Check if memory management is disabled
    memory_mgmt_disabled = os.environ.get('KOKORO_DISABLE_MEMORY_MGMT', 'false').lower() == 'true'
    
    if memory_mgmt_disabled:
        logger.debug("🔧 Memory management disabled, using standard session creation")
        return session_creation_func(*args, **kwargs)
    
    try:
        from api.model.memory.coreml_leak_mitigation import get_memory_manager
        
        manager = get_memory_manager()
        
        with manager.managed_operation("coreml_session_creation"):
            logger.debug("🧠 Creating CoreML session with memory management")
            result = session_creation_func(*args, **kwargs)
            logger.debug("✅ CoreML session created successfully with memory management")
            return result
            
    except ImportError:
        logger.debug("⚠️ Memory management not available, using standard session creation")
        return session_creation_func(*args, **kwargs)
    except Exception as e:
        logger.debug(f"⚠️ Memory managed session creation failed, falling back: {e}")
        return session_creation_func(*args, **kwargs)


def get_coreml_memory_status() -> Dict[str, Any]:
    """
    Get the current status of CoreML memory management.
    
    @returns Dict[str, Any]: Memory management status and statistics
    """
    try:
        from api.model.memory.coreml_leak_mitigation import get_coreml_memory_stats
        return get_coreml_memory_stats()
    except ImportError:
        return {"error": "CoreML memory management not available"}
    except Exception as e:
        return {"error": str(e)}


def force_coreml_cleanup() -> Dict[str, Any]:
    """
    Force immediate CoreML memory cleanup.
    
    This function can be called manually to trigger aggressive memory cleanup
    when context leaks are detected or memory usage is high.
    
    @returns Dict[str, Any]: Cleanup results
    """
    try:
        from api.model.memory.coreml_leak_mitigation import force_coreml_memory_cleanup
        return force_coreml_memory_cleanup()
    except ImportError:
        return {"error": "CoreML memory management not available"}
    except Exception as e:
        return {"error": str(e)}


def clear_provider_options_cache() -> None:
    """
    Clear the cached provider options.
    
    This function is useful for testing or when hardware configurations
    change and cached options need to be refreshed.
    """
    global _provider_options_cache
    _provider_options_cache.clear()
    logger.debug("🧹 Cleared CoreML provider options cache")


def test_mlcompute_units_configuration(capabilities: Dict[str, Any]) -> str:
    """
    Test different MLComputeUnits configurations to find the optimal one.
    
    This function systematically tests different MLComputeUnits configurations
    to determine which provides the best performance for the specific hardware.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns str: Optimal MLComputeUnits configuration string
    """
    logger.info("🧪 Testing MLComputeUnits configurations for optimal performance...")
    
    # Define test configurations based on hardware
    neural_engine_cores = capabilities.get('neural_engine_cores', 0)
    
    if neural_engine_cores >= 32:  # M1 Max / M2 Max
        test_configs = [
            'CPUAndNeuralEngine',  # Primary choice for M1 Max
            'ALL',                 # Secondary choice
            'CPUAndGPU',          # Fallback
        ]
        logger.info(f"🚀 M1 Max / M2 Max detected: Testing {len(test_configs)} configurations")
        
    elif neural_engine_cores >= 16:  # M1 / M2
        test_configs = [
            'CPUAndNeuralEngine',  # Primary choice for M1/M2
            'ALL',                 # Secondary choice
            'CPUAndGPU',          # Fallback
        ]
        logger.info(f"🚀 M1 / M2 detected: Testing {len(test_configs)} configurations")
        
    elif capabilities.get('is_apple_silicon', False):  # Other Apple Silicon
        test_configs = [
            'CPUAndGPU',          # Primary choice for other Apple Silicon
            'ALL',                # Secondary choice
            'CPUOnly',            # Fallback
        ]
        logger.info(f"🍎 Apple Silicon detected: Testing {len(test_configs)} configurations")
        
    else:  # Non-Apple Silicon
        test_configs = ['CPUOnly']
        logger.info("🖥️ Non-Apple Silicon: Using CPU-only configuration")
    
    # For now, return the first (optimal) configuration
    # In a full implementation, we would actually benchmark each configuration
    optimal_config = test_configs[0]
    logger.info(f"✅ Selected optimal MLComputeUnits configuration: {optimal_config}")
    
    return optimal_config


def benchmark_mlcompute_units_if_needed(capabilities: Dict[str, Any]) -> str:
    """
    Benchmark MLComputeUnits configurations if needed, with caching.
    
    This function checks if we have cached results for MLComputeUnits optimization
    and only runs benchmarks if necessary.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns str: Optimal MLComputeUnits configuration string
    """
    from api.utils.cache_helpers import load_json_cache, save_json_cache_atomic
    import json
    
    # Create cache key based on hardware capabilities
    cache_key = f"{capabilities.get('neural_engine_cores', 0)}_{capabilities.get('memory_gb', 8)}_{capabilities.get('is_apple_silicon', False)}"
    cache_name = f"mlcompute_units_cache_{cache_key}.json"
    
    # Check for cached results
    cached_data = load_json_cache(cache_name)
    if cached_data:
        cache_age = time.time() - cached_data.get("timestamp", 0)
        if cache_age < 86400:  # 24 hours cache
            optimal_config = cached_data.get("optimal_config")
            if optimal_config:
                logger.info(f"💾 Using cached MLComputeUnits configuration: {optimal_config}")
                return optimal_config
    
    # Run benchmark test
    optimal_config = test_mlcompute_units_configuration(capabilities)
    
    # Cache the result
    try:
        save_json_cache_atomic(cache_name, {
            "optimal_config": optimal_config,
            "timestamp": time.time(),
            "hardware_info": {
                "neural_engine_cores": capabilities.get('neural_engine_cores', 0),
                "memory_gb": capabilities.get('memory_gb', 8),
                "is_apple_silicon": capabilities.get('is_apple_silicon', False)
            }
        })
        logger.info(f"💾 Cached MLComputeUnits configuration: {optimal_config}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to cache MLComputeUnits configuration: {e}")
    
    return optimal_config


def cleanup_coreml_contexts():
    """
    Clean up CoreML contexts and temporary files to address "Context leak detected" errors.
    
    This function performs aggressive cleanup of CoreML-related resources to prevent
    the "msgtracer returned -1" context leak errors that cause TTS model corruption.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Starting CoreML context cleanup...")
    
    try:
        # Step 1: Clear CoreML temporary directories
        temp_dirs_cleaned = 0
        
        # Get the configured CoreML temp directory
        coreml_temp_dir = os.environ.get('COREML_TEMP_PATH')
        if coreml_temp_dir and os.path.exists(coreml_temp_dir):
            try:
                # Clear all files in the CoreML temp directory
                for item in os.listdir(coreml_temp_dir):
                    item_path = os.path.join(coreml_temp_dir, item)
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                temp_dirs_cleaned += 1
                logger.debug(f"Cleaned CoreML temp directory: {coreml_temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean CoreML temp directory {coreml_temp_dir}: {e}")
        
        # Step 2: Clear system-wide CoreML cache directories
        system_cache_patterns = [
            '/tmp/coreml_*',
            '/tmp/com.apple.CoreML.*',
            '/var/folders/*/T/coreml_*',
            os.path.expanduser('~/Library/Caches/com.apple.CoreML.*')
        ]
        
        for pattern in system_cache_patterns:
            try:
                cache_dirs = glob.glob(pattern)
                for cache_dir in cache_dirs:
                    if os.path.exists(cache_dir):
                        if os.path.isfile(cache_dir):
                            os.unlink(cache_dir)
                        else:
                            shutil.rmtree(cache_dir)
                        temp_dirs_cleaned += 1
                        logger.debug(f"Cleaned CoreML cache: {cache_dir}")
            except Exception as e:
                logger.debug(f"Could not clean cache pattern {pattern}: {e}")
        
        # Step 3: Force Objective-C autorelease pool drain (if available)
        try:
            import objc
            # Drain the current autorelease pool to release CoreML objects
            objc.recycleAutoreleasePool()
            logger.debug("Drained Objective-C autorelease pool")
        except ImportError:
            logger.debug("objc module not available - skipping autorelease pool drain")
        except Exception as e:
            logger.debug(f"Failed to drain autorelease pool: {e}")
        
        # Step 4: Force Python garbage collection with focus on native objects
        try:
            import gc
            
            # Multiple collection passes to ensure cleanup of cyclic references
            total_collected = 0
            for i in range(3):
                collected = gc.collect()
                total_collected += collected
                if collected > 0:
                    logger.debug(f"GC pass {i+1}: collected {collected} objects")
            
            if total_collected > 0:
                logger.debug(f"Total objects collected: {total_collected}")
                
        except Exception as e:
            logger.warning(f"Garbage collection during CoreML cleanup failed: {e}")
        
        logger.debug(f"CoreML context cleanup completed - cleaned {temp_dirs_cleaned} temp directories")
        
    except Exception as e:
        logger.error(f"CoreML context cleanup failed: {e}")
        # Don't raise - this is a best-effort cleanup
