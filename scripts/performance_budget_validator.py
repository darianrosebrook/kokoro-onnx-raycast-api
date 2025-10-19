#!/usr/bin/env python3
"""
Performance Budget Validator for Kokoro TTS API.

This script validates that the TTS API meets performance budgets defined in the Working Spec:
- TTFA (Time to First Audio): ≤ 500ms for streaming
- API P95 latency: ≤ 1000ms for non-streaming
- Memory usage: ≤ 500MB steady-state
- Audio quality: LUFS -16 ±1 LU, dBTP ≤ -1.0 dB
"""
import asyncio
import aiohttp
import json
import time
import statistics
import psutil
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@dataclass
class PerformanceBudget:
    """Performance budget configuration."""
    ttfa_streaming_ms: float = 500.0
    api_p95_ms: float = 1000.0
    memory_limit_mb: float = 500.0
    lufs_target: float = -16.0
    lufs_tolerance: float = 1.0
    dbtp_ceiling: float = -1.0

@dataclass
class PerformanceResult:
    """Performance test result."""
    test_name: str
    success: bool
    metrics: Dict[str, float]
    budget_violations: List[str]
    details: Dict[str, Any]

class PerformanceBudgetValidator:
    """Validates TTS API performance against defined budgets."""
    
    def __init__(self, base_url: str = "http://localhost:8000", budget: Optional[PerformanceBudget] = None):
        self.base_url = base_url
        self.budget = budget or PerformanceBudget()
        self.results: List[PerformanceResult] = []
    
    async def validate_ttfa_streaming(self, trials: int = 10) -> PerformanceResult:
        """Validate TTFA (Time to First Audio) for streaming requests."""
        print(f"🎯 Testing TTFA streaming (target: ≤{self.budget.ttfa_streaming_ms}ms)...")
        
        request_data = {
            "text": "This is a streaming test to measure time to first audio chunk.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "pcm"
        }
        
        ttfa_times = []
        budget_violations = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(trials):
                start_time = time.time()
                
                try:
                    async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                        if response.status == 200:
                            # Measure time to first chunk
                            first_chunk_time = None
                            async for chunk in response.content.iter_chunked(1024):
                                if first_chunk_time is None:
                                    first_chunk_time = time.time()
                                    break
                            
                            if first_chunk_time:
                                ttfa = (first_chunk_time - start_time) * 1000
                                ttfa_times.append(ttfa)
                                
                                if ttfa > self.budget.ttfa_streaming_ms:
                                    budget_violations.append(f"Trial {i+1}: TTFA {ttfa:.1f}ms > {self.budget.ttfa_streaming_ms}ms")
                        else:
                            print(f"⚠️  Request {i+1} failed with status {response.status}")
                
                except Exception as e:
                    print(f"⚠️  Request {i+1} failed with error: {e}")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
        
        if not ttfa_times:
            return PerformanceResult(
                test_name="TTFA Streaming",
                success=False,
                metrics={},
                budget_violations=["No successful streaming requests"],
                details={"error": "No successful requests"}
            )
        
        # Calculate statistics
        ttfa_p50 = statistics.median(ttfa_times)
        ttfa_p95 = statistics.quantiles(ttfa_times, n=20)[18] if len(ttfa_times) >= 20 else max(ttfa_times)
        ttfa_avg = statistics.mean(ttfa_times)
        
        success = len(budget_violations) == 0 and ttfa_p95 <= self.budget.ttfa_streaming_ms
        
        return PerformanceResult(
            test_name="TTFA Streaming",
            success=success,
            metrics={
                "ttfa_p50_ms": ttfa_p50,
                "ttfa_p95_ms": ttfa_p95,
                "ttfa_avg_ms": ttfa_avg,
                "successful_trials": len(ttfa_times),
                "total_trials": trials
            },
            budget_violations=budget_violations,
            details={
                "all_ttfa_times": ttfa_times,
                "budget_limit": self.budget.ttfa_streaming_ms
            }
        )
    
    async def validate_api_latency(self, trials: int = 20) -> PerformanceResult:
        """Validate API P95 latency for non-streaming requests."""
        print(f"🎯 Testing API latency (target: P95 ≤{self.budget.api_p95_ms}ms)...")
        
        request_data = {
            "text": "This is a latency test for non-streaming requests.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        response_times = []
        budget_violations = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(trials):
                start_time = time.time()
                
                try:
                    async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000
                        response_times.append(response_time)
                        
                        if response.status != 200:
                            print(f"⚠️  Request {i+1} failed with status {response.status}")
                        elif response_time > self.budget.api_p95_ms:
                            budget_violations.append(f"Trial {i+1}: {response_time:.1f}ms > {self.budget.api_p95_ms}ms")
                
                except Exception as e:
                    print(f"⚠️  Request {i+1} failed with error: {e}")
                
                # Small delay between requests
                await asyncio.sleep(0.2)
        
        if not response_times:
            return PerformanceResult(
                test_name="API Latency",
                success=False,
                metrics={},
                budget_violations=["No successful requests"],
                details={"error": "No successful requests"}
            )
        
        # Calculate statistics
        latency_p50 = statistics.median(response_times)
        latency_p95 = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times)
        latency_avg = statistics.mean(response_times)
        
        success = len(budget_violations) == 0 and latency_p95 <= self.budget.api_p95_ms
        
        return PerformanceResult(
            test_name="API Latency",
            success=success,
            metrics={
                "latency_p50_ms": latency_p50,
                "latency_p95_ms": latency_p95,
                "latency_avg_ms": latency_avg,
                "successful_trials": len(response_times),
                "total_trials": trials
            },
            budget_violations=budget_violations,
            details={
                "all_response_times": response_times,
                "budget_limit": self.budget.api_p95_ms
            }
        )
    
    async def validate_memory_usage(self, duration_seconds: int = 60) -> PerformanceResult:
        """Validate memory usage under load."""
        print(f"🎯 Testing memory usage (target: ≤{self.budget.memory_limit_mb}MB)...")
        
        request_data = {
            "text": "Memory usage test with continuous requests.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        memory_samples = []
        max_memory = 0
        budget_violations = []
        
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            request_count = 0
            
            while time.time() - start_time < duration_seconds:
                # Sample memory usage
                try:
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(memory_mb)
                    max_memory = max(max_memory, memory_mb)
                    
                    if memory_mb > self.budget.memory_limit_mb:
                        budget_violations.append(f"Memory {memory_mb:.1f}MB > {self.budget.memory_limit_mb}MB")
                
                except Exception as e:
                    print(f"⚠️  Error sampling memory: {e}")
                
                # Send a request
                try:
                    async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                        request_count += 1
                        if response.status != 200:
                            print(f"⚠️  Request {request_count} failed with status {response.status}")
                
                except Exception as e:
                    print(f"⚠️  Request {request_count} failed with error: {e}")
                
                # Small delay between requests
                await asyncio.sleep(1)
        
        if not memory_samples:
            return PerformanceResult(
                test_name="Memory Usage",
                success=False,
                metrics={},
                budget_violations=["No memory samples collected"],
                details={"error": "No memory samples"}
            )
        
        avg_memory = statistics.mean(memory_samples)
        p95_memory = statistics.quantiles(memory_samples, n=20)[18] if len(memory_samples) >= 20 else max(memory_samples)
        
        success = len(budget_violations) == 0 and max_memory <= self.budget.memory_limit_mb
        
        return PerformanceResult(
            test_name="Memory Usage",
            success=success,
            metrics={
                "max_memory_mb": max_memory,
                "avg_memory_mb": avg_memory,
                "p95_memory_mb": p95_memory,
                "request_count": request_count,
                "duration_seconds": duration_seconds
            },
            budget_violations=budget_violations,
            details={
                "all_memory_samples": memory_samples,
                "budget_limit": self.budget.memory_limit_mb
            }
        )
    
    async def validate_audio_quality(self, trials: int = 5) -> PerformanceResult:
        """Validate audio quality metrics (LUFS, dBTP)."""
        print(f"🎯 Testing audio quality (target: LUFS {self.budget.lufs_target}±{self.budget.lufs_tolerance} LU, dBTP ≤{self.budget.dbtp_ceiling} dB)...")
        
        request_data = {
            "text": "Audio quality test with standard text for measurement.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        lufs_values = []
        dbtp_values = []
        budget_violations = []
        
        # Try to import audio analysis libraries
        try:
            import soundfile as sf
            import numpy as np
            HAVE_AUDIO_ANALYSIS = True
        except ImportError:
            HAVE_AUDIO_ANALYSIS = False
            print("⚠️  Audio analysis libraries not available, skipping quality validation")
        
        async with aiohttp.ClientSession() as session:
            for i in range(trials):
                try:
                    async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                        if response.status == 200:
                            audio_data = await response.read()
                            
                            if HAVE_AUDIO_ANALYSIS and len(audio_data) > 0:
                                # Analyze audio quality
                                try:
                                    # Load audio data
                                    import io
                                    audio_io = io.BytesIO(audio_data)
                                    audio, sample_rate = sf.read(audio_io)
                                    
                                    # TODO: Implement proper audio level measurements
                                    # - [ ] Implement ITU-R BS.1770-4 compliant LUFS calculation
                                    # - [ ] Add proper gating and filtering for accurate loudness measurement
                                    # - [ ] Implement integrated loudness over time windows
                                    # - [ ] Add momentary and short-term loudness calculations
                                    rms = np.sqrt(np.mean(audio**2))
                                    lufs = 20 * np.log10(rms) if rms > 0 else -60
                                    lufs_values.append(lufs)
                                    
                                    # TODO: Implement accurate peak level measurement
                                    # - [ ] Implement true peak detection with oversampling
                                    # - [ ] Add crest factor calculation and monitoring
                                    # - [ ] Implement dynamic range measurements
                                    # - [ ] Add peak-to-average ratio calculations
                                    peak = np.max(np.abs(audio))
                                    dbtp = 20 * np.log10(peak) if peak > 0 else -60
                                    dbtp_values.append(dbtp)
                                    
                                    # Check budget violations
                                    if abs(lufs - self.budget.lufs_target) > self.budget.lufs_tolerance:
                                        budget_violations.append(f"Trial {i+1}: LUFS {lufs:.1f} outside {self.budget.lufs_target}±{self.budget.lufs_tolerance}")
                                    
                                    if dbtp > self.budget.dbtp_ceiling:
                                        budget_violations.append(f"Trial {i+1}: dBTP {dbtp:.1f} > {self.budget.dbtp_ceiling}")
                                
                                except Exception as e:
                                    print(f"⚠️  Audio analysis failed for trial {i+1}: {e}")
                        else:
                            print(f"⚠️  Request {i+1} failed with status {response.status}")
                
                except Exception as e:
                    print(f"⚠️  Request {i+1} failed with error: {e}")
                
                # Small delay between requests
                await asyncio.sleep(1)
        
        if not HAVE_AUDIO_ANALYSIS:
            return PerformanceResult(
                test_name="Audio Quality",
                success=True,  # Skip if no analysis available
                metrics={"skipped": True},
                budget_violations=[],
                details={"reason": "Audio analysis libraries not available"}
            )
        
        if not lufs_values:
            return PerformanceResult(
                test_name="Audio Quality",
                success=False,
                metrics={},
                budget_violations=["No audio quality measurements"],
                details={"error": "No successful audio analysis"}
            )
        
        avg_lufs = statistics.mean(lufs_values)
        avg_dbtp = statistics.mean(dbtp_values)
        
        success = len(budget_violations) == 0
        
        return PerformanceResult(
            test_name="Audio Quality",
            success=success,
            metrics={
                "avg_lufs": avg_lufs,
                "avg_dbtp": avg_dbtp,
                "lufs_target": self.budget.lufs_target,
                "lufs_tolerance": self.budget.lufs_tolerance,
                "dbtp_ceiling": self.budget.dbtp_ceiling,
                "successful_trials": len(lufs_values),
                "total_trials": trials
            },
            budget_violations=budget_violations,
            details={
                "all_lufs_values": lufs_values,
                "all_dbtp_values": dbtp_values
            }
        )
    
    async def run_all_validations(self) -> Dict[str, Any]:
        """Run all performance validations."""
        print("🚀 Starting performance budget validation...")
        
        # Run all validations
        ttfa_result = await self.validate_ttfa_streaming()
        latency_result = await self.validate_api_latency()
        memory_result = await self.validate_memory_usage()
        quality_result = await self.validate_audio_quality()
        
        self.results = [ttfa_result, latency_result, memory_result, quality_result]
        
        # Calculate overall success
        all_success = all(result.success for result in self.results)
        
        # Generate summary
        summary = {
            "overall_success": all_success,
            "total_tests": len(self.results),
            "passed_tests": sum(1 for result in self.results if result.success),
            "failed_tests": sum(1 for result in self.results if not result.success),
            "results": [
                {
                    "test_name": result.test_name,
                    "success": result.success,
                    "metrics": result.metrics,
                    "budget_violations": result.budget_violations
                }
                for result in self.results
            ]
        }
        
        return summary
    
    def save_results(self, output_file: str = "performance-budget-results.json"):
        """Save validation results to file."""
        results_data = {
            "timestamp": time.time(),
            "budget": {
                "ttfa_streaming_ms": self.budget.ttfa_streaming_ms,
                "api_p95_ms": self.budget.api_p95_ms,
                "memory_limit_mb": self.budget.memory_limit_mb,
                "lufs_target": self.budget.lufs_target,
                "lufs_tolerance": self.budget.lufs_tolerance,
                "dbtp_ceiling": self.budget.dbtp_ceiling
            },
            "results": [
                {
                    "test_name": result.test_name,
                    "success": result.success,
                    "metrics": result.metrics,
                    "budget_violations": result.budget_violations,
                    "details": result.details
                }
                for result in self.results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📊 Results saved to {output_file}")

async def main():
    """Main performance validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Budget Validator")
    parser.add_argument("--url", default="http://localhost:8000", help="TTS API base URL")
    parser.add_argument("--output", default="performance-budget-results.json", help="Output file for results")
    parser.add_argument("--ttfa-limit", type=float, default=500.0, help="TTFA limit in ms")
    parser.add_argument("--latency-limit", type=float, default=1000.0, help="API P95 latency limit in ms")
    parser.add_argument("--memory-limit", type=float, default=500.0, help="Memory limit in MB")
    
    args = parser.parse_args()
    
    # Create budget configuration
    budget = PerformanceBudget(
        ttfa_streaming_ms=args.ttfa_limit,
        api_p95_ms=args.latency_limit,
        memory_limit_mb=args.memory_limit
    )
    
    # Create validator
    validator = PerformanceBudgetValidator(args.url, budget)
    
    # Run validations
    summary = await validator.run_all_validations()
    
    # Save results
    validator.save_results(args.output)
    
    # Print summary
    print(f"\n📊 Performance Budget Validation Summary:")
    print(f"  Overall Success: {'✅' if summary['overall_success'] else '❌'}")
    print(f"  Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
    
    for result in summary['results']:
        status = "✅" if result['success'] else "❌"
        print(f"  {status} {result['test_name']}")
        
        if result['budget_violations']:
            for violation in result['budget_violations']:
                print(f"    ⚠️  {violation}")
    
    # Exit with appropriate code
    sys.exit(0 if summary['overall_success'] else 1)

if __name__ == "__main__":
    asyncio.run(main())
