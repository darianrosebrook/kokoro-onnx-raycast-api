"""
Scheduled Benchmark Management for Kokoro ONNX TTS

This module provides automated benchmark scheduling that respects the configured
benchmark frequency and persists results for monitoring and optimization.

@author: @darianrosebrook
@date: 2025-01-27
@version: 1.0.0
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from api.config import TTSConfig

logger = logging.getLogger(__name__)

# Global state for benchmark scheduling
_last_benchmark_run: Optional[datetime] = None
_benchmark_scheduler_task: Optional[asyncio.Task] = None
_benchmark_results_file: Optional[str] = None

def get_benchmark_results_path() -> str:
    """
    Get the path for storing benchmark results.
    
    Returns:
        Path to the benchmark results file
    """
    reports_dir = Path("reports/benchmarks")
    reports_dir.mkdir(parents=True, exist_ok=True)
    return str(reports_dir / "latest_benchmark_results.json")

def get_last_benchmark_timestamp() -> Optional[datetime]:
    """
    Get the timestamp of the last benchmark run from the results file.
    
    Returns:
        Timestamp of last benchmark run or None if not found
    """
    global _last_benchmark_run
    
    if _last_benchmark_run:
        return _last_benchmark_run
    
    results_file = get_benchmark_results_path()
    if not os.path.exists(results_file):
        return None
    
    try:
        with open(results_file, 'r') as f:
            data = json.load(f)
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                _last_benchmark_run = datetime.fromisoformat(timestamp_str)
                return _last_benchmark_run
    except Exception as e:
        logger.warning(f"Could not read last benchmark timestamp: {e}")
    
    return None

def should_run_benchmark() -> bool:
    """
    Determine if a benchmark should run based on the configured frequency.
    
    Returns:
        True if benchmark should run, False otherwise
    """
    if TTSConfig.SKIP_BENCHMARKING:
        logger.debug("Benchmarking skipped due to SKIP_BENCHMARKING flag")
        return False
    
    last_run = get_last_benchmark_timestamp()
    if not last_run:
        logger.info("No previous benchmark found, will run initial benchmark")
        return True
    
    # Calculate time since last run
    time_since_last = datetime.now() - last_run
    frequency_seconds = TTSConfig.BENCHMARK_FREQUENCY_OPTIONS.get(TTSConfig.BENCHMARK_FREQUENCY, 86400)
    
    should_run = time_since_last.total_seconds() >= frequency_seconds
    
    if should_run:
        logger.info(f"Benchmark due: last run was {time_since_last.total_seconds() / 3600:.1f} hours ago, "
                   f"frequency is {frequency_seconds / 3600:.1f} hours")
    else:
        logger.debug(f"Benchmark not due: last run was {time_since_last.total_seconds() / 3600:.1f} hours ago, "
                    f"frequency is {frequency_seconds / 3600:.1f} hours")
    
    return should_run

async def run_scheduled_benchmark() -> Dict[str, Any]:
    """
    Run a scheduled benchmark using the existing benchmark script.
    
    Returns:
        Dictionary containing benchmark results and metadata
    """
    global _last_benchmark_run, _benchmark_results_file
    
    logger.info("Starting scheduled benchmark...")
    start_time = time.time()
    
    try:
        # Run the benchmark script
        script_path = Path("scripts/run_benchmark.py")
        if not script_path.exists():
            raise FileNotFoundError(f"Benchmark script not found: {script_path}")
        
        # Run benchmark with minimal output for scheduled execution
        result = subprocess.run([
            sys.executable, str(script_path),
            "--quick",  # Quick benchmark with minimal testing
            "--consistency-runs", "1"  # Single run for speed
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode != 0:
            logger.warning(f"Benchmark script failed: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": time.time() - start_time
            }
        
        # Parse benchmark results
        benchmark_results = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time,
            "frequency": TTSConfig.BENCHMARK_FREQUENCY,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
        # Save results
        results_file = get_benchmark_results_path()
        with open(results_file, 'w') as f:
            json.dump(benchmark_results, f, indent=2)
        
        _last_benchmark_run = datetime.now()
        _benchmark_results_file = results_file
        
        logger.info(f"Scheduled benchmark completed successfully in {benchmark_results['duration_seconds']:.2f}s")
        return benchmark_results
        
    except subprocess.TimeoutExpired:
        error_msg = "Benchmark timed out after 5 minutes"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time
        }
    except Exception as e:
        error_msg = f"Benchmark failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time
        }

async def benchmark_scheduler_loop():
    """
    Main scheduler loop that periodically checks if benchmarks should run.
    """
    logger.info("Starting benchmark scheduler...")
    
    while True:
        try:
            if should_run_benchmark():
                await run_scheduled_benchmark()
            
            # Check every hour
            await asyncio.sleep(3600)
            
        except asyncio.CancelledError:
            logger.info("Benchmark scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in benchmark scheduler: {e}")
            await asyncio.sleep(3600)  # Continue after error

def start_benchmark_scheduler() -> asyncio.Task:
    """
    Start the benchmark scheduler as a background task.
    
    Returns:
        The scheduler task
    """
    global _benchmark_scheduler_task
    
    if _benchmark_scheduler_task and not _benchmark_scheduler_task.done():
        logger.warning("Benchmark scheduler already running")
        return _benchmark_scheduler_task
    
    _benchmark_scheduler_task = asyncio.create_task(benchmark_scheduler_loop())
    logger.info("Benchmark scheduler started")
    return _benchmark_scheduler_task

def stop_benchmark_scheduler():
    """
    Stop the benchmark scheduler.
    """
    global _benchmark_scheduler_task
    
    if _benchmark_scheduler_task and not _benchmark_scheduler_task.done():
        _benchmark_scheduler_task.cancel()
        logger.info("Benchmark scheduler stopped")

def get_scheduled_benchmark_stats() -> Dict[str, Any]:
    """
    Get statistics about scheduled benchmarking.
    
    Returns:
        Dictionary containing benchmark scheduling information
    """
    last_run = get_last_benchmark_timestamp()
    results_file = get_benchmark_results_path()
    
    stats = {
        "scheduler_active": _benchmark_scheduler_task is not None and not _benchmark_scheduler_task.done(),
        "frequency": TTSConfig.BENCHMARK_FREQUENCY,
        "skip_benchmarking": TTSConfig.SKIP_BENCHMARKING,
        "last_run": last_run.isoformat() if last_run else None,
        "results_file": results_file if os.path.exists(results_file) else None
    }
    
    if last_run:
        time_since_last = datetime.now() - last_run
        frequency_seconds = TTSConfig.BENCHMARK_FREQUENCY_OPTIONS.get(TTSConfig.BENCHMARK_FREQUENCY, 86400)
        next_run = last_run + timedelta(seconds=frequency_seconds)
        
        stats.update({
            "time_since_last_hours": time_since_last.total_seconds() / 3600,
            "next_scheduled_run": next_run.isoformat(),
            "due_for_benchmark": should_run_benchmark()
        })
    
    return stats
