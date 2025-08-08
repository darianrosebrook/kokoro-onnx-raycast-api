"""
Base normalizer class for text normalization components.

This module provides the foundation for all text normalization operations,
ensuring consistent behavior and enabling composition of normalizers.
"""

from abc import abstractmethod
from typing import Dict, Any, Pattern, List, Tuple
import re
import logging

from ..core.base import BaseProcessor, ProcessingContext
from ..core.exceptions import NormalizationError

logger = logging.getLogger(__name__)


class BaseNormalizer(BaseProcessor):
    """
    Abstract base class for text normalizers.
    
    This class provides common functionality for text normalization
    operations including pattern matching, text validation, and
    error handling.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.patterns: Dict[str, Pattern] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """
        Compile regex patterns used by this normalizer.
        
        Subclasses should override this method to define their patterns.
        Patterns are compiled once at initialization for performance.
        """
        pass
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """
        Process text normalization on the given context.
        
        Args:
            context: Processing context with text to normalize
            
        Returns:
            Updated context with normalized text
            
        Raises:
            NormalizationError: If normalization fails
        """
        self._validate_context(context)
        
        if not context.current_text:
            return context
        
        context.start_stage(self.name)
        
        try:
            self._log_processing_start(context)
            
            original_text = context.current_text
            normalized_text = self._normalize_text(context.current_text)
            
            context.current_text = normalized_text
            
            # Track changes
            if original_text != normalized_text:
                context.add_normalization_step(f"{self.name}: applied")
                self.logger.debug(f"Normalization applied: '{original_text[:30]}...' -> '{normalized_text[:30]}...'")
            else:
                self.logger.debug(f"No normalization needed for {self.name}")
            
            self._log_processing_end(context, normalized_text)
            
        except Exception as e:
            error_msg = f"Normalization failed in {self.name}: {e}"
            self.logger.error(error_msg)
            raise NormalizationError(error_msg, context.current_text, self.name) from e
        finally:
            context.end_stage(self.name)
        
        return context
    
    @abstractmethod
    def _normalize_text(self, text: str) -> str:
        """
        Perform the actual text normalization.
        
        Subclasses must implement this method to define their specific
        normalization logic.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text
        """
        pass
    
    def _apply_pattern(self, text: str, pattern_name: str, replacement_func) -> str:
        """
        Apply a compiled pattern with the given replacement function.
        
        Args:
            text: Input text
            pattern_name: Name of the compiled pattern to use
            replacement_func: Function to generate replacements
            
        Returns:
            Text with pattern applications
        """
        if pattern_name not in self.patterns:
            self.logger.warning(f"Pattern '{pattern_name}' not found in {self.name}")
            return text
        
        pattern = self.patterns[pattern_name]
        
        try:
            return pattern.sub(replacement_func, text)
        except Exception as e:
            self.logger.error(f"Error applying pattern '{pattern_name}': {e}")
            return text
    
    def _find_matches(self, text: str, pattern_name: str) -> List[Tuple[int, int, str]]:
        """
        Find all matches for a pattern in the text.
        
        Args:
            text: Input text to search
            pattern_name: Name of the compiled pattern
            
        Returns:
            List of (start, end, match_text) tuples
        """
        if pattern_name not in self.patterns:
            return []
        
        pattern = self.patterns[pattern_name]
        matches = []
        
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), match.group()))
        
        return matches
    
    def _safe_replace(self, text: str, old: str, new: str, max_replacements: int = -1) -> str:
        """
        Safely replace text with error handling.
        
        Args:
            text: Input text
            old: Text to replace
            new: Replacement text
            max_replacements: Maximum number of replacements (-1 for all)
            
        Returns:
            Text with replacements applied
        """
        try:
            if max_replacements == -1:
                return text.replace(old, new)
            else:
                return text.replace(old, new, max_replacements)
        except Exception as e:
            self.logger.error(f"Error in safe_replace: {e}")
            return text
    
    def _validate_input(self, text: str) -> bool:
        """
        Validate input text for normalization.
        
        Args:
            text: Input text to validate
            
        Returns:
            True if text is valid for normalization
        """
        if not isinstance(text, str):
            return False
        
        # Check for reasonable length limits
        max_length = self.config.get('max_text_length', 10000)
        if len(text) > max_length:
            self.logger.warning(f"Text length {len(text)} exceeds maximum {max_length}")
            return False
        
        return True
    
    def _should_apply_normalization(self, text: str) -> bool:
        """
        Determine if normalization should be applied to the text.
        
        Subclasses can override this to implement specific conditions
        for when normalization should be applied.
        
        Args:
            text: Input text
            
        Returns:
            True if normalization should be applied
        """
        return True
    
    def get_patterns(self) -> Dict[str, str]:
        """
        Get the regex patterns used by this normalizer.
        
        Returns:
            Dictionary mapping pattern names to pattern strings
        """
        return {name: pattern.pattern for name, pattern in self.patterns.items()}


class CompositeNormalizer(BaseNormalizer):
    """
    Normalizer that combines multiple normalizers in sequence.
    
    This class enables building complex normalization pipelines by
    combining simpler normalizers in a specific order.
    """
    
    def __init__(self, name: str, normalizers: List[BaseNormalizer], config: Dict[str, Any]):
        super().__init__(name, config)
        self.normalizers = normalizers
    
    def _normalize_text(self, text: str) -> str:
        """Apply all normalizers in sequence."""
        result = text
        
        for normalizer in self.normalizers:
            if normalizer.is_available() and normalizer._should_apply_normalization(result):
                try:
                    # Create a temporary context for sub-normalizer
                    temp_context = ProcessingContext(
                        original_text=text,
                        current_text=result
                    )
                    temp_context = normalizer.process(temp_context)
                    result = temp_context.current_text
                except Exception as e:
                    self.logger.error(f"Sub-normalizer {normalizer.name} failed: {e}")
                    # Continue with other normalizers
        
        return result
    
    def is_available(self) -> bool:
        """Check if at least one sub-normalizer is available."""
        return any(normalizer.is_available() for normalizer in self.normalizers)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics including sub-normalizer stats."""
        stats = super().get_stats()
        stats['sub_normalizers'] = [
            normalizer.get_stats() for normalizer in self.normalizers
        ]
        return stats
