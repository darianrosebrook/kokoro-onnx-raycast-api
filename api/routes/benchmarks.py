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
        # TODO: Implement BenchmarkRunner class
        # Generate report based on last results
        # runner = BenchmarkRunner()
        # report = runner.generate_performance_report(_benchmark_status["last_results"])
        
        return {
            "report": "Performance report generation temporarily disabled",
            "format": "markdown",
            "generated_at": time.time(),
            "benchmark_timestamp": _benchmark_status["last_results"].get("execution_timestamp")
        }
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
    
    # TODO: Implement BenchmarkRunner class
    # runner = BenchmarkRunner()
    # results = await runner.run_full_benchmark_suite()
    results = {"error": "Full spectrum benchmark temporarily disabled"}
    
    _benchmark_status["progress"] = 0.9
    
    # Save results if requested
    timestamp = int(time.time())
    results_dir = "reports/benchmarks"
    os.makedirs(results_dir, exist_ok=True)
    
    results_file = f"{results_dir}/benchmark_{timestamp}.json"
    runner.save_benchmark_results(results, results_file)
    
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
        return f"⚠️ TTFA above target. Primary bottleneck: {bottleneck}. Enable streaming optimization."
    elif ttfa_ms <= 2000:
        return f"🔴 Poor TTFA performance. Bottleneck: {bottleneck}. Review model inference and chunking."
    else:
        return f"🔴 Critical TTFA issues. Bottleneck: {bottleneck}. Immediate optimization required."

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
