"""
Audio Quality Benchmark for Enterprise TTS

This module provides comprehensive benchmarking of audio quality metrics
including LUFS, dBTP, crest factor, and dynamic range measurements.

@sign: @darianrosebrook
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

from api.audio.audio_quality_metrics import (
    AudioQualityAnalyzer,
    AudioQualityMetrics,
    AudioQualityStandard,
    analyze_audio_quality
)
from api.config import TTSConfig
from api.model.loader import get_model_status

logger = logging.getLogger(__name__)


@dataclass
class AudioQualityBenchmarkResult:
    """Results from audio quality benchmarking."""
    test_name: str
    voice: str
    text_sample: str
    metrics: AudioQualityMetrics
    processing_time_ms: float
    meets_enterprise_standard: bool
    quality_score: float
    recommendations: List[str]


class AudioQualityBenchmark:
    """
    Comprehensive audio quality benchmarking for TTS systems.

    Tests audio output against enterprise standards including loudness,
    peak levels, and dynamic range requirements.
    """

    def __init__(self):
        self.analyzer = AudioQualityAnalyzer()
        self.test_texts = {
            "short": "Hello, world! This is a test.",
            "medium": "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the alphabet.",
            "long": "In the realm of artificial intelligence and machine learning, text-to-speech synthesis represents a critical bridge between computational systems and human communication. Advanced TTS systems must deliver not only accurate pronunciation and natural prosody, but also consistent audio quality that meets professional broadcasting standards."
        }

    async def run_comprehensive_benchmark(self, voices: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run comprehensive audio quality benchmark across multiple voices and text lengths.

        @param voices: List of voices to test (default: all available)
        @returns Dict with benchmark results and analysis
        """
        if not get_model_status():
            raise RuntimeError("TTS model not loaded")

        # Default to common voices if none specified
        if voices is None:
            voices = ["af_heart", "af_bella", "am_michael", "bf_alice"]

        results = []
        benchmark_start = time.time()

        logger.info(f"🎯 Starting comprehensive audio quality benchmark with {len(voices)} voices")

        for voice in voices:
            for text_type, text in self.test_texts.items():
                try:
                    result = await self._benchmark_voice_text(voice, text_type, text)
                    results.append(result)

                    status = "✅ PASS" if result.meets_enterprise_standard else "❌ FAIL"
                    logger.info(
                        f"{status} {voice}/{text_type}: LUFS={result.metrics.lufs:.1f}, "
                        f"dBTP={result.metrics.dbtp:.1f}, Score={result.quality_score:.0f}"
                    )

                except Exception as e:
                    logger.error(f"Failed to benchmark {voice}/{text_type}: {e}")
                    continue

        benchmark_duration = time.time() - benchmark_start

        # Analyze results
        analysis = self._analyze_benchmark_results(results)

        logger.info(f"🎯 Audio quality benchmark completed in {benchmark_duration:.1f}s")
        logger.info(f"📊 Results: {analysis['summary']['pass_rate']:.1f}% pass rate, "
                   f"Avg score: {analysis['summary']['avg_quality_score']:.1f}")

        return {
            "benchmark_info": {
                "duration_seconds": benchmark_duration,
                "voices_tested": len(voices),
                "text_samples": len(self.test_texts),
                "total_tests": len(results)
            },
            "results": [result.__dict__ for result in results],
            "analysis": analysis
        }

    async def _benchmark_voice_text(self, voice: str, text_type: str, text: str) -> AudioQualityBenchmarkResult:
        """Benchmark a specific voice and text combination."""
        from api.tts.core import stream_tts_audio
        from api.main import get_tts_config
        from fastapi import Request
        from unittest.mock import MagicMock

        # Create mock request for TTS generation
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-request-id": f"benchmark-{voice}-{text_type}"}

        start_time = time.time()

        # Generate audio
        audio_chunks = []
        async for chunk in stream_tts_audio(text, voice, 1.0, "en-us", "wav", mock_request, no_cache=True):
            audio_chunks.append(chunk)

        processing_time_ms = (time.time() - start_time) * 1000

        # Combine chunks into complete audio
        complete_audio = b''.join(audio_chunks)

        # Analyze audio quality
        metrics = analyze_audio_quality(complete_audio, TTSConfig.SAMPLE_RATE, AudioQualityStandard.ENTERPRISE)

        # Generate recommendations
        recommendations = self._generate_quality_recommendations(metrics)

        return AudioQualityBenchmarkResult(
            test_name=f"{voice}_{text_type}",
            voice=voice,
            text_sample=text,
            metrics=metrics,
            processing_time_ms=processing_time_ms,
            meets_enterprise_standard=metrics.meets_standard,
            quality_score=metrics.quality_score,
            recommendations=recommendations
        )

    def _analyze_benchmark_results(self, results: List[AudioQualityBenchmarkResult]) -> Dict[str, Any]:
        """Analyze benchmark results and provide insights."""
        if not results:
            return {"error": "No results to analyze"}

        # Calculate summary statistics
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.meets_enterprise_standard)
        pass_rate = (passed_tests / total_tests) * 100

        quality_scores = [r.quality_score for r in results if r.quality_score >= 0]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        processing_times = [r.processing_time_ms for r in results]
        avg_processing_time = sum(processing_times) / len(processing_times)

        # Voice-specific analysis
        voice_stats = {}
        for result in results:
            if result.voice not in voice_stats:
                voice_stats[result.voice] = {"tests": 0, "passed": 0, "scores": []}
            voice_stats[result.voice]["tests"] += 1
            if result.meets_enterprise_standard:
                voice_stats[result.voice]["passed"] += 1
            voice_stats[result.voice]["scores"].append(result.quality_score)

        # Calculate voice averages
        for voice, stats in voice_stats.items():
            stats["pass_rate"] = (stats["passed"] / stats["tests"]) * 100
            stats["avg_score"] = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0

        # Text length analysis
        text_stats = {}
        for result in results:
            text_type = result.test_name.split('_')[-1]  # Extract text type from name
            if text_type not in text_stats:
                text_stats[text_type] = {"tests": 0, "passed": 0, "scores": []}
            text_stats[text_type]["tests"] += 1
            if result.meets_enterprise_standard:
                text_stats[text_type]["passed"] += 1
            text_stats[text_type]["scores"].append(result.quality_score)

        # Calculate text type averages
        for text_type, stats in text_stats.items():
            stats["pass_rate"] = (stats["passed"] / stats["tests"]) * 100
            stats["avg_score"] = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0

        # Quality issues analysis
        all_issues = []
        for result in results:
            all_issues.extend(result.metrics.issues or [])

        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        return {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "pass_rate": pass_rate,
                "avg_quality_score": avg_quality_score,
                "avg_processing_time_ms": avg_processing_time,
                "common_issues": sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            },
            "voice_analysis": voice_stats,
            "text_analysis": text_stats,
            "quality_distribution": {
                "excellent": len([r for r in results if r.quality_score >= 90]),
                "good": len([r for r in results if 80 <= r.quality_score < 90]),
                "fair": len([r for r in results if 70 <= r.quality_score < 80]),
                "poor": len([r for r in results if r.quality_score < 70])
            },
            "recommendations": self._generate_benchmark_recommendations(results)
        }

    def _generate_quality_recommendations(self, metrics: AudioQualityMetrics) -> List[str]:
        """Generate quality improvement recommendations based on metrics."""
        recommendations = []

        if metrics.lufs != -float('inf'):
            if abs(metrics.lufs - (-16.0)) > 1.0:
                recommendations.append(f"Adjust loudness target (current: {metrics.lufs:.1f} LUFS, target: -16±1)")

        if metrics.dbtp > -1.0:
            recommendations.append(f"Reduce peak levels (current: {metrics.dbtp:.1f} dBTP, ceiling: -1.0)")

        if metrics.crest_factor and metrics.crest_factor > 20:
            recommendations.append(f"High crest factor indicates peaky audio (current: {metrics.crest_factor:.1f}dB)")

        if metrics.dynamic_range and metrics.dynamic_range < 10:
            recommendations.append(f"Low dynamic range may indicate compressed audio (current: {metrics.dynamic_range:.1f}dB)")

        return recommendations

    def _generate_benchmark_recommendations(self, results: List[AudioQualityBenchmarkResult]) -> List[str]:
        """Generate overall benchmark recommendations."""
        recommendations = []

        # Check overall pass rate
        pass_rate = sum(1 for r in results if r.meets_enterprise_standard) / len(results) * 100
        if pass_rate < 90:
            recommendations.append(f"Overall pass rate below 90% (current: {pass_rate:.1f}%) - review audio processing pipeline")

        # Check for voice-specific issues
        voice_failures = {}
        for result in results:
            if not result.meets_enterprise_standard:
                voice = result.voice
                voice_failures[voice] = voice_failures.get(voice, 0) + 1

        if voice_failures:
            worst_voice = max(voice_failures.items(), key=lambda x: x[1])
            recommendations.append(f"Voice '{worst_voice[0]}' has {worst_voice[1]} quality failures - investigate voice-specific processing")

        # Check for text length issues
        long_text_failures = sum(1 for r in results if "long" in r.test_name and not r.meets_enterprise_standard)
        if long_text_failures > len(results) * 0.3:
            recommendations.append("High failure rate for long texts - review long-form audio processing")

        return recommendations

    def save_benchmark_report(self, results: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Save benchmark results to a JSON file."""
        import json
        from datetime import datetime

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"artifacts/bench/audio_quality_{timestamp}.json"

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp to results
        results["timestamp"] = datetime.now().isoformat()
        results["benchmark_type"] = "audio_quality"

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Audio quality benchmark report saved to: {output_path}")
        return output_path


# Convenience function for quick benchmarking
async def run_audio_quality_benchmark(voices: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run a comprehensive audio quality benchmark.

    @param voices: List of voices to test
    @returns Benchmark results dictionary
    """
    benchmark = AudioQualityBenchmark()
    return await benchmark.run_comprehensive_benchmark(voices)
