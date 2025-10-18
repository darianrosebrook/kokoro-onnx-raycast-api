"""
Pipeline Warmer Fix

This module fixes the pipeline warmer initialization issue by ensuring
the warm-up process is triggered during system startup.

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


def fix_pipeline_warmer_initialization() -> Dict[str, Any]:
    """
    Fix the pipeline warmer initialization by triggering the warm-up process.
    
    @returns Dict[str, Any]: Fix results and status
    """
    try:
        from api.model.pipeline.warmer import get_pipeline_warmer
        
        pipeline_warmer = get_pipeline_warmer()
        if pipeline_warmer is None:
            logger.warning("Pipeline warmer not available - cannot fix initialization")
            return {
                "status": "failed",
                "reason": "Pipeline warmer not available",
                "warm_up_complete": False
            }
        
        # Check if warm-up is already complete
        if pipeline_warmer.warm_up_complete:
            logger.info("✅ Pipeline warmer already complete")
            return {
                "status": "already_complete",
                "warm_up_complete": True,
                "warm_up_duration": pipeline_warmer.warm_up_duration
            }
        
        # Trigger warm-up in background
        logger.info("🔄 Triggering pipeline warmer initialization...")
        
        # Run warm-up asynchronously
        async def run_warm_up():
            try:
                await pipeline_warmer.warm_up_complete_pipeline()
                logger.info("✅ Pipeline warmer initialization completed successfully")
                return True
            except Exception as e:
                logger.error(f"❌ Pipeline warmer initialization failed: {e}")
                return False
        
        # Schedule the warm-up to run in background
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a task
            task = asyncio.create_task(run_warm_up())
            logger.info("🔄 Pipeline warmer warm-up scheduled in background")
            return {
                "status": "scheduled",
                "warm_up_complete": False,
                "message": "Warm-up scheduled in background"
            }
        else:
            # If we're not in an async context, run it synchronously
            result = asyncio.run(run_warm_up())
            return {
                "status": "completed" if result else "failed",
                "warm_up_complete": result,
                "message": "Warm-up completed synchronously"
            }
        
    except Exception as e:
        logger.error(f"❌ Failed to fix pipeline warmer initialization: {e}")
        return {
            "status": "error",
            "error": str(e),
            "warm_up_complete": False
        }


def get_pipeline_warmer_status() -> Dict[str, Any]:
    """
    Get the current pipeline warmer status.
    
    @returns Dict[str, Any]: Pipeline warmer status
    """
    try:
        from api.model.pipeline.warmer import get_pipeline_warmer
        
        pipeline_warmer = get_pipeline_warmer()
        if pipeline_warmer is None:
            return {
                "available": False,
                "warm_up_complete": False,
                "error": "Pipeline warmer not available"
            }
        
        return {
            "available": True,
            "warm_up_complete": pipeline_warmer.warm_up_complete,
            "warm_up_duration": pipeline_warmer.warm_up_duration,
            "common_patterns_count": len(pipeline_warmer.common_text_patterns),
            "phoneme_patterns_count": len(pipeline_warmer.phoneme_test_patterns),
            "voice_patterns_count": len(pipeline_warmer.common_voice_patterns)
        }
        
    except Exception as e:
        return {
            "available": False,
            "warm_up_complete": False,
            "error": str(e)
        }
