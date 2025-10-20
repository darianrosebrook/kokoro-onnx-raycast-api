"""
Audio Processing Module for Enterprise TTS

This module provides comprehensive audio processing capabilities including:
- Audio quality metrics (LUFS, dBTP, peak/RMS levels)
- Audio validation against enterprise standards
- Audio format conversion and optimization
- Real-time audio processing utilities

@sign: @darianrosebrook
"""

from .audio_quality_metrics import (
    AudioQualityAnalyzer,
    AudioQualityMetrics,
    AudioQualityStandard,
    get_audio_quality_analyzer,
    analyze_audio_quality,
    validate_audio_quality_enterprise
)

__all__ = [
    'AudioQualityAnalyzer',
    'AudioQualityMetrics',
    'AudioQualityStandard',
    'get_audio_quality_analyzer',
    'analyze_audio_quality',
    'validate_audio_quality_enterprise'
]
