"""
Session lifecycle management.

This module handles the basic session management functions including
model access, status checking, and session state management.
"""

import threading
import logging
from typing import Optional
from kokoro_onnx import Kokoro

# Global model state and management
kokoro_model: Optional[Kokoro] = None
model_loaded = False
_active_provider: str = "CPUExecutionProvider"
_model_lock = threading.Lock()

logger = logging.getLogger(__name__)


def get_model_status() -> bool:
    """Check if the model is loaded and ready for inference."""
    global model_loaded
    return model_loaded


def get_model() -> Optional[Kokoro]:
    """Get the loaded Kokoro model instance."""
    global kokoro_model, model_loaded
    
    if not model_loaded or kokoro_model is None:
        return None
    
    return kokoro_model


def get_active_provider() -> str:
    """Returns the currently active ONNX execution provider."""
    global _active_provider
    return _active_provider


def set_model(model: Kokoro, provider: str) -> None:
    """
    Set the global model instance and provider.
    
    @param model: The Kokoro model instance
    @param provider: The provider name used for this model
    """
    global kokoro_model, model_loaded, _active_provider
    
    with _model_lock:
        kokoro_model = model
        _active_provider = provider
        model_loaded = True
    
    logger.info(f"Model set with provider: {provider}")


def clear_model() -> None:
    """Clear the global model instance."""
    global kokoro_model, model_loaded, _active_provider
    
    with _model_lock:
        kokoro_model = None
        model_loaded = False
        _active_provider = "CPUExecutionProvider"
    
    logger.info("Model cleared")


def is_model_loaded() -> bool:
    """Check if a model is currently loaded."""
    return get_model_status()


def get_model_info() -> dict:
    """
    Get information about the currently loaded model.
    
    @returns dict: Model information including provider and status
    """
    return {
        'loaded': model_loaded,
        'provider': _active_provider,
        'model_available': kokoro_model is not None
    }
