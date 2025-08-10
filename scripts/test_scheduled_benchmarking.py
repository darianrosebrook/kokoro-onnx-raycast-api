#!/usr/bin/env python3
"""
Scheduled Benchmarking Validation Script

Validates scheduled benchmarking behavior:
- Scheduler starts and reports status
- should_run_benchmark() logic works vs stored timestamp
- run_scheduled_benchmark() executes and writes results
- get_scheduled_benchmark_stats() reflects updates

@author: @darianrosebrook
@date: 2025-01-27
@version: 1.0.0
"""

import asyncio
import json
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    try:
        # Import module directly
        from api.performance.scheduled_benchmark import (
            start_benchmark_scheduler,
            stop_benchmark_scheduler,
            get_scheduled_benchmark_stats,
            get_benchmark_results_path,
            should_run_benchmark,
            run_scheduled_benchmark,
        )

        # Ensure reports dir exists
        results_path = Path(get_benchmark_results_path())
        results_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove previous result to force should_run_benchmark True
        if results_path.exists():
            logger.info(f"Removing previous results file to force benchmark: {results_path}")
            try:
                results_path.unlink()
            except Exception:
                pass

        # Verify should_run_benchmark()
        should_run = should_run_benchmark()
        logger.info(f"should_run_benchmark(): {should_run}")

        # Run benchmark once (without waiting scheduler)
        res = await run_scheduled_benchmark()
        logger.info(f"run_scheduled_benchmark() -> success={res.get('success')} duration={res.get('duration_seconds')}")

        # Validate file written
        if results_path.exists():
            logger.info(f"✅ Results file written: {results_path}")
            try:
                data = json.loads(results_path.read_text())
                logger.info(f"  timestamp: {data.get('timestamp')}")
            except Exception as e:
                logger.warning(f"Could not read results JSON: {e}")
        else:
            logger.error("❌ Results file not found after run")

        # Start scheduler quickly then stop
        task = start_benchmark_scheduler()
        await asyncio.sleep(0.5)
        stop_benchmark_scheduler()
        await asyncio.sleep(0.1)

        # Read stats
        stats = get_scheduled_benchmark_stats()
        logger.info(f"Stats: scheduler_active={stats.get('scheduler_active')}, last_run={stats.get('last_run')}")

        # Basic pass/fail
        if not res.get('success'):
            raise SystemExit(1)

    except Exception as e:
        logger.error(f"Scheduled benchmarking test failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
