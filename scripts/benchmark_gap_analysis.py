#!/usr/bin/env python3
"""
Gap Analysis Benchmark for Gapless Audio Streaming

This script specifically measures the time gaps between audio chunks, focusing on:
1. Gap between first chunk and second chunk (critical for seamless audio start)
2. Gaps between all subsequent chunks
3. Identification of patterns that cause audio gaps
4. Measurement of chunk timing precision

Key metrics:
- First-to-second chunk gap (ms)
- Average inter-chunk gap (ms)
- Maximum inter-chunk gap (ms)
- Gap variability (coefficient of variation)
- Underrun detection (gaps > threshold)

Usage:
  python scripts/benchmark_gap_analysis.py --trials 10 --text-length medium --voice af_heart

Author: @darianrosebrook
Date: 2025-09-24
Version: 1.0.0
"""

import asyncio
import aiohttp
import json
import logging
import time
import statistics
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class GapAnalyzer:
    """
    Specialized analyzer for measuring and analyzing gaps between audio chunks.
    """

    def __init__(self, threshold_ms: float = 50.0):
        """
        Initialize gap analyzer.

        Args:
            threshold_ms: Gap threshold for underrun detection (default: 50ms)
        """
        self.threshold_ms = threshold_ms
        self.gap_history: List[List[float]] = []

    def analyze_chunk_gaps(self, chunks: List[Tuple[float, int]]) -> Dict[str, Any]:
        """
        Analyze gaps between chunks with detailed metrics.

        Args:
            chunks: List of (timestamp_ms, chunk_size_bytes) tuples

        Returns:
            Dictionary with gap analysis metrics
        """
        if len(chunks) < 2:
            return {
                "total_chunks": len(chunks),
                "analysis_possible": False,
                "error": "Insufficient chunks for gap analysis"
            }

        timestamps = [timestamp for timestamp, _ in chunks]

        # Calculate all inter-chunk gaps
        gaps = []
        for i in range(1, len(timestamps)):
            gap = timestamps[i] - timestamps[i-1]
            gaps.append(gap)

        # First-to-second chunk gap (critical for seamless start)
        first_to_second_gap = gaps[0] if gaps else None

        # Statistical analysis
        if gaps:
            mean_gap = statistics.mean(gaps)
            median_gap = statistics.median(gaps)
            max_gap = max(gaps)
            min_gap = min(gaps)
            std_dev = statistics.stdev(gaps) if len(gaps) > 1 else 0.0
            cv = (std_dev / mean_gap) if mean_gap > 0 else 0.0  # Coefficient of variation

            # Underrun detection (gaps significantly larger than threshold)
            underruns = [gap for gap in gaps if gap > self.threshold_ms]
            underrun_count = len(underruns)

            # Gap pattern analysis
            gap_patterns = self._analyze_gap_patterns(gaps)

            return {
                "total_chunks": len(chunks),
                "analysis_possible": True,
                "first_to_second_gap_ms": first_to_second_gap,
                "mean_gap_ms": mean_gap,
                "median_gap_ms": median_gap,
                "max_gap_ms": max_gap,
                "min_gap_ms": min_gap,
                "std_dev_ms": std_dev,
                "coefficient_of_variation": cv,
                "underrun_threshold_ms": self.threshold_ms,
                "underrun_count": underrun_count,
                "underrun_percentage": (underrun_count / len(gaps)) * 100 if gaps else 0,
                "largest_underruns": sorted(underruns, reverse=True)[:5] if underruns else [],
                "gap_patterns": gap_patterns,
                "recommendations": self._generate_recommendations(first_to_second_gap, mean_gap, underrun_count, gap_patterns)
            }
        else:
            return {
                "total_chunks": len(chunks),
                "analysis_possible": False,
                "error": "No gaps found"
            }

    def _analyze_gap_patterns(self, gaps: List[float]) -> Dict[str, Any]:
        """
        Analyze patterns in gap distribution.

        Args:
            gaps: List of gap measurements in milliseconds

        Returns:
            Dictionary with pattern analysis
        """
        if not gaps:
            return {"pattern_detected": False}

        # Categorize gaps
        small_gaps = [g for g in gaps if g < 20]  # < 20ms
        medium_gaps = [g for g in gaps if 20 <= g < 50]  # 20-50ms
        large_gaps = [g for g in gaps if g >= 50]  # >= 50ms

        # Check for periodicity (regular gaps)
        if len(gaps) >= 3:
            # Simple periodicity check - look for repeated gap patterns
            diffs = [abs(gaps[i] - gaps[i-1]) for i in range(1, len(gaps))]
            periodic = statistics.mean(diffs) < 10  # Low variance in gap differences
        else:
            periodic = False

        # Check for increasing gaps (drift)
        if len(gaps) >= 3:
            increasing = all(gaps[i] >= gaps[i-1] * 0.9 for i in range(1, len(gaps)))  # Monotonically non-decreasing
        else:
            increasing = False

        return {
            "pattern_detected": True,
            "small_gaps_count": len(small_gaps),
            "medium_gaps_count": len(medium_gaps),
            "large_gaps_count": len(large_gaps),
            "periodic_gaps": periodic,
            "increasing_gaps": increasing,
            "gap_distribution": {
                "small_pct": (len(small_gaps) / len(gaps)) * 100,
                "medium_pct": (len(medium_gaps) / len(gaps)) * 100,
                "large_pct": (len(large_gaps) / len(gaps)) * 100
            }
        }

    def _generate_recommendations(self, first_gap: Optional[float], mean_gap: float,
                                underrun_count: int, patterns: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on gap analysis.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if first_gap and first_gap > 100:
            recommendations.append("🚨 CRITICAL: First-to-second chunk gap is very large ({}ms). "
                                "This causes noticeable audio delay at start.".format(first_gap))

        if mean_gap > 30:
            recommendations.append("⚠️  WARNING: Average inter-chunk gap is high ({}ms). "
                                "Consider optimizing chunk generation pipeline.".format(mean_gap))

        if underrun_count > 0:
            recommendations.append("⚠️  WARNING: {} underruns detected (gaps > {}ms). "
                                "This indicates potential audio starvation.".format(underrun_count, self.threshold_ms))

        if patterns.get("periodic_gaps", False):
            recommendations.append("ℹ️  Periodic gaps detected. This might indicate regular processing delays.")

        if patterns.get("increasing_gaps", False):
            recommendations.append("ℹ️  Increasing gaps detected. This suggests accumulating delays over time.")

        if not recommendations:
            recommendations.append("✅ Gap analysis looks good. No significant issues detected.")

        return recommendations


class GapBenchmarkRunner:
    """
    Specialized benchmark runner for gap analysis.
    """

    def __init__(self, url: str, headers: Dict[str, str], base_payload: Dict[str, Any],
                 trials: int, text_length: str, timeout: int = 60):
        self.url = url
        self.headers = headers
        self.base_payload = base_payload
        self.trials = trials
        self.text_length = text_length
        self.timeout = timeout
        self.analyzer = GapAnalyzer()

        # Test texts of different lengths
        self.test_texts = {
            "short": "This is a short sentence for quick gap testing.",
            "medium": "This is a medium length paragraph designed to test streaming performance and identify potential bottlenecks in the audio generation pipeline that might cause gaps between chunks.",
            "long": "This is a longer paragraph that will be segmented into multiple chunks, allowing us to measure the consistency of inter-chunk timing and identify any patterns that emerge over sustained streaming periods. The goal is to ensure smooth, gapless audio playback throughout the entire duration of the synthesized speech."
        }

        # Results storage
        self.trial_results: List[Dict[str, Any]] = []
        self.baseline_metrics: Dict[str, Any] = {}

    async def run_trial(self, session: aiohttp.ClientSession, trial_num: int) -> Dict[str, Any]:
        """
        Run a single benchmark trial.

        Args:
            session: HTTP session
            trial_num: Trial number for logging

        Returns:
            Trial results dictionary
        """
        text = self.test_texts[self.text_length]
        payload = dict(self.base_payload)
        payload.update({"text": text, "stream": True})

        logger.info(f"Trial {trial_num + 1}/{self.trials}: Starting gap analysis for {self.text_length} text")

        # Measure chunk arrival times with high precision
        start_time = time.perf_counter()
        chunks: List[Tuple[float, int]] = []

        try:
            async with session.post(self.url, json=payload, headers=self.headers, timeout=self.timeout) as resp:
                resp.raise_for_status()

                async for chunk in resp.content.iter_chunked(1024):
                    if chunk:
                        chunk_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
                        chunks.append((chunk_time, len(chunk)))

        except Exception as e:
            logger.error(f"Trial {trial_num + 1} failed: {e}")
            return {"trial": trial_num + 1, "success": False, "error": str(e), "chunks": []}

        # Analyze gaps
        if len(chunks) < 2:
            logger.warning(f"Trial {trial_num + 1}: Insufficient chunks ({len(chunks)}) for gap analysis")
            return {"trial": trial_num + 1, "success": False, "error": "Insufficient chunks", "chunks": chunks}

        gap_analysis = self.analyzer.analyze_chunk_gaps(chunks)

        trial_result = {
            "trial": trial_num + 1,
            "success": True,
            "text_length": self.text_length,
            "total_chunks": len(chunks),
            "first_chunk_time_ms": chunks[0][0] if chunks else None,
            "last_chunk_time_ms": chunks[-1][0] if chunks else None,
            "total_duration_ms": chunks[-1][0] - chunks[0][0] if len(chunks) >= 2 else 0,
            "gap_analysis": gap_analysis,
            "chunks": chunks  # Keep raw chunk data for detailed analysis
        }

        logger.info(f"Trial {trial_num + 1}: Completed - {len(chunks)} chunks, "
                   f"first-to-second gap: {gap_analysis.get('first_to_second_gap_ms', 'N/A')}ms")

        return trial_result

    async def run_benchmark(self) -> Dict[str, Any]:
        """
        Run the complete gap analysis benchmark.

        Returns:
            Complete benchmark results
        """
        logger.info(f"Starting gap analysis benchmark: {self.trials} trials, {self.text_length} text")

        async with aiohttp.ClientSession() as session:
            # Run all trials
            tasks = [self.run_trial(session, i) for i in range(self.trials)]
            self.trial_results = await asyncio.gather(*tasks)

        # Analyze results across all trials
        return self._aggregate_results()

    def _aggregate_results(self) -> Dict[str, Any]:
        """
        Aggregate and analyze results across all trials.

        Returns:
            Aggregated benchmark results
        """
        successful_trials = [r for r in self.trial_results if r["success"]]

        if not successful_trials:
            return {"error": "No successful trials", "trials": self.trial_results}

        # Extract metrics from all trials
        first_to_second_gaps = []
        mean_gaps = []
        max_gaps = []
        underrun_counts = []
        all_gap_analyses = []

        for trial in successful_trials:
            gap_analysis = trial["gap_analysis"]
            all_gap_analyses.append(gap_analysis)

            if gap_analysis.get("analysis_possible"):
                first_to_second_gaps.append(gap_analysis["first_to_second_gap_ms"])
                mean_gaps.append(gap_analysis["mean_gap_ms"])
                max_gaps.append(gap_analysis["max_gap_ms"])
                underrun_counts.append(gap_analysis["underrun_count"])

        # Calculate statistics
        def safe_stats(values: List[float], name: str) -> Dict[str, Any]:
            if not values:
                return {f"{name}_available": False}

            return {
                f"{name}_available": True,
                f"{name}_mean": statistics.mean(values),
                f"{name}_median": statistics.median(values),
                f"{name}_min": min(values),
                f"{name}_max": max(values),
                f"{name}_p95": self._percentile(values, 0.95),
                f"{name}_std_dev": statistics.stdev(values) if len(values) > 1 else 0.0
            }

        # Compile results
        results = {
            "benchmark_config": {
                "trials": self.trials,
                "text_length": self.text_length,
                "url": self.url,
                "timeout_s": self.timeout,
                "underrun_threshold_ms": self.analyzer.threshold_ms
            },
            "summary": {
                "successful_trials": len(successful_trials),
                "failed_trials": self.trials - len(successful_trials),
                "total_chunks_analyzed": sum(t["total_chunks"] for t in successful_trials),
                **safe_stats(first_to_second_gaps, "first_to_second_gap"),
                **safe_stats(mean_gaps, "mean_gap"),
                **safe_stats(max_gaps, "max_gap")
            },
            "underrun_analysis": {
                "total_underruns": sum(underrun_counts),
                "avg_underruns_per_trial": statistics.mean(underrun_counts) if underrun_counts else 0,
                **safe_stats(underrun_counts, "underruns_per_trial")
            },
            "trials": self.trial_results,
            "gap_analyses": all_gap_analyses,
            "recommendations": self._generate_benchmark_recommendations(successful_trials)
        }

        return results

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile safely."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]

    def _generate_benchmark_recommendations(self, successful_trials: List[Dict[str, Any]]) -> List[str]:
        """
        Generate benchmark-level recommendations.

        Args:
            successful_trials: List of successful trial results

        Returns:
            List of recommendation strings
        """
        if not successful_trials:
            return ["❌ No successful trials to analyze"]

        # Extract key metrics
        first_gaps = []
        mean_gaps = []
        underrun_counts = []

        for trial in successful_trials:
            gap_analysis = trial["gap_analysis"]
            if gap_analysis.get("analysis_possible"):
                first_gaps.append(gap_analysis["first_to_second_gap_ms"])
                mean_gaps.append(gap_analysis["mean_gap_ms"])
                underrun_counts.append(gap_analysis["underrun_count"])

        recommendations = []

        # First-to-second gap analysis
        if first_gaps:
            avg_first_gap = statistics.mean(first_gaps)
            max_first_gap = max(first_gaps)

            if max_first_gap > 200:
                recommendations.append(f"🚨 CRITICAL: Maximum first-to-second gap is {max_first_gap:.1f}ms. "
                                    "Audio start will have noticeable delay.")
            elif avg_first_gap > 100:
                recommendations.append(f"⚠️  WARNING: Average first-to-second gap is {avg_first_gap:.1f}ms. "
                                    "Consider optimizing initial chunk generation.")
            else:
                recommendations.append(f"✅ First-to-second gap looks good (avg: {avg_first_gap:.1f}ms)")

        # Overall gap analysis
        if mean_gaps:
            avg_mean_gap = statistics.mean(mean_gaps)
            if avg_mean_gap > 50:
                recommendations.append(f"⚠️  WARNING: Average inter-chunk gap is high ({avg_mean_gap:.1f}ms). "
                                    "This affects overall streaming smoothness.")
            elif avg_mean_gap < 20:
                recommendations.append(f"✅ Excellent: Very low average inter-chunk gap ({avg_mean_gap:.1f}ms)")

        # Underrun analysis
        total_underruns = sum(underrun_counts)
        if total_underruns > 0:
            avg_underruns = statistics.mean(underrun_counts)
            recommendations.append(f"⚠️  WARNING: {total_underruns} underruns detected across all trials "
                                f"(avg {avg_underruns:.1f} per trial)")

        # Consistency analysis
        if len(successful_trials) > 1:
            gap_variability = statistics.stdev(mean_gaps) if len(mean_gaps) > 1 else 0
            if gap_variability > 20:
                recommendations.append("📊 High variability in gap timing detected. "
                                    "Consider investigating sources of timing inconsistency.")

        if not recommendations:
            recommendations.append("✅ Overall gap analysis shows good performance with no significant issues.")

        return recommendations


async def main():
    """Main entry point for gap analysis benchmark."""
    parser = argparse.ArgumentParser(
        description="Gap Analysis Benchmark for Gapless Audio Streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick analysis with short text
  python scripts/benchmark_gap_analysis.py --trials 5 --text-length short

  # Comprehensive analysis with medium text
  python scripts/benchmark_gap_analysis.py --trials 10 --text-length medium --voice af_heart

  # Long text analysis with custom threshold
  python scripts/benchmark_gap_analysis.py --trials 10 --text-length long --underrun-threshold 30
        """
    )

    parser.add_argument("--url", default="http://localhost:8000/v1/audio/speech",
                       help="TTS endpoint URL")
    parser.add_argument("--voice", default="af_heart", help="Voice name")
    parser.add_argument("--lang", default="en-us", help="Language code")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    parser.add_argument("--text-length", choices=["short", "medium", "long"],
                       default="medium", help="Text length preset")
    parser.add_argument("--trials", type=int, default=5,
                       help="Number of benchmark trials")
    parser.add_argument("--timeout", type=int, default=60,
                       help="Request timeout in seconds")
    parser.add_argument("--underrun-threshold", type=float, default=50.0,
                       help="Gap threshold for underrun detection (ms)")
    parser.add_argument("--header", action="append", default=[],
                       help="Extra header 'Key: Value' (repeatable)")
    parser.add_argument("--output", type=str, default=None,
                       help="Output file path (default: auto-generated)")

    args = parser.parse_args()

    # Parse headers
    headers = {}
    for header in args.header:
        if ":" in header:
            key, value = header.split(":", 1)
            headers[key.strip()] = value.strip()

    # Setup payload with valid parameters
    base_payload = {
        "text": "",  # Will be set per request
        "voice": args.voice,
        "speed": max(1.25, args.speed),  # Ensure speed is within valid range (1.25-4.1)
        "lang": args.lang,
        "stream": True,  # Enable streaming for gap analysis
        "format": "wav"
    }

    # Create benchmark runner
    runner = GapBenchmarkRunner(
        url=args.url,
        headers=headers,
        base_payload=base_payload,
        trials=args.trials,
        text_length=args.text_length,
        timeout=args.timeout
    )

    # Update analyzer threshold
    runner.analyzer.threshold_ms = args.underrun_threshold

    try:
        # Run benchmark
        results = await runner.run_benchmark()

        # Generate output filename if not specified
        if args.output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"artifacts/bench/gap_analysis_{args.text_length}_{timestamp}.json"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        else:
            output_file = args.output

        # Save results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Print summary
        print("\n" + "=" * 80)
        print(" GAP ANALYSIS BENCHMARK RESULTS")
        print("=" * 80)

        summary = results.get("summary", {})
        if "error" in results:
            print(f"❌ ERROR: {results['error']}")
            return 1

        print(f"Text Length: {args.text_length}")
        print(f"Successful Trials: {summary.get('successful_trials', 0)}/{args.trials}")
        print(f"Total Chunks Analyzed: {summary.get('total_chunks_analyzed', 0)}")

        if summary.get("first_to_second_gap_available"):
            print("\n📊 First-to-Second Chunk Gap (Critical for seamless start):")
            print(f"  Average: {summary['first_to_second_gap_mean']:.2f}ms")
            print(f"  Median:  {summary['first_to_second_gap_median']:.2f}ms")
            print(f"  Min/Max: {summary['first_to_second_gap_min']:.2f}ms / {summary['first_to_second_gap_max']:.2f}ms")
            print(f"  P95:     {summary['first_to_second_gap_p95']:.2f}ms")

        if summary.get("mean_gap_available"):
            print("\n📊 Overall Inter-Chunk Gaps:")
            print(f"  Average: {summary['mean_gap_mean']:.2f}ms")
            print(f"  Median:  {summary['mean_gap_median']:.2f}ms")
            print(f"  Min/Max: {summary['mean_gap_min']:.2f}ms / {summary['mean_gap_max']:.2f}ms")
            print(f"  P95:     {summary['mean_gap_p95']:.2f}ms")

        underrun_analysis = results.get("underrun_analysis", {})
        if underrun_analysis.get("total_underruns", 0) > 0:
            print("\n⚠️  Underrun Analysis:")
            print(f"  Total Underruns: {underrun_analysis['total_underruns']}")
            print(f"  Avg per Trial:   {underrun_analysis['avg_underruns_per_trial']:.1f}")

        recommendations = results.get("recommendations", [])
        print("\n🔧 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

        print("\n📁 Detailed results saved to: {}".format(output_file))
        print("=" * 80)

        # Check for critical issues
        failed_trials = args.trials - summary.get('successful_trials', 0)
        if failed_trials > 0:
            print(f"⚠️  WARNING: {failed_trials} trials failed")
            return 1

        # Check for critical gaps
        if (summary.get("first_to_second_gap_available") and
            summary.get("first_to_second_gap_p95", 0) > 200):
            print("🚨 CRITICAL: First-to-second chunk gaps are too large for seamless audio")
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
