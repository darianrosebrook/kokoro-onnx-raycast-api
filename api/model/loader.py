"""
Model Loader - Hardware-Accelerated Model Initialization and Optimization

This module provides intelligent model loading and hardware acceleration for the 
Kokoro-ONNX TTS model with sophisticated Apple Silicon optimization.

This is the main orchestration module that imports functionality from specialized modules:
- Hardware detection: api.model.hardware
- Provider management: api.model.providers
- Session management: api.model.sessions
- Memory management: api.model.memory
- Pipeline optimization: api.model.pipeline
- Initialization: api.model.initialization

@author @darianrosebrook
@version 2.0.0
@since 2025-07-08
@license MIT
"""

import logging
import atexit

# Apply patches BEFORE importing anything else
from api.model.patch import apply_all_patches
apply_all_patches()

# Set up CoreML temp directory early
from api.model.utils import setup_early_temp_directory  # noqa: E402
setup_early_temp_directory()

# Logger
logger = logging.getLogger(__name__)

# Global model state (kept minimal)
kokoro_model = None
model_loaded = False
_active_provider = None


# Legacy compatibility functions - only import when needed
def get_model():
    """Get the current model instance. Legacy compatibility wrapper."""
    from api.model.sessions import get_model as _get_model
    return _get_model()


def get_model_status():
    """Get model status. Legacy compatibility wrapper."""
    from api.model.sessions import get_model_status as _get_model_status
    return _get_model_status()


def get_active_provider():
    """Get active provider. Legacy compatibility wrapper."""
    from api.model.sessions import get_active_provider as _get_active_provider
    return _get_active_provider()


def detect_apple_silicon_capabilities():
    """Detect Apple Silicon capabilities. Legacy compatibility wrapper."""
    from api.model.hardware import detect_apple_silicon_capabilities as _detect_capabilities
    return _detect_capabilities()


def initialize_model_fast():
    """Fast model initialization. Legacy compatibility wrapper."""
    from api.model.initialization.fast_init import initialize_model_fast as _initialize_fast
    return _initialize_fast()


def initialize_model():
    """Standard model initialization. Legacy compatibility wrapper."""
    from api.model.initialization.fast_init import initialize_model_fast as _initialize_fast
    return _initialize_fast()


def get_dual_session_manager():
    """Get dual session manager. Legacy compatibility wrapper."""
    from api.model.sessions import get_dual_session_manager as _get_dual_session_manager
    return _get_dual_session_manager()


def get_dynamic_memory_manager():
    """Get dynamic memory manager. Legacy compatibility wrapper."""
    from api.model.memory import get_dynamic_memory_manager as _get_dynamic_memory_manager
    return _get_dynamic_memory_manager()


def get_pipeline_warmer():
    """Get pipeline warmer. Legacy compatibility wrapper."""
    from api.model.pipeline import get_pipeline_warmer as _get_pipeline_warmer
    return _get_pipeline_warmer()


def cleanup_model():
    """Clean up model resources. Legacy compatibility wrapper."""
    from api.model.initialization.lifecycle import cleanup_model as _cleanup_model
    return _cleanup_model()


# Register cleanup at exit
atexit.register(cleanup_model)
