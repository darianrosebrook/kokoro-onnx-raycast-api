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
    
    # Long text (>1000 chars): Implement optimized long text strategy
    else:
        # For long text, prioritize memory efficiency and streaming performance
        # CPU provider is more predictable for long text processing
        if current == "CoreMLExecutionProvider" and compute_units == 'ALL':
            # Avoid CoreML ALL for long text due to memory pressure
            selected = "CPUExecutionProvider"
            logger.info(f" Adaptive provider: text_len={text_length} → {selected} (long text - avoiding CoreML ALL for memory efficiency)")
        elif current == "CoreMLExecutionProvider" and compute_units == 'CPUAndGPU':
            # CPUAndGPU can handle long text better than ALL
            selected = current
            logger.info(f" Adaptive provider: text_len={text_length} → {selected} (long text - CoreML CPUAndGPU optimized)")
        else:
            # Default to CPU for long text as it's most predictable
            selected = "CPUExecutionProvider"
            logger.info(f" Adaptive provider: text_len={text_length} → {selected} (long text - CPU for predictable performance)")
        
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
