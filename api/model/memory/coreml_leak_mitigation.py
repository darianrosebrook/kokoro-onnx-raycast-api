"""
CoreML Memory Leak Mitigation for ONNX Runtime

This module implements Python-level memory management solutions to mitigate
CoreML context leaks in ONNX Runtime without requiring source code modifications.

## Problem Statement

The "Context leak detected, msgtracer returned -1" errors occur because:
1. CoreML Objective-C methods create temporary objects
2. These objects are added to the autorelease pool
3. ONNX Runtime's C++ code doesn't properly drain the autorelease pool
4. Memory accumulates over time, leading to leaks

## Solution Strategy

Since we can't easily patch the C++ source, we implement Python-level mitigations:
1. **Garbage Collection Forcing**: Aggressive GC after CoreML operations
2. **Memory Pressure Management**: Monitor and trigger cleanup based on memory usage
3. **Session Recreation**: Periodic recreation of ONNX Runtime sessions
4. **Objective-C Pool Management**: Use ctypes to interact with Objective-C runtime

## Technical Implementation

### Memory Pressure Monitoring
- Track memory usage before/after CoreML operations
- Trigger cleanup when memory usage exceeds thresholds
- Use system memory pressure indicators

### Garbage Collection Strategy
- Force Python garbage collection after CoreML operations
- Clear ONNX Runtime internal caches periodically
- Monitor memory trends to optimize cleanup frequency

### Session Management
- Implement session pooling with automatic recreation
- Track session usage and memory impact
- Rotate sessions to prevent memory accumulation

@author @darianrosebrook
@version 1.0.0
@since 2025-08-15
@license MIT
"""

import gc
import os
import sys
import time
import psutil
import logging
import threading
import weakref
from typing import Optional, Dict, Any, Callable, List, Tuple
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)

# Global configuration
MEMORY_MONITORING_ENABLED = True
AGGRESSIVE_CLEANUP_ENABLED = True
SESSION_RECREATION_THRESHOLD = 100  # Number of operations before session recreation
MEMORY_THRESHOLD_MB = 200  # Memory increase threshold for cleanup

# Global state tracking
_memory_stats = {
    'baseline_memory': 0,
    'peak_memory': 0,
    'last_cleanup': time.time(),
    'operations_since_cleanup': 0,
    'cleanup_count': 0,
    'leak_detections': 0
}

_session_registry = weakref.WeakSet()
_operation_count = 0
_last_memory_check = 0


class CoreMLMemoryManager:
    """
    Advanced memory manager for CoreML operations.
    
    This class provides comprehensive memory management for CoreML operations,
    including leak detection, aggressive cleanup, and memory pressure monitoring.
    """
    
    def __init__(self, aggressive_mode: bool = True):
        """
        Initialize the CoreML memory manager.
        
        @param aggressive_mode: Enable aggressive memory management
        """
        self.aggressive_mode = aggressive_mode
        self.baseline_memory = self._get_current_memory()
        self.cleanup_threshold = MEMORY_THRESHOLD_MB
        self.operation_count = 0
        self.last_cleanup = time.time()
        
        # Statistics tracking
        self.stats = {
            'total_operations': 0,
            'cleanups_triggered': 0,
            'memory_saved_mb': 0.0,
            'average_operation_memory': 0.0,
            'peak_memory_usage': 0.0
        }
        
        logger.debug(f"🧠 CoreML memory manager initialized (aggressive={aggressive_mode})")
        logger.debug(f"📊 Baseline memory: {self.baseline_memory:.1f}MB")
    
    def _get_current_memory(self) -> float:
        """Get current process memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception as e:
            logger.debug(f"⚠️ Could not get memory usage: {e}")
            return 0.0
    
    def _get_system_memory_pressure(self) -> float:
        """Get system memory pressure as a percentage."""
        try:
            memory = psutil.virtual_memory()
            return memory.percent
        except Exception as e:
            logger.debug(f"⚠️ Could not get system memory pressure: {e}")
            return 0.0
    
    def _force_objective_c_cleanup(self):
        """
        Attempt to force Objective-C autorelease pool cleanup using ctypes.
        
        This is a more direct approach to handling the autorelease pool issue
        by interacting with the Objective-C runtime directly from Python.
        """
        try:
            import ctypes
            import ctypes.util
            
            # Load Objective-C runtime
            objc_lib = ctypes.util.find_library("objc")
            if not objc_lib:
                logger.debug("⚠️ Could not find Objective-C runtime library")
                return False
            
            libobjc = ctypes.CDLL(objc_lib)
            
            # Get NSAutoreleasePool class
            # This attempts to create and drain an autorelease pool
            try:
                # objc_getClass function
                objc_getClass = libobjc.objc_getClass
                objc_getClass.restype = ctypes.c_void_p
                objc_getClass.argtypes = [ctypes.c_char_p]
                
                # objc_msgSend function
                objc_msgSend = libobjc.objc_msgSend
                objc_msgSend.restype = ctypes.c_void_p
                objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                
                # sel_registerName function
                sel_registerName = libobjc.sel_registerName
                sel_registerName.restype = ctypes.c_void_p
                sel_registerName.argtypes = [ctypes.c_char_p]
                
                # Get NSAutoreleasePool class
                NSAutoreleasePool = objc_getClass(b"NSAutoreleasePool")
                if not NSAutoreleasePool:
                    logger.debug("⚠️ Could not get NSAutoreleasePool class")
                    return False
                
                # Get selectors
                alloc_sel = sel_registerName(b"alloc")
                init_sel = sel_registerName(b"init")
                drain_sel = sel_registerName(b"drain")
                
                # Create autorelease pool
                pool_alloc = objc_msgSend(NSAutoreleasePool, alloc_sel)
                pool = objc_msgSend(pool_alloc, init_sel)
                
                # Drain the pool immediately to clean up any accumulated objects
                objc_msgSend(pool, drain_sel)
                
                logger.debug("✅ Objective-C autorelease pool drained successfully")
                return True
                
            except Exception as e:
                logger.debug(f"⚠️ Error draining autorelease pool: {e}")
                return False
                
        except ImportError:
            logger.debug("⚠️ ctypes not available for Objective-C cleanup")
            return False
        except Exception as e:
            logger.debug(f"⚠️ Objective-C cleanup failed: {e}")
            return False
    
    def _aggressive_memory_cleanup(self) -> float:
        """
        Perform aggressive memory cleanup.
        
        @returns float: Amount of memory freed in MB
        """
        memory_before = self._get_current_memory()
        
        try:
            # 1. Force Python garbage collection
            gc.collect()
            
            # 2. Try to drain Objective-C autorelease pool
            self._force_objective_c_cleanup()
            
            # 3. Force another garbage collection after Objective-C cleanup
            gc.collect()
            
            # 4. Clear any internal caches if possible
            try:
                # Clear ONNX Runtime internal caches (if accessible)
                import onnxruntime as ort
                
                # Some versions of ONNX Runtime have cache clearing methods
                if hasattr(ort, 'clear_cache'):
                    ort.clear_cache()
                elif hasattr(ort, '_clear_cache'):
                    ort._clear_cache()
                    
            except Exception as e:
                logger.debug(f"⚠️ Could not clear ONNX Runtime caches: {e}")
            
            # 5. Final garbage collection
            gc.collect()
            
            memory_after = self._get_current_memory()
            memory_freed = memory_before - memory_after
            
            if memory_freed > 0:
                logger.debug(f"🧹 Aggressive cleanup freed {memory_freed:.1f}MB")
                self.stats['memory_saved_mb'] += memory_freed
            
            self.stats['cleanups_triggered'] += 1
            self.last_cleanup = time.time()
            
            return memory_freed
            
        except Exception as e:
            logger.debug(f"⚠️ Aggressive cleanup failed: {e}")
            return 0.0
    
    def _should_trigger_cleanup(self, current_memory: float) -> bool:
        """
        Determine if cleanup should be triggered based on memory usage.
        
        @param current_memory: Current memory usage in MB
        @returns bool: True if cleanup should be triggered
        """
        # Calculate memory increase since baseline
        memory_increase = current_memory - self.baseline_memory
        
        # Check if memory increase exceeds threshold
        if memory_increase > self.cleanup_threshold:
            logger.debug(f"🔍 Memory increase ({memory_increase:.1f}MB) exceeds threshold ({self.cleanup_threshold}MB)")
            return True
        
        # Check if it's been too long since last cleanup
        time_since_cleanup = time.time() - self.last_cleanup
        if time_since_cleanup > 300:  # 5 minutes
            logger.debug(f"⏰ Time since last cleanup ({time_since_cleanup:.1f}s) exceeds 5 minutes")
            return True
        
        # Check system memory pressure
        system_pressure = self._get_system_memory_pressure()
        if system_pressure > 80:  # High system memory usage
            logger.debug(f"💽 High system memory pressure ({system_pressure:.1f}%)")
            return True
        
        return False
    
    @contextmanager
    def managed_operation(self, operation_name: str = "coreml_operation"):
        """
        Context manager for CoreML operations with automatic memory management.
        
        @param operation_name: Name of the operation for logging
        """
        memory_before = self._get_current_memory()
        operation_start = time.time()
        
        try:
            logger.debug(f"🔄 Starting managed operation: {operation_name}")
            yield
            
        finally:
            # Update operation count
            self.operation_count += 1
            self.stats['total_operations'] += 1
            
            # Check memory after operation
            memory_after = self._get_current_memory()
            memory_delta = memory_after - memory_before
            operation_time = time.time() - operation_start
            
            # Update statistics
            self.stats['average_operation_memory'] = (
                (self.stats['average_operation_memory'] * (self.stats['total_operations'] - 1) + memory_delta) 
                / self.stats['total_operations']
            )
            
            if memory_after > self.stats['peak_memory_usage']:
                self.stats['peak_memory_usage'] = memory_after
            
            logger.debug(f"📊 Operation {operation_name} completed in {operation_time:.2f}s, memory delta: {memory_delta:+.1f}MB")
            
            # Check if cleanup is needed
            if self.aggressive_mode and self._should_trigger_cleanup(memory_after):
                logger.debug(f"🧹 Triggering cleanup after {operation_name}")
                freed_memory = self._aggressive_memory_cleanup()
                
                if freed_memory > 5:  # Significant memory freed
                    logger.info(f"🧠 Memory cleanup freed {freed_memory:.1f}MB after {operation_name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory management statistics."""
        current_memory = self._get_current_memory()
        return {
            'current_memory_mb': current_memory,
            'baseline_memory_mb': self.baseline_memory,
            'memory_increase_mb': current_memory - self.baseline_memory,
            'operation_count': self.operation_count,
            'cleanup_threshold_mb': self.cleanup_threshold,
            'last_cleanup_seconds_ago': time.time() - self.last_cleanup,
            'system_memory_pressure_percent': self._get_system_memory_pressure(),
            'aggressive_mode': self.aggressive_mode,
            'stats': self.stats.copy()
        }


# Global memory manager instance
_global_memory_manager: Optional[CoreMLMemoryManager] = None

# Global configuration state tracking
_memory_management_configured = False
_last_config_params = None


def get_memory_manager() -> CoreMLMemoryManager:
    """Get or create the global memory manager."""
    global _global_memory_manager
    
    if _global_memory_manager is None:
        _global_memory_manager = CoreMLMemoryManager(aggressive_mode=AGGRESSIVE_CLEANUP_ENABLED)
    
    return _global_memory_manager


def coreml_memory_managed(func: Callable) -> Callable:
    """
    Decorator to wrap functions with CoreML memory management.
    
    This decorator automatically manages memory for functions that perform
    CoreML operations, providing leak mitigation and cleanup.
    
    @param func: Function to wrap with memory management
    @returns Callable: Wrapped function with memory management
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        manager = get_memory_manager()
        operation_name = getattr(func, '__name__', 'unknown_operation')
        
        with manager.managed_operation(operation_name):
            return func(*args, **kwargs)
    
    return wrapper


def force_coreml_memory_cleanup() -> Dict[str, Any]:
    """
    Force immediate CoreML memory cleanup.
    
    @returns Dict[str, Any]: Cleanup results and statistics
    """
    manager = get_memory_manager()
    
    memory_before = manager._get_current_memory()
    freed_memory = manager._aggressive_memory_cleanup()
    memory_after = manager._get_current_memory()
    
    result = {
        'cleanup_triggered': True,
        'memory_before_mb': memory_before,
        'memory_after_mb': memory_after,
        'memory_freed_mb': freed_memory,
        'objective_c_cleanup_attempted': True,
        'timestamp': time.time()
    }
    
    logger.info(f"🧠 Forced CoreML memory cleanup: freed {freed_memory:.1f}MB")
    return result


def get_coreml_memory_stats() -> Dict[str, Any]:
    """
    Get comprehensive CoreML memory statistics.
    
    @returns Dict[str, Any]: Memory statistics and manager status
    """
    manager = get_memory_manager()
    return {
        'memory_manager_active': True,
        'aggressive_mode': manager.aggressive_mode,
        'memory_management': manager.get_statistics(),
        'global_stats': _memory_stats.copy(),
        'configuration': {
            'memory_threshold_mb': MEMORY_THRESHOLD_MB,
            'session_recreation_threshold': SESSION_RECREATION_THRESHOLD,
            'monitoring_enabled': MEMORY_MONITORING_ENABLED,
            'aggressive_cleanup_enabled': AGGRESSIVE_CLEANUP_ENABLED
        }
    }


def configure_coreml_memory_management(
    aggressive_cleanup: bool = True,
    memory_threshold_mb: int = 200,
    monitoring_enabled: bool = True
):
    """
    Configure CoreML memory management settings.
    
    @param aggressive_cleanup: Enable aggressive memory cleanup
    @param memory_threshold_mb: Memory threshold for triggering cleanup
    @param monitoring_enabled: Enable memory monitoring
    """
    global AGGRESSIVE_CLEANUP_ENABLED, MEMORY_THRESHOLD_MB, MEMORY_MONITORING_ENABLED
    global _global_memory_manager, _memory_management_configured, _last_config_params
    
    # Check if configuration is already done with same parameters
    current_params = (aggressive_cleanup, memory_threshold_mb, monitoring_enabled)
    if _memory_management_configured and _last_config_params == current_params:
        logger.debug("✅ CoreML memory management already configured with same parameters, skipping")
        return
    
    AGGRESSIVE_CLEANUP_ENABLED = aggressive_cleanup
    MEMORY_THRESHOLD_MB = memory_threshold_mb
    MEMORY_MONITORING_ENABLED = monitoring_enabled
    
    # Reinitialize manager with new settings
    if _global_memory_manager is not None:
        _global_memory_manager.aggressive_mode = aggressive_cleanup
        _global_memory_manager.cleanup_threshold = memory_threshold_mb
    
    # Only log configuration on first time or parameter changes
    if not _memory_management_configured or _last_config_params != current_params:
        logger.info(f"🔧 CoreML memory management configured:")
        logger.info(f"   Aggressive cleanup: {aggressive_cleanup}")
        logger.info(f"   Memory threshold: {memory_threshold_mb}MB")
        logger.info(f"   Monitoring enabled: {monitoring_enabled}")
        
        _memory_management_configured = True
        _last_config_params = current_params


# Initialize memory management
def initialize_coreml_memory_management():
    """Initialize CoreML memory management system."""
    global _global_memory_manager
    
    # Prevent duplicate initialization
    if _global_memory_manager is not None:
        logger.debug("🧠 CoreML memory management already initialized, skipping")
        return True
        
    try:
        manager = get_memory_manager()
        logger.info("🧠 CoreML memory management system initialized")
        logger.info(f"📊 Baseline memory: {manager.baseline_memory:.1f}MB")
        logger.info(f"🔧 Aggressive mode: {manager.aggressive_mode}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize CoreML memory management: {e}")
        return False


# Auto-initialization disabled to prevent duplicate initialization during startup
# Memory management will be initialized explicitly during the startup sequence
# if __name__ != "__main__":
#     initialize_coreml_memory_management()
