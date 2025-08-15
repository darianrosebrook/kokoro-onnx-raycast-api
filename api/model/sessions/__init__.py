"""
Session management module.

This module handles session lifecycle management, dual session coordination,
and session performance monitoring.
"""

from .manager import (
    get_model, 
    get_model_status, 
    get_active_provider,
    set_model,
    clear_model,
    is_model_loaded,
    get_model_info
)
from .dual_session import (
    DualSessionManager, 
    get_dual_session_manager, 
    initialize_dual_session_manager,
    set_dual_session_manager,
    SessionUtilization,
    MemoryFragmentationWatchdog
)
from .utilization import (
    SessionUtilizationTracker,
    SessionMetrics
)

__all__ = [
    # Manager
    'get_model',
    'get_model_status', 
    'get_active_provider',
    'set_model',
    'clear_model',
    'is_model_loaded',
    'get_model_info',
    
    # Dual Session
    'DualSessionManager',
    'get_dual_session_manager',
    'initialize_dual_session_manager',
    'set_dual_session_manager',
    'SessionUtilization',
    'MemoryFragmentationWatchdog',
    
    # Utilization Tracking
    'SessionUtilizationTracker',
    'SessionMetrics'
]