#!/usr/bin/env python3
"""
Comprehensive TTS Performance Benchmark Script

This script provides advanced benchmarking capabilities for the Kokoro-ONNX TTS system,
including warmup inferences, extended text testing, and detailed performance analysis.

## Features

- **Model Warmup**: Performs multiple warmup inferences to stabilize performance
- **Extended Text Testing**: Tests with longer paragraphs to evaluate real-world performance
- **Provider Comparison**: Compares CoreML vs CPU performance side-by-side
- **Consistency Testing**: Multiple runs to evaluate performance stability
- **Thermal Analysis**: Monitors performance under sustained load
- **Detailed Reporting**: Comprehensive results with statistical analysis
- **Robust Error Handling**: Comprehensive exception handling and logging
- **Graceful Degradation**: Continues operation even with partial failures

## Usage

```bash
# Run full benchmark suite
python run_benchmark.py

# Run with custom parameters
python run_benchmark.py --warmup-runs 5 --consistency-runs 5 --enable-long-text

# Quick benchmark (minimal testing)
python run_benchmark.py --quick

# Verbose output with detailed timing
python run_benchmark.py --verbose
```

@author: @darianrosebrook
@date: 2025-07-08
@version: 1.1.0
@license: MIT
"""

import argparse
import asyncio
import logging
import os
import sys
import time
import traceback
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import aiohttp

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.config import TTSConfig
from api.model.loader import initialize_model, benchmark_providers
from api.model.patch import get_patch_status
from api.performance.reporting import save_benchmark_report
from api.warnings import configure_onnx_runtime_logging, setup_coreml_warning_handler, suppress_phonemizer_warnings, suppress_onnx_warnings


def setup_logging(verbose: bool = False):
    """
    Setup comprehensive logging configuration for benchmark testing.
    
    This function configures logging with multiple handlers for different output
    destinations and provides detailed logging for debugging and monitoring.
    
    @param verbose: Enable verbose logging with debug level output
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()
    
    # Console handler with color support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    
    # File handler for detailed logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f'logs/benchmark_{timestamp}.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Log initial setup
    logger = logging.getLogger(__name__)
    logger.info(f" Logging configured - Level: {logging.getLevelName(level)}")
    logger.info(f" Detailed logs will be written to: {log_file}")


def parse_arguments():
    """
    Parse command line arguments for benchmark configuration.
    
    This function provides comprehensive argument parsing with validation
    and helpful error messages for incorrect usage.
    
    @returns argparse.Namespace: Parsed command line arguments
    @raises SystemExit: If arguments are invalid or help is requested
    """
    parser = argparse.ArgumentParser(
        description='Comprehensive TTS Performance Benchmark',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_benchmark.py                    # Full benchmark suite
  python run_benchmark.py --quick           # Quick benchmark
  python run_benchmark.py --warmup-runs 5   # Custom warmup runs
  python run_benchmark.py --verbose         # Detailed output
  python run_benchmark.py --output-file custom_report.md  # Custom output file
        """
    )
    
    parser.add_argument(
        '--warmup-runs', 
        type=int, 
        default=TTSConfig.BENCHMARK_WARMUP_RUNS,
        help=f'Number of warmup inferences (default: {TTSConfig.BENCHMARK_WARMUP_RUNS})'
    )
    
    parser.add_argument(
        '--consistency-runs', 
        type=int, 
        default=TTSConfig.BENCHMARK_CONSISTENCY_RUNS,
        help=f'Number of consistency test runs (default: {TTSConfig.BENCHMARK_CONSISTENCY_RUNS})'
    )
    
    parser.add_argument(
        '--enable-long-text', 
        action='store_true',
        default=TTSConfig.BENCHMARK_ENABLE_LONG_TEXT,
        help='Enable extended text performance testing'
    )
    
    parser.add_argument(
        '--disable-long-text', 
        action='store_true',
        help='Disable extended text performance testing'
    )
    
    parser.add_argument(
        '--quick', 
        action='store_true',
        help='Quick benchmark with minimal testing (1 warmup, 1 consistency)'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose logging with detailed timing information'
    )
    
    parser.add_argument(
        '--output-file', 
        type=str,
        default='benchmark_results.md',
        help='Output file for benchmark results (default: benchmark_results.md)'
    )
    
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue benchmark execution even if individual tests fail'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration and dependencies without running benchmarks'
    )
    
    parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='Run a comprehensive benchmark suite testing multiple configurations'
    )
    
    return parser.parse_args()


def validate_arguments(args):
    """
    Validate command line arguments and provide helpful error messages.
    
    This function performs comprehensive validation of benchmark parameters
    to prevent invalid configurations that could cause failures.
    
    @param args: Parsed command line arguments
    @raises ValueError: If arguments are invalid
    """
    logger = logging.getLogger(__name__)
    
    # Validate numeric parameters
    if args.warmup_runs < 0:
        raise ValueError("warmup-runs must be non-negative")
    
    if args.consistency_runs < 1:
        raise ValueError("consistency-runs must be at least 1")
    
    if args.warmup_runs > 100:
        logger.warning("⚠️ Large number of warmup runs may significantly increase benchmark time")
    
    if args.consistency_runs > 50:
        logger.warning("⚠️ Large number of consistency runs may take a very long time")
    
    # Validate output file
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f" Created output directory: {output_dir}")
        except Exception as e:
            raise ValueError(f"Cannot create output directory {output_dir}: {e}")
    
    # Check for conflicting options
    if args.enable_long_text and args.disable_long_text:
        raise ValueError("Cannot specify both --enable-long-text and --disable-long-text")
    
    if args.quick and (args.warmup_runs > 1 or args.consistency_runs > 1):
        logger.warning("⚠️ --quick mode overrides custom warmup/consistency run counts")
    
    if args.comprehensive and args.quick:
        raise ValueError("Cannot specify both --comprehensive and --quick mode")
    
    logger.info("✅ Command line arguments validated successfully")


def configure_benchmark_settings(args):
    """
    Configure benchmark settings based on command line arguments.
    
    This function applies the parsed arguments to the global configuration,
    ensuring that all benchmark components use consistent settings.
    
    @param args: Parsed command line arguments
    """
    logger = logging.getLogger(__name__)
    
    if args.quick:
        logger.info("Configuring quick benchmark mode")
        TTSConfig.BENCHMARK_WARMUP_RUNS = 1
        TTSConfig.BENCHMARK_CONSISTENCY_RUNS = 1
        TTSConfig.BENCHMARK_ENABLE_LONG_TEXT = False
    else:
        TTSConfig.BENCHMARK_WARMUP_RUNS = args.warmup_runs
        TTSConfig.BENCHMARK_CONSISTENCY_RUNS = args.consistency_runs
        
        if args.disable_long_text:
            TTSConfig.BENCHMARK_ENABLE_LONG_TEXT = False
        elif args.enable_long_text:
            TTSConfig.BENCHMARK_ENABLE_LONG_TEXT = True
    
    logger.info(f" Benchmark configuration applied:")
    logger.info(f"   • Warmup runs: {TTSConfig.BENCHMARK_WARMUP_RUNS}")
    logger.info(f"   • Consistency runs: {TTSConfig.BENCHMARK_CONSISTENCY_RUNS}")
    logger.info(f"   • Long text testing: {'✅ Enabled' if TTSConfig.BENCHMARK_ENABLE_LONG_TEXT else ' Disabled'}")


def display_benchmark_info(args):
    """
    Display comprehensive benchmark configuration information.
    
    This function provides a clear overview of the benchmark configuration
    and system capabilities to help users understand what will be tested.
    
    @param args: Parsed command line arguments
    """
    logger = logging.getLogger(__name__)
    
    print(" Kokoro-ONNX TTS Performance Benchmark")
    print("=" * 50)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Configuration:")
    print(f"   • Warmup runs: {TTSConfig.BENCHMARK_WARMUP_RUNS}")
    print(f"   • Consistency runs: {TTSConfig.BENCHMARK_CONSISTENCY_RUNS}")
    print(f"   • Long text testing: {'✅ Enabled' if TTSConfig.BENCHMARK_ENABLE_LONG_TEXT else ' Disabled'}")
    print(f"   • Min improvement threshold: {TTSConfig.BENCHMARK_MIN_IMPROVEMENT_PERCENT}%")
    print(f"   • Output file: {args.output_file}")
    print(f"   • Continue on error: {'✅ Yes' if args.continue_on_error else ' No'}")
    print(f"   • Validation only: {'✅ Yes' if args.validate_only else ' No'}")
    print(f"   • Comprehensive mode: {'✅ Yes' if args.comprehensive else ' No'}")
    print("\n")


def get_system_info():
    """
    Get comprehensive system information for benchmark reporting.
    
    This function collects detailed system information including hardware
    capabilities, software versions, and environment details for accurate
    benchmark reporting and troubleshooting.
    
    @returns Dict[str, Any]: System information dictionary
    """
    import platform
    
    logger = logging.getLogger(__name__)
    
    # Apple Silicon detection
    is_apple_silicon = platform.machine() == 'arm64' and platform.system() == 'Darwin'
    
    # Try to get detailed system info with psutil
    try:
        import psutil
        
        # Get CPU information
        cpu_count = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        
        # Get memory information
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        
        # Get disk information
        disk = psutil.disk_usage('/')
        disk_gb = disk.total / (1024**3)
        
        system_info = {
            'platform': f"{platform.system()} {platform.machine()}",
            'cpu_cores': cpu_count,
            'cpu_threads': cpu_count_logical,
            'memory_gb': round(memory_gb, 1),
            'disk_gb': round(disk_gb, 1),
            'is_apple_silicon': is_apple_silicon,
            'has_neural_engine': is_apple_silicon,
            'python_version': platform.python_version(),
            'psutil_available': True
        }
        
        logger.debug(f" System info collected with psutil: {cpu_count} cores, {memory_gb:.1f}GB RAM")
        
    except ImportError:
        # Fallback without psutil
        system_info = {
            'platform': f"{platform.system()} {platform.machine()}",
            'cpu_cores': 'Unknown',
            'cpu_threads': 'Unknown', 
            'memory_gb': 'Unknown',
            'disk_gb': 'Unknown',
            'is_apple_silicon': is_apple_silicon,
            'has_neural_engine': is_apple_silicon,
            'python_version': platform.python_version(),
            'psutil_available': False
        }
        
        logger.warning("⚠️ psutil not available - limited system information")
    
    # Get ONNX Runtime information
    try:
        import onnxruntime as ort
        system_info['onnxruntime_version'] = ort.__version__
        system_info['available_providers'] = ort.get_available_providers()
        logger.debug(f" ONNX Runtime {ort.__version__} with providers: {ort.get_available_providers()}")
    except Exception as e:
        logger.warning(f"⚠️ Could not get ONNX Runtime info: {e}")
        system_info['onnxruntime_version'] = 'Unknown'
        system_info['available_providers'] = []
    
    return system_info


def validate_dependencies():
    """
    Validate that all required dependencies are available.
    
    This function checks for the presence and compatibility of all required
    dependencies before starting the benchmark to prevent runtime failures.
    
    @returns bool: True if all dependencies are valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info(" Validating dependencies...")
    
    missing_deps = []
    version_issues = []
    
    # Check critical dependencies
    required_packages = [
        ('onnxruntime', 'onnxruntime'),
        ('numpy', 'numpy'),
        ('kokoro_onnx', 'kokoro-onnx'),
        ('espeakng_loader', 'espeakng-loader'),
    ]
    
    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
            logger.debug(f"✅ {package_name} available")
        except ImportError:
            missing_deps.append(package_name)
            logger.error(f" {package_name} not found")
    
    # Check optional dependencies
    optional_packages = [
        ('psutil', 'psutil'),
        ('phonemizer_fork', 'phonemizer-fork'),
    ]
    
    for import_name, package_name in optional_packages:
        try:
            __import__(import_name)
            logger.debug(f"✅ {package_name} available (optional)")
        except ImportError:
            logger.warning(f"⚠️ {package_name} not found (optional)")
    
    # Check eSpeak installation
    try:
        import subprocess
        result = subprocess.run(['which', 'espeak-ng'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.debug("✅ eSpeak-ng found in system PATH")
        else:
            logger.warning("⚠️ eSpeak-ng not found in system PATH")
    except Exception as e:
        logger.warning(f"⚠️ Could not check eSpeak-ng installation: {e}")
    
    # Report results
    if missing_deps:
        logger.error(f" Missing required dependencies: {', '.join(missing_deps)}")
        logger.error(" Install missing packages with: pip install " + " ".join(missing_deps))
        return False
    
    if version_issues:
        logger.warning(f"⚠️ Version compatibility issues: {', '.join(version_issues)}")
    
    logger.info("✅ All dependencies validated successfully")
    return True


def run_extended_benchmark_analysis(benchmark_results: Dict[str, float]):
    """
    Run extended analysis on benchmark results with comprehensive statistics.
    
    This function provides detailed performance analysis including statistical
    measures, performance comparisons, and actionable recommendations.
    
    @param benchmark_results: Dictionary of provider names to inference times
    """
    logger = logging.getLogger(__name__)
    
    if not benchmark_results:
        logger.error(" No benchmark results to analyze")
        return
    
    print("\n Extended Performance Analysis")
    print("-" * 40)
    
    # Calculate performance metrics
    times = list(benchmark_results.values())
    providers = list(benchmark_results.keys())
    
    if len(times) >= 2:
        fastest_time = min(times)
        slowest_time = max(times)
        improvement = ((slowest_time - fastest_time) / slowest_time) * 100
        
        # Calculate statistical measures
        import statistics
        mean_time = statistics.mean(times)
        median_time = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        print(f" Performance Summary:")
        print(f"   • Fastest: {fastest_time:.3f}s")
        print(f"   • Slowest: {slowest_time:.3f}s")
        print(f"   • Mean: {mean_time:.3f}s")
        print(f"   • Median: {median_time:.3f}s")
        print(f"   • Std Dev: {std_dev:.3f}s")
        print(f"   • Improvement: {improvement:.1f}%")
        print(f"   • Speed-up: {slowest_time/fastest_time:.2f}x")
        
        # Detailed comparison
        print(f"\n Provider Comparison:")
        for i, (provider, time_taken) in enumerate(sorted(benchmark_results.items(), key=lambda x: x[1])):
            relative_perf = time_taken / fastest_time
            rank = "" if i == 0 else "" if i == 1 else ""
            print(f"   {rank} {provider}: {time_taken:.3f}s ({relative_perf:.2f}x)")
    
    # Performance recommendations
    print(f"\n Recommendations:")
    best_provider = min(benchmark_results, key=benchmark_results.get)
    
    if 'CoreML' in best_provider:
        print("   ✅ CoreML is optimal for your Apple Silicon system")
        print("   Hardware acceleration is working effectively")
    elif 'CPU' in best_provider:
        print("    CPU provider is optimal for your system")
        print("    Consider checking CoreML compatibility if available")
    
    print(f"    Recommended provider: {best_provider}")
    
    # Performance insights
    if len(times) > 1:
        cv = (std_dev / mean_time) * 100 if mean_time > 0 else 0
        if cv < 5:
            print("    Excellent performance consistency")
        elif cv < 15:
            print("    Good performance consistency")
        else:
            print("   ⚠️ High performance variability - consider more warmup runs")


async def run_comprehensive_benchmark(args):
    """
    Run a comprehensive benchmark suite with multiple configurations.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting comprehensive benchmark suite...")

    scenarios = define_benchmark_scenarios()
    all_results = []

    for scenario in scenarios:
        logger.info(f"--- Running Scenario: {scenario['name']} ---")
        server_process = None
        try:
            server_process = await start_server_for_scenario(scenario)
            
            # Run benchmarks for this scenario
            scenario_results = await run_scenario_benchmarks(scenario)
            all_results.append(scenario_results)
            
        except Exception as e:
            logger.error(f" Scenario '{scenario['name']}' failed: {e}")
        finally:
            if server_process:
                logger.info("Stopping server...")
                try:
                    # Check if the process is still running before terminating
                    if server_process.returncode is None:
                        server_process.terminate()
                        await server_process.wait()
                    else:
                        logger.warning(f"⚠️ Server for scenario '{scenario['name']}' already exited with code {server_process.returncode}.")
                except ProcessLookupError:
                    logger.warning(f"⚠️ Server process for scenario '{scenario['name']}' not found, it might have already been terminated.")

    display_comprehensive_results(all_results)

def define_benchmark_scenarios() -> List[Dict[str, Any]]:
    """Defines the scenarios for the comprehensive benchmark."""
    base_scenarios = [
        {"name": "Dev Mode", "env": {"KOKORO_PRODUCTION": "false", "KOKORO_DEVELOPMENT_MODE": "true"}},
        {"name": "Prod Mode", "env": {"KOKORO_PRODUCTION": "true", "KOKORO_DEVELOPMENT_MODE": "false"}},
    ]

    ort_levels = ["DISABLED", "BASIC", "EXTENDED", "ALL"]
    for level in ort_levels:
        base_scenarios.append({
            "name": f"Prod Mode - ORT Level: {level}",
            "env": {"KOKORO_PRODUCTION": "true", "KOKORO_GRAPH_OPT_LEVEL": level}
        })

    # Apple Silicon specific scenarios
    if sys.platform == "darwin" and os.uname().machine == "arm64":
        coreml_units = ["CPUOnly", "CPUAndGPU", "ALL"]
        for unit in coreml_units:
            base_scenarios.append({
                "name": f"Prod Mode - CoreML Units: {unit}",
                "env": {"KOKORO_PRODUCTION": "true", "KOKORO_COREML_COMPUTE_UNITS": unit}
            })
            
    return base_scenarios

def display_comprehensive_results(results: List[Dict[str, Any]]):
    """Displays the results of the comprehensive benchmark in a formatted table."""
    logger = logging.getLogger(__name__)
    logger.info("\n--- Comprehensive Benchmark Results ---")
    
    # Header
    header = f"| {'Scenario':<35} | {'Standard Text (s)':<20} | {'Article Text (s)':<20} |"
    print(header)
    print(f"|{'-'*37}|{'-'*22}|{'-'*22}|")

    for result in results:
        std_time = f"{result.get('standard_text_time', 'N/A'):.3f}" if isinstance(result.get('standard_text_time'), float) else "FAIL"
        art_time = f"{result.get('article_text_time', 'N/A'):.3f}" if isinstance(result.get('article_text_time'), float) else "FAIL"
        
        row = f"| {result['name']:<35} | {std_time:<20} | {art_time:<20} |"
        print(row)
        
    logger.info("\n--- End of Report ---")


async def start_server_for_scenario(scenario: Dict[str, Any]) -> asyncio.subprocess.Process:
    """Starts the Uvicorn server in a subprocess with a given environment."""
    logger = logging.getLogger(__name__)
    env = os.environ.copy()
    env.update(scenario["env"])
    
    venv_python = Path(sys.executable)
    cmd = [str(venv_python), "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    
    logger.info(f"Starting server for '{scenario['name']}'...")
    process = await asyncio.create_subprocess_exec(*cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    
    # Improved readiness check
    for _ in range(60): # Try for 120 seconds
        await asyncio.sleep(2)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:8000/health") as response:
                    if response.status == 200:
                        logger.info("✅ Server is ready.")
                        return process
        except aiohttp.ClientConnectorError:
            continue
            
    raise RuntimeError("Server failed to start in time.")

async def run_scenario_benchmarks(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a set of benchmarks for a single server configuration."""
    logger = logging.getLogger(__name__)
    results = {"name": scenario["name"]}
    
    async with aiohttp.ClientSession() as session:
        # Standard Text Benchmark
        try:
            payload = {"text": TTSConfig.TEST_TEXT, "voice": "af_heart"}
            start_time = time.perf_counter()
            async with session.post("http://127.0.0.1:8000/v1/audio/speech", json=payload) as response:
                if response.status == 200:
                    await response.read() # Consume body
                    results["standard_text_time"] = time.perf_counter() - start_time
                    logger.info(f"Standard text benchmark: {results['standard_text_time']:.3f}s")
                else:
                    logger.error(f"Standard text benchmark failed with status: {response.status}")
        except Exception as e:
            logger.error(f"Standard text benchmark request failed: {e}")

        # Article Text Benchmark
        try:
            payload = {"text": TTSConfig.BENCHMARK_ARTICLE_LENGTH_TEXT, "voice": "af_heart"}
            start_time = time.perf_counter()
            async with session.post("http://127.0.0.1:8000/v1/audio/speech", json=payload) as response:
                if response.status == 200:
                    await response.read() # Consume body
                    results["article_text_time"] = time.perf_counter() - start_time
                    logger.info(f"Article text benchmark: {results['article_text_time']:.3f}s")
                else:
                    logger.error(f"Article text benchmark failed with status: {response.status}")
        except Exception as e:
            logger.error(f"Article text benchmark request failed: {e}")

    return results


async def main():
    """
    Main function to run the TTS benchmark.
    
    This function orchestrates the entire benchmark process with robust
    error handling, detailed logging, and graceful degradation.
    
    @returns int: Exit code (0 for success, 1 for failure)
    """
    # Parse arguments first, so we can configure logging
    args = parse_arguments()
    setup_logging(args.verbose)
    
    # Now that logging is configured, get a logger instance
    logger = logging.getLogger(__name__)

    try:
        # Validate and apply settings
        try:
            validate_arguments(args)
            configure_benchmark_settings(args)
        except ValueError as e:
            logger.error(f" Invalid configuration: {e}")
            return 1
        
        # Display benchmark information
        display_benchmark_info(args)
        
        # Validate dependencies
        if not validate_dependencies():
            logger.error(" Dependency validation failed")
            return 1
        
        # Check patch status
        patch_status = get_patch_status()
        logger.info(f" Patch status: {patch_status['applied']}")
        if patch_status['patch_errors']:
            logger.warning(f"⚠️ Patch errors detected: {patch_status['patch_errors']}")
        
        # Validation-only mode
        if args.validate_only:
            logger.info("✅ Validation completed successfully")
            return 0
        
        # Run comprehensive benchmark if requested
        if args.comprehensive:
            await run_comprehensive_benchmark(args)
            return 0

        # Initialize the model
        logger.info("Initializing TTS model...")
        start_init = time.perf_counter()
        
        try:
            # Use comprehensive warning suppression during model initialization
            with suppress_onnx_warnings():
                initialize_model()
            init_time = time.perf_counter() - start_init
            logger.info(f"✅ Model initialized in {init_time:.3f}s")
        except Exception as e:
            logger.error(f" Model initialization failed: {e}")
            if not args.continue_on_error:
                return 1
            logger.warning("⚠️ Continuing with benchmark despite initialization failure")
        
        # Run benchmark
        logger.info("\n Running comprehensive benchmark...")
        start_benchmark = time.perf_counter()
        
        benchmark_results = {}
        optimal_provider = "Unknown"
        try:
            # Use comprehensive warning suppression during benchmarking
            with suppress_onnx_warnings():
                optimal_provider, benchmark_results = benchmark_providers()
            benchmark_time = time.perf_counter() - start_benchmark
            logger.info(f"✅ Benchmark completed in {benchmark_time:.3f}s")
        except Exception as e:
            logger.error(f" Benchmark execution failed: {e}")
            if args.verbose:
                logger.debug(f" Full traceback:\n{traceback.format_exc()}")
            if not args.continue_on_error:
                return 1
            logger.warning("⚠️ Continuing with partial results")
        
        # Display results
        if benchmark_results:
            logger.info(f"\n Benchmark Results:")
            logger.info(f"   • Optimal provider: {optimal_provider}")
            
            # Run extended analysis
            run_extended_benchmark_analysis(benchmark_results)
            
            # Generate comprehensive report
            logger.info(f"\n Generating comprehensive report...")
            try:
                system_info = get_system_info()
                save_benchmark_report(system_info, benchmark_results, optimal_provider, args.output_file)
                logger.info(f"✅ Report saved to: {args.output_file}")
            except Exception as e:
                logger.error(f" Failed to save benchmark report: {e}")
                if not args.continue_on_error:
                    return 1
            
        else:
            logger.error(" Benchmark failed - no results obtained")
            if not args.continue_on_error:
                return 1

        logger.info("\n✅ Benchmark completed successfully!")
        return 0
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Benchmark interrupted by user")
        return 1
    except Exception as e:
        logger.error(f" Benchmark failed with unexpected error: {e}")
        if args.verbose:
            logger.debug(f" Full traceback:\n{traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Benchmark execution cancelled.")
        sys.exit(1)
    except Exception as e:
        # Fallback for errors that might occur outside the main async function
        logging.basicConfig(level=logging.ERROR)
        log = logging.getLogger(__name__)
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1) 