#!/usr/bin/env python3
"""
MPS Provider Benchmark for Kokoro TTS Models
Benchmarks different quantized models with MPS provider for CoreML/ANE performance
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import onnxruntime as ort

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("kokoro.mps_bench")


def get_model_size_mb(path: str) -> float:
    """Get model size in MB"""
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0


def benchmark_model_mps(
    model_path: str,
    runs: int = 5,
    providers_order: Optional[List[str]] = None,
    coreml_compute_units: Optional[str] = None,
) -> Dict[str, Any]:
    """Benchmark a model with a specific provider order (MPS/CoreML/CPU) and optional CoreML compute units."""
    pretty_order = ",".join(providers_order) if providers_order else "MPS,CoreML,CPU"
    logger.info(
        f"Benchmarking {os.path.basename(model_path)} with providers: {pretty_order} ..."
    )

    try:
        # Build providers preference
        if providers_order is None:
            providers = [
                "MPSExecutionProvider",
                "CoreMLExecutionProvider",
                "CPUExecutionProvider",
            ]
        else:
            # Map shorthand to ORT provider names
            mapping = {
                "mps": "MPSExecutionProvider",
                "coreml": "CoreMLExecutionProvider",
                "cpu": "CPUExecutionProvider",
                # Allow direct ORT names too
                "MPSExecutionProvider": "MPSExecutionProvider",
                "CoreMLExecutionProvider": "CoreMLExecutionProvider",
                "CPUExecutionProvider": "CPUExecutionProvider",
            }
            providers = []
            for p in providers_order:
                mapped = mapping.get(p.lower(), p)
                # If CoreML and compute units specified, add options
                if mapped == "CoreMLExecutionProvider" and coreml_compute_units:
                    providers.append(
                        (
                            "CoreMLExecutionProvider",
                            {"MLComputeUnits": coreml_compute_units},
                        )
                    )
                else:
                    providers.append(mapped)
            # Always add CPU fallback for CoreML
            if "CoreMLExecutionProvider" in [
                p if isinstance(p, str) else p[0] for p in providers
            ]:
                if "CPUExecutionProvider" not in [
                    p if isinstance(p, str) else p[0] for p in providers
                ]:
                    providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(model_path, providers=providers)

        # Get actual provider being used
        actual_provider = session.get_providers()[0]
        logger.info(f"Using provider: {actual_provider}")

        # Prepare inputs
        inputs = {
            "tokens": np.array([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]], dtype=np.int64),
            "style": np.random.randn(1, 256).astype(np.float32),
            "speed": np.array([1.0], dtype=np.float32),
        }

        # Warmup
        for _ in range(3):
            session.run(None, inputs)

        # Benchmark
        times = []
        for i in range(runs):
            start = time.time()
            session.run(None, inputs)
            end = time.time()
            times.append((end - start) * 1000)
            logger.info(f"  Trial {i + 1}: {times[-1]:.2f}ms")

        return {
            "provider": actual_provider,
            "avg": np.mean(times),
            "min": np.min(times),
            "max": np.max(times),
            "p50": np.median(times),
            "p95": np.percentile(times, 95),
            "std": np.std(times),
        }

    except Exception as e:
        logger.error(f"Failed to benchmark {model_path}: {e}")
        return {
            "provider": "ERROR",
            "avg": 0,
            "min": 0,
            "max": 0,
            "p50": 0,
            "p95": 0,
            "std": 0,
            "error": str(e),
        }


def compare_models_mps(
    model_paths: List[str], runs: int = 5, providers_order: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Compare multiple models with a given provider order."""
    logger.info(
        "Comparing models with provider order: %s",
        ",".join(providers_order) if providers_order else "MPS,CoreML,CPU",
    )

    results = {}

    for model_path in model_paths:
        if not os.path.exists(model_path):
            logger.warning(f"Model not found: {model_path}")
            continue

        model_name = os.path.basename(model_path)
        size_mb = get_model_size_mb(model_path)

        bench_results = benchmark_model_mps(model_path, runs, providers_order)
        bench_results["size_mb"] = size_mb

        results[model_name] = bench_results

        logger.info(f"{model_name}: {size_mb:.1f}MB, {bench_results['avg']:.2f}ms avg")

    return results


def generate_report(results: Dict[str, Any], output_file: Optional[str] = None) -> str:
    """Generate a comprehensive benchmark report"""
    report = []
    report.append("# MPS Provider Benchmark Report")
    report.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Author:** @darianrosebrook")
    report.append("")

    # Summary table
    report.append("## Model Comparison")
    report.append("")
    report.append(
        "| Model | Size (MB) | Provider | Avg (ms) | Min (ms) | Max (ms) | P50 (ms) | P95 (ms) | Std (ms) |"
    )
    report.append(
        "|-------|-----------|----------|----------|----------|----------|----------|----------|----------|"
    )

    for model_name, data in results.items():
        if "error" in data:
            report.append(
                f"| {model_name} | {data['size_mb']:.1f} | ERROR | - | - | - | - | - | - |"
            )
        else:
            report.append(
                f"| {model_name} | {data['size_mb']:.1f} | {data['provider']} | {data['avg']:.2f} | {data['min']:.2f} | {data['max']:.2f} | {data['p50']:.2f} | {data['p95']:.2f} | {data['std']:.2f} |"
            )

    report.append("")

    # Performance analysis
    report.append("## Performance Analysis")
    report.append("")

    # Find best performing model
    valid_results = {k: v for k, v in results.items() if "error" not in v}
    if valid_results:
        best_model = min(valid_results.items(), key=lambda x: x[1]["avg"])
        report.append(
            f"**Fastest Model:** {best_model[0]} ({best_model[1]['avg']:.2f}ms avg)"
        )

        # Size vs performance analysis
        report.append("")
        report.append("### Size vs Performance Trade-off")
        for model_name, data in valid_results.items():
            size_reduction = ((310.5 - data["size_mb"]) / 310.5) * 100
            report.append(
                f"- **{model_name}**: {data['size_mb']:.1f}MB ({size_reduction:+.1f}% size) → {data['avg']:.2f}ms avg"
            )

    # Provider analysis
    report.append("")
    report.append("## Provider Analysis")
    report.append("")
    providers_used = set()
    for data in valid_results.values():
        providers_used.add(data["provider"])

    for provider in providers_used:
        provider_models = [
            k for k, v in valid_results.items() if v["provider"] == provider
        ]
        report.append(f"- **{provider}**: {', '.join(provider_models)}")

    # Recommendations
    report.append("")
    report.append("## Recommendations")
    report.append("")

    if valid_results:
        fastest = min(valid_results.items(), key=lambda x: x[1]["avg"])
        smallest = min(valid_results.items(), key=lambda x: x[1]["size_mb"])

        report.append(
            f"1. **For maximum speed**: Use {fastest[0]} ({fastest[1]['avg']:.2f}ms)"
        )
        report.append(
            f"2. **For minimum size**: Use {smallest[0]} ({smallest[1]['size_mb']:.1f}MB)"
        )

        # Find best balance
        if len(valid_results) > 1:
            # Calculate efficiency score (lower is better)
            for model_name, data in valid_results.items():
                size_score = data["size_mb"] / 310.5  # Normalize to original size
                time_score = (
                    data["avg"] / fastest[1]["avg"]
                )  # Normalize to fastest time
                efficiency_score = (size_score + time_score) / 2
                data["efficiency_score"] = efficiency_score

            best_balance = min(
                valid_results.items(), key=lambda x: x[1]["efficiency_score"]
            )
            report.append(
                f"3. **Best balance**: Use {best_balance[0]} (efficiency score: {best_balance[1]['efficiency_score']:.3f})"
            )

    report_text = "\n".join(report)

    if output_file:
        Path(output_file).write_text(report_text)
        logger.info(f"Report saved to {output_file}")

    return report_text


def main():
    parser = argparse.ArgumentParser(
        description="Provider Benchmark for Kokoro TTS Models (MPS/CoreML/CPU)"
    )
    parser.add_argument(
        "--models", nargs="+", required=True, help="Model paths to benchmark"
    )
    parser.add_argument("--runs", type=int, default=5, help="Number of benchmark runs")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--json", help="Output JSON results file")
    parser.add_argument(
        "--provider",
        choices=["cpu", "coreml", "mps"],
        help="Force a specific provider (CPU/CoreML/MPS). Overrides --providers if set.",
    )
    parser.add_argument(
        "--providers",
        help="Comma-separated provider order (e.g., 'MPSExecutionProvider,CoreMLExecutionProvider,CPUExecutionProvider')",
    )

    args = parser.parse_args()

    # Resolve providers order
    providers_order: Optional[List[str]] = None
    if args.provider:
        if args.provider == "cpu":
            providers_order = ["CPUExecutionProvider"]
        elif args.provider == "coreml":
            providers_order = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        elif args.provider == "mps":
            providers_order = ["MPSExecutionProvider", "CPUExecutionProvider"]
    elif args.providers:
        providers_order = [p.strip() for p in args.providers.split(",") if p.strip()]

    # Benchmark all models
    results = compare_models_mps(args.models, args.runs, providers_order)

    # Generate report
    report = generate_report(results, args.output)

    # Save JSON if requested
    if args.json:
        with open(args.json, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"JSON results saved to {args.json}")

    # Print summary
    print("\n" + "=" * 80)
    print("MPS PROVIDER BENCHMARK SUMMARY")
    print("=" * 80)
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
