"""
Type definitions for the text processing system.

This module contains shared type definitions to avoid circular imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ProcessingMode(Enum):
    """Text processing mode for different use cases."""
    FAST = "fast"           # Minimal processing for speed
    BALANCED = "balanced"   # Default balanced processing
    QUALITY = "quality"     # Maximum quality processing
    STREAMING = "streaming" # Optimized for real-time streaming


@dataclass
class ProcessingResult:
    """
    Comprehensive result object containing all processing outputs.
    
    This class provides access to all intermediate and final results
    from the text processing pipeline, enabling fine-grained control
    and monitoring of the processing flow.
    """
    # Input
    original_text: str
    
    # Normalization results
    normalized_text: str
    normalization_steps: List[str] = field(default_factory=list)
    
    # Phonemization results  
    phonemes: List[str] = field(default_factory=list)
    phoneme_method: str = "unknown"
    phoneme_quality_score: float = 0.0
    
    # Segmentation results
    segments: List[str] = field(default_factory=list)
    segment_boundaries: List[int] = field(default_factory=list)
    
    # Padding and formatting
    padded_phonemes: List[str] = field(default_factory=list)
    max_length: int = 256
    truncated: bool = False
    
    # Performance metrics
    processing_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Quality metrics
    text_complexity_score: float = 0.0
    phoneme_confidence: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        if self.phonemes and self.padded_phonemes:
            self.phoneme_coverage = len(self.phonemes) / len(self.padded_phonemes)
        else:
            self.phoneme_coverage = 0.0
            
    @property
    def phoneme_count(self) -> int:
        """Get the original phoneme count."""
        return len(self.phonemes)
        
    @property
    def padded_phoneme_count(self) -> int:
        """Get the padded phoneme count."""
        return len(self.padded_phonemes)
        
    @property
    def segment_count(self) -> int:
        """Get the number of text segments."""
        return len(self.segments)
        
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.cache_hits + self.cache_misses
        return self.cache_hits / total_requests if total_requests > 0 else 0.0
