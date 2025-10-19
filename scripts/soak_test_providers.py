#!/usr/bin/env python3
"""
Kokoro TTS Provider Soak Test

Tests TTFA performance across all three execution provider configurations:
1. CPU Provider (KOKORO_FORCE_CPU_PROVIDER=true)
2. Adaptive Provider (default - CoreML for most cases)
3. CoreML Provider (KOKORO_DISABLE_ADAPTIVE_PROVIDER=true)

Usage:
  python scripts/soak_test_providers.py --iterations 50 --concurrency 2

Author: @darianrosebrook
Date: 2025-10-18
"""

import argparse
import json
import logging
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# ------------------------- Configuration -------------------------------------------

class ProviderConfig:
    def __init__(self, name: str, env_vars: Dict[str, str], description: str):
        self.name = name
        self.env_vars = env_vars
        self.description = description

PROVIDER_CONFIGS = [
    ProviderConfig(
        name="cpu_forced",
        env_vars={"KOKORO_FORCE_CPU_PROVIDER": "true"},
        description="Force CPU provider for all requests"
    ),
    ProviderConfig(
        name="adaptive",
        env_vars={},
        description="Adaptive provider selection (CoreML for most cases)"
    ),
    ProviderConfig(
        name="coreml_forced",
        env_vars={"KOKORO_DISABLE_ADAPTIVE_PROVIDER": "true"},
        description="Force CoreML provider for all requests (fallback to CPU)"
    )
]

# ------------------------- Logging -------------------------------------------

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ------------------------- Test Runner -------------------------------------------

class ProviderSoakTest:
    def __init__(self, iterations: int = 30, concurrency: int = 1, text_preset: str = "short", stream_mode: bool = True):
        self.iterations = iterations
        self.concurrency = concurrency
        self.text_preset = text_preset
        self.stream_mode = stream_mode
        self.results = {}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run soak tests for all provider configurations."""
        logging.info("Starting provider soak tests...")

        for config in PROVIDER_CONFIGS:
            logging.info(f"Testing configuration: {config.name}")
            result = self.run_single_test(config)
            self.results[config.name] = result

        self.generate_report()
        return self.results

    def run_single_test(self, config: ProviderConfig) -> Dict[str, Any]:
        """Run soak test for a single provider configuration."""
        try:
            # Run benchmark with environment variables
            bench_result = self._run_benchmark_with_env(config.env_vars)

            return {
                "config": config.name,
                "description": config.description,
                "env_vars": config.env_vars,
                "benchmark_result": bench_result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logging.error(f"Test failed for {config.name}: {e}")
            return {"error": str(e)}

    def _run_benchmark_with_env(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Run the benchmark script with specific environment variables."""
        try:
            # Build environment
            env = os.environ.copy()
            env.update(env_vars)

            # Build command with virtual environment
            venv_python = os.path.join(os.getcwd(), ".venv", "bin", "python")
            cmd = [
                venv_python, "scripts/run_bench.py",
                "--preset", self.text_preset,
                "--trials", str(self.iterations),
                "--concurrency", str(self.concurrency),
                "--soak-iterations", "0",
                "--speed", "1.25"  # API requires speed >= 1.25
            ]
            # Add stream flag if requested
            if self.stream_mode:
                cmd.append("--stream")

            logging.info(f"Running benchmark with env: {env_vars}")
            logging.info(f"Command: {' '.join(cmd)}")

            # Run the benchmark
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logging.error(f"Benchmark failed with return code {result.returncode}")
                logging.error(f"STDOUT: {result.stdout}")
                logging.error(f"STDERR: {result.stderr}")
                return {"error": f"Benchmark failed: {result.stderr}"}

            # Parse JSON output from file (run_bench.py outputs to artifacts/bench/)
            try:
                # Find the most recent benchmark file
                bench_dir = Path("artifacts/bench")
                if bench_dir.exists():
                    # Get the most recent subdirectory
                    subdirs = [d for d in bench_dir.iterdir() if d.is_dir()]
                    if subdirs:
                        latest_dir = max(subdirs, key=lambda x: x.stat().st_mtime)
                        # Find the most recent JSON file
                        json_files = list(latest_dir.glob("*.json"))
                        if json_files:
                            latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
                            with open(latest_file, 'r') as f:
                                bench_result = json.load(f)
                            return bench_result

                # If we can't find the file, return an error
                logging.error("Could not find benchmark result file")
                return {"error": "Benchmark result file not found"}

            except Exception as e:
                logging.error(f"Failed to read benchmark JSON file: {e}")
                return {"error": f"JSON file read failed: {e}"}

        except subprocess.TimeoutExpired:
            logging.error("Benchmark timed out")
            return {"error": "Benchmark timed out"}
        except Exception as e:
            logging.error(f"Benchmark failed: {e}")
            return {"error": str(e)}

    def generate_report(self):
        """Generate a comprehensive report of all test results."""
        report = {
            "test_summary": {
                "total_configurations": len(PROVIDER_CONFIGS),
                "iterations_per_config": self.iterations,
                "concurrency": self.concurrency,
                "text_preset": self.text_preset,
                "timestamp": datetime.now().isoformat()
            },
            "results": self.results
        }

        # Save detailed report
        report_path = Path("artifacts/soak") / f"provider_soak_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logging.info(f"Detailed report saved to: {report_path}")

        # Generate summary
        self._print_summary_report(report)

    def _print_summary_report(self, report: Dict[str, Any]):
        """Print a human-readable summary."""
        print("\n" + "="*80)
        print("PROVIDER SOAK TEST RESULTS")
        print("="*80)

        print(f"Test Configuration:")
        print(f"  Iterations per config: {self.iterations}")
        print(f"  Concurrency: {self.concurrency}")
        print(f"  Text preset: {self.text_preset}")
        print(f"  Mode: {'Streaming' if self.stream_mode else 'Non-streaming'}")
        print()

        for config_name, result in report["results"].items():
            print(f"Configuration: {config_name.upper()}")
            print(f"  Description: {result.get('description', 'N/A')}")

            if "error" in result:
                print(f"  ❌ Error: {result['error']}")
            else:
                bench = result.get("benchmark_result", {})
                if "error" in bench:
                    print(f"  ❌ Benchmark Error: {bench['error']}")
                else:
                    metrics = bench.get("metrics", {})
                    success_rate = metrics.get("success_rate", 0) * 100
                    print("  ✅ Results:")
                    if self.stream_mode:
                        ttfa_p95 = metrics.get("ttfa_p95_ms", 0)
                        rtf_avg = metrics.get("rtf_avg", 0)
                        print(".2f")
                        print(".2f")
                    else:
                        rtf_p95 = metrics.get("rtf_p95", 0)
                        print(".2f")
                        print(f"    Success Rate: {success_rate:.1f}%")
            print()

def main():
    parser = argparse.ArgumentParser(description="Provider soak test for Kokoro TTS")
    parser.add_argument("--iterations", type=int, default=30,
                       help="Number of iterations per configuration")
    parser.add_argument("--concurrency", type=int, default=1,
                       help="Concurrent requests per configuration")
    parser.add_argument("--preset", choices=["short", "medium", "long"], default="short",
                       help="Text preset for testing")
    parser.add_argument("--no-stream", action="store_true",
                       help="Run non-streaming tests (measures RTF instead of TTFA)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Check if bench script exists
    if not Path("scripts/run_bench.py").exists():
        logging.error("scripts/run_bench.py not found")
        sys.exit(1)

    # Run tests
    tester = ProviderSoakTest(
        iterations=args.iterations,
        concurrency=args.concurrency,
        text_preset=args.preset,
        stream_mode=not args.no_stream
    )

    try:
        results = tester.run_all_tests()
        logging.info("All provider soak tests completed!")
    except KeyboardInterrupt:
        logging.info("Test interrupted by user")
    except Exception as e:
        logging.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()