"""
Enhanced run_bench.py - Consolidated Benchmark Runner

This is the main entry point for running comprehensive benchmarks.
Supports both CLI and programmatic usage.
"""

#!/usr/bin/env python3
"""
Kokoro TTS – Comprehensive Benchmark Harness (Enhanced)

Enhanced version with M-series Mac optimization support and consolidated architecture.
"""

import argparse
import asyncio
import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import consolidated benchmark suites
from benchmarks.suites.ttfa_suite import TTFABenchmarkSuite
from benchmarks.suites.provider_suite import ProviderBenchmarkSuite
from benchmarks.suites.m_series_suite import MSeriesBenchmarkSuite


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


async def run_ttfa_benchmark(args):
    """Run TTFA benchmark suite"""
    print("=" * 64)
    print("TTFA BENCHMARK SUITE")
    print("=" * 64)
    
    suite = TTFABenchmarkSuite(server_url=args.url)
    results = await suite.run_full_suite()
    
    print("\n" + suite.generate_consolidated_report())
    
    return results


async def run_provider_benchmark(args):
    """Run provider comparison benchmark"""
    print("=" * 64)
    print("PROVIDER COMPARISON BENCHMARK")
    print("=" * 64)
    
    suite = ProviderBenchmarkSuite(server_url=args.url)
    results = await suite.run_comprehensive_provider_benchmark()
    summary = suite.get_summary()
    
    print(f"\nProvider Comparison Results:")
    print(f"Overall Recommendation: {summary.get('overall_recommendation', 'N/A')}")
    print(f"M-series Optimized Count: {summary.get('m_series_optimized_count', 0)}")
    
    for text_type, comparison in results.items():
        print(f"\n{text_type.upper()} Text:")
        print(f"  CoreML Avg: {comparison.coreml_avg_time_ms:.1f}ms")
        print(f"  CPU Avg: {comparison.cpu_avg_time_ms:.1f}ms")
        print(f"  Recommended: {comparison.recommended_provider}")
        print(f"  M-series Optimized: {'✅' if comparison.m_series_optimized else ''}")
    
    return results


async def run_m_series_benchmark(args):
    """Run M-series Mac optimization validation"""
    print("=" * 64)
    print("M-SERIES MAC OPTIMIZATION BENCHMARK")
    print("=" * 64)
    
    suite = MSeriesBenchmarkSuite(server_url=args.url)
    results = await suite.run_comprehensive_m_series_benchmark()
    summary = suite.get_summary()
    
    print(f"\nM-series Optimization Validation:")
    print(f"All Targets Met: {'✅' if summary['all_targets_met'] else ''}")
    
    for test_name, result in results.items():
        print(f"\n{test_name.upper()} Test:")
        print(f"  TTFA: {result.ttfa_ms:.1f}ms")
        print(f"  Neural Engine: {'✅' if result.neural_engine_detected else ''}")
        print(f"  CoreML Available: {'✅' if result.coreml_available else ''}")
        print(f"  Targets Met: {sum(result.optimization_targets_met.values())}/{len(result.optimization_targets_met)}")
        if result.recommendations:
            print(f"  Recommendations:")
            for rec in result.recommendations:
                print(f"    - {rec}")
    
    return results


async def run_comprehensive_benchmark(args):
    """Run comprehensive benchmark suite"""
    print("=" * 64)
    print("COMPREHENSIVE BENCHMARK SUITE")
    print("=" * 64)
    
    results = {}
    
    # Run TTFA benchmark
    print("\n[1/3] Running TTFA Benchmark...")
    ttfa_results = await run_ttfa_benchmark(args)
    results["ttfa"] = ttfa_results
    
    # Run provider benchmark
    print("\n[2/3] Running Provider Comparison...")
    provider_results = await run_provider_benchmark(args)
    results["provider"] = provider_results
    
    # Run M-series benchmark
    print("\n[3/3] Running M-series Optimization Validation...")
    m_series_results = await run_m_series_benchmark(args)
    results["m_series"] = m_series_results
    
    print("\n" + "=" * 64)
    print("COMPREHENSIVE BENCHMARK COMPLETE")
    print("=" * 64)
    
    return results


async def main():
    """Main benchmark entry point"""
    parser = argparse.ArgumentParser(
        description="Kokoro TTS Comprehensive Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run TTFA benchmark
  python scripts/run_bench.py --suite ttfa

  # Run provider comparison
  python scripts/run_bench.py --suite provider

  # Run M-series Mac optimization validation
  python scripts/run_bench.py --suite m-series

  # Run comprehensive suite
  python scripts/run_bench.py --suite comprehensive
        """
    )
    
    parser.add_argument("--url", default="http://localhost:8000", help="TTS server URL")
    parser.add_argument(
        "--suite",
        choices=["ttfa", "provider", "m-series", "comprehensive"],
        default="comprehensive",
        help="Benchmark suite to run"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    try:
        if args.suite == "ttfa":
            await run_ttfa_benchmark(args)
        elif args.suite == "provider":
            await run_provider_benchmark(args)
        elif args.suite == "m-series":
            await run_m_series_benchmark(args)
        else:
            await run_comprehensive_benchmark(args)
        
        return 0
    except Exception as e:
        logging.error(f"Benchmark failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))




