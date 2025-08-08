"""
Abbreviation normalization for expanding common abbreviations and acronyms.

This module handles the expansion of abbreviations, acronyms, units,
and other shortened forms to their full spoken equivalents.
"""

import re
from typing import Dict, Any

from .base_normalizer import BaseNormalizer


class AbbreviationNormalizer(BaseNormalizer):
    """
    Normalizer for expanding abbreviations and acronyms.
    
    This normalizer handles common abbreviations, units of measurement,
    titles, and other shortened forms that should be spoken in full.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("abbreviation_normalizer", config)
        
        self.expand_abbreviations = config.get('expand_abbreviations', True)
        self.expand_units = config.get('expand_units', True)
        self.expand_currency = config.get('expand_currency', True)
        
        # Initialize abbreviation dictionaries
        self._load_abbreviations()
    
    def _load_abbreviations(self) -> None:
        """Load abbreviation mappings."""
        # Common abbreviations
        self.abbreviations = {
            # Titles
            'mr.': 'mister',
            'mrs.': 'missus', 
            'ms.': 'miss',
            'dr.': 'doctor',
            'prof.': 'professor',
            'rev.': 'reverend',
            
            # Time and dates
            'jan.': 'january',
            'feb.': 'february',
            'mar.': 'march',
            'apr.': 'april',
            'jun.': 'june',
            'jul.': 'july',
            'aug.': 'august',
            'sep.': 'september',
            'sept.': 'september',
            'oct.': 'october',
            'nov.': 'november',
            'dec.': 'december',
            
            'mon.': 'monday',
            'tue.': 'tuesday',
            'wed.': 'wednesday',
            'thu.': 'thursday',
            'fri.': 'friday',
            'sat.': 'saturday',
            'sun.': 'sunday',
            
            # Common words
            'etc.': 'etcetera',
            'vs.': 'versus',
            'aka': 'also known as',
            'e.g.': 'for example',
            'i.e.': 'that is',
            'p.m.': 'post meridiem',
            'a.m.': 'ante meridiem',
            
            # Locations
            'st.': 'street',
            'ave.': 'avenue',
            'blvd.': 'boulevard',
            'rd.': 'road',
            'ln.': 'lane',
            'dr.': 'drive',
            'ct.': 'court',
            'pl.': 'place',
            
            # Business
            'inc.': 'incorporated',
            'corp.': 'corporation',
            'ltd.': 'limited',
            'llc': 'limited liability company',
            'co.': 'company',
        }
        
        # Units of measurement
        self.units = {
            'kg': 'kilograms',
            'g': 'grams',
            'mg': 'milligrams',
            'lb': 'pounds',
            'lbs': 'pounds',
            'oz': 'ounces',
            
            'km': 'kilometers',
            'm': 'meters',
            'cm': 'centimeters',
            'mm': 'millimeters',
            'ft': 'feet',
            'in': 'inches',
            'mi': 'miles',
            'yd': 'yards',
            
            'l': 'liters',
            'ml': 'milliliters',
            'gal': 'gallons',
            'qt': 'quarts',
            'pt': 'pints',
            'fl': 'fluid',
            
            'mph': 'miles per hour',
            'kph': 'kilometers per hour',
            'rpm': 'revolutions per minute',
            'bpm': 'beats per minute',
        }
        
        # Currency symbols
        self.currency_symbols = {
            '$': 'dollars',
            '€': 'euros',
            '£': 'pounds',
            '¥': 'yen',
            '₹': 'rupees',
        }
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for abbreviation recognition."""
        # Pattern for abbreviations (word with period)
        self.patterns['abbreviation'] = re.compile(
            r'\b(' + '|'.join(re.escape(abbr) for abbr in self.abbreviations.keys()) + r')\b',
            re.IGNORECASE
        )
        
        # Pattern for units (number followed by unit)
        unit_pattern = '|'.join(re.escape(unit) for unit in self.units.keys())
        self.patterns['units'] = re.compile(
            rf'\b(\d+(?:\.\d+)?)\s*({unit_pattern})\b',
            re.IGNORECASE
        )
        
        # Pattern for standalone units
        self.patterns['standalone_units'] = re.compile(
            r'\b(' + unit_pattern + r')\b',
            re.IGNORECASE
        )
        
        # Pattern for currency symbols
        self.patterns['currency_symbols'] = re.compile(
            r'([' + ''.join(re.escape(symbol) for symbol in self.currency_symbols.keys()) + r'])'
        )
    
    def _normalize_text(self, text: str) -> str:
        """
        Apply abbreviation normalization to text.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Text with abbreviations expanded
        """
        result = text
        
        if self.expand_abbreviations:
            result = self._expand_abbreviations(result)
        
        if self.expand_units:
            result = self._expand_units(result)
        
        if self.expand_currency:
            result = self._expand_currency_symbols(result)
        
        return result
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations."""
        def replace_abbreviation(match):
            abbr = match.group(1).lower()
            if abbr in self.abbreviations:
                return self.abbreviations[abbr]
            return match.group(1)
        
        return self._apply_pattern(text, 'abbreviation', replace_abbreviation)
    
    def _expand_units(self, text: str) -> str:
        """Expand units of measurement."""
        result = text
        
        # Handle number + unit combinations
        def replace_unit_with_number(match):
            number = match.group(1)
            unit = match.group(2).lower()
            
            if unit in self.units:
                unit_expansion = self.units[unit]
                return f"{number} {unit_expansion}"
            return match.group(0)
        
        result = self._apply_pattern(result, 'units', replace_unit_with_number)
        
        # Handle standalone units
        def replace_standalone_unit(match):
            unit = match.group(1).lower()
            if unit in self.units:
                return self.units[unit]
            return match.group(1)
        
        result = self._apply_pattern(result, 'standalone_units', replace_standalone_unit)
        
        return result
    
    def _expand_currency_symbols(self, text: str) -> str:
        """Expand currency symbols."""
        def replace_currency(match):
            symbol = match.group(1)
            if symbol in self.currency_symbols:
                return self.currency_symbols[symbol]
            return symbol
        
        return self._apply_pattern(text, 'currency_symbols', replace_currency)
    
    def add_custom_abbreviation(self, abbreviation: str, expansion: str) -> None:
        """
        Add a custom abbreviation mapping.
        
        Args:
            abbreviation: The abbreviation to recognize
            expansion: The full form to expand to
        """
        self.abbreviations[abbreviation.lower()] = expansion.lower()
        # Recompile patterns to include new abbreviation
        self._compile_patterns()
    
    def add_custom_unit(self, unit: str, expansion: str) -> None:
        """
        Add a custom unit mapping.
        
        Args:
            unit: The unit abbreviation
            expansion: The full unit name
        """
        self.units[unit.lower()] = expansion.lower()
        # Recompile patterns to include new unit
        self._compile_patterns()
    
    def get_abbreviation_stats(self, original: str, normalized: str) -> Dict[str, Any]:
        """
        Get statistics about abbreviation expansion.
        
        Args:
            original: Original text
            normalized: Normalized text
            
        Returns:
            Dictionary with expansion statistics
        """
        abbreviations_found = len(re.findall(self.patterns['abbreviation'], original))
        units_found = len(re.findall(self.patterns['units'], original))
        currency_found = len(re.findall(self.patterns['currency_symbols'], original))
        
        return {
            'abbreviations_expanded': abbreviations_found,
            'units_expanded': units_found,
            'currency_symbols_expanded': currency_found,
            'total_expansions': abbreviations_found + units_found + currency_found,
            'original_length': len(original),
            'normalized_length': len(normalized),
            'length_increase': len(normalized) - len(original)
        }
