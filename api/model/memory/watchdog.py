"""
Memory fragmentation monitoring and cleanup.

This module provides monitoring and management of memory fragmentation
in long-running TTS systems to maintain optimal performance.
"""

import time
import logging
import gc
from typing import Dict, Any, Optional


class MemoryFragmentationWatchdog:
    """
    Monitors and manages memory fragmentation in long-running systems.
    
    This watchdog detects memory fragmentation patterns and triggers
    cleanup operations to maintain optimal performance over extended
    periods of operation.
    """
    
    def __init__(self):
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 3600.0  # 1 hour default
        self.memory_pressure_threshold = 0.85  # 85% memory usage
        self.fragmentation_threshold = 0.7  # 70% fragmentation
        self.consecutive_pressure_checks = 0
        self.pressure_check_threshold = 3  # Trigger cleanup after 3 consecutive high pressure readings
        
        self.logger = logging.getLogger(__name__ + ".MemoryFragmentationWatchdog")
        
        # Cleanup statistics
        self.cleanup_count = 0
        self.total_memory_freed_mb = 0.0
        self.last_cleanup_duration = 0.0
    
    def check_memory_pressure(self) -> Dict[str, Any]:
        """
        Check current system memory pressure and fragmentation.
        
        @returns Dict[str, Any]: Memory pressure information
        """
        pressure_info = {
            'memory_percent': 0.0,
            'available_gb': 0.0,
            'fragmentation_percent': 0.0,
            'pressure_level': 'unknown',
            'requires_cleanup': False
        }
        
        try:
            import psutil
            
            # Get system memory information
            memory = psutil.virtual_memory()
            pressure_info.update({
                'memory_percent': memory.percent,
                'available_gb': memory.available / (1024**3),
                'total_gb': memory.total / (1024**3),
                'used_gb': memory.used / (1024**3)
            })
            
            # Calculate pressure level
            if memory.percent > 90:
                pressure_info['pressure_level'] = 'critical'
            elif memory.percent > self.memory_pressure_threshold * 100:
                pressure_info['pressure_level'] = 'high'
            elif memory.percent > 70:
                pressure_info['pressure_level'] = 'moderate'
            else:
                pressure_info['pressure_level'] = 'low'
            
            # Estimate fragmentation (simplified heuristic)
            # Real fragmentation measurement would require OS-specific APIs
            fragmentation_estimate = min(100.0, memory.percent * 0.8)  # Rough estimate
            pressure_info['fragmentation_percent'] = fragmentation_estimate
            
            # Determine if cleanup is required
            high_pressure = memory.percent > self.memory_pressure_threshold * 100
            high_fragmentation = fragmentation_estimate > self.fragmentation_threshold * 100
            
            if high_pressure:
                self.consecutive_pressure_checks += 1
            else:
                self.consecutive_pressure_checks = 0
            
            pressure_info['requires_cleanup'] = (
                high_pressure or 
                high_fragmentation or 
                self.consecutive_pressure_checks >= self.pressure_check_threshold
            )
            
        except ImportError:
            self.logger.debug("psutil not available for memory pressure detection")
            pressure_info['pressure_level'] = 'unknown'
        except Exception as e:
            self.logger.debug(f"Could not check memory pressure: {e}")
            pressure_info['pressure_level'] = 'error'
            pressure_info['error'] = str(e)
        
        return pressure_info
    
    def should_cleanup(self) -> bool:
        """
        Determine if memory cleanup should be performed.
        
        @returns bool: True if cleanup should be performed
        """
        # Check time-based cleanup
        time_since_cleanup = time.time() - self.last_cleanup_time
        time_based_cleanup = time_since_cleanup > self.cleanup_interval
        
        # Check pressure-based cleanup
        pressure_info = self.check_memory_pressure()
        pressure_based_cleanup = pressure_info.get('requires_cleanup', False)
        
        should_cleanup = time_based_cleanup or pressure_based_cleanup
        
        if should_cleanup:
            self.logger.debug(
                f"Cleanup triggered: time_based={time_based_cleanup}, "
                f"pressure_based={pressure_based_cleanup}, "
                f"time_since_last={time_since_cleanup:.1f}s"
            )
        
        return should_cleanup
    
    def cleanup_if_needed(self) -> Dict[str, Any]:
        """
        Perform memory cleanup if needed.
        
        @returns Dict[str, Any]: Cleanup results and statistics
        """
        if not self.should_cleanup():
            return {'cleanup_performed': False, 'reason': 'not_needed'}
        
        return self.force_cleanup()
    
    def force_cleanup(self) -> Dict[str, Any]:
        """
        Force immediate memory cleanup regardless of conditions.
        
        @returns Dict[str, Any]: Cleanup results and statistics
        """
        cleanup_start = time.time()
        memory_before = self._get_memory_usage()
        
        self.logger.info(" Performing memory fragmentation cleanup...")
        
        cleanup_results = {
            'cleanup_performed': True,
            'start_time': cleanup_start,
            'memory_before_mb': memory_before,
            'actions_taken': [],
            'errors': []
        }
        
        try:
            # 1. Clean up dual session manager if available - DISABLED to prevent audio gaps
            # This was causing 8+ second delays during automatic memory cleanup
            # try:
            #     from api.model.sessions import get_dual_session_manager
            #     dual_session_manager = get_dual_session_manager()
            #     if dual_session_manager:
            #         dual_session_manager.cleanup_sessions()
            #         cleanup_results['actions_taken'].append('dual_session_cleanup')
            # except Exception as e:
            #     cleanup_results['errors'].append(f'dual_session_cleanup: {e}')
            
            # 2. Clean up dynamic memory manager if available
            try:
                from .dynamic_manager import get_dynamic_memory_manager
                dynamic_memory_manager = get_dynamic_memory_manager()
                if dynamic_memory_manager:
                    # Reset performance history to free memory
                    dynamic_memory_manager.reset_performance_history()
                    cleanup_results['actions_taken'].append('memory_manager_cleanup')
            except Exception as e:
                cleanup_results['errors'].append(f'memory_manager_cleanup: {e}')
            
            # 3. Clear provider caches
            try:
                from api.model.providers import clear_provider_cache
                clear_provider_cache()
                cleanup_results['actions_taken'].append('provider_cache_cleanup')
            except Exception as e:
                cleanup_results['errors'].append(f'provider_cache_cleanup: {e}')
            
            # 4. Clear hardware capabilities cache
            try:
                from api.model.hardware import clear_capabilities_cache
                clear_capabilities_cache()
                cleanup_results['actions_taken'].append('capabilities_cache_cleanup')
            except Exception as e:
                cleanup_results['errors'].append(f'capabilities_cache_cleanup: {e}')
            
            # 5. Force garbage collection
            try:
                gc.collect()
                cleanup_results['actions_taken'].append('garbage_collection')
            except Exception as e:
                cleanup_results['errors'].append(f'garbage_collection: {e}')
            
            # 6. Cleanup temporary files
            try:
                from api.model.providers.coreml import cleanup_coreml_temp_directory
                cleanup_coreml_temp_directory()
                cleanup_results['actions_taken'].append('temp_file_cleanup')
            except Exception as e:
                cleanup_results['errors'].append(f'temp_file_cleanup: {e}')
            
        except Exception as e:
            self.logger.error(f"Cleanup process failed: {e}")
            cleanup_results['errors'].append(f'cleanup_process: {e}')
        
        # Calculate cleanup results
        cleanup_end = time.time()
        memory_after = self._get_memory_usage()
        
        self.last_cleanup_time = cleanup_end
        self.last_cleanup_duration = cleanup_end - cleanup_start
        self.cleanup_count += 1
        
        memory_freed = max(0, memory_before - memory_after)
        self.total_memory_freed_mb += memory_freed
        
        cleanup_results.update({
            'end_time': cleanup_end,
            'duration_seconds': self.last_cleanup_duration,
            'memory_after_mb': memory_after,
            'memory_freed_mb': memory_freed,
            'cleanup_count': self.cleanup_count,
            'total_memory_freed_mb': self.total_memory_freed_mb
        })
        
        self.logger.info(
            f"✅ Memory cleanup completed in {self.last_cleanup_duration:.2f}s, "
            f"freed {memory_freed:.1f}MB memory"
        )
        
        return cleanup_results
    
    def _get_memory_usage(self) -> float:
        """
        Get current memory usage in MB.
        
        @returns float: Memory usage in MB
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)  # Convert to MB
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cleanup statistics and current status.
        
        @returns Dict[str, Any]: Watchdog statistics
        """
        current_time = time.time()
        time_since_last = current_time - self.last_cleanup_time
        
        pressure_info = self.check_memory_pressure()
        
        return {
            'cleanup_statistics': {
                'total_cleanups': self.cleanup_count,
                'total_memory_freed_mb': self.total_memory_freed_mb,
                'last_cleanup_duration': self.last_cleanup_duration,
                'time_since_last_cleanup': time_since_last,
                'avg_memory_freed_per_cleanup': (
                    self.total_memory_freed_mb / max(self.cleanup_count, 1)
                )
            },
            'current_status': {
                'next_scheduled_cleanup': self.cleanup_interval - time_since_last,
                'cleanup_interval': self.cleanup_interval,
                'memory_pressure_threshold': self.memory_pressure_threshold,
                'fragmentation_threshold': self.fragmentation_threshold,
                'consecutive_pressure_checks': self.consecutive_pressure_checks
            },
            'memory_pressure': pressure_info
        }
    
    def configure(self, cleanup_interval: Optional[float] = None,
                 memory_pressure_threshold: Optional[float] = None,
                 fragmentation_threshold: Optional[float] = None):
        """
        Configure watchdog parameters.
        
        @param cleanup_interval: Time between automatic cleanups (seconds)
        @param memory_pressure_threshold: Memory usage threshold (0.0-1.0)
        @param fragmentation_threshold: Fragmentation threshold (0.0-1.0)
        """
        if cleanup_interval is not None:
            self.cleanup_interval = max(60.0, cleanup_interval)  # Minimum 1 minute
            
        if memory_pressure_threshold is not None:
            self.memory_pressure_threshold = max(0.5, min(0.95, memory_pressure_threshold))
            
        if fragmentation_threshold is not None:
            self.fragmentation_threshold = max(0.3, min(0.9, fragmentation_threshold))
        
        self.logger.info(
            f" Watchdog configured: interval={self.cleanup_interval}s, "
            f"memory_threshold={self.memory_pressure_threshold:.1%}, "
            f"fragmentation_threshold={self.fragmentation_threshold:.1%}"
        )
    
    def reset_statistics(self):
        """Reset all cleanup statistics."""
        self.cleanup_count = 0
        self.total_memory_freed_mb = 0.0
        self.last_cleanup_duration = 0.0
        self.consecutive_pressure_checks = 0
        
        self.logger.info(" Watchdog statistics reset")
