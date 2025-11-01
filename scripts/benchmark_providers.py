#!/usr/bin/env python3
"""
Provider Benchmark Script - Efficient Version

Benchmarks CPU, GPU, and GPU_ANE (Neural Engine) execution providers
by reusing model sessions for efficiency.

Usage:
    python3 scripts/benchmark_providers.py
    python3 scripts/benchmark_providers.py --text "Your custom text here"
    python3 scripts/benchmark_providers.py --runs 10 --warmup 3
"""

import argparse
import os
import sys
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from statistics import mean, median, stdev


# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Test texts of different lengths
SHORT_TEXT = "Hello, this is a short test sentence."
MEDIUM_TEXT = (
    "As you explore, notice how small changes ripple through your design: "
    "a narrow aperture might trip up recognition at 12px, while a higher x-height "
    "can unlock surprising readability in micro-copy."
)
LONG_TEXT = (
    "As you explore, notice how small changes ripple through your design: "
    "a narrow aperture might trip up \"c/e\" recognition at 12px, while a higher x‑height "
    "can unlock surprising readability in micro‑copy. Export your favorite axis settings as tokens, "
    "preview them across light/dark modes and device resolutions, then save and share presets "
    "directly into your design system.\n\n"
    "Ready to turn theory into practice? Jump in, experiment boldly, and let every tweak inform "
    "your next typographic decision—because true mastery comes from seeing anatomy in action."
)


@dataclass
class BenchmarkResult:
    """Results for a single benchmark run."""
    provider: str
    text_length: int
    inference_time_ms: float
    total_samples: int
    success: bool
    error: Optional[str] = None


@dataclass
class ProviderStats:
    """Aggregated statistics for a provider."""
    provider: str
    runs: int
    successful_runs: int
    avg_inference_time_ms: float
    median_inference_time_ms: float
    stddev_inference_time_ms: float
    avg_samples: int
    errors: List[str]


def create_provider_config(provider_type: str) -> List:
    """
    Create provider configuration for testing.
    
    @param provider_type: One of 'cpu', 'gpu', 'gpu_ane'
    @returns: List of providers for ONNX Runtime
    """
    if provider_type == "cpu":
        return ["CPUExecutionProvider"]
    elif provider_type == "gpu":
        return [("CoreMLExecutionProvider", {"MLComputeUnits": "CPUAndGPU"}), "CPUExecutionProvider"]
    elif provider_type == "gpu_ane":
        return [("CoreMLExecutionProvider", {"MLComputeUnits": "CPUAndNeuralEngine"}), "CPUExecutionProvider"]
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


def run_benchmark_suite(
    provider_type: str,
    text: str,
    voice: str = "bm_fable",
    speed: float = 1.25,
    lang: str = "en-us",
    runs: int = 5,
    warmup: int = 2,
) -> ProviderStats:
    """
    Run benchmark suite for a specific provider - reuses model instance for efficiency.
    """
    print(f"  Initializing {provider_type.upper()} provider...")
    
    try:
        import onnxruntime as ort
        from api.config import TTSConfig
        from api.model.providers import create_coreml_provider_options, create_optimized_session_options
        from api.model.hardware import detect_apple_silicon_capabilities
        from kokoro_onnx import Kokoro
        
        capabilities = detect_apple_silicon_capabilities()
        session_options = create_optimized_session_options(capabilities)
        providers = create_provider_config(provider_type)
        
        # Create ONNX session with specific provider (reuse for all runs)
        print(f"  Creating session...")
        ort_session = ort.InferenceSession(
            TTSConfig.MODEL_PATH,
            sess_options=session_options,
            providers=providers
        )
        
        # Wrap in Kokoro model
        model = Kokoro.from_session(
            session=ort_session,
            voices_path=TTSConfig.VOICES_PATH
        )
        
        print(f"  Running {warmup} warmup runs...")
        for i in range(warmup):
            model.create(text, voice, speed, lang)
            time.sleep(0.1)
        
        print(f"  Running {runs} benchmark runs...")
        results: List[BenchmarkResult] = []
        
        for i in range(runs):
            start_time = time.perf_counter()
            try:
                result = model.create(text, voice, speed, lang)
                inference_time_ms = (time.perf_counter() - start_time) * 1000.0
                
                samples = result[0] if isinstance(result, tuple) else result
                total_samples = len(samples) if hasattr(samples, '__len__') else 0
                
                result_obj = BenchmarkResult(
                    provider=provider_type,
                    text_length=len(text),
                    inference_time_ms=inference_time_ms,
                    total_samples=total_samples,
                    success=True,
                    error=None
                )
                results.append(result_obj)
                
                print(f"    Run {i+1}: {inference_time_ms:.2f}ms ({total_samples:,} samples)")
                
            except Exception as e:
                results.append(BenchmarkResult(
                    provider=provider_type,
                    text_length=len(text),
                    inference_time_ms=0.0,
                    total_samples=0,
                    success=False,
                    error=str(e)
                ))
                print(f"    Run {i+1}: Error - {str(e)[:60]}...")
            
            time.sleep(0.1)
        
        # Calculate statistics
        successful_results = [r for r in results if r.success]
        errors = [r.error for r in results if r.error]
        
        if not successful_results:
            return ProviderStats(
                provider=provider_type,
                runs=runs,
                successful_runs=0,
                avg_inference_time_ms=0.0,
                median_inference_time_ms=0.0,
                stddev_inference_time_ms=0.0,
                avg_samples=0,
                errors=errors
            )
        
        inference_times = [r.inference_time_ms for r in successful_results]
        sample_counts = [r.total_samples for r in successful_results]
        
        return ProviderStats(
            provider=provider_type,
            runs=runs,
            successful_runs=len(successful_results),
            avg_inference_time_ms=mean(inference_times),
            median_inference_time_ms=median(inference_times),
            stddev_inference_time_ms=stdev(inference_times) if len(inference_times) > 1 else 0.0,
            avg_samples=int(mean(sample_counts)),
            errors=errors
        )
        
    except Exception as e:
        import traceback
        print(f"  ✗ Failed to initialize: {str(e)}")
        return ProviderStats(
            provider=provider_type,
            runs=runs,
            successful_runs=0,
            avg_inference_time_ms=0.0,
            median_inference_time_ms=0.0,
            stddev_inference_time_ms=0.0,
            avg_samples=0,
            errors=[str(e)]
        )


def print_benchmark_results(stats: List[ProviderStats], text_length: int):
    """Print formatted benchmark results."""
    print("\n" + "=" * 100)
    print(f"PROVIDER BENCHMARK RESULTS (Text Length: {text_length} characters)")
    print("=" * 100)
    print()
    
    # Header
    print(f"{'Provider':<15} {'Runs':<8} {'Success':<10} {'Avg Time':<12} {'Median Time':<14} {'StdDev':<10} {'Avg Samples':<12}")
    print("-" * 100)
    
    # Results
    for stat in stats:
        success_rate = (stat.successful_runs / stat.runs * 100) if stat.runs > 0 else 0
        print(
            f"{stat.provider:<15} "
            f"{stat.runs:<8} "
            f"{stat.successful_runs}/{stat.runs} ({success_rate:.0f}%){'':<2} "
            f"{stat.avg_inference_time_ms:>8.2f}ms{'':<2} "
            f"{stat.median_inference_time_ms:>10.2f}ms{'':<2} "
            f"{stat.stddev_inference_time_ms:>8.2f}ms{'':<2} "
            f"{stat.avg_samples:>10,}"
        )
        
        if stat.errors:
            print(f"  ⚠️  Errors: {len(stat.errors)}")
            for error in stat.errors[:2]:  # Show first 2 errors
                print(f"     - {error[:60]}...")
    
    print()
    
    # Comparison
    print("PERFORMANCE COMPARISON:")
    print("-" * 100)
    
    # Find best inference time
    successful_stats = [s for s in stats if s.successful_runs > 0]
    if successful_stats:
        best_time = min(successful_stats, key=lambda s: s.avg_inference_time_ms)
        print(f"🏆 Fastest: {best_time.provider} ({best_time.avg_inference_time_ms:.2f}ms)")
        
        for stat in successful_stats:
            if stat.provider != best_time.provider:
                diff = stat.avg_inference_time_ms - best_time.avg_inference_time_ms
                pct = (diff / best_time.avg_inference_time_ms * 100) if best_time.avg_inference_time_ms > 0 else 0
                print(f"   vs {stat.provider}: {diff:+.2f}ms ({pct:+.1f}%)")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark CPU, GPU, and GPU_ANE execution providers"
    )
    parser.add_argument(
        "--text",
        help="Custom text to benchmark (default: uses multiple text lengths)"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of benchmark runs per provider (default: 5)"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Number of warmup runs per provider (default: 2)"
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["cpu", "gpu", "gpu_ane"],
        default=["cpu", "gpu", "gpu_ane"],
        help="Providers to benchmark (default: all)"
    )
    parser.add_argument(
        "--voice",
        default="bm_fable",
        help="Voice to use for benchmarking (default: bm_fable)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.25,
        help="Speed multiplier (default: 1.25)"
    )
    parser.add_argument(
        "--json",
        help="Output results to JSON file"
    )
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("PROVIDER BENCHMARK")
    print("=" * 100)
    print(f"Runs per provider: {args.runs}")
    print(f"Warmup runs: {args.warmup}")
    print(f"Providers: {', '.join(args.providers)}")
    print(f"Voice: {args.voice}")
    print(f"Speed: {args.speed}")
    print()
    
    # Determine test texts
    if args.text:
        test_texts = [("custom", args.text)]
    else:
        test_texts = [
            ("short", SHORT_TEXT),
            ("medium", MEDIUM_TEXT),
            ("long", LONG_TEXT),
        ]
    
    all_results = {}
    
    # Run benchmarks for each text length
    for text_name, text in test_texts:
        print(f"\n{'='*100}")
        print(f"Testing: {text_name.upper()} text ({len(text)} characters)")
        print(f"{'='*100}\n")
        
        stats_list: List[ProviderStats] = []
        
        for provider_type in args.providers:
            print(f"Benchmarking {provider_type.upper()} provider...")
            stats = run_benchmark_suite(
                provider_type,
                text,
                voice=args.voice,
                speed=args.speed,
                lang="en-us",
                runs=args.runs,
                warmup=args.warmup,
            )
            stats_list.append(stats)
            print(f"✓ {provider_type.upper()} completed\n")
        
        print_benchmark_results(stats_list, len(text))
        all_results[text_name] = [asdict(s) for s in stats_list]
    
    # Save JSON if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"✓ Results saved to {args.json}")
    
    print("=" * 100)
    print("BENCHMARK COMPLETE")
    print("=" * 100)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
