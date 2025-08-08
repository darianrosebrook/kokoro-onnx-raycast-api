"""
Custom exceptions for text processing pipeline.

This module defines a hierarchy of exceptions specific to text processing
operations, enabling fine-grained error handling and debugging.
"""

class TextProcessingError(Exception):
    """Base exception for all text processing errors."""
    
    def __init__(self, message: str, original_text: str = "", stage: str = ""):
        super().__init__(message)
        self.original_text = original_text
        self.stage = stage
        
    def __str__(self):
        base_msg = super().__str__()
        if self.stage:
            base_msg = f"[{self.stage}] {base_msg}"
        if self.original_text:
            base_msg += f" (text: '{self.original_text[:50]}...')"
        return base_msg


class NormalizationError(TextProcessingError):
    """Exception raised during text normalization."""
    
    def __init__(self, message: str, original_text: str = "", normalizer: str = ""):
        super().__init__(message, original_text, f"normalization/{normalizer}")
        self.normalizer = normalizer


class PhonemeError(TextProcessingError):
    """Exception raised during phoneme conversion."""
    
    def __init__(self, message: str, original_text: str = "", backend: str = ""):
        super().__init__(message, original_text, f"phonemization/{backend}")
        self.backend = backend


class SegmentationError(TextProcessingError):
    """Exception raised during text segmentation."""
    
    def __init__(self, message: str, original_text: str = "", segmenter: str = ""):
        super().__init__(message, original_text, f"segmentation/{segmenter}")
        self.segmenter = segmenter


class CacheError(TextProcessingError):
    """Exception raised during cache operations."""
    
    def __init__(self, message: str, cache_key: str = ""):
        super().__init__(message, "", "cache")
        self.cache_key = cache_key


class ConfigurationError(TextProcessingError):
    """Exception raised for configuration-related issues."""
    
    def __init__(self, message: str, config_key: str = ""):
        super().__init__(message, "", "configuration")
        self.config_key = config_key
