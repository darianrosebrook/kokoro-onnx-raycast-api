"""
Base classes and interfaces for text processing components.

This module defines the abstract base classes that all text processing
components must implement, ensuring consistency and enabling polymorphism
throughout the pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """
    Context object passed through the processing pipeline.
    
    This object carries state information, metrics, and intermediate
    results between processing stages, enabling communication and
    monitoring throughout the pipeline.
    """
    # Input data
    original_text: str
    language: str = "en"
    
    # Processing state
    current_text: str = ""
    processing_stage: str = ""
    
    # Metrics and timing
    start_time: float = field(default_factory=time.time)
    stage_times: Dict[str, float] = field(default_factory=dict)
    
    # Results tracking
    normalization_steps: List[str] = field(default_factory=list)
    phoneme_method: str = "unknown"
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Quality metrics
    quality_scores: Dict[str, float] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    
    def start_stage(self, stage_name: str) -> None:
        """Start timing a processing stage."""
        self.processing_stage = stage_name
        self.stage_times[stage_name] = time.time()
        logger.debug(f"Starting stage: {stage_name}")
    
    def end_stage(self, stage_name: str) -> float:
        """End timing a processing stage and return duration."""
        if stage_name in self.stage_times:
            duration = time.time() - self.stage_times[stage_name]
            self.stage_times[stage_name] = duration
            logger.debug(f"Completed stage {stage_name} in {duration:.3f}s")
            return duration
        return 0.0
    
    def add_normalization_step(self, step: str) -> None:
        """Add a normalization step to the history."""
        self.normalization_steps.append(step)
    
    def set_quality_score(self, component: str, score: float) -> None:
        """Set a quality score for a component."""
        self.quality_scores[component] = score
    
    def set_confidence_score(self, component: str, score: float) -> None:
        """Set a confidence score for a component."""
        self.confidence_scores[component] = score
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1
    
    @property
    def total_processing_time(self) -> float:
        """Get total processing time."""
        return time.time() - self.start_time
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class ProcessorInterface(ABC):
    """
    Abstract interface for all text processing components.
    
    This interface defines the contract that all processors must implement,
    ensuring consistency and enabling composition of processing pipelines.
    """
    
    @abstractmethod
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """
        Process the text in the given context.
        
        Args:
            context: Processing context with input text and state
            
        Returns:
            Updated context with processing results
            
        Raises:
            TextProcessingError: If processing fails
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this processor is available and ready to use.
        
        Returns:
            True if processor is available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name/identifier of this processor.
        
        Returns:
            String identifier for this processor
        """
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration of this processor.
        
        Returns:
            Dictionary containing processor configuration
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics for this processor.
        
        Returns:
            Dictionary containing processor statistics
        """
        return {
            "name": self.get_name(),
            "available": self.is_available(),
            "config": self.get_config()
        }
    
    def cleanup(self) -> None:
        """Clean up resources used by this processor."""
        pass


class BaseProcessor(ProcessorInterface):
    """
    Base implementation of ProcessorInterface with common functionality.
    
    This class provides default implementations for common processor
    functionality, reducing boilerplate in concrete implementations.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the base processor.
        
        Args:
            name: Name/identifier for this processor
            config: Optional configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._available: Optional[bool] = None
        
    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self.config.copy()
    
    def is_available(self) -> bool:
        """
        Check if processor is available (with caching).
        
        Subclasses should override _check_availability() to implement
        actual availability checking.
        """
        if self._available is None:
            try:
                self._available = self._check_availability()
                if self._available:
                    self.logger.info(f"Processor {self.name} is available")
                else:
                    self.logger.warning(f"Processor {self.name} is not available")
            except Exception as e:
                self.logger.error(f"Error checking availability for {self.name}: {e}")
                self._available = False
        
        return self._available
    
    def _check_availability(self) -> bool:
        """
        Check if this processor is available.
        
        Subclasses should override this method to implement actual
        availability checking (e.g., checking for required dependencies).
        
        Returns:
            True if processor is available, False otherwise
        """
        return True
    
    def _validate_context(self, context: ProcessingContext) -> None:
        """
        Validate the processing context.
        
        Args:
            context: Processing context to validate
            
        Raises:
            ValueError: If context is invalid
        """
        if not isinstance(context, ProcessingContext):
            raise ValueError("Invalid context type")
        
        if not hasattr(context, 'current_text'):
            raise ValueError("Context missing current_text")
    
    def _log_processing_start(self, context: ProcessingContext) -> None:
        """Log the start of processing."""
        text_preview = context.current_text[:50] + "..." if len(context.current_text) > 50 else context.current_text
        self.logger.debug(f"Processing text: '{text_preview}'")
    
    def _log_processing_end(self, context: ProcessingContext, result_preview: str = "") -> None:
        """Log the end of processing."""
        if result_preview:
            preview = result_preview[:50] + "..." if len(result_preview) > 50 else result_preview
            self.logger.debug(f"Processing complete: '{preview}'")
        else:
            self.logger.debug("Processing complete")


class CacheableProcessor(BaseProcessor):
    """
    Base class for processors that support caching.
    
    This class provides caching functionality for processors that
    perform expensive operations and can benefit from result caching.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._cache: Optional[Any] = None
        self.cache_enabled = self.config.get('cache_enabled', True)
    
    def _get_cache_key(self, context: ProcessingContext) -> str:
        """
        Generate cache key for the given context.
        
        Subclasses should override this to provide appropriate cache keys.
        
        Args:
            context: Processing context
            
        Returns:
            Cache key string
        """
        return f"{self.name}:{hash(context.current_text)}:{context.language}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """
        Get cached result for the given key.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached result or None if not found
        """
        if not self.cache_enabled or self._cache is None:
            return None
        
        try:
            return self._cache.get(cache_key)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed for {cache_key}: {e}")
            return None
    
    def _set_cached_result(self, cache_key: str, result: Any) -> None:
        """
        Store result in cache.
        
        Args:
            cache_key: Cache key to store under
            result: Result to cache
        """
        if not self.cache_enabled or self._cache is None:
            return
        
        try:
            self._cache.set(cache_key, result)
        except Exception as e:
            self.logger.warning(f"Cache storage failed for {cache_key}: {e}")
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """
        Process with caching support.
        
        This method wraps the actual processing with cache lookup/storage.
        Subclasses should implement _process_uncached() for the actual logic.
        """
        cache_key = self._get_cache_key(context)
        
        # Try cache first
        if self.cache_enabled:
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                context.record_cache_hit()
                return self._apply_cached_result(context, cached_result)
            else:
                context.record_cache_miss()
        
        # Process and cache result
        result_context = self._process_uncached(context)
        
        if self.cache_enabled:
            cache_data = self._extract_cache_data(result_context)
            self._set_cached_result(cache_key, cache_data)
        
        return result_context
    
    @abstractmethod
    def _process_uncached(self, context: ProcessingContext) -> ProcessingContext:
        """
        Perform actual processing without caching.
        
        Subclasses must implement this method.
        """
        pass
    
    def _extract_cache_data(self, context: ProcessingContext) -> Any:
        """
        Extract data to cache from the processing context.
        
        Subclasses can override this to specify what data should be cached.
        """
        return context.current_text
    
    def _apply_cached_result(self, context: ProcessingContext, cached_data: Any) -> ProcessingContext:
        """
        Apply cached result to the processing context.
        
        Subclasses can override this to specify how cached data is applied.
        """
        context.current_text = cached_data
        return context
    
    def clear_cache(self) -> None:
        """Clear the processor cache."""
        if self._cache:
            self._cache.clear()
            self.logger.debug(f"Cache cleared for {self.name}")


class CompositeProcessor(BaseProcessor):
    """
    Base class for processors that compose multiple sub-processors.
    
    This class enables building complex processing pipelines by combining
    simpler processors in sequence or parallel.
    """
    
    def __init__(self, name: str, processors: List[ProcessorInterface], config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.processors = processors
    
    def is_available(self) -> bool:
        """Check if all sub-processors are available."""
        return all(processor.is_available() for processor in self.processors)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics including sub-processor stats."""
        stats = super().get_stats()
        stats['sub_processors'] = [
            processor.get_stats() for processor in self.processors
        ]
        return stats
    
    def cleanup(self) -> None:
        """Clean up all sub-processors."""
        for processor in self.processors:
            processor.cleanup()
