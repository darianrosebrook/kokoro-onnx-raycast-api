"""
Text complexity analysis for processing optimization.

This module analyzes text complexity including character distribution,
phoneme complexity, and linguistic patterns to provide optimization
guidance for TTS processing.
"""

import logging
from functools import lru_cache
from typing import Dict, Any


class TextComplexityAnalyzer:
    """
    Analyzes text complexity for processing optimization.

    This analyzer evaluates various aspects of text complexity including
    character distribution, phoneme complexity, and linguistic patterns
    to provide optimization guidance for TTS processing.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".TextComplexityAnalyzer")

        # Character complexity weights
        self.char_weights = {
            'letters': 1.0,
            'digits': 1.1,
            'punctuation': 1.2,
            'special': 1.5,
            'unicode': 2.0
        }

        # Phoneme complexity patterns
        self.complex_phonemes = {
            'consonant_clusters': 1.3,
            'vowel_combinations': 1.2,
            'silent_letters': 1.4,
            'foreign_sounds': 1.5
        }

    @lru_cache(maxsize=1024)
    def _complexity_cache_key(self, text: str) -> float:
        """Cached wrapper for complexity calculation."""
        return self._calculate_complexity_impl(text)
    
    def _calculate_complexity_impl(self, text: str) -> float:
        """
        Calculate text complexity using multiple analysis methods.
        
        @param text: Input text to analyze
        @returns: Complexity score (0.0 to 1.0)
        """
        if not text or len(text.strip()) == 0:
            return 0.0
        
        # Normalize text for consistent analysis
        normalized_text = text.strip().lower()
        
        # Calculate various complexity factors
        char_complexity = self._analyze_character_complexity(normalized_text)
        length_complexity = self._analyze_length_complexity(normalized_text)
        linguistic_complexity = self._analyze_linguistic_complexity(normalized_text)
        
        # Weighted combination of factors
        complexity = (
            char_complexity * 0.4 +
            length_complexity * 0.3 +
            linguistic_complexity * 0.3
        )
        
        return min(complexity, 1.0)
    
    def calculate_complexity(self, text: str) -> float:
        """
        Calculate overall text complexity score.

        @param text: Text to analyze
        @returns: Complexity score (0.0 to 1.0)
        """
        return self._complexity_cache_key(text)

    def _analyze_character_complexity(self, text: str) -> float:
        """Analyze character distribution complexity."""
        if not text:
            return 0.0

        char_counts = {
            'letters': 0,
            'digits': 0,
            'punctuation': 0,
            'special': 0,
            'unicode': 0
        }

        for char in text:
            if char.isalpha():
                char_counts['letters'] += 1
            elif char.isdigit():
                char_counts['digits'] += 1
            elif char in '.,!?;:':
                char_counts['punctuation'] += 1
            elif ord(char) > 127:
                char_counts['unicode'] += 1
            else:
                char_counts['special'] += 1

        # Calculate weighted complexity
        total_chars = len(text)
        complexity = 0.0

        for char_type, count in char_counts.items():
            if total_chars > 0:
                ratio = count / total_chars
                complexity += ratio * self.char_weights[char_type]

        return complexity / 2.0  # Normalize to reasonable range

    def _analyze_length_complexity(self, text: str) -> float:
        """Analyze text length complexity."""
        text_length = len(text)

        # Length complexity curve
        if text_length < 50:
            return 0.2
        elif text_length < 200:
            return 0.4
        elif text_length < 500:
            return 0.6
        elif text_length < 1000:
            return 0.8
        else:
            return 1.0

    def _analyze_linguistic_complexity(self, text: str) -> float:
        """Analyze linguistic complexity patterns."""
        # Simple heuristic-based linguistic analysis
        complexity = 0.0

        # Count difficult patterns
        difficult_patterns = [
            'tion', 'sion', 'ough', 'augh', 'eigh',
            'ph', 'gh', 'ch', 'sh', 'th', 'wh',
            'qu', 'x', 'z'
        ]

        pattern_count = 0
        for pattern in difficult_patterns:
            pattern_count += text.lower().count(pattern)

        # Calculate complexity based on pattern density
        if len(text) > 0:
            complexity = min(1.0, pattern_count / len(text) * 10)

        return complexity

    def analyze_text_detailed(self, text: str) -> Dict[str, Any]:
        """
        Perform detailed text analysis with breakdown of complexity factors.
        
        @param text: Text to analyze
        @returns: Detailed analysis results
        """
        if not text or len(text.strip()) == 0:
            return {
                'overall_complexity': 0.0,
                'character_complexity': 0.0,
                'length_complexity': 0.0,
                'linguistic_complexity': 0.0,
                'text_length': 0,
                'character_distribution': {},
                'linguistic_patterns': {},
                'recommendations': []
            }

        normalized_text = text.strip().lower()
        
        # Calculate individual complexity components
        char_complexity = self._analyze_character_complexity(normalized_text)
        length_complexity = self._analyze_length_complexity(normalized_text)
        linguistic_complexity = self._analyze_linguistic_complexity(normalized_text)
        
        # Overall complexity
        overall_complexity = (
            char_complexity * 0.4 +
            length_complexity * 0.3 +
            linguistic_complexity * 0.3
        )
        
        # Character distribution analysis
        char_distribution = self._get_character_distribution(text)
        
        # Linguistic pattern analysis
        linguistic_patterns = self._get_linguistic_patterns(normalized_text)
        
        # Generate recommendations
        recommendations = self._generate_complexity_recommendations(
            overall_complexity, char_complexity, length_complexity, linguistic_complexity
        )
        
        return {
            'overall_complexity': min(overall_complexity, 1.0),
            'character_complexity': char_complexity,
            'length_complexity': length_complexity,
            'linguistic_complexity': linguistic_complexity,
            'text_length': len(text),
            'character_distribution': char_distribution,
            'linguistic_patterns': linguistic_patterns,
            'recommendations': recommendations
        }

    def _get_character_distribution(self, text: str) -> Dict[str, Any]:
        """Get detailed character distribution analysis."""
        char_counts = {
            'letters': 0,
            'digits': 0,
            'punctuation': 0,
            'special': 0,
            'unicode': 0,
            'spaces': 0
        }

        for char in text:
            if char.isalpha():
                char_counts['letters'] += 1
            elif char.isdigit():
                char_counts['digits'] += 1
            elif char in '.,!?;:':
                char_counts['punctuation'] += 1
            elif char.isspace():
                char_counts['spaces'] += 1
            elif ord(char) > 127:
                char_counts['unicode'] += 1
            else:
                char_counts['special'] += 1

        total_chars = len(text)
        
        return {
            'counts': char_counts,
            'percentages': {
                char_type: (count / total_chars * 100) if total_chars > 0 else 0.0
                for char_type, count in char_counts.items()
            },
            'total_characters': total_chars
        }

    def _get_linguistic_patterns(self, text: str) -> Dict[str, Any]:
        """Get detailed linguistic pattern analysis."""
        # Count various linguistic patterns
        patterns = {
            'difficult_endings': ['tion', 'sion', 'ough', 'augh', 'eigh'],
            'consonant_clusters': ['ph', 'gh', 'ch', 'sh', 'th', 'wh', 'qu'],
            'rare_letters': ['x', 'z', 'q'],
            'vowel_patterns': ['aa', 'ee', 'ii', 'oo', 'uu', 'ae', 'oe']
        }
        
        pattern_counts = {}
        for category, pattern_list in patterns.items():
            count = 0
            for pattern in pattern_list:
                count += text.count(pattern)
            pattern_counts[category] = count
        
        # Calculate pattern density
        text_length = len(text)
        pattern_density = {
            category: (count / text_length * 100) if text_length > 0 else 0.0
            for category, count in pattern_counts.items()
        }
        
        return {
            'pattern_counts': pattern_counts,
            'pattern_density': pattern_density,
            'total_difficult_patterns': sum(pattern_counts.values())
        }

    def _generate_complexity_recommendations(self, overall: float, char: float, 
                                          length: float, linguistic: float) -> list:
        """Generate optimization recommendations based on complexity analysis."""
        recommendations = []
        
        if overall > 0.8:
            recommendations.append("High complexity text - allocate additional processing resources")
        elif overall > 0.6:
            recommendations.append("Medium complexity text - standard processing recommended")
        else:
            recommendations.append("Low complexity text - can use optimized processing")
        
        if char > 0.7:
            recommendations.append("Complex character distribution - may benefit from character-specific optimization")
        
        if length > 0.8:
            recommendations.append("Long text - consider chunking for better performance")
        
        if linguistic > 0.7:
            recommendations.append("Complex linguistic patterns - may require additional phoneme processing time")
        
        # Memory recommendations
        if overall > 0.7:
            recommendations.append("Increase memory allocation for complex text processing")
        
        # Session routing recommendations
        if overall > 0.6:
            recommendations.append("Route to high-performance session (Neural Engine preferred)")
        else:
            recommendations.append("Can be processed on standard session (CPU acceptable)")
        
        return recommendations

    def get_complexity_classification(self, complexity: float) -> str:
        """
        Classify complexity score into readable categories.
        
        @param complexity: Complexity score (0.0 to 1.0)
        @returns: Classification string
        """
        if complexity >= 0.8:
            return "very_high"
        elif complexity >= 0.6:
            return "high"
        elif complexity >= 0.4:
            return "medium"
        elif complexity >= 0.2:
            return "low"
        else:
            return "very_low"

    def batch_analyze_complexity(self, texts: list) -> Dict[str, Any]:
        """
        Analyze complexity for multiple texts in batch.
        
        @param texts: List of texts to analyze
        @returns: Batch analysis results
        """
        if not texts:
            return {
                'count': 0,
                'avg_complexity': 0.0,
                'min_complexity': 0.0,
                'max_complexity': 0.0,
                'complexity_distribution': {},
                'individual_results': []
            }

        complexities = []
        individual_results = []
        
        for text in texts:
            complexity = self.calculate_complexity(text)
            classification = self.get_complexity_classification(complexity)
            
            complexities.append(complexity)
            individual_results.append({
                'text_preview': text[:50] + '...' if len(text) > 50 else text,
                'complexity': complexity,
                'classification': classification
            })
        
        # Calculate distribution
        classifications = [result['classification'] for result in individual_results]
        distribution = {}
        for classification in ['very_low', 'low', 'medium', 'high', 'very_high']:
            count = classifications.count(classification)
            distribution[classification] = {
                'count': count,
                'percentage': (count / len(texts) * 100) if texts else 0.0
            }
        
        return {
            'count': len(texts),
            'avg_complexity': sum(complexities) / len(complexities) if complexities else 0.0,
            'min_complexity': min(complexities) if complexities else 0.0,
            'max_complexity': max(complexities) if complexities else 0.0,
            'complexity_distribution': distribution,
            'individual_results': individual_results
        }

