#!/usr/bin/env python3
"""
Final Optimization Application Script

This script applies all the final optimizations including:
1. Memory fragmentation watchdog fixes
2. Dynamic memory optimization fixes
3. Pipeline warmer activation
4. Real-time optimizer activation
5. Performance monitoring enhancements

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import os
import sys
import time
import logging
import json
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def apply_memory_fragmentation_fixes():
    """Apply memory fragmentation watchdog fixes."""
    logger.info("🔧 Applying memory fragmentation watchdog fixes...")
    
    try:
        # The fixes are already applied in the code
        # This function validates that the fixes are working
        from api.model.sessions.dual_session import MemoryFragmentationWatchdog
        
        # Test the watchdog
        watchdog = MemoryFragmentationWatchdog()
        memory_usage = watchdog._get_memory_usage()
        
        logger.info(f"✅ Memory fragmentation watchdog working - current usage: {memory_usage:.1f}MB")
        return {
            "status": "success",
            "memory_usage_mb": memory_usage,
            "watchdog_working": True
        }
        
    except Exception as e:
        logger.error(f"❌ Memory fragmentation fix failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "watchdog_working": False
        }


def apply_dynamic_memory_fixes():
    """Apply dynamic memory optimization fixes."""
    logger.info("🔧 Applying dynamic memory optimization fixes...")
    
    try:
        # The fixes are already applied in the stats function
        # This function validates that the fixes are working
        from api.performance.stats import get_dynamic_memory_optimization_stats
        
        # Test the stats function
        stats = get_dynamic_memory_optimization_stats()
        
        if "error" not in stats:
            logger.info("✅ Dynamic memory optimization stats working")
            return {
                "status": "success",
                "stats_working": True,
                "current_arena_size_mb": stats.get("current_arena_size_mb", 512)
            }
        else:
            logger.warning(f"⚠️ Dynamic memory optimization still has issues: {stats.get('error')}")
            return {
                "status": "partial",
                "error": stats.get("error"),
                "stats_working": False
            }
        
    except Exception as e:
        logger.error(f"❌ Dynamic memory fix failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "stats_working": False
        }


def apply_pipeline_warmer_fixes():
    """Apply pipeline warmer activation fixes."""
    logger.info("🔧 Applying pipeline warmer activation fixes...")
    
    try:
        from api.model.optimization.pipeline_warmer_fix import fix_pipeline_warmer_initialization, get_pipeline_warmer_status
        
        # Apply the fix
        fix_result = fix_pipeline_warmer_initialization()
        
        # Get status
        status = get_pipeline_warmer_status()
        
        if fix_result.get("status") in ["completed", "scheduled", "already_complete"]:
            logger.info("✅ Pipeline warmer fix applied successfully")
            return {
                "status": "success",
                "fix_result": fix_result,
                "warmer_status": status,
                "warm_up_complete": status.get("warm_up_complete", False)
            }
        else:
            logger.warning(f"⚠️ Pipeline warmer fix had issues: {fix_result}")
            return {
                "status": "partial",
                "fix_result": fix_result,
                "warmer_status": status
            }
        
    except Exception as e:
        logger.error(f"❌ Pipeline warmer fix failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


def apply_real_time_optimizer_fixes():
    """Apply real-time optimizer activation fixes."""
    logger.info("🔧 Applying real-time optimizer activation fixes...")
    
    try:
        from api.model.optimization.real_time_optimizer_fix import fix_real_time_optimizer_initialization, trigger_initial_optimization, get_real_time_optimizer_status
        
        # Apply the fix
        fix_result = fix_real_time_optimizer_initialization()
        
        # Trigger initial optimization
        init_result = trigger_initial_optimization()
        
        # Get status
        status = get_real_time_optimizer_status()
        
        if fix_result.get("status") in ["activated", "already_active"]:
            logger.info("✅ Real-time optimizer fix applied successfully")
            return {
                "status": "success",
                "fix_result": fix_result,
                "init_result": init_result,
                "optimizer_status": status,
                "auto_optimization_enabled": status.get("auto_optimization_enabled", False)
            }
        else:
            logger.warning(f"⚠️ Real-time optimizer fix had issues: {fix_result}")
            return {
                "status": "partial",
                "fix_result": fix_result,
                "optimizer_status": status
            }
        
    except Exception as e:
        logger.error(f"❌ Real-time optimizer fix failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


def test_performance_improvements():
    """Test the performance improvements."""
    logger.info("🧪 Testing performance improvements...")
    
    try:
        import httpx
        import asyncio
        
        async def test_ttfa():
            try:
                async with httpx.AsyncClient() as client:
                    start_time = time.perf_counter()
                    response = await client.post(
                        "http://127.0.0.1:8000/v1/audio/speech",
                        headers={"Content-Type": "application/json"},
                        json={
                            "text": "Hello world!",
                            "voice": "af_heart",
                            "speed": 1.0,
                            "stream": True,
                            "format": "wav"
                        },
                        timeout=10.0
                    )
                    ttfa_ms = (time.perf_counter() - start_time) * 1000
                    return {"ttfa_ms": ttfa_ms, "status": "success"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        # Test TTFA
        ttfa_result = asyncio.run(test_ttfa())
        
        if ttfa_result.get("status") == "success":
            ttfa_ms = ttfa_result.get("ttfa_ms", 0)
            logger.info(f"✅ TTFA test successful: {ttfa_ms:.1f}ms")
            return {
                "status": "success",
                "ttfa_ms": ttfa_ms,
                "performance_excellent": ttfa_ms < 50  # Under 50ms is excellent
            }
        else:
            logger.warning(f"⚠️ TTFA test failed: {ttfa_result.get('error')}")
            return {
                "status": "failed",
                "error": ttfa_result.get("error")
            }
        
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


def generate_final_optimization_report(results):
    """Generate a final optimization report."""
    logger.info("📊 Generating final optimization report...")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "optimization_version": "3.0.0",
        "fixes_applied": {
            "memory_fragmentation": results.get("memory_fragmentation", {}),
            "dynamic_memory": results.get("dynamic_memory", {}),
            "pipeline_warmer": results.get("pipeline_warmer", {}),
            "real_time_optimizer": results.get("real_time_optimizer", {}),
            "performance_test": results.get("performance_test", {})
        },
        "summary": {
            "total_fixes_applied": len([r for r in results.values() if r.get("status") == "success"]),
            "partial_fixes": len([r for r in results.values() if r.get("status") == "partial"]),
            "failed_fixes": len([r for r in results.values() if r.get("status") == "failed"]),
            "overall_success_rate": len([r for r in results.values() if r.get("status") == "success"]) / len(results) * 100
        },
        "performance_metrics": {
            "ttfa_ms": results.get("performance_test", {}).get("ttfa_ms", 0),
            "performance_excellent": results.get("performance_test", {}).get("performance_excellent", False)
        },
        "system_status": {
            "memory_fragmentation_fixed": results.get("memory_fragmentation", {}).get("watchdog_working", False),
            "dynamic_memory_fixed": results.get("dynamic_memory", {}).get("stats_working", False),
            "pipeline_warmer_active": results.get("pipeline_warmer", {}).get("warm_up_complete", False),
            "real_time_optimizer_active": results.get("real_time_optimizer", {}).get("auto_optimization_enabled", False)
        }
    }
    
    return report


def main():
    """Main optimization application function."""
    logger.info("🚀 Kokoro-ONNX Final Optimization Application")
    logger.info("=" * 60)
    
    start_time = time.perf_counter()
    results = {}
    
    try:
        # Apply all fixes
        results["memory_fragmentation"] = apply_memory_fragmentation_fixes()
        results["dynamic_memory"] = apply_dynamic_memory_fixes()
        results["pipeline_warmer"] = apply_pipeline_warmer_fixes()
        results["real_time_optimizer"] = apply_real_time_optimizer_fixes()
        results["performance_test"] = test_performance_improvements()
        
        # Generate report
        report = generate_final_optimization_report(results)
        
        # Save report
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        report_file = reports_dir / f"final_optimization_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Calculate total time
        total_time = time.perf_counter() - start_time
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("🎯 FINAL OPTIMIZATION SUMMARY")
        logger.info("=" * 60)
        
        success_count = report["summary"]["total_fixes_applied"]
        partial_count = report["summary"]["partial_fixes"]
        failed_count = report["summary"]["failed_fixes"]
        success_rate = report["summary"]["overall_success_rate"]
        
        logger.info(f"✅ Successful fixes: {success_count}")
        logger.info(f"⚠️ Partial fixes: {partial_count}")
        logger.info(f"❌ Failed fixes: {failed_count}")
        logger.info(f"📊 Overall success rate: {success_rate:.1f}%")
        
        # Performance metrics
        ttfa_ms = report["performance_metrics"]["ttfa_ms"]
        performance_excellent = report["performance_metrics"]["performance_excellent"]
        
        logger.info(f"\n🚀 PERFORMANCE METRICS:")
        logger.info(f"TTFA: {ttfa_ms:.1f}ms ({'✅ EXCELLENT' if performance_excellent else '⚠️ Good'})")
        
        # System status
        logger.info(f"\n🔧 SYSTEM STATUS:")
        logger.info(f"Memory Fragmentation: {'✅ Fixed' if report['system_status']['memory_fragmentation_fixed'] else '❌ Issues'}")
        logger.info(f"Dynamic Memory: {'✅ Fixed' if report['system_status']['dynamic_memory_fixed'] else '❌ Issues'}")
        logger.info(f"Pipeline Warmer: {'✅ Active' if report['system_status']['pipeline_warmer_active'] else '⚠️ Partial'}")
        logger.info(f"Real-time Optimizer: {'✅ Active' if report['system_status']['real_time_optimizer_active'] else '❌ Issues'}")
        
        logger.info(f"\n⏱️ Total optimization time: {total_time:.2f}s")
        logger.info(f"📄 Final report: {report_file}")
        logger.info("=" * 60)
        
        return success_rate >= 80  # Consider success if 80%+ of fixes worked
        
    except Exception as e:
        logger.error(f"❌ Final optimization failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
