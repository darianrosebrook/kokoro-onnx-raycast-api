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


def get_adaptive_provider(text_length: int = 0) -> str:
    """
    Get the optimal provider based on text length and performance characteristics.
    
    Based on benchmark results:
    - CPU provider: 8.8ms TTFA p95 for short text (optimal)
    - CoreML ALL: 4827ms TTFA p95 for short text (severe degradation)
    - CPUAndGPU: 9.7ms TTFA p95 for short text (similar to CPU)
    - Long text: degraded on all providers (~2400ms TTFA p95)
    
    @param text_length: Length of text to be processed
    @returns: Optimal provider name for the given text length
    """
    import logging
    import os
    
    logger = logging.getLogger(__name__)
    global _active_provider
    
    current = _active_provider
    compute_units = os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'CPUOnly')
    
    # Short text optimization (< 200 chars): CPU consistently performs best
    if text_length < 200:
        # Force CPU for short text to avoid CoreML context leak issues
        selected = "CPUExecutionProvider"
        logger.info(f" Adaptive provider: text_len={text_length} → {selected} (short text optimization)")
        return selected
    
    # Medium text (200-1000 chars): Use current provider but avoid CoreML ALL
    elif text_length < 1000:
        # If current provider is CoreML with ALL setting, switch to CPU
        # This prevents context leaks while maintaining reasonable performance
        if current == "CoreMLExecutionProvider" and compute_units == 'ALL':
            selected = "CPUExecutionProvider"
            logger.info(f" Adaptive provider: text_len={text_length} → {selected} (avoiding CoreML ALL)")
        else:
            selected = current if current else "CPUExecutionProvider"
            logger.info(f" Adaptive provider: text_len={text_length} → {selected} (medium text)")
        return selected
    
    # Long text (>1000 chars): All providers show degradation, use current
    # TODO: Investigate long text performance issues across all providers
    else:
        selected = current if current else "CPUExecutionProvider"
        logger.info(f" Adaptive provider: text_len={text_length} → {selected} (long text - degraded performance expected)")
        return selected


def set_model(model: Kokoro, provider: str) -> None:
    """
    Set the global model instance and provider.
    
    Also adds the model to the shared cache to avoid duplicate model loading
    during background operations (e.g., extended warming).
    
    @param model: The Kokoro model instance
    @param provider: The provider name used for this model
    """
    global kokoro_model, model_loaded, _active_provider
    
    with _model_lock:
        kokoro_model = model
        _active_provider = provider
        model_loaded = True
    
    # OPTIMIZATION: Add model to shared cache to avoid duplicate loading
    # This ensures background operations (e.g., extended warming) can reuse the model
    try:
        from api.tts.core import _model_cache, _model_cache_lock
        
        with _model_cache_lock:
            if provider not in _model_cache:
                _model_cache[provider] = model
                logger.debug(f"✅ Added model to shared cache for provider: {provider}")
            else:
                logger.debug(f"ℹ Model already in cache for provider: {provider}, skipping")
    except ImportError:
        # Fallback if cache not available
        logger.debug("Could not add model to shared cache (cache module not available)")
    except Exception as e:
        # Don't fail if cache update fails
        logger.debug(f"Could not add model to shared cache: {e}")
    
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
