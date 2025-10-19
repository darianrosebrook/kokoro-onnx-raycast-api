"""
Memory fragmentation monitoring and cleanup.

This module provides monitoring and management of memory fragmentation
in long-running TTS systems to maintain optimal performance.
"""

import time
import logging
import gc
import os
from typing import Dict, Any, List, Optional


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

        # Fragmentation tracking
        self.fragmentation_history: List[Dict[str, Any]] = []
        self.max_history_size = 100  # Keep last 100 measurements
    
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
            
            # Implement proper memory fragmentation measurement
            fragmentation_info = self._measure_memory_fragmentation()
            pressure_info['fragmentation_percent'] = fragmentation_info['fragmentation_percent']
            pressure_info['fragmentation_details'] = fragmentation_info
            
            # Determine if cleanup is required
            high_pressure = memory.percent > self.memory_pressure_threshold * 100
            high_fragmentation = fragmentation_info['fragmentation_percent'] > self.fragmentation_threshold * 100
            
            if high_pressure:
                self.consecutive_pressure_checks += 1
            else:
                self.consecutive_pressure_checks = 0
            
            pressure_info['requires_cleanup'] = (
                high_pressure or
                high_fragmentation or
                self.consecutive_pressure_checks >= self.pressure_check_threshold
            )

            # Record fragmentation measurement for trend analysis
            self._record_fragmentation_measurement(fragmentation_info)
            
        except ImportError:
            self.logger.debug("psutil not available for memory pressure detection")
            pressure_info['pressure_level'] = 'unknown'
        except Exception as e:
            self.logger.debug(f"Could not check memory pressure: {e}")
            pressure_info['pressure_level'] = 'error'
            pressure_info['error'] = str(e)
        
        return pressure_info

    def _measure_memory_fragmentation(self) -> Dict[str, Any]:
        """
        Measure actual memory fragmentation using OS-specific APIs.

        This implements proper fragmentation measurement for macOS using:
        - malloc_zone_statistics for heap fragmentation
        - vm_statistics for virtual memory fragmentation
        - Process memory map analysis

        @returns Dict[str, Any]: Fragmentation measurement results
        """
        fragmentation_info = {
            'fragmentation_percent': 0.0,
            'heap_fragmentation': 0.0,
            'vm_fragmentation': 0.0,
            'memory_efficiency': 100.0,
            'measurement_method': 'estimate',
            'details': {}
        }

        try:
            import platform
            system = platform.system()

            if system == 'Darwin':  # macOS
                fragmentation_info.update(self._measure_macos_fragmentation())
            elif system == 'Linux':
                fragmentation_info.update(self._measure_linux_fragmentation())
            elif system == 'Windows':
                fragmentation_info.update(self._measure_windows_fragmentation())
            else:
                # Fallback to process-based estimation
                fragmentation_info.update(self._measure_process_fragmentation())

        except Exception as e:
            self.logger.debug(f"Could not measure memory fragmentation: {e}")
            # Fallback to basic estimation
            try:
                import psutil
                memory = psutil.virtual_memory()
                fragmentation_info['fragmentation_percent'] = min(100.0, memory.percent * 0.8)
                fragmentation_info['measurement_method'] = 'fallback_estimate'
            except Exception:
                fragmentation_info['fragmentation_percent'] = 0.0
                fragmentation_info['measurement_method'] = 'unavailable'

        return fragmentation_info

    def _measure_macos_fragmentation(self) -> Dict[str, Any]:
        """
        Measure memory fragmentation on macOS using system APIs.
        """
        result = {
            'fragmentation_percent': 0.0,
            'heap_fragmentation': 0.0,
            'vm_fragmentation': 0.0,
            'memory_efficiency': 100.0,
            'measurement_method': 'macos_apis',
            'details': {}
        }

        try:
            # Method 1: Use vm_statistics for virtual memory fragmentation
            vm_stats = self._get_macos_vm_statistics()
            if vm_stats:
                # Calculate VM fragmentation based on free vs wired pages
                total_pages = vm_stats.get('free_count', 0) + vm_stats.get('active_count', 0) + vm_stats.get('inactive_count', 0) + vm_stats.get('wired_count', 0)
                if total_pages > 0:
                    # VM fragmentation is related to how scattered free memory is
                    free_ratio = vm_stats.get('free_count', 0) / total_pages
                    wired_ratio = vm_stats.get('wired_count', 0) / total_pages
                    vm_fragmentation = min(100.0, (1.0 - free_ratio) * 50.0 + wired_ratio * 30.0)
                    result['vm_fragmentation'] = vm_fragmentation
                    result['details']['vm_stats'] = vm_stats

            # Method 2: Use malloc_zone_statistics for heap fragmentation
            heap_stats = self._get_macos_heap_statistics()
            if heap_stats:
                # Calculate heap fragmentation based on allocated vs used
                allocated_mb = heap_stats.get('allocated_mb', 0)
                used_mb = heap_stats.get('used_mb', 0)
                if allocated_mb > 0:
                    heap_efficiency = (used_mb / allocated_mb) * 100.0
                    heap_fragmentation = 100.0 - heap_efficiency
                    result['heap_fragmentation'] = heap_fragmentation
                    result['details']['heap_stats'] = heap_stats

            # Method 3: Process memory map analysis
            process_stats = self._analyze_process_memory_map()
            if process_stats:
                # Calculate memory efficiency based on resident vs virtual size
                rss_mb = process_stats.get('rss_mb', 0)
                vms_mb = process_stats.get('vms_mb', 0)
                if vms_mb > 0:
                    memory_efficiency = (rss_mb / vms_mb) * 100.0
                    result['memory_efficiency'] = memory_efficiency
                    result['details']['process_stats'] = process_stats

            # Combine measurements with weights
            heap_weight = 0.4
            vm_weight = 0.3
            efficiency_weight = 0.3

            combined_fragmentation = (
                result['heap_fragmentation'] * heap_weight +
                result['vm_fragmentation'] * vm_weight +
                (100.0 - result['memory_efficiency']) * efficiency_weight
            )

            result['fragmentation_percent'] = min(100.0, max(0.0, combined_fragmentation))

        except Exception as e:
            self.logger.debug(f"macOS fragmentation measurement failed: {e}")
            result['measurement_method'] = 'macos_failed'

        return result

    def _get_macos_vm_statistics(self) -> Optional[Dict[str, int]]:
        """
        Get macOS virtual memory statistics using sysctl.
        """
        try:
            import subprocess
            # Get VM statistics
            result = subprocess.run([
                'sysctl', '-n',
                'vm.page_free_count',
                'vm.page_active_count',
                'vm.page_inactive_count',
                'vm.page_wired_count'
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 4:
                    return {
                        'free_count': int(lines[0]),
                        'active_count': int(lines[1]),
                        'inactive_count': int(lines[2]),
                        'wired_count': int(lines[3])
                    }
        except Exception as e:
            self.logger.debug(f"Could not get macOS VM statistics: {e}")

        return None

    def _get_macos_heap_statistics(self) -> Optional[Dict[str, float]]:
        """
        Get macOS heap statistics using malloc_zone_statistics.
        This is a simplified version - full implementation would use C extensions.
        """
        try:
            import subprocess
            # Use vmmap to get process memory map information
            result = subprocess.run([
                'vmmap', '--summary', str(os.getpid())
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse vmmap output for heap information
                lines = result.stdout.split('\n')
                heap_info = {}

                for line in lines:
                    if 'MALLOC' in line and 'HEAP' in line:
                        # Extract size information from MALLOC HEAP lines
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.endswith('M)'):
                                try:
                                    size_str = part.rstrip('M)')
                                    size_mb = float(size_str)
                                    heap_info['allocated_mb'] = size_mb
                                except ValueError:
                                    pass

                # Estimate used memory from RSS
                try:
                    import psutil
                    process = psutil.Process()
                    rss_bytes = process.memory_info().rss
                    heap_info['used_mb'] = rss_bytes / (1024 * 1024)
                except Exception:
                    heap_info['used_mb'] = heap_info.get('allocated_mb', 0) * 0.8  # Estimate

                return heap_info

        except Exception as e:
            self.logger.debug(f"Could not get macOS heap statistics: {e}")

        return None

    def _analyze_process_memory_map(self) -> Optional[Dict[str, float]]:
        """
        Analyze process memory map for fragmentation patterns.
        """
        try:
            import psutil
            process = psutil.Process()

            # Get memory info
            mem_info = process.memory_info()
            mem_maps = process.memory_maps(grouped=False)

            # Calculate basic metrics
            rss_mb = mem_info.rss / (1024 * 1024)
            vms_mb = mem_info.vms / (1024 * 1024)

            # Analyze memory map for fragmentation
            total_regions = len(mem_maps)
            anonymous_regions = sum(1 for m in mem_maps if 'anon' in m.path.lower() or m.path == '')
            mapped_regions = total_regions - anonymous_regions

            # Fragmentation estimate based on region count vs size
            avg_region_size_mb = vms_mb / max(total_regions, 1)
            fragmentation_score = min(100.0, total_regions / 10.0)  # Rough heuristic

            return {
                'rss_mb': rss_mb,
                'vms_mb': vms_mb,
                'total_regions': total_regions,
                'anonymous_regions': anonymous_regions,
                'mapped_regions': mapped_regions,
                'avg_region_size_mb': avg_region_size_mb,
                'map_fragmentation_score': fragmentation_score
            }

        except Exception as e:
            self.logger.debug(f"Could not analyze process memory map: {e}")

        return None

    def _measure_linux_fragmentation(self) -> Dict[str, Any]:
        """
        Measure memory fragmentation on Linux using /proc information.
        """
        # Placeholder for Linux-specific implementation
        return {
            'fragmentation_percent': 0.0,
            'measurement_method': 'linux_not_implemented',
            'details': {}
        }

    def _measure_windows_fragmentation(self) -> Dict[str, Any]:
        """
        Measure memory fragmentation on Windows using VirtualAlloc information.
        """
        # Placeholder for Windows-specific implementation
        return {
            'fragmentation_percent': 0.0,
            'measurement_method': 'windows_not_implemented',
            'details': {}
        }

    def _measure_process_fragmentation(self) -> Dict[str, Any]:
        """
        Fallback fragmentation measurement using process information.
        """
        try:
            import psutil
            process = psutil.Process()

            # Get basic memory info
            mem_info = process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            vms_mb = mem_info.vms / (1024 * 1024)

            # Estimate fragmentation based on RSS vs VMS ratio
            if vms_mb > 0:
                efficiency = (rss_mb / vms_mb) * 100.0
                fragmentation = 100.0 - efficiency
            else:
                fragmentation = 0.0

            return {
                'fragmentation_percent': min(100.0, fragmentation),
                'memory_efficiency': max(0.0, 100.0 - fragmentation),
                'measurement_method': 'process_fallback',
                'details': {
                    'rss_mb': rss_mb,
                    'vms_mb': vms_mb,
                    'efficiency_ratio': rss_mb / max(vms_mb, 1)
                }
            }

        except Exception as e:
            return {
                'fragmentation_percent': 0.0,
                'measurement_method': 'process_failed',
                'details': {}
            }

    def _record_fragmentation_measurement(self, fragmentation_info: Dict[str, Any]) -> None:
        """
        Record fragmentation measurement for trend analysis.
        """
        measurement = {
            'timestamp': time.time(),
            'fragmentation_percent': fragmentation_info.get('fragmentation_percent', 0.0),
            'heap_fragmentation': fragmentation_info.get('heap_fragmentation', 0.0),
            'vm_fragmentation': fragmentation_info.get('vm_fragmentation', 0.0),
            'memory_efficiency': fragmentation_info.get('memory_efficiency', 100.0),
            'measurement_method': fragmentation_info.get('measurement_method', 'unknown')
        }

        self.fragmentation_history.append(measurement)

        # Maintain history size limit
        if len(self.fragmentation_history) > self.max_history_size:
            self.fragmentation_history.pop(0)

    def analyze_fragmentation_trends(self) -> Dict[str, Any]:
        """
        Analyze fragmentation trends over time.

        @returns Dict[str, Any]: Trend analysis results
        """
        if len(self.fragmentation_history) < 3:
            return {
                'trend_available': False,
                'reason': 'insufficient_data',
                'min_measurements_needed': 3
            }

        # Extract time series data
        timestamps = [m['timestamp'] for m in self.fragmentation_history]
        fragmentation_values = [m['fragmentation_percent'] for m in self.fragmentation_history]
        efficiency_values = [m['memory_efficiency'] for m in self.fragmentation_history]

        # Calculate trends using linear regression
        fragmentation_trend = self._calculate_trend(timestamps, fragmentation_values)
        efficiency_trend = self._calculate_trend(timestamps, efficiency_values)

        # Calculate volatility (standard deviation of changes)
        fragmentation_volatility = self._calculate_volatility(fragmentation_values)
        efficiency_volatility = self._calculate_volatility(efficiency_values)

        # Determine trend direction and severity
        current_fragmentation = fragmentation_values[-1]
        avg_fragmentation = sum(fragmentation_values) / len(fragmentation_values)

        trend_direction = 'stable'
        severity = 'low'

        if abs(fragmentation_trend['slope']) > 0.1:  # Significant trend per minute
            trend_direction = 'increasing' if fragmentation_trend['slope'] > 0 else 'decreasing'

            # Determine severity based on current level and trend
            if current_fragmentation > 70 and trend_direction == 'increasing':
                severity = 'high'
            elif current_fragmentation > 50 and trend_direction == 'increasing':
                severity = 'medium'
            elif trend_direction == 'decreasing' and current_fragmentation < 30:
                severity = 'improving'

        return {
            'trend_available': True,
            'trend_direction': trend_direction,
            'severity': severity,
            'current_fragmentation': current_fragmentation,
            'average_fragmentation': avg_fragmentation,
            'fragmentation_trend': fragmentation_trend,
            'efficiency_trend': efficiency_trend,
            'fragmentation_volatility': fragmentation_volatility,
            'efficiency_volatility': efficiency_volatility,
            'measurements_count': len(self.fragmentation_history),
            'time_span_hours': (timestamps[-1] - timestamps[0]) / 3600 if timestamps else 0
        }

    def _calculate_trend(self, x_values: List[float], y_values: List[float]) -> Dict[str, Any]:
        """
        Calculate linear trend using simple linear regression.
        """
        if len(x_values) < 2:
            return {'slope': 0.0, 'intercept': 0.0, 'r_squared': 0.0}

        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_xx = sum(x * x for x in x_values)
        sum_yy = sum(y * y for y in y_values)

        # Calculate slope and intercept
        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return {'slope': 0.0, 'intercept': 0.0, 'r_squared': 0.0}

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Calculate R-squared
        y_mean = sum_y / n
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

        return {
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_squared
        }

    def _calculate_volatility(self, values: List[float]) -> float:
        """
        Calculate volatility (standard deviation of consecutive differences).
        """
        if len(values) < 2:
            return 0.0

        differences = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
        if not differences:
            return 0.0

        mean_diff = sum(differences) / len(differences)
        variance = sum((d - mean_diff) ** 2 for d in differences) / len(differences)

        return variance ** 0.5  # Standard deviation

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
        trend_analysis = self.analyze_fragmentation_trends()

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
            'memory_pressure': pressure_info,
            'fragmentation_analysis': trend_analysis,
            'fragmentation_history_size': len(self.fragmentation_history)
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
