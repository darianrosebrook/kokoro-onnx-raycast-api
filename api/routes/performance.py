"""
Performance Monitoring and Benchmarking API Routes

This module provides REST API endpoints for performance monitoring, benchmarking,
and TTFA analysis of the Kokoro-ONNX TTS system.

@author: @darianrosebrook
@date: 2025-08-15
@version: 1.0.0
@license: MIT
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


class BenchmarkRequest(BaseModel):
    """Request model for custom benchmark execution"""
    text: str = Field(..., description="Text to benchmark", max_length=2000)
    voice: str = Field(default="af_heart", description="Voice to use for benchmarking")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    benchmark_type: str = Field(default="ttfa", description="Type of benchmark: ttfa, streaming, provider, or comprehensive")
    quick: bool = Field(default=True, description="Run quick benchmark (faster but less comprehensive)")


class TTFAResponse(BaseModel):
    """Response model for TTFA metrics"""
    current_ttfa_ms: float
    target_ttfa_ms: float
    achievement_rate_percent: float
    recent_trend: str
    recommendations: list


@router.get("/health", summary="Performance monitoring health check")
async def performance_health():
    """
    Check if performance monitoring systems are operational
    """
    try:
        from api.performance.ttfa_monitor import get_ttfa_monitor
        from api.performance.stats import coreml_performance_stats
        
        ttfa_monitor = get_ttfa_monitor()
        
        return {
            "status": "healthy",
            "monitoring_active": True,
            "ttfa_monitor_initialized": ttfa_monitor is not None,
            "stats_available": bool(coreml_performance_stats),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Performance health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance monitoring error: {str(e)}")


@router.get("/ttfa", response_model=TTFAResponse, summary="Get current TTFA metrics")
async def get_ttfa_metrics():
    """
    Get current Time to First Audio (TTFA) performance metrics and analysis
    """
    try:
        from api.performance.ttfa_monitor import get_ttfa_monitor
        
        ttfa_monitor = get_ttfa_monitor()
        summary = ttfa_monitor.get_performance_summary()
        
        return TTFAResponse(
            current_ttfa_ms=summary['timing_stats_ms']['average'],
            target_ttfa_ms=summary['target_ttfa_ms'],
            achievement_rate_percent=summary['performance']['target_achievement_rate_percent'],
            recent_trend=summary['performance']['recent_trend'],
            recommendations=summary['recommendations']
        )
    except Exception as e:
        logger.error(f"Failed to get TTFA metrics: {e}")
        raise HTTPException(status_code=500, detail=f"TTFA metrics error: {str(e)}")


@router.get("/stats", summary="Get comprehensive performance statistics")
async def get_performance_stats():
    """
    Get comprehensive performance statistics including all monitored metrics
    """
    try:
        from api.performance.stats import coreml_performance_stats
        from api.performance.ttfa_monitor import get_ttfa_monitor
        
        # Get TTS performance stats
        stats = dict(coreml_performance_stats)
        
        # Get TTFA metrics
        ttfa_monitor = get_ttfa_monitor()
        ttfa_summary = ttfa_monitor.get_performance_summary()
        
        # Combine all metrics
        response = {
            "timestamp": datetime.now().isoformat(),
            "tts_stats": stats,
            "ttfa_metrics": ttfa_summary,
            "system_health": await _get_system_health()
        }
        
        return response
    except Exception as e:
        logger.error(f"Failed to get performance stats: {e}")
        raise HTTPException(status_code=500, detail=f"Performance stats error: {str(e)}")


@router.post("/benchmark/ttfa", summary="Run TTFA benchmark")
async def run_ttfa_benchmark(
    background_tasks: BackgroundTasks,
    quick: bool = Query(default=True, description="Run quick benchmark for faster results")
):
    """
    Run Time to First Audio (TTFA) benchmark across multiple scenarios
    """
    try:
        from api.performance.benchmarks.ttfa_benchmark import run_ttfa_benchmark
        
        logger.info(f"Starting TTFA benchmark (quick={quick})")
        
        # Run benchmark
        benchmark_suite = await run_ttfa_benchmark(quick=quick)
        summary = benchmark_suite.get_summary()
        
        # Save results in background
        background_tasks.add_task(_save_benchmark_results, benchmark_suite, "ttfa")
        
        return {
            "benchmark_type": "ttfa",
            "quick_mode": quick,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"TTFA benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTFA benchmark error: {str(e)}")


@router.post("/benchmark/streaming", summary="Run streaming performance benchmark")  
async def run_streaming_benchmark(
    background_tasks: BackgroundTasks,
    quick: bool = Query(default=True, description="Run quick benchmark for faster results")
):
    """
    Run streaming performance benchmark to analyze chunk delivery and buffer management
    """
    try:
        from api.performance.benchmarks.streaming_benchmark import run_streaming_benchmark
        
        logger.info(f"Starting streaming benchmark (quick={quick})")
        
        # Run benchmark
        benchmark_suite = await run_streaming_benchmark(quick=quick)
        summary = benchmark_suite.get_summary()
        
        # Save results in background
        background_tasks.add_task(_save_benchmark_results, benchmark_suite, "streaming")
        
        return {
            "benchmark_type": "streaming",
            "quick_mode": quick,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Streaming benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming benchmark error: {str(e)}")


@router.post("/benchmark/provider", summary="Run provider comparison benchmark")
async def run_provider_benchmark(
    background_tasks: BackgroundTasks,
    quick: bool = Query(default=True, description="Run quick benchmark for faster results")
):
    """
    Run provider comparison benchmark to analyze CoreML vs CPU performance
    """
    try:
        from api.performance.benchmarks.provider_benchmark import run_provider_benchmark
        
        logger.info(f"Starting provider benchmark (quick={quick})")
        
        # Run benchmark
        benchmark_suite = await run_provider_benchmark(quick=quick)
        summary = benchmark_suite.get_summary()
        
        # Save results in background
        background_tasks.add_task(_save_benchmark_results, benchmark_suite, "provider")
        
        return {
            "benchmark_type": "provider",
            "quick_mode": quick,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Provider benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Provider benchmark error: {str(e)}")


@router.post("/benchmark/comprehensive", summary="Run comprehensive benchmark suite")
async def run_comprehensive_benchmark(
    background_tasks: BackgroundTasks,
    quick: bool = Query(default=True, description="Run quick benchmark for faster results"),
    include_providers: bool = Query(default=True, description="Include provider comparison tests")
):
    """
    Run comprehensive benchmark suite including TTFA, streaming, and provider tests
    """
    try:
        from api.performance.benchmarks.comprehensive_benchmark import run_comprehensive_benchmark, run_quick_benchmark
        
        logger.info(f"Starting comprehensive benchmark (quick={quick}, include_providers={include_providers})")
        
        # Run benchmark
        if quick:
            benchmark_result = await run_quick_benchmark()
        else:
            benchmark_result = await run_comprehensive_benchmark(include_providers)
        
        summary = benchmark_result.get_executive_summary()
        
        # Save results in background
        background_tasks.add_task(_save_comprehensive_results, benchmark_result)
        
        return {
            "benchmark_type": "comprehensive",
            "quick_mode": quick,
            "executive_summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Comprehensive benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comprehensive benchmark error: {str(e)}")


@router.post("/benchmark/custom", summary="Run custom benchmark")
async def run_custom_benchmark(request: BenchmarkRequest, background_tasks: BackgroundTasks):
    """
    Run custom benchmark with specific text, voice, and parameters
    """
    try:
        logger.info(f"Starting custom {request.benchmark_type} benchmark")
        
        if request.benchmark_type == "ttfa":
            from api.performance.benchmarks.ttfa_benchmark import benchmark_single_text
            result = await benchmark_single_text(request.text, request.voice, request.speed)
            return {
                "benchmark_type": "custom_ttfa",
                "result": result.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        
        elif request.benchmark_type == "streaming":
            from api.performance.benchmarks.streaming_benchmark import StreamingBenchmark
            benchmark = StreamingBenchmark()
            result = await benchmark.run_single_streaming_test(
                request.text, request.voice, request.speed, "custom_streaming"
            )
            return {
                "benchmark_type": "custom_streaming", 
                "result": result.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        
        elif request.benchmark_type == "provider":
            from api.performance.benchmarks.provider_benchmark import compare_providers
            results = await compare_providers(request.text, request.voice)
            return {
                "benchmark_type": "custom_provider",
                "results": [result.to_dict() for result in results],
                "timestamp": datetime.now().isoformat()
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown benchmark type: {request.benchmark_type}")
    
    except Exception as e:
        logger.error(f"Custom benchmark failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Custom benchmark error: {str(e)}")


@router.get("/reports", summary="List available benchmark reports")
async def list_benchmark_reports():
    """
    List all available benchmark report files
    """
    try:
        import os
        import glob
        from datetime import datetime
        
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            return {"reports": [], "count": 0}
        
        # Find all benchmark report files
        pattern = os.path.join(reports_dir, "*benchmark*.json")
        report_files = glob.glob(pattern)
        
        reports = []
        for file_path in sorted(report_files, reverse=True):  # Most recent first
            filename = os.path.basename(file_path)
            file_stat = os.stat(file_path)
            
            reports.append({
                "filename": filename,
                "file_path": file_path,
                "size_bytes": file_stat.st_size,
                "created_timestamp": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                "modified_timestamp": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            })
        
        return {
            "reports": reports,
            "count": len(reports),
            "reports_directory": reports_dir
        }
    except Exception as e:
        logger.error(f"Failed to list benchmark reports: {e}")
        raise HTTPException(status_code=500, detail=f"Report listing error: {str(e)}")


@router.get("/reports/{filename}", summary="Get specific benchmark report")
async def get_benchmark_report(filename: str):
    """
    Retrieve a specific benchmark report by filename
    """
    try:
        import os
        import json
        
        # Security: Ensure filename doesn't contain path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = os.path.join("reports", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Report not found")
        
        with open(file_path, 'r') as f:
            report_data = json.load(f)
        
        return report_data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid report format")
    except Exception as e:
        logger.error(f"Failed to get benchmark report: {e}")
        raise HTTPException(status_code=500, detail=f"Report retrieval error: {str(e)}")


@router.post("/clear_cache", summary="Clear model and session caches")
async def clear_cache():
    """
    Clear model and session caches to ensure consistent benchmark results.
    This endpoint is useful for benchmarking to prevent cache pollution between trials.
    """
    try:
        from api.model.sessions.manager import clear_model
        from api.tts.text_processing import clear_phoneme_cache
        from api.utils.cache_helpers import clear_inference_cache
        
        # Clear model sessions
        clear_model()
        
        # Clear phoneme cache
        clear_phoneme_cache()
        
        # Clear inference cache
        clear_inference_cache()
        
        logger.info("✅ Model and session caches cleared successfully")
        
        return {
            "status": "success",
            "message": "Model and session caches cleared",
            "timestamp": datetime.now().isoformat(),
            "cleared_caches": [
                "model_sessions",
                "phoneme_cache", 
                "inference_cache"
            ]
        }
    except Exception as e:
        logger.error(f"Failed to clear caches: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clearing error: {str(e)}")


# Helper functions
async def _get_system_health() -> Dict[str, Any]:
    """Get current system health metrics"""
    try:
        import psutil
        
        # Get memory info
        memory = psutil.virtual_memory()
        
        # Get CPU info
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        return {
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent
            },
            "cpu": {
                "usage_percent": cpu_percent
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.warning(f"Failed to get system health: {e}")
        return {"error": str(e)}


async def _save_benchmark_results(benchmark_suite, benchmark_type: str):
    """Background task to save benchmark results"""
    try:
        if hasattr(benchmark_suite, 'save_benchmark_results'):
            # For TTFA benchmark
            benchmark_suite.save_benchmark_results()
        else:
            # For other benchmark types, implement similar save logic
            logger.warning(f"Save method not implemented for {benchmark_type} benchmark")
    except Exception as e:
        logger.error(f"Failed to save {benchmark_type} benchmark results: {e}")


async def _save_comprehensive_results(benchmark_result):
    """Background task to save comprehensive benchmark results"""
    try:
        from api.performance.benchmarks.comprehensive_benchmark import ComprehensiveBenchmark
        benchmark = ComprehensiveBenchmark()
        benchmark.save_comprehensive_results(benchmark_result)
    except Exception as e:
        logger.error(f"Failed to save comprehensive benchmark results: {e}")


# datetime is already imported at module level above
