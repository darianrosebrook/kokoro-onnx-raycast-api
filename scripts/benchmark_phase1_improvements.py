#!/usr/bin/env python3
"""
Phase 1 Phonemizer Improvements Benchmark

This script benchmarks the enhanced phonemizer configuration to measure
performance improvements and quality enhancements over the baseline implementation.

## Features

- **Performance Comparison**: Measures processing speed improvements
- **Quality Assessment**: Evaluates phonemization accuracy and consistency
- **Configuration Testing**: Tests different phonemizer settings
- **Statistical Analysis**: Provides detailed performance metrics

## Usage

```bash
# Run basic benchmark
python scripts/benchmark_phase1_improvements.py

# Run with specific configuration
KOKORO_PHONEMIZER_BACKEND=espeak-ng python scripts/benchmark_phase1_improvements.py

# Run comprehensive test
python scripts/benchmark_phase1_improvements.py --comprehensive
```

@author: @darianrosebrook
@date: 2025-01-08
@version: 1.0.0
"""

import sys
import os
import time
import argparse
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import statistics

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.config import TTSConfig
from api.tts.text_processing import text_to_phonemes
# PerformanceStats not available, using functions directly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark test."""
    test_name: str
    text: str
    processing_time: float
    phoneme_count: int
    word_count: int
    quality_score: float
    error_count: int
    configuration: Dict[str, Any]


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results."""
    total_tests: int
    average_processing_time: float
    average_quality_score: float
    total_errors: int
    performance_improvement: float
    quality_improvement: float
    best_configuration: Dict[str, Any]
    recommendations: List[str]


class Phase1Benchmark:
    """
    Benchmark suite for Phase 1 phonemizer improvements.
    
    This class provides comprehensive benchmarking capabilities for evaluating
    the enhanced phonemizer configuration against baseline performance.
    """
    
    def __init__(self):
        """Initialize the benchmark suite."""
        self.results: List[BenchmarkResult] = []
        self.baseline_results: List[BenchmarkResult] = []
        self.test_texts = self._load_test_texts()
        
    def _load_test_texts(self) -> List[str]:
        """Load test texts for benchmarking."""
        return [
            # Short texts for basic performance
            "Hello world",
            "The quick brown fox jumps over the lazy dog.",
            "Kokoro TTS synthesis is amazing.",
            
            # Medium texts for quality assessment
            "If you can hear this, you are apparently a human. Unlike Dave, who is apparently a robot.",
            "This comprehensive benchmark test evaluates TTS performance under realistic conditions.",
            
            # Complex texts for stress testing
            "The evaluation includes various linguistic elements: punctuation marks, numbers like 123 and 456, different sentence structures, and sustained processing requirements.",
            
            # Edge cases
            "What's up with the wire in his mouth? I thought at first he was just a quirky IT guy.",
            "I've been serving Dave oil instead of chocolate milk, like he was originally asking for.",
        ]
    
    def _calculate_quality_score(self, text: str, phonemes: List[str]) -> float:
        """
        Calculate phonemization quality score.
        
        Args:
            text: Original input text
            phonemes: Generated phonemes
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not phonemes:
            return 0.0
        
        # Basic quality metrics
        text_length = len(text.replace(' ', ''))
        phoneme_length = len(phonemes)
        
        # Length ratio (should be reasonable)
        length_ratio = min(phoneme_length / max(text_length, 1), 3.0) / 3.0
        
        # Character coverage (phonemes should cover most characters)
        text_chars = set(text.lower().replace(' ', ''))
        phoneme_chars = set(''.join(phonemes).lower())
        coverage = len(text_chars.intersection(phoneme_chars)) / max(len(text_chars), 1)
        
        # Consistency (phonemes should be consistent)
        unique_phonemes = len(set(phonemes))
        consistency = 1.0 - (unique_phonemes / max(len(phonemes), 1))
        
        # Combined score
        quality_score = (length_ratio * 0.3 + coverage * 0.4 + consistency * 0.3)
        return min(max(quality_score, 0.0), 1.0)
    
    def _count_errors(self, text: str, phonemes: List[str]) -> int:
        """
        Count phonemization errors.
        
        Args:
            text: Original input text
            phonemes: Generated phonemes
            
        Returns:
            Number of detected errors
        """
        error_count = 0
        
        # Check for empty phonemes
        if not phonemes:
            error_count += 1
        
        # Check for extremely short phonemes
        if len(phonemes) < len(text) * 0.1:
            error_count += 1
        
        # Check for extremely long phonemes
        if len(phonemes) > len(text) * 10:
            error_count += 1
        
        # Check for repeated phonemes (potential stuck state)
        if len(set(phonemes)) < len(phonemes) * 0.1:
            error_count += 1
        
        return error_count
    
    def run_single_test(self, text: str, config_name: str = "default") -> BenchmarkResult:
        """
        Run a single benchmark test.
        
        Args:
            text: Text to phonemize
            config_name: Name of the configuration being tested
            
        Returns:
            Benchmark result
        """
        start_time = time.time()
        
        try:
            # Perform phonemization
            phonemes = text_to_phonemes(text)
            processing_time = time.time() - start_time
            
            # Calculate metrics
            phoneme_count = len(phonemes)
            word_count = len(text.split())
            quality_score = self._calculate_quality_score(text, phonemes)
            error_count = self._count_errors(text, phonemes)
            
            # Get current configuration
            configuration = {
                "backend": TTSConfig.PHONEMIZER_BACKEND,
                "language": TTSConfig.PHONEMIZER_LANGUAGE,
                "preserve_punctuation": TTSConfig.PHONEMIZER_PRESERVE_PUNCTUATION,
                "strip_stress": TTSConfig.PHONEMIZER_STRIP_STRESS,
                "quality_mode": TTSConfig.PHONEMIZER_QUALITY_MODE,
                "error_tolerance": TTSConfig.PHONEMIZER_ERROR_TOLERANCE,
            }
            
            result = BenchmarkResult(
                test_name=f"{config_name}_{len(text)}",
                text=text,
                processing_time=processing_time,
                phoneme_count=phoneme_count,
                word_count=word_count,
                quality_score=quality_score,
                error_count=error_count,
                configuration=configuration
            )
            
            logger.debug(f"✅ Test completed: {result.test_name} in {processing_time:.4f}s")
            return result
            
        except Exception as e:
            logger.error(f" Failed test {config_name}: {e}")
            processing_time = time.time() - start_time
            
            return BenchmarkResult(
                test_name=f"{config_name}_{len(text)}",
                text=text,
                processing_time=processing_time,
                phoneme_count=0,
                word_count=len(text.split()),
                quality_score=0.0,
                error_count=1,
                configuration={}
            )
    
    def run_baseline_tests(self) -> None:
        """Run baseline tests with default configuration."""
        logger.info(" Running baseline tests...")
        
        # Store original configuration
        original_backend = TTSConfig.PHONEMIZER_BACKEND
        original_language = TTSConfig.PHONEMIZER_LANGUAGE
        
        # Set baseline configuration
        TTSConfig.PHONEMIZER_BACKEND = "espeak"
        TTSConfig.PHONEMIZER_LANGUAGE = "en-us"
        TTSConfig.PHONEMIZER_PRESERVE_PUNCTUATION = False
        TTSConfig.PHONEMIZER_STRIP_STRESS = True
        TTSConfig.PHONEMIZER_QUALITY_MODE = False
        TTSConfig.PHONEMIZER_ERROR_TOLERANCE = 0.0
        
        # Run tests
        for text in self.test_texts:
            result = self.run_single_test(text, "baseline")
            self.baseline_results.append(result)
        
        # Restore original configuration
        TTSConfig.PHONEMIZER_BACKEND = original_backend
        TTSConfig.PHONEMIZER_LANGUAGE = original_language
        
        logger.info(f"✅ Baseline tests completed: {len(self.baseline_results)} tests")
    
    def run_enhanced_tests(self) -> None:
        """Run enhanced tests with optimized configuration."""
        logger.info(" Running enhanced tests...")
        
        # Enhanced configuration is already set in TTSConfig
        for text in self.test_texts:
            result = self.run_single_test(text, "enhanced")
            self.results.append(result)
        
        logger.info(f"✅ Enhanced tests completed: {len(self.results)} tests")
    
    def run_configuration_tests(self) -> None:
        """Run tests with different phonemizer configurations."""
        logger.info(" Running configuration comparison tests...")
        
        configurations = [
            ("espeak_quality", {
                "backend": "espeak",
                "language": "en-us",
                "preserve_punctuation": True,
                "strip_stress": False,
                "quality_mode": True,
                "error_tolerance": 0.1
            }),
            ("espeak_fast", {
                "backend": "espeak",
                "language": "en-us",
                "preserve_punctuation": False,
                "strip_stress": True,
                "quality_mode": False,
                "error_tolerance": 0.0
            }),
            ("espeak_ng_quality", {
                "backend": "espeak-ng",
                "language": "en-us",
                "preserve_punctuation": True,
                "strip_stress": False,
                "quality_mode": True,
                "error_tolerance": 0.1
            }),
        ]
        
        for config_name, config in configurations:
            logger.info(f" Testing configuration: {config_name}")
            
            # Apply configuration
            TTSConfig.PHONEMIZER_BACKEND = config["backend"]
            TTSConfig.PHONEMIZER_LANGUAGE = config["language"]
            TTSConfig.PHONEMIZER_PRESERVE_PUNCTUATION = config["preserve_punctuation"]
            TTSConfig.PHONEMIZER_STRIP_STRESS = config["strip_stress"]
            TTSConfig.PHONEMIZER_QUALITY_MODE = config["quality_mode"]
            TTSConfig.PHONEMIZER_ERROR_TOLERANCE = config["error_tolerance"]
            
            # Run tests with this configuration
            for text in self.test_texts:
                result = self.run_single_test(text, config_name)
                self.results.append(result)
    
    def generate_summary(self) -> BenchmarkSummary:
        """
        Generate comprehensive benchmark summary.
        
        Returns:
            Benchmark summary with recommendations
        """
        if not self.results:
            raise ValueError("No benchmark results available")
        
        # Calculate enhanced metrics
        enhanced_times = [r.processing_time for r in self.results if r.test_name.startswith("enhanced")]
        enhanced_quality = [r.quality_score for r in self.results if r.test_name.startswith("enhanced")]
        enhanced_errors = sum(r.error_count for r in self.results if r.test_name.startswith("enhanced"))
        
        # Calculate baseline metrics
        baseline_times = [r.processing_time for r in self.baseline_results]
        baseline_quality = [r.quality_score for r in self.baseline_results]
        baseline_errors = sum(r.error_count for r in self.baseline_results)
        
        # Calculate improvements
        performance_improvement = 0.0
        quality_improvement = 0.0
        
        if baseline_times and enhanced_times:
            baseline_avg_time = statistics.mean(baseline_times)
            enhanced_avg_time = statistics.mean(enhanced_times)
            performance_improvement = ((baseline_avg_time - enhanced_avg_time) / baseline_avg_time) * 100
        
        if baseline_quality and enhanced_quality:
            baseline_avg_quality = statistics.mean(baseline_quality)
            enhanced_avg_quality = statistics.mean(enhanced_quality)
            quality_improvement = ((enhanced_avg_quality - baseline_avg_quality) / baseline_avg_quality) * 100
        
        # Find best configuration
        config_scores = {}
        for result in self.results:
            config_key = f"{result.configuration.get('backend', 'unknown')}_{result.configuration.get('quality_mode', False)}"
            if config_key not in config_scores:
                config_scores[config_key] = []
            config_scores[config_key].append(result.quality_score)
        
        best_config_key = max(config_scores.keys(), key=lambda k: statistics.mean(config_scores[k]))
        best_configuration = {
            "backend": best_config_key.split('_')[0],
            "quality_mode": best_config_key.split('_')[1] == "True"
        }
        
        # Generate recommendations
        recommendations = []
        
        if performance_improvement > 10:
            recommendations.append("✅ Significant performance improvement achieved")
        elif performance_improvement > 0:
            recommendations.append("✅ Moderate performance improvement achieved")
        else:
            recommendations.append("⚠️ No performance improvement detected")
        
        if quality_improvement > 10:
            recommendations.append("✅ Significant quality improvement achieved")
        elif quality_improvement > 0:
            recommendations.append("✅ Moderate quality improvement achieved")
        else:
            recommendations.append("⚠️ No quality improvement detected")
        
        if enhanced_errors < baseline_errors:
            recommendations.append("✅ Error rate reduced")
        else:
            recommendations.append("⚠️ Error rate increased")
        
        if best_configuration["quality_mode"]:
            recommendations.append("✅ Quality mode recommended for production")
        else:
            recommendations.append("✅ Fast mode recommended for development")
        
        return BenchmarkSummary(
            total_tests=len(self.results),
            average_processing_time=statistics.mean(enhanced_times) if enhanced_times else 0.0,
            average_quality_score=statistics.mean(enhanced_quality) if enhanced_quality else 0.0,
            total_errors=enhanced_errors,
            performance_improvement=performance_improvement,
            quality_improvement=quality_improvement,
            best_configuration=best_configuration,
            recommendations=recommendations
        )
    
    def print_results(self, summary: BenchmarkSummary) -> None:
        """
        Print benchmark results in a formatted way.
        
        Args:
            summary: Benchmark summary to display
        """
        print("\n" + "="*80)
        print("PHASE 1 PHONEMIZER IMPROVEMENTS BENCHMARK RESULTS")
        print("="*80)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total tests: {summary.total_tests}")
        print(f"   Average processing time: {summary.average_processing_time:.4f}s")
        print(f"   Average quality score: {summary.average_quality_score:.3f}")
        print(f"   Total errors: {summary.total_errors}")
        
        print(f"\n📈 IMPROVEMENTS:")
        print(f"   Performance improvement: {summary.performance_improvement:+.1f}%")
        print(f"   Quality improvement: {summary.quality_improvement:+.1f}%")
        
        print(f"\n⚙️ BEST CONFIGURATION:")
        print(f"   Backend: {summary.best_configuration['backend']}")
        print(f"   Quality mode: {summary.best_configuration['quality_mode']}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for recommendation in summary.recommendations:
            print(f"   {recommendation}")
        
        print(f"\n🔧 CURRENT CONFIGURATION:")
        print(f"   Backend: {TTSConfig.PHONEMIZER_BACKEND}")
        print(f"   Language: {TTSConfig.PHONEMIZER_LANGUAGE}")
        print(f"   Preserve punctuation: {TTSConfig.PHONEMIZER_PRESERVE_PUNCTUATION}")
        print(f"   Strip stress: {TTSConfig.PHONEMIZER_STRIP_STRESS}")
        print(f"   Quality mode: {TTSConfig.PHONEMIZER_QUALITY_MODE}")
        print(f"   Error tolerance: {TTSConfig.PHONEMIZER_ERROR_TOLERANCE}")
        
        print("\n" + "="*80)


def main():
    """Main benchmark execution function."""
    parser = argparse.ArgumentParser(description="Phase 1 Phonemizer Improvements Benchmark")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive configuration tests")
    parser.add_argument("--baseline-only", action="store_true", help="Run only baseline tests")
    parser.add_argument("--enhanced-only", action="store_true", help="Run only enhanced tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🚀 Starting Phase 1 Phonemizer Improvements Benchmark")
    
    # Initialize benchmark suite
    benchmark = Phase1Benchmark()
    
    try:
        # Run baseline tests
        if not args.enhanced_only:
            benchmark.run_baseline_tests()
        
        # Run enhanced tests
        if not args.baseline_only:
            benchmark.run_enhanced_tests()
        
        # Run configuration tests if comprehensive
        if args.comprehensive:
            benchmark.run_configuration_tests()
        
        # Generate and display results
        summary = benchmark.generate_summary()
        benchmark.print_results(summary)
        
        logger.info("✅ Benchmark completed successfully")
        
    except Exception as e:
        logger.error(f" Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 