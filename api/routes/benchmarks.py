"""
Benchmark API Endpoints

This module provides HTTP endpoints for running comprehensive TTS performance benchmarks
and accessing detailed performance analysis.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import time
import os

from api.performance.benchmarks.ttfa_benchmark import TTFABenchmark
from api.performance.benchmarks.audio_quality_benchmark import AudioQualityBenchmark, run_audio_quality_benchmark
from api.performance.benchmarks.runner import BenchmarkRunner, BenchmarkConfig
from api.utils.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class BenchmarkRequest(BaseModel):
    """Request model for benchmark execution"""
    benchmark_type: str = "full"  # "ttfa", "streaming", "full"
    include_voice_tests: bool = True
    include_speed_tests: bool = True
    save_results: bool = True
    custom_text: Optional[str] = None

class BenchmarkStatus(BaseModel):
    """Benchmark execution status"""
    running: bool
    progress: float  # 0-1
    current_test: str
    estimated_completion_s: Optional[float]

# Global benchmark state
_benchmark_status = {
    "running": False,
    "progress": 0.0,
    "current_test": "",
    "estimated_completion_s": None,
    "last_results": None,
    "start_time": None
}

@router.get("/status")
async def get_benchmark_status() -> Dict[str, Any]:
    """Get current benchmark execution status"""
    return {
        "status": _benchmark_status,
        "benchmark_types_available": ["ttfa", "streaming", "full"],
        "last_execution": _benchmark_status.get("last_results", {}).get("execution_timestamp") if _benchmark_status.get("last_results") else None
    }

@router.post("/run")
async def run_benchmark(
    request: BenchmarkRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Start a comprehensive benchmark run.
    
    This endpoint initiates benchmark execution in the background
    and returns immediately with a status.
    """
    if _benchmark_status["running"]:
        raise HTTPException(
            status_code=409,
            detail="Benchmark already running. Check /benchmarks/status for progress."
        )
    
    logger.info(f"Starting {request.benchmark_type} benchmark")
    
    # Start benchmark in background
    background_tasks.add_task(
        _execute_benchmark,
        request.benchmark_type,
        request.include_voice_tests,
        request.include_speed_tests,
        request.save_results,
        request.custom_text
    )
    
    return {
        "message": f"{request.benchmark_type.title()} benchmark started",
        "benchmark_id": f"bench_{int(time.time())}",
        "estimated_duration_s": _estimate_benchmark_duration(request.benchmark_type),
        "status_endpoint": "/benchmarks/status",
        "results_endpoint": "/benchmarks/results"
    }

@router.get("/results")
async def get_benchmark_results() -> Dict[str, Any]:
    """Get the latest benchmark results"""
    if not _benchmark_status.get("last_results"):
        raise HTTPException(
            status_code=404,
            detail="No benchmark results available. Run a benchmark first."
        )
    
    return _benchmark_status["last_results"]

@router.get("/results/report")
async def get_benchmark_report() -> Dict[str, str]:
    """Get human-readable benchmark report"""
    if not _benchmark_status.get("last_results"):
        raise HTTPException(
            status_code=404,
            detail="No benchmark results available. Run a benchmark first."
        )
    
    try:
        # Generate report based on last results using BenchmarkRunner
        runner = BenchmarkRunner()
        report = runner.generate_performance_report(_benchmark_status["last_results"])
        
        return report
    except Exception as e:
        logger.error(f"Failed to generate benchmark report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/ttfa/quick")
async def run_quick_ttfa_test(text: str = "Quick TTFA test") -> Dict[str, Any]:
    """
    Run a quick TTFA test for immediate feedback.
    
    This endpoint provides rapid TTFA measurement without full benchmark overhead.
    """
    try:
        from api.performance.benchmarks.ttfa_benchmark import TTFABenchmark
        
        benchmark = TTFABenchmark()
        measurement = await benchmark.measure_single_ttfa(text)
        
        return {
            "ttfa_ms": measurement.total_ttfa_ms,
            "target_met": measurement.target_met,
            "category": measurement.category.value,
            "bottleneck": measurement.bottleneck,
            "text_length": measurement.text_length,
            "provider_used": measurement.provider_used,
            "recommendation": _get_quick_recommendation(measurement.total_ttfa_ms, measurement.bottleneck)
        }
    except Exception as e:
        logger.error(f"Quick TTFA test failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTFA test failed: {str(e)}")

@router.get("/optimization/status")
async def get_optimization_status() -> Dict[str, Any]:
    """Get current streaming optimization status"""
    try:
        from api.tts.streaming_optimizer import get_streaming_optimizer
        
        optimizer = get_streaming_optimizer()
        status = optimizer.get_optimization_status()
        
        # Add system performance indicators
        from api.performance.stats import get_performance_stats
        stats = get_performance_stats()
        
        return {
            "streaming_optimization": status,
            "performance_stats": {
                "ttfa_average": stats.get("ttfa_average", 0),
                "ttfa_target": stats.get("ttfa_target", 800),
                "success_rate": stats.get("success_rate", 0),
                "fast_path_requests": stats.get("fast_path_requests", 0)
            },
            "recommendations": _get_optimization_recommendations(stats)
        }
    except Exception as e:
        logger.error(f"Failed to get optimization status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

async def _execute_benchmark(
    benchmark_type: str,
    include_voice_tests: bool,
    include_speed_tests: bool,
    save_results: bool,
    custom_text: Optional[str]
):
    """Execute benchmark in background task"""
    _benchmark_status.update({
        "running": True,
        "progress": 0.0,
        "current_test": "Initializing...",
        "start_time": time.time()
    })
    
    try:
        if benchmark_type == "ttfa":
            await _execute_ttfa_benchmark()
        elif benchmark_type == "full":
            await _execute_full_benchmark()
        else:
            raise ValueError(f"Unknown benchmark type: {benchmark_type}")
        
        logger.info(f"Benchmark {benchmark_type} completed successfully")
        
    except Exception as e:
        logger.error(f"Benchmark {benchmark_type} failed: {e}")
        _benchmark_status.update({
            "running": False,
            "current_test": f"Failed: {str(e)}",
            "progress": 0.0
        })
    finally:
        _benchmark_status["running"] = False

async def _execute_ttfa_benchmark():
    """Execute TTFA-focused benchmark"""
    _benchmark_status["current_test"] = "TTFA Benchmark Suite"
    _benchmark_status["progress"] = 0.1
    
    suite = TTFABenchmarkSuite()
    results = await suite.run_full_suite()
    
    _benchmark_status["progress"] = 0.8
    
    # Convert results to serializable format
    serialized_results = {}
    for name, result in results.items():
        serialized_results[name] = {
            "benchmark_name": result.benchmark_name,
            "average_ttfa_ms": result.average_ttfa_ms,
            "success_rate": result.success_rate,
            "total_measurements": result.total_measurements,
            "primary_bottleneck": result.primary_bottleneck
        }
    
    _benchmark_status["last_results"] = {
        "benchmark_type": "ttfa",
        "results": serialized_results,
        "execution_timestamp": time.time(),
        "summary": suite.generate_consolidated_report()
    }
    
    _benchmark_status["progress"] = 1.0
    _benchmark_status["current_test"] = "Completed"

async def _execute_full_benchmark():
    """Execute comprehensive benchmark"""
    _benchmark_status["current_test"] = "Full Spectrum Benchmark"
    _benchmark_status["progress"] = 0.1
    
    # Run full benchmark suite using BenchmarkRunner
    config = BenchmarkConfig(
        include_ttfa=True,
        include_streaming=True,
        include_provider_comparison=True,
        include_full_spectrum=True,
        save_results=True
    )
    runner = BenchmarkRunner(config)
    execution_result = await runner.run_full_benchmark_suite()
    
    # Convert execution result to expected format
    results = {
        "execution_id": execution_result.execution_id,
        "completed_successfully": execution_result.completed_successfully,
        "execution_time_seconds": execution_result.execution_time_seconds,
        "errors": execution_result.errors,
        "ttfa_results": execution_result.ttfa_results,
        "streaming_results": execution_result.streaming_results,
        "provider_results": execution_result.provider_results,
        "full_spectrum_results": execution_result.full_spectrum_results,
        "execution_timestamp": execution_result.start_time.timestamp()
    }
    
    _benchmark_status["progress"] = 0.9
    
    # Results are already saved by BenchmarkRunner if save_results=True
    # Additional saving can be done here if needed
    timestamp = int(time.time())
    results_dir = "reports/benchmarks"
    os.makedirs(results_dir, exist_ok=True)
    
    results_file = f"{results_dir}/benchmark_{timestamp}.json"
    with open(results_file, 'w') as f:
        import json
        json.dump(results, f, indent=2, default=str)
    
    _benchmark_status["last_results"] = results
    _benchmark_status["progress"] = 1.0
    _benchmark_status["current_test"] = "Completed"

def _estimate_benchmark_duration(benchmark_type: str) -> float:
    """Estimate benchmark execution time"""
    estimates = {
        "ttfa": 30.0,      # 30 seconds for TTFA suite
        "streaming": 45.0,  # 45 seconds for streaming tests
        "full": 120.0       # 2 minutes for full spectrum
    }
    return estimates.get(benchmark_type, 60.0)

def _get_quick_recommendation(ttfa_ms: float, bottleneck: str) -> str:
    """Get quick optimization recommendation"""
    if ttfa_ms <= 400:
        return "✅ Excellent TTFA performance"
    elif ttfa_ms <= 800:
        return "✅ Good TTFA performance, meeting target"
    elif ttfa_ms <= 1200:
        return f" TTFA above target. Primary bottleneck: {bottleneck}. Enable streaming optimization."
    elif ttfa_ms <= 2000:
        return f" Poor TTFA performance. Bottleneck: {bottleneck}. Review model inference and chunking."
    else:
        return f" Critical TTFA issues. Bottleneck: {bottleneck}. Immediate optimization required."

def _get_optimization_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate optimization recommendations based on current stats"""
    recommendations = []
    
    ttfa_avg = stats.get("ttfa_average", 0)
    success_rate = stats.get("success_rate", 0)
    
    if ttfa_avg > 1200:
        recommendations.append("Enable streaming optimization for better TTFA performance")
    if success_rate < 0.8:
        recommendations.append("Review text processing pipeline for consistency")
    if stats.get("fast_path_requests", 0) < 10:
        recommendations.append("Run more tests to gather statistical data")
    
    return recommendations


@router.post("/audio-quality/run", summary="Run Audio Quality Benchmark", tags=["audio-quality"])
async def run_audio_quality_benchmark_endpoint(
    voices: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """
    Run comprehensive audio quality benchmark.

    Tests audio output against enterprise standards including:
    - LUFS loudness (target: -16 ±1)
    - dBTP true peak levels (ceiling: -1.0)
    - Crest factor and dynamic range
    - Quality scoring and compliance validation

    **Parameters:**
    - `voices`: Optional list of voices to test (default: common voices)

    **Returns:**
    Benchmark results with quality analysis and recommendations.
    """
    try:
        if not voices:
            voices = ["af_heart", "af_bella", "am_michael", "bf_alice"]

        logger.info(f"Starting audio quality benchmark for voices: {voices}")

        # Run benchmark
        results = await run_audio_quality_benchmark(voices)

        # Save results in background if requested
        if background_tasks:
            background_tasks.add_task(_save_audio_quality_results, results)

        return {
            "status": "success",
            "message": "Audio quality benchmark completed",
            "results": results
        }

    except Exception as e:
        logger.error(f"Audio quality benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")


@router.get("/audio-quality/status", summary="Get Audio Quality Benchmark Status", tags=["audio-quality"])
async def get_audio_quality_status() -> Dict[str, Any]:
    """
    Get current audio quality benchmark status and recent results.

    Returns the most recent benchmark results and system health status.
    """
    try:
        # Check for recent benchmark results
        import glob
        import os
        from pathlib import Path

        results_dir = Path("artifacts/bench")
        if results_dir.exists():
            audio_quality_files = list(results_dir.glob("audio_quality_*.json"))
            if audio_quality_files:
                latest_file = max(audio_quality_files, key=lambda x: x.stat().st_mtime)

                import json
                with open(latest_file, 'r') as f:
                    latest_results = json.load(f)

                return {
                    "status": "available",
                    "latest_benchmark": {
                        "file": str(latest_file),
                        "timestamp": latest_results.get("timestamp"),
                        "pass_rate": latest_results.get("analysis", {}).get("summary", {}).get("pass_rate"),
                        "avg_score": latest_results.get("analysis", {}).get("summary", {}).get("avg_quality_score")
                    }
                }

        return {
            "status": "no_recent_benchmarks",
            "message": "No recent audio quality benchmarks found"
        }

    except Exception as e:
        logger.error(f"Failed to get audio quality status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


def _save_audio_quality_results(results: Dict[str, Any]):
    """Save audio quality benchmark results to file."""
    try:
        from api.performance.benchmarks.audio_quality_benchmark import AudioQualityBenchmark

        benchmark = AudioQualityBenchmark()
        output_path = benchmark.save_benchmark_report(results)

        logger.info(f"Audio quality benchmark results saved: {output_path}")

    except Exception as e:
        logger.error(f"Failed to save audio quality results: {e}")


# Status Update Endpoints
@router.get("/status/operations", summary="List All Operations", tags=["status"])
async def list_operations(status: Optional[str] = None) -> Dict[str, Any]:
    """
    List all tracked operations with optional status filtering.

    **Parameters:**
    - `status`: Optional filter by operation status (pending, processing, completed, failed)

    **Returns:**
    List of operations with their current status and progress.
    """
    try:
        from api.performance.status_handler import get_status_handler, OperationStatus

        handler = get_status_handler()

        status_filter = None
        if status:
            try:
                status_filter = OperationStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        operations = handler.list_operations(status_filter)

        return {
            "status": "success",
            "total_operations": len(operations),
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "operation_type": op.operation_type,
                    "status": op.status.value,
                    "progress_percent": op.progress_percent,
                    "start_time": op.start_time,
                    "duration_seconds": op.duration_seconds,
                    "completed_items": op.completed_items,
                    "total_items": op.total_items,
                    "current_item": op.current_item,
                    "warnings": op.warnings,
                    "errors": op.errors,
                    "estimated_completion_time": op.estimated_completion_time
                }
                for op in operations
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list operations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list operations: {str(e)}")


@router.get("/status/operations/{operation_id}", summary="Get Operation Status", tags=["status"])
async def get_operation_status(operation_id: str) -> Dict[str, Any]:
    """
    Get detailed status of a specific operation.

    **Parameters:**
    - `operation_id`: Unique operation identifier

    **Returns:**
    Detailed operation status including progress, metrics, and history.
    """
    try:
        from api.performance.status_handler import get_status_handler

        handler = get_status_handler()
        operation = handler.get_operation_status(operation_id)

        if not operation:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")

        return {
            "status": "success",
            "operation": {
                "operation_id": operation.operation_id,
                "operation_type": operation.operation_type,
                "status": operation.status.value,
                "progress_percent": operation.progress_percent,
                "start_time": operation.start_time,
                "last_update_time": operation.last_update_time,
                "duration_seconds": operation.duration_seconds,
                "progress": {
                    "completed_items": operation.completed_items,
                    "total_items": operation.total_items,
                    "current_item": operation.current_item
                },
                "metrics": operation.metrics,
                "warnings": operation.warnings,
                "errors": operation.errors,
                "estimated_completion_time": operation.estimated_completion_time,
                "is_complete": operation.is_complete
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get operation status for {operation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get operation status: {str(e)}")


@router.post("/status/operations/{operation_id}/cancel", summary="Cancel Operation", tags=["status"])
async def cancel_operation(operation_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel a running operation.

    **Parameters:**
    - `operation_id`: Unique operation identifier
    - `reason`: Optional cancellation reason

    **Returns:**
    Confirmation of operation cancellation.
    """
    try:
        from api.performance.status_handler import get_status_handler

        handler = get_status_handler()
        operation = handler.get_operation_status(operation_id)

        if not operation:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")

        if operation.is_complete:
            raise HTTPException(status_code=400, detail=f"Operation {operation_id} is already complete")

        handler.cancel_operation(operation_id, reason)

        return {
            "status": "success",
            "message": f"Operation {operation_id} cancelled",
            "reason": reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel operation {operation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel operation: {str(e)}")
