#!/usr/bin/env python3
"""
Model Optimization Benchmark CLI

Command-line interface for running model optimization benchmarks,
comparing original vs optimized ONNX models side-by-side.

Usage:
    python scripts/run_model_optimization_benchmark.py \\
        --original kokoro-v1.0.int8.onnx \\
        --optimized kokoro-v1.0.int8.optimized.onnx \\
        --compare \\
        --trials 5 \\
        --output results.json

Author: @darianrosebrook
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig
from benchmarks.suites.model_optimization_suite import ModelOptimizationBenchmarkSuite

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_model_optimization_benchmark(
    original_model: str,
    optimized_model: str,
    server_url: str = "http://localhost:8000",
    text: Optional[str] = None,
    provider_preference: Optional[str] = None,
    trials: int = 5,
    output_json: Optional[str] = None,
    output_markdown: Optional[str] = None,
) -> None:
    """
    Run model optimization benchmark comparison.

    Args:
        original_model: Path to original model file
        optimized_model: Path to optimized model file
        server_url: API server URL
        text: Test text (uses default if not provided)
        provider_preference: Provider preference header (CoreML/CPU)
        trials: Number of benchmark trials
        output_json: Path to save JSON results
        output_markdown: Path to save markdown report
    """
    # Verify model files exist
    if not os.path.exists(original_model):
        logger.error(f"Original model not found: {original_model}")
        sys.exit(1)

    if not os.path.exists(optimized_model):
        logger.error(f"Optimized model not found: {optimized_model}")
        sys.exit(1)

    # Use default test text if not provided
    if text is None:
        text = "Test text for model optimization comparison"

    logger.info("Starting model optimization benchmark...")
    logger.info(f"Original model: {original_model}")
    logger.info(f"Optimized model: {optimized_model}")
    logger.info(f"Trials: {trials}")
    logger.info(f"Server URL: {server_url}")

    # Create benchmark suite
    suite = ModelOptimizationBenchmarkSuite(server_url=server_url)

    # Run comparison
    try:
        results = await suite.run_comprehensive_comparison(
            original_model_path=original_model,
            optimized_model_path=optimized_model,
            test_texts=[text],
            provider_preference=provider_preference,
            trials=trials,
        )

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Model Optimization Benchmark Results")
        logger.info("=" * 60)
        logger.info(
            f"Original Model TTFA: {results.original_ttfa_mean:.2f}ms (median: {results.original_ttfa_median:.2f}ms)"
        )
        logger.info(
            f"Optimized Model TTFA: {results.optimized_ttfa_mean:.2f}ms (median: {results.optimized_ttfa_median:.2f}ms)"
        )
        logger.info(f"TTFA Improvement: {results.ttfa_improvement_percent:.2f}%")

        if results.original_rtf_mean and results.optimized_rtf_mean:
            logger.info(f"Original Model RTF: {results.original_rtf_mean:.3f}")
            logger.info(f"Optimized Model RTF: {results.optimized_rtf_mean:.3f}")
            if results.rtf_improvement_percent:
                logger.info(f"RTF Improvement: {results.rtf_improvement_percent:.2f}%")

        logger.info(f"Memory Improvement: {results.memory_improvement_percent:.2f}%")
        logger.info(f"Recommended Model: {results.recommended_model}")
        logger.info(
            f"Regression Detected: {'Yes' if results.regression_detected else 'No'}"
        )
        logger.info(
            f"Significant Improvement: {'Yes' if results.significant_improvement else 'No'}"
        )
        logger.info("=" * 60)

        # Save JSON results
        if output_json:
            results_dict = results.to_dict()
            with open(output_json, "w") as f:
                json.dump(results_dict, f, indent=2)
            logger.info(f"\nJSON results saved to: {output_json}")

        # Save markdown report
        if output_markdown:
            report = results.generate_report()
            with open(output_markdown, "w") as f:
                f.write(report)
            logger.info(f"Markdown report saved to: {output_markdown}")

        # Exit with error code if regression detected
        if results.regression_detected:
            logger.warning("\n⚠️  WARNING: Regression detected in optimized model!")
            sys.exit(1)
        elif results.significant_improvement:
            logger.info("\n✅ Optimized model shows significant improvement!")
            sys.exit(0)
        else:
            logger.info("\nℹ️  Optimized model performance is similar to original.")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run model optimization benchmark comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare models with default settings
  python scripts/run_model_optimization_benchmark.py \\
      --original kokoro-v1.0.int8.onnx \\
      --optimized kokoro-v1.0.int8.optimized.onnx \\
      --compare

  # Custom test with more trials
  python scripts/run_model_optimization_benchmark.py \\
      --original kokoro-v1.0.int8.onnx \\
      --optimized kokoro-v1.0.int8.optimized.onnx \\
      --compare \\
      --trials 10 \\
      --text "Longer test text for comprehensive comparison" \\
      --output results.json

  # Use CoreML provider
  python scripts/run_model_optimization_benchmark.py \\
      --original kokoro-v1.0.int8.onnx \\
      --optimized kokoro-v1.0.int8.optimized.onnx \\
      --compare \\
      --provider CoreMLExecutionProvider
        """,
    )

    parser.add_argument(
        "--original", "-o", required=True, help="Path to original model file"
    )

    parser.add_argument(
        "--optimized", "-p", required=True, help="Path to optimized model file"
    )

    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Enable side-by-side comparison mode",
    )

    parser.add_argument(
        "--trials",
        "-t",
        type=int,
        default=5,
        help="Number of benchmark trials (default: 5)",
    )

    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Test text for benchmarking (uses default if not provided)",
    )

    parser.add_argument(
        "--server-url",
        "-s",
        type=str,
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=["CoreMLExecutionProvider", "CPUExecutionProvider"],
        default=None,
        help="Provider preference (CoreML or CPU)",
    )

    parser.add_argument(
        "--output", "-j", type=str, default=None, help="Path to save JSON results file"
    )

    parser.add_argument(
        "--output-markdown",
        "-m",
        type=str,
        default=None,
        help="Path to save markdown report file",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Use config defaults if not provided
    original_model = args.original or TTSConfig.MODEL_PATH
    optimized_model = args.optimized or TTSConfig.OPTIMIZED_MODEL_PATH

    # Run benchmark
    asyncio.run(
        run_model_optimization_benchmark(
            original_model=original_model,
            optimized_model=optimized_model,
            server_url=args.server_url,
            text=args.text,
            provider_preference=args.provider,
            trials=args.trials,
            output_json=args.output,
            output_markdown=args.output_markdown,
        )
    )


if __name__ == "__main__":
    main()
