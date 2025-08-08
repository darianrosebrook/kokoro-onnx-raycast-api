"""
Number normalization for converting numeric expressions to words.

This module handles the conversion of various numeric formats including
integers, decimals, fractions, percentages, ordinals, dates, times,
and currency to their spoken equivalents.
"""

import re
from datetime import datetime
from typing import Dict, Any, Match, Optional
import logging

try:
    import inflect
    _inflect_available = True
except ImportError:
    _inflect_available = False

from .base_normalizer import BaseNormalizer

logger = logging.getLogger(__name__)


class NumberNormalizer(BaseNormalizer):
    """
    Normalizer for converting numbers and numeric expressions to words.
    
    This normalizer handles various types of numeric content including:
    - Integers and decimals
    - Fractions and percentages  
    - Ordinal numbers
    - Dates and times
    - Currency amounts
    - Measurements and units
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("number_normalizer", config)
        
        # Configuration options
        self.expand_numbers = config.get('expand_numbers', True)
        self.expand_ordinals = config.get('expand_ordinals', True)
        self.expand_decimals = config.get('expand_decimals', True)
        self.expand_fractions = config.get('expand_fractions', True)
        self.expand_dates = config.get('expand_dates', True)
        self.expand_times = config.get('expand_times', True)
        self.expand_currency = config.get('expand_currency', True)
        self.date_format = config.get('date_format', 'natural')
        
        # Initialize inflect engine
        self.inflect_engine = None
        if _inflect_available:
            try:
                self.inflect_engine = inflect.engine()
            except Exception as e:
                logger.warning(f"Failed to initialize inflect engine: {e}")
    
    def _check_availability(self) -> bool:
        """Check if the normalizer can function (requires inflect)."""
        return _inflect_available and self.inflect_engine is not None
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for number recognition."""
        # Basic number patterns
        self.patterns['integer'] = re.compile(r'\b(\d{1,3}(?:,\d{3})*|\d+)\b')
        self.patterns['decimal'] = re.compile(r'\b\d+\.\d+\b')
        self.patterns['fraction'] = re.compile(r'\b(\d+)/(\d+)\b')
        self.patterns['percentage'] = re.compile(r'\b(\d+(?:\.\d+)?)\s*%\b')
        
        # Ordinal patterns
        self.patterns['ordinal'] = re.compile(r'\b(\d+)(?:st|nd|rd|th)\b', re.IGNORECASE)
        
        # Date patterns
        self.patterns['iso_date'] = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
        self.patterns['us_date'] = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
        self.patterns['eu_date'] = re.compile(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b')
        
        # Time patterns
        self.patterns['time_24h'] = re.compile(r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b')
        self.patterns['time_12h'] = re.compile(r'\b(\d{1,2}):(\d{2})\s*(AM|PM)\b', re.IGNORECASE)
        
        # Currency patterns
        self.patterns['currency_dollar'] = re.compile(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b')
        self.patterns['currency_euro'] = re.compile(r'€(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b')
        self.patterns['currency_pound'] = re.compile(r'£(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b')
        
        # Unit patterns
        self.patterns['measurements'] = re.compile(
            r'\b(\d+(?:\.\d+)?)\s*(kg|g|mg|lb|oz|km|m|cm|mm|ft|in|mi|l|ml|gal)\b',
            re.IGNORECASE
        )
    
    def _normalize_text(self, text: str) -> str:
        """
        Apply number normalization to the text.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Text with numbers converted to words
        """
        if not self.is_available():
            logger.warning("NumberNormalizer not available, skipping normalization")
            return text
        
        result = text
        
        # Apply normalizations in order (most specific first)
        if self.expand_currency:
            result = self._normalize_currency(result)
        
        if self.expand_dates:
            result = self._normalize_dates(result)
        
        if self.expand_times:
            result = self._normalize_times(result)
        
        if self.expand_fractions:
            result = self._normalize_fractions(result)
        
        if self.expand_decimals:
            result = self._normalize_decimals(result)
        
        if self.expand_ordinals:
            result = self._normalize_ordinals(result)
        
        if self.expand_numbers:
            result = self._normalize_integers(result)
        
        # Normalize percentages
        result = self._normalize_percentages(result)
        
        # Normalize measurements
        result = self._normalize_measurements(result)
        
        return result
    
    def _normalize_integers(self, text: str) -> str:
        """Convert integer numbers to words."""
        def replace_integer(match: Match) -> str:
            number_str = match.group(1).replace(',', '')
            try:
                number = int(number_str)
                # Handle large numbers appropriately
                if abs(number) > 1000000000:  # > 1 billion
                    return self._format_large_number(number)
                else:
                    return self.inflect_engine.number_to_words(number)
            except (ValueError, AttributeError):
                return match.group(0)  # Return original if conversion fails
        
        return self._apply_pattern(text, 'integer', replace_integer)
    
    def _normalize_decimals(self, text: str) -> str:
        """Convert decimal numbers to words."""
        def replace_decimal(match: Match) -> str:
            try:
                number = float(match.group(0))
                if number == int(number):
                    # It's actually a whole number
                    return self.inflect_engine.number_to_words(int(number))
                else:
                    # Split into integer and decimal parts
                    integer_part = int(number)
                    decimal_part = match.group(0).split('.')[1]
                    
                    integer_words = self.inflect_engine.number_to_words(integer_part) if integer_part != 0 else ""
                    decimal_words = " ".join(self.inflect_engine.number_to_words(int(d)) for d in decimal_part)
                    
                    if integer_words:
                        return f"{integer_words} point {decimal_words}"
                    else:
                        return f"zero point {decimal_words}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        return self._apply_pattern(text, 'decimal', replace_decimal)
    
    def _normalize_fractions(self, text: str) -> str:
        """Convert fractions to words."""
        def replace_fraction(match: Match) -> str:
            try:
                numerator = int(match.group(1))
                denominator = int(match.group(2))
                
                if numerator == 1 and denominator == 2:
                    return "half"
                elif numerator == 1 and denominator == 4:
                    return "quarter"
                elif numerator == 3 and denominator == 4:
                    return "three quarters"
                else:
                    num_words = self.inflect_engine.number_to_words(numerator)
                    den_words = self.inflect_engine.ordinal(self.inflect_engine.number_to_words(denominator))
                    
                    if numerator > 1:
                        den_words = self.inflect_engine.plural(den_words)
                    
                    return f"{num_words} {den_words}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        return self._apply_pattern(text, 'fraction', replace_fraction)
    
    def _normalize_ordinals(self, text: str) -> str:
        """Convert ordinal numbers to words."""
        def replace_ordinal(match: Match) -> str:
            try:
                number = int(match.group(1))
                return self.inflect_engine.ordinal(self.inflect_engine.number_to_words(number))
            except (ValueError, AttributeError):
                return match.group(0)
        
        return self._apply_pattern(text, 'ordinal', replace_ordinal)
    
    def _normalize_percentages(self, text: str) -> str:
        """Convert percentages to words."""
        def replace_percentage(match: Match) -> str:
            try:
                number = float(match.group(1))
                if number == int(number):
                    number_words = self.inflect_engine.number_to_words(int(number))
                else:
                    number_words = self._decimal_to_words(number)
                
                return f"{number_words} percent"
            except (ValueError, AttributeError):
                return match.group(0)
        
        return self._apply_pattern(text, 'percentage', replace_percentage)
    
    def _normalize_dates(self, text: str) -> str:
        """Convert dates to words."""
        result = text
        
        # ISO dates (YYYY-MM-DD)
        result = self._apply_pattern(result, 'iso_date', self._format_iso_date)
        
        # US dates (MM/DD/YYYY)
        result = self._apply_pattern(result, 'us_date', self._format_us_date)
        
        # European dates (DD.MM.YYYY)
        result = self._apply_pattern(result, 'eu_date', self._format_eu_date)
        
        return result
    
    def _normalize_times(self, text: str) -> str:
        """Convert times to words."""
        result = text
        
        # 24-hour format
        result = self._apply_pattern(result, 'time_24h', self._format_24h_time)
        
        # 12-hour format
        result = self._apply_pattern(result, 'time_12h', self._format_12h_time)
        
        return result
    
    def _normalize_currency(self, text: str) -> str:
        """Convert currency amounts to words."""
        result = text
        
        # Dollar amounts
        result = self._apply_pattern(result, 'currency_dollar', lambda m: self._format_currency(m.group(1), "dollar"))
        
        # Euro amounts
        result = self._apply_pattern(result, 'currency_euro', lambda m: self._format_currency(m.group(1), "euro"))
        
        # Pound amounts
        result = self._apply_pattern(result, 'currency_pound', lambda m: self._format_currency(m.group(1), "pound"))
        
        return result
    
    def _normalize_measurements(self, text: str) -> str:
        """Convert measurements to words."""
        def replace_measurement(match: Match) -> str:
            try:
                number = float(match.group(1))
                unit = match.group(2).lower()
                
                number_words = self._number_to_words(number)
                unit_words = self._unit_to_words(unit, number != 1)
                
                return f"{number_words} {unit_words}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        return self._apply_pattern(text, 'measurements', replace_measurement)
    
    def _format_iso_date(self, match: Match) -> str:
        """Format ISO date (YYYY-MM-DD)."""
        try:
            year, month, day = match.groups()
            date_obj = datetime(int(year), int(month), int(day))
            
            if self.date_format == 'natural':
                return date_obj.strftime("the %d of %B, %Y").replace(' 0', ' ')
            else:
                month_name = date_obj.strftime("%B")
                day_ord = self.inflect_engine.ordinal(self.inflect_engine.number_to_words(int(day)))
                year_words = self.inflect_engine.number_to_words(int(year))
                return f"the {day_ord} of {month_name}, {year_words}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    def _format_us_date(self, match: Match) -> str:
        """Format US date (MM/DD/YYYY)."""
        try:
            month, day, year = match.groups()
            date_obj = datetime(int(year), int(month), int(day))
            
            month_name = date_obj.strftime("%B")
            day_ord = self.inflect_engine.ordinal(self.inflect_engine.number_to_words(int(day)))
            year_words = self.inflect_engine.number_to_words(int(year))
            
            return f"{month_name} {day_ord}, {year_words}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    def _format_eu_date(self, match: Match) -> str:
        """Format European date (DD.MM.YYYY)."""
        try:
            day, month, year = match.groups()
            date_obj = datetime(int(year), int(month), int(day))
            
            month_name = date_obj.strftime("%B")
            day_ord = self.inflect_engine.ordinal(self.inflect_engine.number_to_words(int(day)))
            year_words = self.inflect_engine.number_to_words(int(year))
            
            return f"the {day_ord} of {month_name}, {year_words}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    def _format_24h_time(self, match: Match) -> str:
        """Format 24-hour time."""
        try:
            hour, minute = int(match.group(1)), int(match.group(2))
            seconds = int(match.group(3)) if match.group(3) else None
            
            hour_words = self.inflect_engine.number_to_words(hour)
            minute_words = self.inflect_engine.number_to_words(minute)
            
            if seconds is not None and seconds > 0:
                second_words = self.inflect_engine.number_to_words(seconds)
                return f"{hour_words} {minute_words} and {second_words} seconds"
            else:
                return f"{hour_words} {minute_words}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    def _format_12h_time(self, match: Match) -> str:
        """Format 12-hour time with AM/PM."""
        try:
            hour, minute, period = int(match.group(1)), int(match.group(2)), match.group(3).upper()
            
            hour_words = self.inflect_engine.number_to_words(hour)
            minute_words = self.inflect_engine.number_to_words(minute)
            period_words = "in the morning" if period == "AM" else "in the evening"
            
            if minute == 0:
                return f"{hour_words} o'clock {period_words}"
            else:
                return f"{hour_words} {minute_words} {period_words}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    def _format_currency(self, amount_str: str, currency: str) -> str:
        """Format currency amounts."""
        try:
            amount = float(amount_str.replace(',', ''))
            
            if amount == int(amount):
                # Whole amount
                amount_words = self.inflect_engine.number_to_words(int(amount))
                currency_word = currency if amount == 1 else f"{currency}s"
                return f"{amount_words} {currency_word}"
            else:
                # Amount with cents
                dollars = int(amount)
                cents = round((amount - dollars) * 100)
                
                dollar_words = self.inflect_engine.number_to_words(dollars) if dollars > 0 else ""
                cent_words = self.inflect_engine.number_to_words(cents) if cents > 0 else ""
                
                parts = []
                if dollars > 0:
                    currency_word = currency if dollars == 1 else f"{currency}s"
                    parts.append(f"{dollar_words} {currency_word}")
                
                if cents > 0:
                    cent_unit = "cent" if cents == 1 else "cents"
                    parts.append(f"{cent_words} {cent_unit}")
                
                return " and ".join(parts) if parts else f"zero {currency}s"
        except (ValueError, AttributeError):
            return f"{amount_str} {currency}s"
    
    def _unit_to_words(self, unit: str, plural: bool) -> str:
        """Convert unit abbreviations to words."""
        unit_map = {
            'kg': 'kilogram', 'g': 'gram', 'mg': 'milligram',
            'lb': 'pound', 'oz': 'ounce',
            'km': 'kilometer', 'm': 'meter', 'cm': 'centimeter', 'mm': 'millimeter',
            'ft': 'foot', 'in': 'inch', 'mi': 'mile',
            'l': 'liter', 'ml': 'milliliter', 'gal': 'gallon'
        }
        
        unit_word = unit_map.get(unit.lower(), unit)
        
        if plural and unit_word != unit:
            # Special cases for pluralization
            if unit_word == 'foot':
                return 'feet'
            else:
                return self.inflect_engine.plural(unit_word) if self.inflect_engine else f"{unit_word}s"
        
        return unit_word
    
    def _number_to_words(self, number: float) -> str:
        """Convert a number to words."""
        if number == int(number):
            return self.inflect_engine.number_to_words(int(number))
        else:
            return self._decimal_to_words(number)
    
    def _decimal_to_words(self, number: float) -> str:
        """Convert decimal number to words."""
        if number == int(number):
            return self.inflect_engine.number_to_words(int(number))
        
        str_number = str(number)
        if '.' in str_number:
            integer_part, decimal_part = str_number.split('.')
            integer_words = self.inflect_engine.number_to_words(int(integer_part)) if int(integer_part) != 0 else ""
            decimal_words = " ".join(self.inflect_engine.number_to_words(int(d)) for d in decimal_part)
            
            if integer_words:
                return f"{integer_words} point {decimal_words}"
            else:
                return f"zero point {decimal_words}"
        else:
            return self.inflect_engine.number_to_words(int(number))
    
    def _format_large_number(self, number: int) -> str:
        """Format very large numbers in a readable way."""
        if abs(number) >= 1000000000000:  # Trillion
            return f"{number / 1000000000000:.1f} trillion"
        elif abs(number) >= 1000000000:  # Billion
            return f"{number / 1000000000:.1f} billion"
        else:
            return self.inflect_engine.number_to_words(number)
