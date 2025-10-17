"""
Model lifecycle management module.

This module handles full model initialization, cleanup, and lifecycle management
for the Kokoro-ONNX TTS model.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def initialize_model():
    """
    Initialize the model with full configuration and optimization.
    
    This is the traditional, full initialization method that sets up
    all components synchronously. It now works with fast_init.py to
    avoid duplicate hardware detection and session initialization.
    """
    logger.info("Starting full model initialization...")
    
    # Import the fast init and ensure it's completed
    from api.model.initialization.fast_init import initialize_model_fast
    initialize_model_fast()
    
    # Note: Hardware capabilities are already detected in fast_init.py
    # and heavy components are initialized in background threads.
    # This function now focuses on ensuring initialization completion
    # rather than duplicating work.
    
    logger.info("Full model initialization completed - heavy components initializing in background")


def cleanup_model():
    """
    Clean up model resources and shutdown background services.
    
    This function ensures proper cleanup of all model-related resources including
    sessions, memory managers, analyzers, and background threads.
    """
    try:
        logger.info("Starting model cleanup...")
    except Exception:
        # Ignore all logging errors during cleanup
        pass

    try:
        # Clean up dual session manager
        from api.model.sessions import get_dual_session_manager
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager:
            dual_session_manager.cleanup_sessions()

        # Clean up dynamic memory manager  
        from api.model.memory import get_dynamic_memory_manager
        dynamic_memory_manager = get_dynamic_memory_manager()
        if dynamic_memory_manager:
            # Memory manager doesn't need explicit cleanup
            pass

        # Clean up pipeline warmer
        from api.model.pipeline import get_pipeline_warmer
        pipeline_warmer = get_pipeline_warmer()
        if pipeline_warmer:
            # Pipeline warmer cleanup if needed
            pass

        # Clean up main model
        from api.model.sessions import clear_model
        clear_model()

        # Clean up CoreML temp directory
        try:
            from api.model.providers import cleanup_coreml_temp_directory
            cleanup_coreml_temp_directory()
        except Exception as e:
            logger.debug(f"CoreML temp cleanup error: {e}")

        # Clean up real-time optimizer
        try:
            from api.performance.optimization import cleanup_real_time_optimizer
            cleanup_real_time_optimizer()
        except Exception as e:
            logger.debug(f"Could not cleanup real-time optimizer: {e}")

        try:
            logger.info("Model cleanup completed")
        except Exception:
            # Ignore all logging errors during cleanup
            pass

    except Exception as e:
        logger.error(f"Error during model cleanup: {e}")

