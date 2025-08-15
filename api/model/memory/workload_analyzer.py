"""
Advanced workload profiling and analysis for memory optimization.

This module provides comprehensive workload characterization to enable
intelligent memory optimization and performance tuning.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict
from dataclasses import dataclass


@dataclass
class WorkloadProfile:
    """Tracks workload characteristics for memory optimization."""
    avg_concurrent_requests: float = 1.0
    avg_text_length: float = 100.0
    avg_segment_complexity: float = 0.5
    peak_concurrent_requests: int = 1
    total_requests: int = 0
    total_processing_time: float = 0.0
    last_updated: float = 0.0
    
    def update_from_stats(self, session_stats: Dict[str, Any], memory_stats: Dict[str, Any]):
        """Update workload profile from session and memory statistics."""
        # Update concurrent request metrics
        self.peak_concurrent_requests = max(
            self.peak_concurrent_requests,
            session_stats.get('concurrent_segments_active', 0)
        )
        
        # Update timing metrics
        if 'total_requests' in session_stats and session_stats['total_requests'] > 0:
            self.total_requests = session_stats['total_requests']
            self.total_processing_time = session_stats.get('total_processing_time', 0.0)
        
        self.last_updated = time.time()


class WorkloadAnalyzer:
    """
    Advanced workload profiling and analysis system for adaptive memory optimization.

    This analyzer provides comprehensive workload characterization to enable
    intelligent memory optimization and performance tuning. It tracks text
    complexity, usage patterns, and performance trends to optimize system
    configuration dynamically.

    ## Analysis Capabilities

    ### Text Complexity Analysis
    - **Character Distribution**: Analysis of character types and frequency
    - **Phoneme Complexity**: Phonemic content analysis for processing complexity
    - **Sentence Structure**: Sentence length and complexity patterns
    - **Language Patterns**: Language-specific processing requirements

    ### Usage Pattern Analysis
    - **Request Frequency**: Temporal patterns of TTS usage
    - **Concurrency Patterns**: Concurrent request patterns and load distribution
    - **Session Duration**: Length and characteristics of usage sessions
    - **Voice Distribution**: Usage patterns across different voice models

    ### Performance Trend Analysis
    - **Processing Time Trends**: How processing times change over time
    - **Memory Usage Patterns**: Memory consumption trends and patterns
    - **Bottleneck Identification**: Detection of performance bottlenecks
    - **Optimization Opportunities**: Identification of optimization targets
    """

    def __init__(self):
        self.text_complexity_history = deque(maxlen=1000)
        self.processing_time_history = deque(maxlen=1000)
        self.concurrent_request_history = deque(maxlen=1000)
        self.voice_usage_stats = defaultdict(int)
        self.language_usage_stats = defaultdict(int)
        self.hourly_request_counts = defaultdict(int)
        
        # Text analysis caches
        self.complexity_cache = {}
        self.max_cache_size = 10000
        
        # Performance trend tracking
        self.performance_trend_window = 100
        self.trend_analysis_cache = {}
        
        self.logger = logging.getLogger(__name__ + ".WorkloadAnalyzer")
        
        # Statistics for optimization
        self.total_requests = 0
        self.total_processing_time = 0.0
        self.analysis_start_time = time.time()

    def calculate_text_complexity(self, text: str) -> float:
        """
        Calculate text complexity score for processing optimization.
        
        @param text: Input text to analyze
        @returns float: Complexity score (0.0 - 1.0)
        """
        if not text:
            return 0.0
        
        # Check cache first
        text_hash = hash(text)
        if text_hash in self.complexity_cache:
            return self.complexity_cache[text_hash]
        
        complexity = 0.0
        
        # Length-based complexity (0-0.3)
        length_factor = min(1.0, len(text) / 500)  # Normalize to 500 chars
        complexity += length_factor * 0.3
        
        # Character diversity (0-0.25)
        unique_chars = len(set(text.lower()))
        diversity_factor = min(1.0, unique_chars / 80)
        complexity += diversity_factor * 0.25
        
        # Special characters and punctuation (0-0.2)
        special_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
        special_factor = min(1.0, special_count / 30)
        complexity += special_factor * 0.2
        
        # Number density (0-0.15)
        number_count = sum(1 for c in text if c.isdigit())
        number_factor = min(1.0, number_count / 20)
        complexity += number_factor * 0.15
        
        # Sentence complexity (0-0.1)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        if sentence_count > 0:
            avg_sentence_length = len(text) / sentence_count
            sentence_factor = min(1.0, avg_sentence_length / 100)
            complexity += sentence_factor * 0.1
        
        # Normalize to 0-1 range
        complexity = min(1.0, complexity)
        
        # Cache the result (with size limit)
        if len(self.complexity_cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.complexity_cache.keys())[:100]
            for key in oldest_keys:
                del self.complexity_cache[key]
        
        self.complexity_cache[text_hash] = complexity
        return complexity

    def record_request(self, text: str, voice: str, language: str, 
                      processing_time: float, concurrent_requests: int):
        """
        Record a TTS request for workload analysis.
        
        @param text: Text that was processed
        @param voice: Voice used for synthesis
        @param language: Language of the text
        @param processing_time: Time taken for processing
        @param concurrent_requests: Number of concurrent requests at the time
        """
        current_time = time.time()
        
        # Calculate text complexity
        complexity = self.calculate_text_complexity(text)
        
        # Record in histories
        self.text_complexity_history.append({
            'timestamp': current_time,
            'complexity': complexity,
            'text_length': len(text),
            'voice': voice,
            'language': language
        })
        
        self.processing_time_history.append({
            'timestamp': current_time,
            'processing_time': processing_time,
            'text_length': len(text),
            'complexity': complexity
        })
        
        self.concurrent_request_history.append({
            'timestamp': current_time,
            'concurrent_requests': concurrent_requests
        })
        
        # Update usage statistics
        self.voice_usage_stats[voice] += 1
        self.language_usage_stats[language] += 1
        
        # Update hourly statistics
        current_hour = int(current_time // 3600)
        self.hourly_request_counts[current_hour] += 1
        
        # Update totals
        self.total_requests += 1
        self.total_processing_time += processing_time
        
        self.logger.debug(f"Recorded request: complexity={complexity:.2f}, time={processing_time:.3f}s")

    def get_workload_insights(self) -> Dict[str, Any]:
        """
        Get comprehensive workload insights for optimization.
        
        @returns Dict[str, Any]: Detailed workload analysis
        """
        current_time = time.time()
        analysis_duration = current_time - self.analysis_start_time
        
        insights = {
            'analysis_period': {
                'duration_hours': analysis_duration / 3600,
                'start_time': self.analysis_start_time,
                'end_time': current_time
            },
            'request_volume': {
                'total_requests': self.total_requests,
                'requests_per_hour': self.total_requests / max(analysis_duration / 3600, 0.01),
                'total_processing_time': self.total_processing_time,
                'avg_processing_time': self.total_processing_time / max(self.total_requests, 1)
            }
        }
        
        # Text complexity analysis
        if self.text_complexity_history:
            complexities = [entry['complexity'] for entry in self.text_complexity_history]
            text_lengths = [entry['text_length'] for entry in self.text_complexity_history]
            
            insights['text_analysis'] = {
                'avg_complexity': sum(complexities) / len(complexities),
                'max_complexity': max(complexities),
                'min_complexity': min(complexities),
                'avg_text_length': sum(text_lengths) / len(text_lengths),
                'max_text_length': max(text_lengths),
                'complexity_distribution': self._calculate_complexity_distribution(complexities)
            }
        
        # Concurrency analysis
        if self.concurrent_request_history:
            concurrent_counts = [entry['concurrent_requests'] for entry in self.concurrent_request_history]
            
            insights['concurrency_analysis'] = {
                'avg_concurrent_requests': sum(concurrent_counts) / len(concurrent_counts),
                'peak_concurrent_requests': max(concurrent_counts),
                'concurrency_distribution': self._calculate_concurrency_distribution(concurrent_counts)
            }
        
        # Performance trends
        insights['performance_trends'] = self._analyze_performance_trends()
        
        # Usage patterns
        insights['usage_patterns'] = {
            'voice_distribution': dict(self.voice_usage_stats),
            'language_distribution': dict(self.language_usage_stats),
            'hourly_patterns': self._analyze_hourly_patterns()
        }
        
        # Optimization recommendations
        insights['optimization_recommendations'] = self._generate_optimization_recommendations(insights)
        
        return insights

    def _calculate_complexity_distribution(self, complexities: List[float]) -> Dict[str, float]:
        """Calculate distribution of text complexities."""
        if not complexities:
            return {}
        
        low_count = sum(1 for c in complexities if c < 0.3)
        medium_count = sum(1 for c in complexities if 0.3 <= c < 0.7)
        high_count = sum(1 for c in complexities if c >= 0.7)
        total = len(complexities)
        
        return {
            'low_complexity': (low_count / total) * 100,
            'medium_complexity': (medium_count / total) * 100,
            'high_complexity': (high_count / total) * 100
        }

    def _calculate_concurrency_distribution(self, concurrent_counts: List[int]) -> Dict[str, float]:
        """Calculate distribution of concurrent request patterns."""
        if not concurrent_counts:
            return {}
        
        single_count = sum(1 for c in concurrent_counts if c == 1)
        low_concurrent = sum(1 for c in concurrent_counts if 2 <= c <= 3)
        high_concurrent = sum(1 for c in concurrent_counts if c > 3)
        total = len(concurrent_counts)
        
        return {
            'single_requests': (single_count / total) * 100,
            'low_concurrency': (low_concurrent / total) * 100,
            'high_concurrency': (high_concurrent / total) * 100
        }

    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(self.processing_time_history) < 20:
            return {'trend': 'insufficient_data'}
        
        # Split into time windows for trend analysis
        recent_entries = list(self.processing_time_history)[-self.performance_trend_window:]
        
        # Split into first and second half for comparison
        mid_point = len(recent_entries) // 2
        first_half = recent_entries[:mid_point]
        second_half = recent_entries[mid_point:]
        
        first_avg = sum(entry['processing_time'] for entry in first_half) / len(first_half)
        second_avg = sum(entry['processing_time'] for entry in second_half) / len(second_half)
        
        # Calculate trend
        change_percent = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
        
        if change_percent < -5:  # 5% improvement
            trend = 'improving'
        elif change_percent > 5:  # 5% degradation
            trend = 'degrading'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change_percent': change_percent,
            'first_half_avg': first_avg,
            'second_half_avg': second_avg,
            'sample_size': len(recent_entries)
        }

    def _analyze_hourly_patterns(self) -> Dict[str, Any]:
        """Analyze hourly usage patterns."""
        if not self.hourly_request_counts:
            return {}
        
        current_hour = int(time.time() // 3600)
        recent_hours = [current_hour - i for i in range(24)]  # Last 24 hours
        
        hourly_data = []
        for hour in recent_hours:
            count = self.hourly_request_counts.get(hour, 0)
            hourly_data.append(count)
        
        if not hourly_data:
            return {}
        
        avg_requests_per_hour = sum(hourly_data) / len(hourly_data)
        peak_hour_requests = max(hourly_data)
        
        return {
            'avg_requests_per_hour': avg_requests_per_hour,
            'peak_hour_requests': peak_hour_requests,
            'hourly_variation': (peak_hour_requests - avg_requests_per_hour) / max(avg_requests_per_hour, 1)
        }

    def _generate_optimization_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on workload analysis."""
        recommendations = []
        
        # Check text complexity patterns
        text_analysis = insights.get('text_analysis', {})
        if text_analysis.get('avg_complexity', 0) > 0.7:
            recommendations.append(
                "High text complexity detected - consider increasing memory arena size"
            )
        elif text_analysis.get('avg_complexity', 0) < 0.3:
            recommendations.append(
                "Low text complexity detected - memory arena size can be reduced"
            )
        
        # Check concurrency patterns
        concurrency = insights.get('concurrency_analysis', {})
        if concurrency.get('avg_concurrent_requests', 1) > 2:
            recommendations.append(
                "High concurrency detected - enable dual session manager for better performance"
            )
        
        # Check performance trends
        trends = insights.get('performance_trends', {})
        if trends.get('trend') == 'degrading':
            recommendations.append(
                f"Performance degrading by {trends.get('change_percent', 0):.1f}% - trigger memory optimization"
            )
        
        # Check usage patterns
        usage = insights.get('usage_patterns', {})
        hourly = usage.get('hourly_patterns', {})
        if hourly.get('hourly_variation', 0) > 2:
            recommendations.append(
                "High hourly variation detected - implement adaptive scheduling"
            )
        
        return recommendations

    def reset_analysis(self):
        """Reset all analysis data for fresh tracking."""
        self.text_complexity_history.clear()
        self.processing_time_history.clear()
        self.concurrent_request_history.clear()
        self.voice_usage_stats.clear()
        self.language_usage_stats.clear()
        self.hourly_request_counts.clear()
        self.complexity_cache.clear()
        self.trend_analysis_cache.clear()
        
        self.total_requests = 0
        self.total_processing_time = 0.0
        self.analysis_start_time = time.time()
        
        self.logger.info("🔄 Workload analysis data reset")

    def export_analysis_data(self) -> Dict[str, Any]:
        """Export raw analysis data for external processing."""
        return {
            'text_complexity_history': list(self.text_complexity_history),
            'processing_time_history': list(self.processing_time_history),
            'concurrent_request_history': list(self.concurrent_request_history),
            'voice_usage_stats': dict(self.voice_usage_stats),
            'language_usage_stats': dict(self.language_usage_stats),
            'hourly_request_counts': dict(self.hourly_request_counts),
            'total_requests': self.total_requests,
            'total_processing_time': self.total_processing_time,
            'analysis_start_time': self.analysis_start_time
        }
