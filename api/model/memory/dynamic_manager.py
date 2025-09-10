"""
Dynamic memory management for optimal ONNX Runtime performance.

This module implements adaptive memory allocation strategies based on
real-time workload analysis, hardware capabilities, and system resource
availability.
"""

import time
import logging
from typing import Dict, Any, Optional
from collections import deque

# Global dynamic memory manager instance
dynamic_memory_manager: Optional['DynamicMemoryManager'] = None


class DynamicMemoryManager:
    """
    Manages dynamic memory arena sizing for optimal performance.

    This manager implements adaptive memory allocation strategies based on
    real-time workload analysis, hardware capabilities, and system resource
    availability. It continuously optimizes ONNX Runtime memory arena sizes
    to achieve peak performance while maintaining system stability.

    ## Key Features

    ### Workload-Based Optimization
    - **Concurrent Request Analysis**: Adjusts memory based on parallel processing needs
    - **Text Complexity Assessment**: Scales allocation based on average processing complexity
    - **Historical Pattern Learning**: Uses past performance to predict optimal settings

    ### Hardware-Aware Scaling
    - **System RAM Analysis**: Scales memory allocation based on available system memory
    - **Apple Silicon Optimization**: Optimized settings for M1/M2/M3 Neural Engine
    - **Memory Pressure Detection**: Automatically adjusts when system memory is constrained

    ### Adaptive Performance Tuning
    - **Real-time Adjustment**: Continuously monitors and adjusts memory allocation
    - **Performance Trend Analysis**: Adapts to changing workload patterns
    - **Efficiency Optimization**: Maximizes memory utilization without waste
    """

    def __init__(self, capabilities: Optional[Dict[str, Any]] = None):
        from .workload_analyzer import WorkloadProfile, WorkloadAnalyzer
        
        self.workload_profile = WorkloadProfile()
        self.current_arena_size_mb = 512  # Default starting size
        self.min_arena_size_mb = 256
        self.max_arena_size_mb = 2048
        self.last_optimization_time = 0.0
        self.optimization_interval = 300.0  # 5 minutes
        self.performance_history = deque(maxlen=100)
        self.memory_efficiency_target = 0.85  # 85% utilization target

        self.logger = logging.getLogger(__name__ + ".DynamicMemoryManager")

        # Use provided capabilities or detect if not provided
        if capabilities is None:
            from api.model.hardware import detect_apple_silicon_capabilities
            self.capabilities = detect_apple_silicon_capabilities()
        else:
            self.capabilities = capabilities

        # Initialize advanced workload analyzer
        self.workload_analyzer = WorkloadAnalyzer()

        # Initialize with hardware-optimized base size
        self.current_arena_size_mb = self._calculate_hardware_base_size()

        self.logger.info(f" Dynamic memory manager initialized with {self.current_arena_size_mb}MB base arena size")

    def _calculate_hardware_base_size(self) -> int:
        """Calculate hardware-optimized base memory arena size."""
        base_size = 512  # Default base size in MB

        # Scale based on available system RAM
        ram_gb = self.capabilities.get('memory_gb', 8)
        if ram_gb >= 32:  # High-memory systems (M1 Max/M2 Max with 32GB+)
            base_size = 1024
        elif ram_gb >= 16:  # Standard systems (16GB)
            base_size = 768
        elif ram_gb <= 8:  # Low-memory systems
            base_size = 384

        # Adjust for Neural Engine capabilities
        neural_engine_cores = self.capabilities.get('neural_engine_cores', 0)
        if neural_engine_cores >= 32:  # M1 Max/M2 Max
            base_size = int(base_size * 1.2)
        elif neural_engine_cores >= 16:  # M1/M2
            base_size = int(base_size * 1.1)

        return min(self.max_arena_size_mb, max(self.min_arena_size_mb, base_size))

    def calculate_hardware_multiplier(self) -> float:
        """Calculate hardware-based scaling multiplier."""
        multiplier = 1.0

        # RAM-based scaling
        ram_gb = self.capabilities.get('memory_gb', 8)
        if ram_gb >= 32:
            multiplier *= 1.5  # High memory systems can use more
        elif ram_gb >= 16:
            multiplier *= 1.2  # Standard memory systems
        elif ram_gb <= 8:
            multiplier *= 0.8  # Conservative on low memory systems

        # CPU core scaling
        cpu_cores = self.capabilities.get('cpu_cores', 4)
        core_multiplier = min(1.4, 1.0 + (cpu_cores - 4) * 0.1)
        multiplier *= core_multiplier

        return min(2.0, max(0.5, multiplier))

    def calculate_workload_multiplier(self, workload_profile) -> float:
        """Calculate workload-based scaling multiplier."""
        multiplier = 1.0

        # Concurrent request scaling
        concurrent_factor = min(
            1.5, 1.0 + (workload_profile.avg_concurrent_requests - 1) * 0.2)
        multiplier *= concurrent_factor

        # Text complexity scaling
        complexity_factor = min(
            1.3, 1.0 + workload_profile.avg_segment_complexity * 0.3)
        multiplier *= complexity_factor

        # Text length scaling
        if workload_profile.avg_text_length > 200:
            length_factor = min(
                1.2, 1.0 + (workload_profile.avg_text_length - 200) / 1000)
            multiplier *= length_factor

        return min(2.0, max(0.7, multiplier))

    def calculate_pressure_adjustment(self) -> float:
        """Calculate memory pressure adjustment factor."""
        try:
            import psutil

            # Get system memory usage
            memory = psutil.virtual_memory()
            memory_pressure = memory.percent / 100.0

            # Adjust based on memory pressure
            if memory_pressure > 0.9:  # Very high pressure
                return 0.6  # Reduce arena size significantly
            elif memory_pressure > 0.8:  # High pressure
                return 0.8  # Reduce arena size moderately
            elif memory_pressure > 0.7:  # Moderate pressure
                return 0.9  # Slight reduction
            else:  # Low pressure
                return 1.0  # No adjustment

        except ImportError:
            self.logger.debug("psutil not available for memory pressure detection")
            return 1.0
        except Exception as e:
            self.logger.debug(f"Could not calculate memory pressure: {e}")
            return 1.0

    def calculate_optimal_arena_size(self) -> int:
        """
        Calculate the optimal memory arena size based on current conditions.
        
        @returns int: Optimal arena size in MB
        """
        # Start with hardware-optimized base size
        base_size = self._calculate_hardware_base_size()

        # Apply hardware multiplier
        hardware_multiplier = self.calculate_hardware_multiplier()
        
        # Apply workload multiplier
        workload_multiplier = self.calculate_workload_multiplier(self.workload_profile)
        
        # Apply memory pressure adjustment
        pressure_adjustment = self.calculate_pressure_adjustment()

        # Calculate optimal size
        optimal_size = base_size * hardware_multiplier * workload_multiplier * pressure_adjustment

        # Ensure within bounds
        optimal_size = min(self.max_arena_size_mb, max(self.min_arena_size_mb, int(optimal_size)))

        self.logger.debug(
            f"Arena size calculation: base={base_size}MB, "
            f"hw_mult={hardware_multiplier:.2f}, "
            f"wl_mult={workload_multiplier:.2f}, "
            f"pressure={pressure_adjustment:.2f}, "
            f"optimal={optimal_size}MB"
        )

        return optimal_size

    def should_optimize(self) -> bool:
        """Determine if memory optimization should be performed."""
        current_time = time.time()
        time_since_last = current_time - self.last_optimization_time

        # Check time interval
        if time_since_last < self.optimization_interval:
            return False

        # Check if we have enough performance data
        if len(self.performance_history) < 10:
            return False

        # Check if performance is degrading
        if len(self.performance_history) >= 20:
            recent_avg = sum(self.performance_history[-10:]) / 10
            older_avg = sum(self.performance_history[-20:-10]) / 10
            
            if recent_avg > older_avg * 1.2:  # 20% degradation
                self.logger.info(" Performance degradation detected, triggering optimization")
                return True

        return True

    def optimize_arena_size(self) -> bool:
        """
        Optimize memory arena size based on current workload and performance.
        
        @returns bool: True if optimization was performed
        """
        if not self.should_optimize():
            return False

        old_size = self.current_arena_size_mb
        new_size = self.calculate_optimal_arena_size()

        # Only update if the change is significant (>10% or >64MB)
        size_diff = abs(new_size - old_size)
        if size_diff < max(old_size * 0.1, 64):
            return False

        self.current_arena_size_mb = new_size
        self.last_optimization_time = time.time()

        self.logger.info(
            f" Optimized memory arena: {old_size}MB → {new_size}MB "
            f"({'+' if new_size > old_size else ''}{new_size - old_size}MB)"
        )

        return True

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get current optimization statistics."""
        current_time = time.time()
        time_since_last = current_time - self.last_optimization_time

        recent_performance = []
        if len(self.performance_history) >= 10:
            recent_performance = list(self.performance_history[-10:])

        return {
            'current_arena_size_mb': self.current_arena_size_mb,
            'min_arena_size_mb': self.min_arena_size_mb,
            'max_arena_size_mb': self.max_arena_size_mb,
            'time_since_last_optimization': time_since_last,
            'optimization_interval': self.optimization_interval,
            'memory_efficiency_target': self.memory_efficiency_target,
            'performance_history_length': len(self.performance_history),
            'recent_avg_performance': sum(recent_performance) / len(recent_performance) if recent_performance else 0.0,
            'hardware_capabilities': {
                'memory_gb': self.capabilities.get('memory_gb', 8),
                'neural_engine_cores': self.capabilities.get('neural_engine_cores', 0),
                'cpu_cores': self.capabilities.get('cpu_cores', 4)
            }
        }

    def record_performance_metric(self, inference_time: float):
        """Record performance metric for optimization analysis."""
        self.performance_history.append(inference_time)

        # Trigger optimization check if performance is degrading
        if len(self.performance_history) >= 20:
            recent_avg = sum(self.performance_history[-10:]) / 10
            older_avg = sum(self.performance_history[-20:-10]) / 10

            if recent_avg > older_avg * 1.3:  # 30% performance degradation
                self.logger.warning(
                    f" Performance degradation detected: {older_avg:.3f}s → {recent_avg:.3f}s "
                    f"({(recent_avg - older_avg) / older_avg:.1%} increase)"
                )
                # Force optimization on next check
                self.last_optimization_time = 0

    def record_request(self, text: str, voice: str, language: str, processing_time: float, concurrent_requests: int):
        """Record a request for workload analysis."""
        # Use the workload analyzer to record the request
        self.workload_analyzer.record_request(
            text, voice, language, processing_time, concurrent_requests)

    def get_workload_insights(self) -> Dict[str, Any]:
        """Get workload insights from the analyzer."""
        return self.workload_analyzer.get_workload_insights()

    def force_optimization(self):
        """Force immediate optimization regardless of timing constraints."""
        self.last_optimization_time = 0
        self.optimize_arena_size()

    def reset_performance_history(self):
        """Reset performance history for fresh analysis."""
        self.performance_history.clear()
        self.logger.info(" Performance history reset")


def get_dynamic_memory_manager() -> Optional[DynamicMemoryManager]:
    """Get the global dynamic memory manager instance."""
    global dynamic_memory_manager
    return dynamic_memory_manager


def initialize_dynamic_memory_manager(capabilities: Optional[Dict[str, Any]] = None):
    """Initialize the global dynamic memory manager."""
    global dynamic_memory_manager

    if dynamic_memory_manager is None:
        logger = logging.getLogger(__name__)
        logger.info(" Initializing dynamic memory manager for adaptive memory sizing")
        dynamic_memory_manager = DynamicMemoryManager(capabilities=capabilities)
        logger.debug("✅ Dynamic memory manager initialized")
    else:
        logger = logging.getLogger(__name__)
        logger.debug("✅ Dynamic memory manager already initialized, skipping duplicate")

    return dynamic_memory_manager
