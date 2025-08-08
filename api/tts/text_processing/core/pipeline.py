"""
Text processing pipeline coordinator.

This module implements the main pipeline that coordinates all text processing
operations, managing the flow between normalization, phonemization, and
segmentation components.
"""

import logging
import time
from typing import Dict, Any, List, Optional

from .base import ProcessingContext
from .exceptions import TextProcessingError
from ..types import ProcessingResult, ProcessingMode
from ..config import ProcessingConfig
from ..normalization.text_normalizer import TextNormalizer
from ..normalization.number_normalizer import NumberNormalizer

logger = logging.getLogger(__name__)


class TextProcessingPipeline:
    """
    Main text processing pipeline coordinator.
    
    This class orchestrates the complete text processing workflow,
    managing components, caching, error handling, and performance
    monitoring.
    """
    
    def __init__(self, config: ProcessingConfig, mode: ProcessingMode = ProcessingMode.BALANCED):
        """
        Initialize the text processing pipeline.
        
        Args:
            config: Processing configuration
            mode: Processing mode for performance/quality tradeoffs
        """
        self.config = config
        self.mode = mode
        self.logger = logging.getLogger(f"{__name__}.pipeline")
        
        # Initialize components (lazy loading)
        self._text_normalizer: Optional[TextNormalizer] = None
        self._number_normalizer: Optional[NumberNormalizer] = None
        self._phonemizer = None  # Will be implemented later
        self._segmenter = None   # Will be implemented later
        
        # Statistics tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_processing_time': 0.0,
            'component_stats': {}
        }
        
        self.logger.info(f"Initialized TextProcessingPipeline in {mode.value} mode")
    
    @property
    def text_normalizer(self) -> TextNormalizer:
        """Get text normalizer (lazy initialization)."""
        if self._text_normalizer is None:
            self._text_normalizer = TextNormalizer(self.config.normalization.__dict__)
        return self._text_normalizer
    
    @property
    def number_normalizer(self) -> NumberNormalizer:
        """Get number normalizer (lazy initialization)."""
        if self._number_normalizer is None:
            self._number_normalizer = NumberNormalizer(self.config.normalization.__dict__)
        return self._number_normalizer
    
    def process_full(self, text: str) -> ProcessingResult:
        """
        Process text through the complete pipeline.
        
        Args:
            text: Input text to process
            
        Returns:
            ProcessingResult with all processing outputs
        """
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # Create processing context
            context = ProcessingContext(
                original_text=text,
                current_text=text,
                language=self.config.language
            )
            
            # Apply normalization
            context = self._apply_normalization(context)
            
            # Apply phonemization (placeholder for now)
            phonemes = self._apply_phonemization(context.current_text)
            
            # Apply segmentation (placeholder for now)
            segments = self._apply_segmentation(context.current_text)
            
            # Apply padding
            padded_phonemes = self._apply_padding(phonemes)
            
            # Create result
            result = ProcessingResult(
                original_text=text,
                normalized_text=context.current_text,
                normalization_steps=context.normalization_steps,
                phonemes=phonemes,
                phoneme_method=context.phoneme_method,
                segments=segments,
                padded_phonemes=padded_phonemes,
                max_length=self.config.padding.max_phoneme_length,
                truncated=len(phonemes) > self.config.padding.max_phoneme_length,
                processing_time=time.time() - start_time,
                cache_hits=context.cache_hits,
                cache_misses=context.cache_misses
            )
            
            self.stats['successful_requests'] += 1
            self._update_processing_time(result.processing_time)
            
            return result
            
        except Exception as e:
            self.stats['failed_requests'] += 1
            self.logger.error(f"Pipeline processing failed: {e}")
            raise TextProcessingError(f"Pipeline processing failed: {e}") from e
    
    def process_for_inference(self, text: str, config: ProcessingConfig) -> ProcessingResult:
        """
        Process text specifically for TTS inference.
        
        Args:
            text: Input text to process
            config: Processing configuration (may override pipeline config)
            
        Returns:
            ProcessingResult optimized for inference
        """
        # Use provided config for this specific request
        original_config = self.config
        self.config = config
        
        try:
            return self.process_full(text)
        finally:
            # Restore original config
            self.config = original_config
    
    def normalize_text(self, text: str) -> str:
        """
        Apply only text normalization.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text
        """
        context = ProcessingContext(
            original_text=text,
            current_text=text,
            language=self.config.language
        )
        
        context = self._apply_normalization(context)
        return context.current_text
    
    def phonemize_text(self, text: str) -> List[str]:
        """
        Apply only phonemization.
        
        Args:
            text: Input text to phonemize
            
        Returns:
            List of phoneme tokens
        """
        return self._apply_phonemization(text)
    
    def segment_text(self, text: str, max_length: int) -> List[str]:
        """
        Apply only text segmentation.
        
        Args:
            text: Input text to segment
            max_length: Maximum segment length
            
        Returns:
            List of text segments
        """
        return self._apply_segmentation(text, max_length)
    
    def _apply_normalization(self, context: ProcessingContext) -> ProcessingContext:
        """Apply text normalization to the context."""
        context.start_stage("normalization")
        
        try:
            # Apply text normalization
            if self.text_normalizer.is_available():
                context = self.text_normalizer.process(context)
            else:
                self.logger.warning("Text normalizer not available")
            
            # Apply number normalization
            if self.number_normalizer.is_available():
                context = self.number_normalizer.process(context)
            else:
                self.logger.warning("Number normalizer not available")
            
        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            # Continue with original text
        finally:
            context.end_stage("normalization")
        
        return context
    
    def _apply_phonemization(self, text: str) -> List[str]:
        """
        Apply phonemization to text.
        
        This is a placeholder implementation that will be replaced
        with the actual phonemization pipeline.
        """
        # Placeholder: return character-level tokenization
        return list(text.replace(' ', ''))
    
    def _apply_segmentation(self, text: str, max_length: Optional[int] = None) -> List[str]:
        """
        Apply text segmentation.
        
        This is a placeholder implementation that will be replaced
        with the actual segmentation pipeline.
        """
        max_len = max_length or self.config.segmentation.max_segment_length
        
        # Simple segmentation for now
        if len(text) <= max_len:
            return [text]
        
        segments = []
        words = text.split()
        current_segment = ""
        
        for word in words:
            test_segment = f"{current_segment} {word}".strip()
            if len(test_segment) <= max_len:
                current_segment = test_segment
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = word
        
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def _apply_padding(self, phonemes: List[str]) -> List[str]:
        """Apply phoneme padding."""
        max_len = self.config.padding.max_phoneme_length
        padding_token = self.config.padding.padding_token
        
        if len(phonemes) > max_len:
            # Truncate
            return phonemes[:max_len]
        else:
            # Pad
            return phonemes + [padding_token] * (max_len - len(phonemes))
    
    def _update_processing_time(self, processing_time: float) -> None:
        """Update average processing time statistics."""
        total_requests = self.stats['successful_requests']
        if total_requests == 1:
            self.stats['average_processing_time'] = processing_time
        else:
            # Running average
            current_avg = self.stats['average_processing_time']
            self.stats['average_processing_time'] = (
                (current_avg * (total_requests - 1) + processing_time) / total_requests
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive pipeline statistics.
        
        Returns:
            Dictionary with pipeline statistics
        """
        stats = self.stats.copy()
        
        # Add component statistics
        if self._text_normalizer:
            stats['component_stats']['text_normalizer'] = self._text_normalizer.get_stats()
        
        if self._number_normalizer:
            stats['component_stats']['number_normalizer'] = self._number_normalizer.get_stats()
        
        # Calculate derived metrics
        total_requests = stats['total_requests']
        if total_requests > 0:
            stats['success_rate'] = stats['successful_requests'] / total_requests
            stats['failure_rate'] = stats['failed_requests'] / total_requests
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        stats['config'] = self.config.to_dict()
        stats['mode'] = self.mode.value
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear all component caches."""
        if self._text_normalizer:
            if hasattr(self._text_normalizer, 'clear_cache'):
                self._text_normalizer.clear_cache()
        
        if self._number_normalizer:
            if hasattr(self._number_normalizer, 'clear_cache'):
                self._number_normalizer.clear_cache()
        
        self.logger.debug("Pipeline caches cleared")
    
    def cleanup(self) -> None:
        """Clean up pipeline resources."""
        if self._text_normalizer:
            self._text_normalizer.cleanup()
        
        if self._number_normalizer:
            self._number_normalizer.cleanup()
        
        self.logger.debug("Pipeline cleanup completed")
