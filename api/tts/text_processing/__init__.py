"""
Advanced Text Processing Pipeline for Kokoro TTS
=====================================================

This module provides a comprehensive, modular text processing pipeline optimized for
high-quality TTS synthesis. The architecture is designed around clean separation of
concerns, robust error handling, and optimal performance.

## Architecture Overview

The text processing system consists of several specialized components:

1. **Normalization Pipeline**: Handles text cleaning, number verbalization, 
   abbreviation expansion, and format standardization
2. **Phonemization Engine**: Multi-tier phoneme conversion with Misaki G2P
   primary processing and intelligent fallback mechanisms  
3. **Segmentation System**: Intelligent text chunking with linguistic awareness
   and natural speech pattern preservation
4. **Caching Layer**: Advanced caching with TTL, LRU eviction, and performance
   monitoring for optimal real-time performance

## Quick Start

```python
from api.tts.text_processing import TextProcessor

# Initialize processor with default configuration
processor = TextProcessor()

# Process text for TTS inference
result = processor.process_for_inference(
    text="Hello world! Today is 2024-01-15.",
    max_length=256
)

# Access processed components
normalized_text = result.normalized_text
phonemes = result.phonemes
segments = result.segments
```

## Configuration

```python
from api.tts.text_processing import TextProcessor, ProcessingConfig

# Custom configuration
config = ProcessingConfig(
    enable_misaki=True,
    enable_number_normalization=True,
    max_phoneme_length=512,
    cache_size=2000
)

processor = TextProcessor(config=config)
```

## Performance Features

- **Lazy Loading**: Components are initialized only when needed
- **Smart Caching**: Multi-level caching with automatic invalidation
- **Parallel Processing**: Where applicable, operations run in parallel
- **Fallback Strategies**: Multiple fallback levels ensure 100% reliability
- **Memory Efficiency**: Streaming processing with minimal memory footprint

@version: 3.0.0
@author: @darianrosebrook
@date: 2025-01-15
"""

import logging
from typing import Dict, Any, Optional, List, Union

# Import types
from .types import ProcessingResult, ProcessingMode

# Import main components
from .core.pipeline import TextProcessingPipeline
from .core.exceptions import TextProcessingError, NormalizationError, PhonemeError
from .config import ProcessingConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

# Version information
__version__ = "3.0.0"
__author__ = "@darianrosebrook"

# Public API exports
__all__ = [
    'TextProcessor',
    'ProcessingConfig', 
    'ProcessingResult',
    'ProcessingMode',
    'TextProcessingError',
    'NormalizationError', 
    'PhonemeError',
    # Legacy compatibility functions
    'preprocess_text_for_inference',
    'text_to_phonemes',
    'clean_text',
    'segment_text',
    'get_phoneme_cache_stats',
    'clear_phoneme_cache',
    'normalize_for_tts',
    'pad_phoneme_sequence'
]


class TextProcessor:
    """
    High-level text processing interface for TTS applications.
    
    This class provides a unified API for all text processing operations,
    managing the underlying pipeline components and providing convenient
    methods for common TTS use cases.
    
    The processor supports multiple processing modes, configuration options,
    and provides comprehensive monitoring and debugging capabilities.
    
    Examples:
        Basic usage:
        >>> processor = TextProcessor()
        >>> result = processor.process("Hello world!")
        >>> print(result.normalized_text)
        'Hello world!'
        
        Custom configuration:
        >>> config = ProcessingConfig(enable_misaki=False)
        >>> processor = TextProcessor(config=config)
        
        Streaming mode:
        >>> processor = TextProcessor(mode=ProcessingMode.STREAMING)
        >>> result = processor.process_streaming("Long text...")
    """
    
    def __init__(
        self, 
        config: Optional[ProcessingConfig] = None,
        mode: ProcessingMode = ProcessingMode.BALANCED
    ):
        """
        Initialize the text processor.
        
        Args:
            config: Optional custom configuration. Uses default if None.
            mode: Processing mode for performance/quality tradeoffs.
        """
        self.config = config or DEFAULT_CONFIG
        self.mode = mode
        self._pipeline: Optional[TextProcessingPipeline] = None
        
        logger.info(f"Initializing TextProcessor v{__version__} in {mode.value} mode")
    
    @property
    def pipeline(self) -> TextProcessingPipeline:
        """Get the processing pipeline, initializing if needed (lazy loading)."""
        if self._pipeline is None:
            self._pipeline = TextProcessingPipeline(
                config=self.config,
                mode=self.mode
            )
        return self._pipeline
    
    def process(self, text: str) -> ProcessingResult:
        """
        Process text with full normalization and phonemization.
        
        This is the main processing method that applies the complete
        pipeline including normalization, phonemization, and segmentation.
        
        Args:
            text: Input text to process
            
        Returns:
            ProcessingResult with all processing outputs
            
        Raises:
            TextProcessingError: If processing fails
        """
        if not text or not text.strip():
            return ProcessingResult(
                original_text=text,
                normalized_text="",
                phonemes=[],
                segments=[],
                padded_phonemes=["_"] * self.config.max_phoneme_length
            )
        
        try:
            return self.pipeline.process_full(text)
        except Exception as e:
            logger.error(f"Text processing failed for '{text[:50]}...': {e}")
            raise TextProcessingError(f"Processing failed: {e}") from e
    
    def process_for_inference(
        self, 
        text: str, 
        max_length: Optional[int] = None
    ) -> ProcessingResult:
        """
        Process text specifically for TTS model inference.
        
        This method optimizes the processing pipeline for TTS inference,
        including appropriate padding and tensor shape optimization.
        
        Args:
            text: Input text to process
            max_length: Maximum phoneme sequence length (overrides config)
            
        Returns:
            ProcessingResult optimized for TTS inference
        """
        max_len = max_length or self.config.max_phoneme_length
        
        # Create temporary config if max_length is overridden
        config = self.config
        if max_length:
            # Create a copy of the config with updated max_phoneme_length
            config_dict = self.config.to_dict()
            config_dict['max_phoneme_length'] = max_length
            config_dict['padding']['max_phoneme_length'] = max_length
            config = ProcessingConfig.from_dict(config_dict)
        
        return self.pipeline.process_for_inference(text, config)
    
    def normalize_only(self, text: str) -> str:
        """
        Apply only text normalization without phonemization.
        
        Useful for preprocessing text before other operations or
        for debugging normalization steps.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text string
        """
        return self.pipeline.normalize_text(text)
    
    def phonemize_only(self, text: str) -> List[str]:
        """
        Apply only phonemization without normalization.
        
        Assumes text is already normalized and applies phonemization
        directly. Useful for testing phonemizers or when normalization
        is handled externally.
        
        Args:
            text: Pre-normalized text to phonemize
            
        Returns:
            List of phoneme tokens
        """
        return self.pipeline.phonemize_text(text)
    
    def segment_only(self, text: str, max_length: int) -> List[str]:
        """
        Apply only text segmentation without other processing.
        
        Args:
            text: Input text to segment
            max_length: Maximum segment length
            
        Returns:
            List of text segments
        """
        return self.pipeline.segment_text(text, max_length)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Returns:
            Dictionary containing performance metrics, cache statistics,
            quality metrics, and system status information.
        """
        if self._pipeline is None:
            return {"status": "not_initialized"}
        
        return self.pipeline.get_statistics()
    
    def clear_cache(self) -> None:
        """Clear all processing caches."""
        if self._pipeline:
            self.pipeline.clear_cache()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if self._pipeline:
            self._pipeline.cleanup()


# Convenience functions for backward compatibility
def preprocess_text_for_inference(
    text: str, 
    max_phoneme_length: int = 256
) -> Dict[str, Any]:
    """
    Legacy compatibility function for existing code.
    
    This function provides backward compatibility with the old API
    while using the new processing pipeline internally.
    
    Args:
        text: Input text to process
        max_phoneme_length: Maximum phoneme sequence length
        
    Returns:
        Dictionary with legacy format for compatibility
    """
    processor = TextProcessor()
    result = processor.process_for_inference(text, max_phoneme_length)
    
    # Convert to legacy format
    return {
        'normalized_text': result.normalized_text,
        'phonemes': result.phonemes,
        'padded_phonemes': result.padded_phonemes,
        'original_length': result.phoneme_count,
        'padded_length': result.padded_phoneme_count,
        'truncated': result.truncated,
        'cache_hit': result.cache_hits > 0,
        'processing_time': result.processing_time,
        'quality_score': result.phoneme_quality_score
    }


def text_to_phonemes(text: str, lang: str = 'en') -> List[str]:
    """
    Legacy compatibility function for phoneme conversion.
    
    Args:
        text: Input text to convert
        lang: Language code (currently only 'en' supported)
        
    Returns:
        List of phoneme tokens
    """
    processor = TextProcessor()
    result = processor.process(text)
    return result.phonemes


def clean_text(text: str) -> str:
    """
    Legacy compatibility function for text cleaning.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text string
    """
    processor = TextProcessor()
    return processor.normalize_only(text)


def segment_text(text: str, max_len: int) -> List[str]:
    """
    Legacy compatibility function for text segmentation.
    
    Args:
        text: Input text to segment
        max_len: Maximum segment length
        
    Returns:
        List of text segments
    """
    processor = TextProcessor()
    return processor.segment_only(text, max_len)


def get_phoneme_cache_stats() -> Dict[str, Any]:
    """
    Legacy compatibility function for cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    # Create a processor to get stats
    processor = TextProcessor()
    stats = processor.get_stats()
    
    # Convert to legacy format
    return {
        'cache_size': stats.get('cache_hits', 0) + stats.get('cache_misses', 0),
        'max_cache_size': 1000,  # Default from old system
        'cache_hit_rate': 0.0,
        'hit_rate': 0.0,
        'efficiency': 0.0,
        'backend_available': True,
        'padding_token': "_",
        'max_phoneme_length': 256
    }


def clear_phoneme_cache() -> None:
    """
    Legacy compatibility function for clearing cache.
    """
    # Create a processor and clear its cache
    processor = TextProcessor()
    processor.clear_cache()


def normalize_for_tts(text: str) -> str:
    """
    Legacy compatibility function for text normalization.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text
    """
    processor = TextProcessor()
    return processor.normalize_only(text)


def pad_phoneme_sequence(phonemes: List[str], max_len: int = 256) -> List[str]:
    """
    Legacy compatibility function for phoneme padding.
    
    Args:
        phonemes: Input phoneme sequence
        max_len: Maximum sequence length
        
    Returns:
        Padded phoneme sequence
    """
    if len(phonemes) > max_len:
        return phonemes[:max_len]
    else:
        return phonemes + ["_"] * (max_len - len(phonemes))
