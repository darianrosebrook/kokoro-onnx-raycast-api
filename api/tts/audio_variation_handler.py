"""
Audio Variation Handler for CoreML Precision Variations

This module provides utilities to handle natural audio size variations
that occur with CoreML execution, particularly for longer texts.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import hashlib
import time

logger = logging.getLogger(__name__)

class AudioVariationHandler:
    """
    Handles natural audio variations from CoreML execution to ensure
    consistent streaming experience while preserving hardware acceleration benefits.
    Features adaptive threshold optimization based on stream success rates.
    """
    
    def __init__(self):
        # Track audio size patterns for identical texts
        self._size_patterns: Dict[str, List[Tuple[int, float]]] = {}  # text_hash -> [(size, timestamp)]
        self._size_cache_ttl = 3600  # 1 hour
        self._max_cache_entries = 1000
        
        # Adaptive threshold system
        self._variation_threshold = 15.0  # Start with 15% threshold
        self._min_threshold = 5.0   # Minimum threshold (too strict)
        self._max_threshold = 30.0  # Maximum threshold (too loose)
        self._threshold_history: List[Tuple[float, float, float]] = []  # (threshold, success_rate, timestamp)
        self._optimization_enabled = True
        
        # Stream health tracking for threshold optimization
        self._stream_health: Dict[str, List[Dict]] = {}  # text_hash -> [health_records]
        self._health_cache_ttl = 1800  # 30 minutes
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'consistent_requests': 0,
            'variation_requests': 0,
            'max_variation_pct': 0.0,
            'avg_variation_pct': 0.0,
            'threshold_optimizations': 0,
            'current_threshold': self._variation_threshold,
            'threshold_effectiveness': 0.0
        }
    
    def get_text_hash(self, text: str, voice: str, speed: float, lang: str) -> str:
        """Generate a hash for text+voice+speed+lang combination"""
        content = f"{text.strip()}:{voice}:{speed:.3f}:{lang}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    def record_audio_size(self, text_hash: str, audio_size: int) -> Dict[str, Union[bool, float, int]]:
        """
        Record an audio size for a given text hash and analyze variation.
        
        Returns:
            Dict containing variation analysis:
            - 'is_consistent': bool - whether this matches previous sizes
            - 'variation_pct': float - percentage variation from baseline
            - 'baseline_size': int - the expected size based on history
            - 'is_new_text': bool - whether this is the first time seeing this text
        """
        current_time = time.time()
        
        # Clean up old entries
        self._cleanup_cache(current_time)
        
        # Initialize tracking for this text if not seen before
        if text_hash not in self._size_patterns:
            self._size_patterns[text_hash] = []
        
        # Add this size to the pattern
        self._size_patterns[text_hash].append((audio_size, current_time))
        
        # Analyze the pattern
        sizes = [size for size, _ in self._size_patterns[text_hash]]
        is_new_text = len(sizes) == 1
        
        if is_new_text:
            # First time seeing this text
            result = {
                'is_consistent': True,  # No previous data to compare
                'variation_pct': 0.0,
                'baseline_size': audio_size,
                'is_new_text': True,
                'pattern_count': 1
            }
        else:
            # Analyze variation
            baseline_size = sizes[0]  # Use first generation as baseline
            variation_pct = abs(audio_size - baseline_size) / baseline_size * 100
            
            # Consider it consistent if within current adaptive threshold
            is_consistent = variation_pct <= self._variation_threshold
            
            result = {
                'is_consistent': is_consistent,
                'variation_pct': variation_pct,
                'baseline_size': baseline_size,
                'is_new_text': False,
                'pattern_count': len(sizes),
                'all_sizes': sizes,
                'threshold_used': self._variation_threshold
            }
            
            # Update statistics
            self.stats['total_requests'] += 1
            if is_consistent:
                self.stats['consistent_requests'] += 1
            else:
                self.stats['variation_requests'] += 1
                self.stats['max_variation_pct'] = max(self.stats['max_variation_pct'], variation_pct)
                
                # Update rolling average
                total_variations = self.stats['variation_requests']
                if total_variations > 1:
                    self.stats['avg_variation_pct'] = (
                        (self.stats['avg_variation_pct'] * (total_variations - 1) + variation_pct) / total_variations
                    )
                else:
                    self.stats['avg_variation_pct'] = variation_pct
        
        # Reduce log noise: only log inconsistencies at INFO, full result at DEBUG
        if not result.get('is_consistent', True):
            logger.info(f" Audio size variation detected: {result}")
        else:
            logger.debug(f"Audio variation analysis: {result}")
        return result
    
    def normalize_audio_for_streaming(self, audio_data: np.ndarray, target_size: Optional[int] = None) -> np.ndarray:
        """
        Normalize audio data for consistent streaming experience.
        
        Args:
            audio_data: Raw PCM audio data
            target_size: Optional target size for padding/trimming
            
        Returns:
            Normalized audio data
        """
        if target_size is None:
            return audio_data
        
        current_size = len(audio_data)
        
        if current_size == target_size:
            # Perfect match
            return audio_data
        elif current_size < target_size:
            # Pad with silence (zeros)
            padding_size = target_size - current_size
            padding = np.zeros(padding_size, dtype=audio_data.dtype)
            normalized_audio = np.concatenate([audio_data, padding])
            logger.debug(f"Padded audio: {current_size} -> {target_size} bytes (+{padding_size} silence)")
            return normalized_audio
        else:
            # Trim excess (from the end to preserve speech timing)
            normalized_audio = audio_data[:target_size]
            trimmed_size = current_size - target_size
            logger.debug(f"Trimmed audio: {current_size} -> {target_size} bytes (-{trimmed_size} from end)")
            return normalized_audio
    
    def should_normalize_stream(self, variation_analysis: Dict) -> Tuple[bool, Optional[int]]:
        """
        Determine if stream normalization should be applied.
        
        Returns:
            Tuple of (should_normalize, target_size)
        """
        if variation_analysis['is_new_text']:
            # No normalization needed for new text
            return False, None
        
        if variation_analysis['is_consistent']:
            # Already consistent, no normalization needed
            return False, None
        
        if variation_analysis['variation_pct'] > 25.0:
            # Variation too large, might indicate a real issue
            logger.warning(f"Large audio variation detected: {variation_analysis['variation_pct']:.1f}%")
            return False, None
        
        # Apply normalization to baseline size
        target_size = variation_analysis['baseline_size']
        logger.info(f"Applying stream normalization to {target_size} bytes (variation: {variation_analysis['variation_pct']:.1f}%)")
        return True, target_size
    
    def _cleanup_cache(self, current_time: float):
        """Clean up expired cache entries"""
        expired_hashes = []
        
        for text_hash, patterns in self._size_patterns.items():
            # Remove expired entries
            valid_patterns = [(size, timestamp) for size, timestamp in patterns 
                            if current_time - timestamp < self._size_cache_ttl]
            
            if valid_patterns:
                self._size_patterns[text_hash] = valid_patterns
            else:
                expired_hashes.append(text_hash)
        
        # Remove completely expired text hashes
        for text_hash in expired_hashes:
            del self._size_patterns[text_hash]
        
        # Limit cache size
        if len(self._size_patterns) > self._max_cache_entries:
            # Remove oldest entries
            all_entries = []
            for text_hash, patterns in self._size_patterns.items():
                latest_timestamp = max(timestamp for _, timestamp in patterns)
                all_entries.append((latest_timestamp, text_hash))
            
            all_entries.sort()  # Sort by timestamp
            entries_to_remove = len(all_entries) - self._max_cache_entries
            
            for _, text_hash in all_entries[:entries_to_remove]:
                del self._size_patterns[text_hash]
            
            logger.debug(f"Cache cleanup: removed {entries_to_remove + len(expired_hashes)} entries")
    
    def record_stream_health(self, text_hash: str, stream_success: bool, error_details: Optional[str] = None, 
                           latency_ms: Optional[float] = None, chunk_count: Optional[int] = None) -> None:
        """Record stream health data for threshold optimization"""
        if not self._optimization_enabled:
            return
            
        current_time = time.time()
        health_record = {
            'timestamp': current_time,
            'success': stream_success,
            'error_details': error_details,
            'latency_ms': latency_ms,
            'chunk_count': chunk_count,
            'threshold_at_time': self._variation_threshold
        }
        
        if text_hash not in self._stream_health:
            self._stream_health[text_hash] = []
        
        self._stream_health[text_hash].append(health_record)
        
        # Clean up old health records
        cutoff_time = current_time - self._health_cache_ttl
        self._stream_health[text_hash] = [
            record for record in self._stream_health[text_hash] 
            if record['timestamp'] > cutoff_time
        ]
        
        logger.debug(f"Stream health recorded: success={stream_success}, threshold={self._variation_threshold:.1f}%")
    
    def optimize_threshold(self, min_samples: int = 10) -> Dict[str, Union[bool, float, str]]:
        """
        Optimize variation threshold based on stream health data
        
        Returns:
            Dict containing optimization results
        """
        if not self._optimization_enabled:
            return {'optimized': False, 'reason': 'Optimization disabled'}
        
        # Collect all health records
        all_health_records = []
        for health_list in self._stream_health.values():
            all_health_records.extend(health_list)
        
        if len(all_health_records) < min_samples:
            return {
                'optimized': False, 
                'reason': f'Insufficient data ({len(all_health_records)} < {min_samples} samples)',
                'current_threshold': self._variation_threshold
            }
        
        # Calculate current success rate
        recent_records = sorted(all_health_records, key=lambda x: x['timestamp'])[-min_samples:]
        current_success_rate = sum(1 for r in recent_records if r['success']) / len(recent_records)
        
        # Store current performance
        current_time = time.time()
        self._threshold_history.append((self._variation_threshold, current_success_rate, current_time))
        
        # Keep only recent history (last 24 hours)
        cutoff_time = current_time - 86400
        self._threshold_history = [
            (threshold, rate, timestamp) for threshold, rate, timestamp in self._threshold_history
            if timestamp > cutoff_time
        ]
        
        old_threshold = self._variation_threshold
        optimization_action = "none"
        
        # Optimization logic
        if current_success_rate < 0.85:  # Less than 85% success rate
            # Increase threshold to be more lenient
            new_threshold = min(self._variation_threshold * 1.2, self._max_threshold)
            if new_threshold != self._variation_threshold:
                self._variation_threshold = new_threshold
                optimization_action = "increased"
                logger.info(f" Threshold increased due to low success rate: {old_threshold:.1f}% -> {new_threshold:.1f}%")
        
        elif current_success_rate > 0.98 and self._variation_threshold > self._min_threshold:
            # Very high success rate, we can be more strict
            new_threshold = max(self._variation_threshold * 0.9, self._min_threshold)
            if new_threshold != self._variation_threshold:
                self._variation_threshold = new_threshold
                optimization_action = "decreased"
                logger.info(f" Threshold decreased due to high success rate: {old_threshold:.1f}% -> {new_threshold:.1f}%")
        
        # Update statistics
        if optimization_action != "none":
            self.stats['threshold_optimizations'] += 1
            self.stats['current_threshold'] = self._variation_threshold
        
        # Calculate threshold effectiveness
        if len(self._threshold_history) > 1:
            avg_success_rate = sum(rate for _, rate, _ in self._threshold_history) / len(self._threshold_history)
            self.stats['threshold_effectiveness'] = avg_success_rate
        
        return {
            'optimized': optimization_action != "none",
            'action': optimization_action,
            'old_threshold': old_threshold,
            'new_threshold': self._variation_threshold,
            'success_rate': current_success_rate,
            'samples_used': len(recent_records),
            'threshold_effectiveness': self.stats['threshold_effectiveness']
        }
    
    def run_soak_test(self, duration_minutes: int = 30, test_interval_seconds: int = 60) -> Dict:
        """
        Run a soak test to continuously optimize thresholds
        
        This would typically be run in a background task
        """
        logger.info(f" Starting soak test: {duration_minutes} minutes, {test_interval_seconds}s intervals")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        test_results = []
        
        initial_threshold = self._variation_threshold
        
        while time.time() < end_time:
            # Wait for the interval
            time.sleep(test_interval_seconds)
            
            # Run optimization
            optimization_result = self.optimize_threshold(min_samples=5)  # Lower threshold for soak testing
            test_results.append({
                'timestamp': time.time(),
                'optimization': optimization_result,
                'threshold': self._variation_threshold,
                'health_records': len([r for health_list in self._stream_health.values() for r in health_list])
            })
            
            logger.info(f" Soak test checkpoint: threshold={self._variation_threshold:.1f}%, "
                       f"success_rate={optimization_result.get('success_rate', 0):.2f}")
        
        # Generate soak test summary
        final_threshold = self._variation_threshold
        threshold_changes = sum(1 for result in test_results if result['optimization']['optimized'])
        
        summary = {
            'duration_minutes': duration_minutes,
            'test_points': len(test_results),
            'initial_threshold': initial_threshold,
            'final_threshold': final_threshold,
            'threshold_changes': threshold_changes,
            'improvement': final_threshold != initial_threshold,
            'test_results': test_results[-5:],  # Last 5 results
            'recommendation': self._generate_soak_recommendation(test_results)
        }
        
        logger.info(f"✅ Soak test completed: {threshold_changes} optimizations, "
                   f"threshold: {initial_threshold:.1f}% -> {final_threshold:.1f}%")
        
        return summary
    
    def _generate_soak_recommendation(self, test_results: List[Dict]) -> str:
        """Generate recommendations based on soak test results"""
        if not test_results:
            return "Insufficient data for recommendations"
        
        # Analyze patterns
        thresholds = [r['threshold'] for r in test_results]
        success_rates = [r['optimization'].get('success_rate', 0) for r in test_results if 'success_rate' in r['optimization']]
        
        if len(success_rates) == 0:
            return "No success rate data available"
        
        avg_success_rate = sum(success_rates) / len(success_rates)
        threshold_stability = len(set(thresholds)) / len(thresholds)  # Lower = more stable
        
        if avg_success_rate > 0.95 and threshold_stability < 0.3:
            return "System is well-optimized and stable"
        elif avg_success_rate < 0.85:
            return "Consider increasing base threshold or investigating stream health issues"
        elif threshold_stability > 0.7:
            return "Threshold is unstable, consider slower adaptation rate"
        else:
            return "System is adapting well, continue monitoring"
    
    def enable_optimization(self, enabled: bool = True) -> None:
        """Enable or disable adaptive threshold optimization"""
        self._optimization_enabled = enabled
        logger.info(f" Adaptive optimization {'enabled' if enabled else 'disabled'}")
    
    def set_threshold_bounds(self, min_threshold: float, max_threshold: float) -> None:
        """Set the bounds for adaptive threshold optimization"""
        if min_threshold >= max_threshold:
            raise ValueError("min_threshold must be less than max_threshold")
        
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        
        # Ensure current threshold is within bounds
        self._variation_threshold = max(min_threshold, min(self._variation_threshold, max_threshold))
        
        logger.info(f" Threshold bounds set: {min_threshold:.1f}% - {max_threshold:.1f}%")
    
    def get_statistics(self) -> Dict:
        """Get variation handling statistics"""
        consistency_rate = 0.0
        if self.stats['total_requests'] > 0:
            consistency_rate = self.stats['consistent_requests'] / self.stats['total_requests'] * 100
        
        return {
            **self.stats,
            'consistency_rate_pct': consistency_rate,
            'cache_entries': len(self._size_patterns),
            'total_patterns': sum(len(patterns) for patterns in self._size_patterns.values()),
            'threshold_bounds': (self._min_threshold, self._max_threshold),
            'optimization_enabled': self._optimization_enabled,
            'health_records': sum(len(health_list) for health_list in self._stream_health.values())
        }

# Global instance
_variation_handler = AudioVariationHandler()

def get_variation_handler() -> AudioVariationHandler:
    """Get the global audio variation handler instance"""
    return _variation_handler
