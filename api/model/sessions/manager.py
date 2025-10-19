"""
Session lifecycle management.

This module handles the basic session management functions including
model access, status checking, and session state management.
"""

import threading
import logging
import os
from typing import Optional, Dict, Any
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

    UPDATED 2025-10-19 based on comprehensive soak testing:
    - CoreML providers: 4.8-5.3ms TTFA p95 for all text lengths (optimal)
    - CPU provider: Massive cold start (3.4-11s first request), then 4.7-5.3ms (poor for real-time)
    - Adaptive selection: Use CoreML for all lengths to avoid cold start penalty

    @param text_length: Length of text to be processed
    @returns: Optimal provider name for the given text length
    """
    import logging
    import os
    
    logger = logging.getLogger(__name__)
    global _active_provider
    
    current = _active_provider

    # CoreML optimization: Use CoreML for all text lengths to avoid cold start penalty
    # CoreML provides consistent 4.8-5.3ms TTFA vs CPU's 3.4-11s cold start
    compute_units = os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'CPUAndNeuralEngine')

    if compute_units in ['ALL', 'CPUAndGPU', 'CPUAndNeuralEngine']:
        selected = "CoreMLExecutionProvider"
        logger.info(f" Adaptive provider: text_len={text_length} → {selected} (CoreML optimal for all lengths)")
    else:
        selected = "CPUExecutionProvider"
        logger.info(f" Adaptive provider: text_len={text_length} → {selected} (CPU fallback)")

    return selected


def get_long_text_optimization_recommendations(text_length: int) -> Dict[str, Any]:
    """
    Provide optimization recommendations for long text processing.
    
    Based on analysis of long text performance issues:
    - Memory pressure increases with text length
    - Segmentation overhead grows non-linearly
    - Provider performance degrades significantly
    - Streaming efficiency decreases with more segments
    
    @param text_length: Length of text to be processed
    @returns: Dictionary with optimization recommendations
    """
    recommendations = {
        "text_length": text_length,
        "category": "long_text",
        "performance_impact": "high",
        "optimizations": []
    }
    
    if text_length > 2000:
        recommendations["optimizations"].extend([
            "Consider breaking text into smaller chunks for better performance",
            "Use streaming mode to reduce memory pressure",
            "Monitor memory usage during processing"
        ])
        recommendations["performance_impact"] = "very_high"
    elif text_length > 1000:
        recommendations["optimizations"].extend([
            "Enable streaming mode for better responsiveness",
            "Consider using CPU provider for predictable performance"
        ])
    
    # Add provider-specific recommendations
    current_provider = get_active_provider()
    if current_provider == "CoreMLExecutionProvider":
        compute_units = os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'CPUOnly')
        if compute_units == 'ALL':
            recommendations["optimizations"].append(
                "Consider switching to CPU provider or CPUAndGPU for long text"
            )
    
    # Add segmentation recommendations
    estimated_segments = max(1, text_length // 800)  # Rough estimate based on max segment length
    if estimated_segments > 5:
        recommendations["optimizations"].append(
            f"Text will be split into ~{estimated_segments} segments - consider pre-processing"
        )
    
    return recommendations


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
    
    try:
        logger.info("Model cleared")
    except Exception:
        # Ignore all logging errors during cleanup
        pass


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
