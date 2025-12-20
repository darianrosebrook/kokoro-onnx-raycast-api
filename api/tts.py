"""
Kokoro TTS API v2 - TTS Generation

Simple TTS generation using kokoro-onnx v1.0.
No complex session management, warming, or provider selection.
"""

import logging
import time
from typing import Optional, Tuple
import numpy as np
import kokoro_onnx

from .config import (
    MODEL_PATH,
    VOICES_PATH,
    DEFAULT_VOICE,
    DEFAULT_SPEED,
    MIN_SPEED,
    MAX_SPEED,
    WARMUP_TEXT,
)

logger = logging.getLogger(__name__)

# Global model instance
_model: Optional[kokoro_onnx.Kokoro] = None
_model_ready: bool = False


def get_model() -> kokoro_onnx.Kokoro:
    """Get the global model instance."""
    global _model
    if _model is None:
        raise RuntimeError("Model not initialized. Call initialize_model() first.")
    return _model


def is_model_ready() -> bool:
    """Check if model is loaded and ready."""
    return _model_ready


def initialize_model() -> float:
    """
    Initialize the TTS model.
    
    Returns:
        Initialization time in seconds.
    """
    global _model, _model_ready
    
    start_time = time.perf_counter()
    
    logger.info(f"Loading model from {MODEL_PATH}")
    _model = kokoro_onnx.Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    
    # Single warmup call
    logger.info("Warming up model...")
    _model.create(WARMUP_TEXT, voice=DEFAULT_VOICE, speed=DEFAULT_SPEED)
    
    init_time = time.perf_counter() - start_time
    _model_ready = True
    
    logger.info(f"Model initialized in {init_time:.2f}s")
    return init_time


def get_voices() -> list[str]:
    """Get list of available voices."""
    if _model is None:
        return []
    return _model.get_voices()


def generate_audio(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> Tuple[np.ndarray, int, float]:
    """
    Generate audio from text.
    
    Args:
        text: Text to synthesize.
        voice: Voice ID to use.
        speed: Speed multiplier (0.5-2.0).
    
    Returns:
        Tuple of (audio_array, sample_rate, generation_time).
    """
    model = get_model()
    
    # Validate speed
    speed = max(MIN_SPEED, min(MAX_SPEED, speed))
    
    # Validate voice
    available_voices = model.get_voices()
    if voice not in available_voices:
        logger.warning(f"Voice '{voice}' not found, using default '{DEFAULT_VOICE}'")
        voice = DEFAULT_VOICE
    
    # Generate audio
    start_time = time.perf_counter()
    audio, sample_rate = model.create(text, voice=voice, speed=speed)
    generation_time = time.perf_counter() - start_time
    
    # Calculate metrics
    audio_duration = len(audio) / sample_rate
    rtf = generation_time / audio_duration if audio_duration > 0 else 0
    
    logger.debug(
        f"Generated {audio_duration:.2f}s audio in {generation_time:.2f}s "
        f"(RTF: {rtf:.3f})"
    )
    
    return audio, sample_rate, generation_time
