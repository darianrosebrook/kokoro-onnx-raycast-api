"""
Core text normalization for cleaning and standardizing text.

This module handles basic text cleaning operations including whitespace
normalization, control character removal, punctuation standardization,
and other fundamental text preprocessing operations.
"""

import re
import unicodedata
from typing import Dict, Any

from .base_normalizer import BaseNormalizer
from ..config import NormalizationLevel


class TextNormalizer(BaseNormalizer):
    """
    Core text normalizer for basic cleaning and standardization.
    
    This normalizer handles fundamental text preprocessing operations
    that are typically required before any other processing can occur.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("text_normalizer", config)
        self.level = config.get('level', NormalizationLevel.STANDARD)
        self.normalize_whitespace = config.get('normalize_whitespace', True)
        self.remove_control_chars = config.get('remove_control_chars', True)
        self.normalize_punctuation = config.get('normalize_punctuation', True)
        self.normalize_quotes = config.get('normalize_quotes', True)
        self.preserve_case = config.get('preserve_case', True)
        self.normalize_case = config.get('normalize_case', 'none')
        self.custom_replacements = config.get('custom_replacements', {})
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for text normalization."""
        # Whitespace patterns
        self.patterns['whitespace'] = re.compile(r'\s+')
        self.patterns['leading_trailing_ws'] = re.compile(r'^\s+|\s+$')
        
        # Control character patterns
        self.patterns['control_chars'] = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
        
        # Punctuation patterns
        self.patterns['repeated_punct'] = re.compile(r'([.!?])\1{2,}')  # More than 2 repeats
        self.patterns['punct_spacing'] = re.compile(r'([.!?;:,])([^\s])')
        self.patterns['multiple_punct'] = re.compile(r'([.!?])\s*([.!?])')
        
        # Quote patterns
        self.patterns['smart_quotes'] = re.compile(r'[""''‚„]')
        self.patterns['fancy_quotes'] = re.compile(r'[«»‹›]')
        
        # Special character patterns
        self.patterns['ellipsis'] = re.compile(r'\.{3,}')
        self.patterns['em_dash'] = re.compile(r'—')
        self.patterns['en_dash'] = re.compile(r'–')
        
        # Unicode normalization patterns
        self.patterns['combining_chars'] = re.compile(r'[\u0300-\u036f]')  # Combining diacritical marks
    
    def _normalize_text(self, text: str) -> str:
        """
        Apply text normalization based on configuration level.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text
        """
        if not self._validate_input(text):
            return text
        
        result = text
        
        # Apply normalization based on level
        if self.level == NormalizationLevel.MINIMAL:
            result = self._apply_minimal_normalization(result)
        elif self.level == NormalizationLevel.STANDARD:
            result = self._apply_standard_normalization(result)
        elif self.level == NormalizationLevel.AGGRESSIVE:
            result = self._apply_aggressive_normalization(result)
        
        # Apply custom replacements
        result = self._apply_custom_replacements(result)
        
        return result
    
    def _apply_minimal_normalization(self, text: str) -> str:
        """Apply minimal normalization (whitespace only)."""
        result = text
        
        if self.normalize_whitespace:
            # Basic whitespace normalization
            result = self._apply_pattern(result, 'whitespace', ' ')
            result = result.strip()
        
        return result
    
    def _apply_standard_normalization(self, text: str) -> str:
        """Apply standard normalization."""
        result = text
        
        # Unicode normalization
        result = unicodedata.normalize('NFKC', result)
        
        # Remove control characters
        if self.remove_control_chars:
            result = self._apply_pattern(result, 'control_chars', '')
        
        # Normalize whitespace
        if self.normalize_whitespace:
            result = self._apply_pattern(result, 'whitespace', ' ')
            result = result.strip()
        
        # Normalize punctuation
        if self.normalize_punctuation:
            result = self._normalize_punctuation(result)
        
        # Normalize quotes
        if self.normalize_quotes:
            result = self._normalize_quotes(result)
        
        # Case normalization
        if not self.preserve_case:
            result = self._normalize_case_text(result)
        
        return result
    
    def _apply_aggressive_normalization(self, text: str) -> str:
        """Apply aggressive normalization."""
        result = self._apply_standard_normalization(text)
        
        # Additional aggressive normalizations
        
        # Remove combining diacritical marks
        result = self._apply_pattern(result, 'combining_chars', '')
        
        # Normalize special characters
        result = self._normalize_special_chars(result)
        
        # Remove excessive punctuation
        result = self._remove_excessive_punctuation(result)
        
        return result
    
    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation spacing and repetition."""
        result = text
        
        # Fix spacing after punctuation
        result = self._apply_pattern(
            result, 
            'punct_spacing', 
            lambda m: f"{m.group(1)} {m.group(2)}"
        )
        
        # Reduce repeated punctuation (keep max 2)
        result = self._apply_pattern(
            result,
            'repeated_punct',
            lambda m: m.group(1) * 2
        )
        
        # Handle multiple different punctuation marks
        result = self._apply_pattern(
            result,
            'multiple_punct',
            lambda m: f"{m.group(1)} {m.group(2)}"
        )
        
        return result
    
    def _normalize_quotes(self, text: str) -> str:
        """Normalize various quote characters to standard ASCII."""
        result = text
        
        # Smart quotes to regular quotes
        result = self._apply_pattern(result, 'smart_quotes', '"')
        
        # Fancy quotes to regular quotes
        result = self._apply_pattern(result, 'fancy_quotes', '"')
        
        return result
    
    def _normalize_special_chars(self, text: str) -> str:
        """Normalize special characters to ASCII equivalents."""
        result = text
        
        # Ellipsis to three dots
        result = self._apply_pattern(result, 'ellipsis', '...')
        
        # Em dash to double hyphen
        result = self._apply_pattern(result, 'em_dash', '--')
        
        # En dash to single hyphen
        result = self._apply_pattern(result, 'en_dash', '-')
        
        return result
    
    def _remove_excessive_punctuation(self, text: str) -> str:
        """Remove or reduce excessive punctuation."""
        result = text
        
        # Remove more than 3 consecutive identical punctuation marks
        excessive_punct = re.compile(r'([.!?,:;])\1{3,}')
        result = excessive_punct.sub(lambda m: m.group(1) * 3, result)
        
        return result
    
    def _normalize_case_text(self, text: str) -> str:
        """Apply case normalization."""
        if self.normalize_case == 'lower':
            return text.lower()
        elif self.normalize_case == 'upper':
            return text.upper()
        elif self.normalize_case == 'title':
            return text.title()
        else:
            return text
    
    def _apply_custom_replacements(self, text: str) -> str:
        """Apply custom text replacements."""
        result = text
        
        for old, new in self.custom_replacements.items():
            try:
                # Support regex replacements if old text starts with 'regex:'
                if old.startswith('regex:'):
                    pattern = re.compile(old[6:])  # Remove 'regex:' prefix
                    result = pattern.sub(new, result)
                else:
                    result = result.replace(old, new)
            except Exception as e:
                self.logger.warning(f"Custom replacement failed for '{old}' -> '{new}': {e}")
        
        return result
    
    def _should_apply_normalization(self, text: str) -> bool:
        """Check if text needs normalization."""
        if not text or not text.strip():
            return False
        
        # Check for obvious normalization needs
        if self.normalize_whitespace and re.search(r'\s{2,}', text):
            return True
        
        if self.remove_control_chars and re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', text):
            return True
        
        if self.normalize_quotes and re.search(r'[""''‚„«»‹›]', text):
            return True
        
        return True  # Default to applying normalization
    
    def get_normalization_stats(self, original: str, normalized: str) -> Dict[str, Any]:
        """
        Get statistics about the normalization process.
        
        Args:
            original: Original text
            normalized: Normalized text
            
        Returns:
            Dictionary with normalization statistics
        """
        return {
            'original_length': len(original),
            'normalized_length': len(normalized),
            'length_change': len(normalized) - len(original),
            'whitespace_normalized': original != re.sub(r'\s+', ' ', original.strip()),
            'characters_changed': sum(1 for a, b in zip(original, normalized) if a != b),
            'level': self.level.value,
            'operations_applied': self._get_applied_operations(original, normalized)
        }
    
    def _get_applied_operations(self, original: str, normalized: str) -> list:
        """Determine which operations were applied during normalization."""
        operations = []
        
        # Check for whitespace changes
        if re.sub(r'\s+', ' ', original.strip()) != original:
            operations.append('whitespace_normalization')
        
        # Check for control character removal
        if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', original):
            operations.append('control_char_removal')
        
        # Check for quote normalization
        if re.search(r'[""''‚„«»‹›]', original):
            operations.append('quote_normalization')
        
        # Check for punctuation changes
        original_punct = re.findall(r'[.!?,:;]', original)
        normalized_punct = re.findall(r'[.!?,:;]', normalized)
        if original_punct != normalized_punct:
            operations.append('punctuation_normalization')
        
        return operations
