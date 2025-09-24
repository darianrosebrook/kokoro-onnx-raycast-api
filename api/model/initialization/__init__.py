"""
Model initialization module.

This module handles model initialization strategies, lifecycle management,
and global state coordination.
"""

from .fast_init import initialize_model_fast
from .lifecycle import initialize_model, cleanup_model
from .state import get_active_provider

__all__ = [
    'initialize_model_fast',
    'initialize_model', 
    'cleanup_model',
    'get_active_provider'
]