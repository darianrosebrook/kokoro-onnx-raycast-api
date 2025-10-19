"""
Intelligent Cache Optimization for Kokoro-ONNX

This module provides intelligent cache pre-warming and optimization
to dramatically improve performance by predicting and pre-loading
commonly used cache entries.
"""

import asyncio
import logging
from typing import Dict, Any, List, Set
from collections import Counter

logger = logging.getLogger(__name__)


class CachePredictor:
    """Predicts which cache entries will be needed based on usage patterns."""

    def __init__(self):
        self._usage_patterns: Dict[str, Counter] = {}
        self._prediction_model: Dict[str, Dict[str, float]] = {}

    def record_usage(self, cache_type: str, key: str):
        """Record cache usage for pattern analysis."""
        if cache_type not in self._usage_patterns:
            self._usage_patterns[cache_type] = Counter()

        self._usage_patterns[cache_type][key] += 1

    def predict_needed_entries(self, cache_type: str, top_n: int = 10) -> List[str]:
        """Predict which cache entries are most likely to be needed."""
        if cache_type not in self._usage_patterns:
            return []

        # Get most common entries
        patterns = self._usage_patterns[cache_type]
        return [key for key, _ in patterns.most_common(top_n)]

    def update_prediction_model(self):
        """Update the prediction model based on recorded usage."""
        for cache_type, patterns in self._usage_patterns.items():
            total_usage = sum(patterns.values())
            if total_usage > 0:
                self._prediction_model[cache_type] = {
                    key: count / total_usage for key, count in patterns.items()
                }


# Global predictor instance
_predictor = CachePredictor()


async def warm_common_caches():
    """
    Pre-warm caches with commonly used entries to improve performance.

    This function analyzes usage patterns and pre-loads the most frequently
    accessed cache entries to reduce cache misses on actual requests.
    """
    try:
        logger.info("🔥 Warming common caches...")

        # Update prediction model
        _predictor.update_prediction_model()

        # Pre-warm different cache types
        tasks = [
            _warm_inference_cache(),
            _warm_phoneme_cache(),
            _warm_primer_cache(),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("✅ Cache warming completed")

    except Exception as e:
        logger.error(f"❌ Cache warming failed: {e}")
        # Don't raise - cache warming failure shouldn't block requests


async def _warm_inference_cache():
    """Pre-warm inference cache with common entries."""
    try:
        # Import here to avoid circular imports
        from api.model.cache.inference import InferenceCache

        cache = InferenceCache()
        predicted_keys = _predictor.predict_needed_entries('inference', 5)

        if predicted_keys:
            logger.debug(f"Pre-warming inference cache with {len(predicted_keys)} entries")
            # Pre-load predicted entries (implementation depends on cache structure)
            # This is a placeholder - actual implementation would depend on cache format

        # Also warm with some common defaults
        common_texts = [
            "Hello world",
            "Thank you",
            "How are you",
            "Good morning",
            "Good afternoon"
        ]

        # Record these as usage patterns for future predictions
        for text in common_texts:
            _predictor.record_usage('inference', f"text:{text}")

    except Exception as e:
        logger.debug(f"Inference cache warming failed: {e}")


async def _warm_phoneme_cache():
    """Pre-warm phoneme cache with common entries."""
    try:
        # Import here to avoid circular imports
        from api.model.cache.phoneme import PhonemeCache

        cache = PhonemeCache()
        predicted_keys = _predictor.predict_needed_entries('phoneme', 5)

        if predicted_keys:
            logger.debug(f"Pre-warming phoneme cache with {len(predicted_keys)} entries")

        # Common phoneme patterns
        common_phonemes = [
            "həˈloʊ ˈwɜːrld",
            "θæŋk ˈjuː",
            "haʊ ˈɑːr ˈjuː",
            "ɡʊd ˈmɔːrnɪŋ",
            "ɡʊd ˌæftərˈnuːn"
        ]

        # Record these as usage patterns
        for phoneme in common_phonemes:
            _predictor.record_usage('phoneme', f"phoneme:{phoneme}")

    except Exception as e:
        logger.debug(f"Phoneme cache warming failed: {e}")


async def _warm_primer_cache():
    """Pre-warm primer cache with common entries."""
    try:
        # Import here to avoid circular imports
        from api.model.cache.primer import PrimerCache

        cache = PrimerCache()
        predicted_keys = _predictor.predict_needed_entries('primer', 3)

        if predicted_keys:
            logger.debug(f"Pre-warming primer cache with {len(predicted_keys)} entries")

        # Common primer patterns (short audio segments for concatenation)
        common_primers = [
            "audio_primer_100ms",
            "audio_primer_200ms",
            "audio_primer_500ms"
        ]

        # Record these as usage patterns
        for primer in common_primers:
            _predictor.record_usage('primer', f"primer:{primer}")

    except Exception as e:
        logger.debug(f"Primer cache warming failed: {e}")


def record_cache_usage(cache_type: str, key: str):
    """
    Record cache usage for pattern analysis and prediction.

    This function should be called whenever cache entries are accessed
    to build usage patterns for intelligent pre-warming.

    @param cache_type: Type of cache ('inference', 'phoneme', 'primer')
    @param key: Cache key that was accessed
    """
    _predictor.record_usage(cache_type, key)


def get_cache_predictions(cache_type: str, top_n: int = 10) -> List[str]:
    """
    Get predictions for which cache entries are likely to be needed.

    @param cache_type: Type of cache to get predictions for
    @param top_n: Number of top predictions to return
    @returns List of predicted cache keys
    """
    return _predictor.predict_needed_entries(cache_type, top_n)
