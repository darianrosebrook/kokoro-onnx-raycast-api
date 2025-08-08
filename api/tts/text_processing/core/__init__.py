"""Core text processing components."""

from .base import BaseProcessor, ProcessorInterface
from .pipeline import TextProcessingPipeline
from .exceptions import (
    TextProcessingError,
    NormalizationError, 
    PhonemeError,
    SegmentationError
)

__all__ = [
    'BaseProcessor',
    'ProcessorInterface',
    'TextProcessingPipeline',
    'TextProcessingError',
    'NormalizationError',
    'PhonemeError', 
    'SegmentationError'
]
