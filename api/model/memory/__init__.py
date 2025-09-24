"""
Memory management module.

This module provides dynamic memory management, workload analysis,
and memory optimization strategies for optimal performance.
"""

from .dynamic_manager import (
    DynamicMemoryManager, 
    get_dynamic_memory_manager, 
    initialize_dynamic_memory_manager
)
from .workload_analyzer import (
    WorkloadAnalyzer, 
    WorkloadProfile
)
from .optimization import (
    create_optimized_session_options,
    get_memory_optimization_recommendations,
    create_memory_profile_for_workload,
    optimize_session_for_inference
)
from .watchdog import (
    MemoryFragmentationWatchdog
)

__all__ = [
    # Dynamic Memory Management
    'DynamicMemoryManager',
    'get_dynamic_memory_manager',
    'initialize_dynamic_memory_manager',
    
    # Workload Analysis
    'WorkloadAnalyzer',
    'WorkloadProfile',
    
    # Optimization
    'create_optimized_session_options',
    'get_memory_optimization_recommendations',
    'create_memory_profile_for_workload', 
    'optimize_session_for_inference',
    
    # Monitoring
    'MemoryFragmentationWatchdog'
]