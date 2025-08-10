#!/usr/bin/env python3
"""
Performance Metrics Collection Test Script

This script tests the performance metrics collection system to validate:
- TTFA (Time To First Audio) measurements
- RTF (Real Time Factor) calculations
- Provider switching performance
- Memory usage tracking
- Performance statistics aggregation

@author: @darianrosebrook
@date: 2025-01-27
@version: 1.0.1
"""

import asyncio
import aiohttp
import time
import json
import logging
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceTestResult:
    """Results from a single performance test."""
    test_name: str
    provider: str
    text_length: int
    ttfa_ms: float
    total_duration_ms: float
    rtf: float
    memory_usage_mb: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class PerformanceMetricsTester:
    """Comprehensive performance metrics tester."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results: List[PerformanceTestResult] = []
        
        # Test text samples
        self.test_texts = {
            "short": "Hello world, this is a test.",
            "medium": "The quick brown fox jumps over the lazy dog. This is a medium length text that should test the performance metrics collection system.",
            "long": """Artificial intelligence is transforming our world in profound ways. From natural language processing to computer vision, 
            AI systems are becoming increasingly sophisticated and capable. The performance metrics collection system must accurately 
            measure and track various performance indicators including TTFA, RTF, and memory usage across different providers and text lengths."""
        }
        
        # Test providers (for labeling only; the API may not support provider override)
        self.providers = ["default", "cpu", "coreml", "mps"]
    
    async def test_provider_performance(self, text: str, provider: str, test_name: str) -> PerformanceTestResult:
        """Test performance for a specific provider label.
        Note: The API does not take a provider field in TTSRequest. We still label the run to compare timing.
        """
        start_time = time.perf_counter()
        first_chunk_time = None
        total_duration = 0
        
        try:
            # Prepare request payload (TTSRequest schema)
            payload = {
                "text": text,
                "voice": "af_heart",
                "speed": 1.0,
                "lang": "en-us",
                "format": "wav",
                "stream": True
            }
            
            # Make streaming request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        return PerformanceTestResult(
                            test_name=test_name,
                            provider=provider,
                            text_length=len(text),
                            ttfa_ms=0,
                            total_duration_ms=0,
                            rtf=0,
                            success=False,
                            error_message=f"HTTP {response.status}: {error_text}"
                        )
                    
                    # Process streaming response
                    async for chunk in response.content.iter_chunked(1024):
                        # Record first chunk time
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                            ttfa_ms = (first_chunk_time - start_time) * 1000
                        
                        # Small delay to simulate real-time processing
                        await asyncio.sleep(0.001)
            
            total_duration = (time.perf_counter() - start_time) * 1000
            
            # Calculate RTF estimate from words
            estimated_audio_duration = len(text.split()) * 0.5  # secs
            rtf = total_duration / (estimated_audio_duration * 1000) if estimated_audio_duration > 0 else 0
            
            return PerformanceTestResult(
                test_name=test_name,
                provider=provider,
                text_length=len(text),
                ttfa_ms=ttfa_ms if first_chunk_time else 0,
                total_duration_ms=total_duration,
                rtf=rtf,
                success=True
            )
            
        except Exception as e:
            return PerformanceTestResult(
                test_name=test_name,
                provider=provider,
                text_length=len(text),
                ttfa_ms=0,
                total_duration_ms=0,
                rtf=0,
                success=False,
                error_message=str(e)
            )
    
    async def test_provider_switching(self) -> List[PerformanceTestResult]:
        """Test labeled provider switching performance (labels only)."""
        logger.info("Testing provider switching performance...")
        
        results = []
        text = self.test_texts["medium"]
        
        for provider in self.providers:
            label = provider
            logger.info(f"Testing provider label: {label}")
            result = await self.test_provider_performance(text, label, f"provider_switch_{label}")
            results.append(result)
            
            if result.success:
                logger.info(f"✅ {label}: TTFA {result.ttfa_ms:.1f}ms, RTF {result.rtf:.2f}")
            else:
                logger.error(f"❌ {label}: {result.error_message}")
            
            await asyncio.sleep(0.1)
        
        return results
    
    async def test_ttfa_measurements(self) -> List[PerformanceTestResult]:
        """Test TTFA measurements across different text lengths."""
        logger.info("Testing TTFA measurements for various text lengths...")
        
        results = []
        provider = "default"
        
        for text_type, text in self.test_texts.items():
            logger.info(f"Testing {text_type} text (length: {len(text)}) with {provider}")
            result = await self.test_provider_performance(text, provider, f"ttfa_{text_type}_{provider}")
            results.append(result)
            
            if result.success:
                if result.ttfa_ms <= 800:
                    logger.info(f"✅ {text_type}: TTFA {result.ttfa_ms:.1f}ms <= 800ms target")
                else:
                    logger.warning(f"⚠️ {text_type}: TTFA {result.ttfa_ms:.1f}ms > 800ms target")
            else:
                logger.error(f"❌ {text_type}: Test failed - {result.error_message}")
        
        return results
    
    async def test_rtf_calculations(self) -> List[PerformanceTestResult]:
        """Test RTF calculations and accuracy."""
        logger.info("Testing RTF calculations...")
        
        results = []
        text = self.test_texts["long"]
        
        for provider in self.providers:
            label = provider
            logger.info(f"Testing RTF with provider label {label}")
            result = await self.test_provider_performance(text, label, f"rtf_{label}")
            results.append(result)
            
            if result.success:
                logger.info(f"✅ {label}: RTF {result.rtf:.2f}")
                if result.rtf < 1.0:
                    logger.info("  • Real-time performance achieved")
                elif result.rtf < 2.0:
                    logger.info("  • Acceptable performance (2x real-time)")
                else:
                    logger.warning(f"  • Performance below target ({result.rtf:.2f}x real-time)")
            else:
                logger.error(f"❌ {label}: RTF test failed - {result.error_message}")
        
        return results
    
    async def test_memory_tracking(self) -> List[PerformanceTestResult]:
        """Test memory usage tracking during performance tests."""
        logger.info("Testing memory usage tracking...")
        
        try:
            import psutil
            process = psutil.Process()
            
            results = []
            text = self.test_texts["long"]
            
            for provider in self.providers:
                label = provider
                logger.info(f"Testing memory usage with provider label {label}")
                
                initial_memory = process.memory_info().rss / 1024 / 1024
                result = await self.test_provider_performance(text, label, f"memory_{label}")
                final_memory = process.memory_info().rss / 1024 / 1024
                result.memory_usage_mb = final_memory - initial_memory
                results.append(result)
                
                if result.success:
                    logger.info(f"✅ {label}: Memory delta {result.memory_usage_mb:.1f}MB")
                else:
                    logger.error(f"❌ {label}: Memory test failed - {result.error_message}")
                
                await asyncio.sleep(0.1)
            
            return results
            
        except ImportError:
            logger.warning("psutil not available, skipping memory tracking test")
            return []
    
    async def test_concurrent_provider_performance(self) -> List[PerformanceTestResult]:
        """Test concurrent performance across different provider labels."""
        logger.info("Testing concurrent provider performance...")
        
        results = []
        text = self.test_texts["medium"]
        
        tasks = []
        for provider in self.providers:
            tasks.append(self.test_provider_performance(text, provider, f"concurrent_{provider}"))
        
        concurrent_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(concurrent_results):
            if isinstance(result, Exception):
                results.append(PerformanceTestResult(
                    test_name=f"concurrent_{self.providers[i]}",
                    provider=self.providers[i],
                    text_length=len(text),
                    ttfa_ms=0,
                    total_duration_ms=0,
                    rtf=0,
                    success=False,
                    error_message=str(result)
                ))
            else:
                results.append(result)
        
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive performance metrics test."""
        logger.info("Starting comprehensive performance metrics test...")
        
        start_time = time.perf_counter()
        
        ttfa_results = await self.test_ttfa_measurements()
        rtf_results = await self.test_rtf_calculations()
        provider_switch_results = await self.test_provider_switching()
        memory_results = await self.test_memory_tracking()
        concurrent_results = await self.test_concurrent_provider_performance()
        
        all_results = ttfa_results + rtf_results + provider_switch_results + memory_results + concurrent_results
        
        successful_results = [r for r in all_results if r.success]
        
        if successful_results:
            provider_stats = {}
            for provider in self.providers:
                pr = [r for r in successful_results if r.provider == provider]
                if pr:
                    ttfa_values = [r.ttfa_ms for r in pr if r.ttfa_ms > 0]
                    rtf_values = [r.rtf for r in pr if r.rtf > 0]
                    duration_values = [r.total_duration_ms for r in pr]
                    provider_stats[provider] = {
                        "test_count": len(pr),
                        "ttfa_stats": {
                            "mean": statistics.mean(ttfa_values) if ttfa_values else 0,
                            "median": statistics.median(ttfa_values) if ttfa_values else 0,
                            "min": min(ttfa_values) if ttfa_values else 0,
                            "max": max(ttfa_values) if ttfa_values else 0,
                            "target_met": len([v for v in ttfa_values if v <= 800]) / len(ttfa_values) * 100 if ttfa_values else 0
                        },
                        "rtf_stats": {
                            "mean": statistics.mean(rtf_values) if rtf_values else 0,
                            "median": statistics.median(rtf_values) if rtf_values else 0,
                            "min": min(rtf_values) if rtf_values else 0,
                            "max": max(rtf_values) if rtf_values else 0,
                            "real_time_achieved": len([v for v in rtf_values if v < 1.0]) / len(rtf_values) * 100 if rtf_values else 0
                        },
                        "duration_stats": {
                            "mean": statistics.mean(duration_values) if duration_values else 0,
                            "median": statistics.median(duration_values) if duration_values else 0,
                            "min": min(duration_values) if duration_values else 0,
                            "max": max(duration_values) if duration_values else 0
                        }
                    }
            
            all_ttfa_values = [r.ttfa_ms for r in successful_results if r.ttfa_ms > 0]
            all_rtf_values = [r.rtf for r in successful_results if r.rtf > 0]
            all_duration_values = [r.total_duration_ms for r in successful_results]
            
            overall_stats = {
                "total_tests": len(all_results),
                "successful_tests": len(successful_results),
                "success_rate": len(successful_results) / len(all_results) * 100,
                "overall_ttfa_stats": {
                    "mean": statistics.mean(all_ttfa_values) if all_ttfa_values else 0,
                    "median": statistics.median(all_ttfa_values) if all_ttfa_values else 0,
                    "min": min(all_ttfa_values) if all_ttfa_values else 0,
                    "max": max(all_ttfa_values) if all_ttfa_values else 0,
                    "target_met": len([v for v in all_ttfa_values if v <= 800]) / len(all_ttfa_values) * 100 if all_ttfa_values else 0
                },
                "overall_rtf_stats": {
                    "mean": statistics.mean(all_rtf_values) if all_rtf_values else 0,
                    "median": statistics.median(all_rtf_values) if all_rtf_values else 0,
                    "min": min(all_rtf_values) if all_rtf_values else 0,
                    "max": max(all_rtf_values) if all_rtf_values else 0,
                    "real_time_achieved": len([v for v in all_rtf_values if v < 1.0]) / len(all_rtf_values) * 100 if all_rtf_values else 0
                },
                "overall_duration_stats": {
                    "mean": statistics.mean(all_duration_values) if all_duration_values else 0,
                    "median": statistics.median(all_duration_values) if all_duration_values else 0,
                    "min": min(all_duration_values) if all_duration_values else 0,
                    "max": max(all_duration_values) if all_duration_values else 0
                }
            }
        else:
            provider_stats = {}
            overall_stats = {
                "total_tests": len(all_results),
                "successful_tests": 0,
                "success_rate": 0,
                "error": "No successful tests to analyze"
            }
        
        total_test_time = (time.perf_counter() - start_time) * 1000
        self.test_results = all_results
        
        return {
            "test_summary": {
                "overall": overall_stats,
                "by_provider": provider_stats
            },
            "total_test_time_ms": total_test_time,
            "test_results": [vars(r) for r in all_results]
        }
    
    def print_summary(self, summary: Dict[str, Any]):
        logger.info("=" * 70)
        logger.info("PERFORMANCE METRICS TEST SUMMARY")
        logger.info("=" * 70)
        
        test_summary = summary["test_summary"]
        overall = test_summary["overall"]
        
        logger.info(f"Total Tests: {overall['total_tests']}")
        logger.info(f"Successful Tests: {overall['successful_tests']}")
        logger.info(f"Success Rate: {overall['success_rate']:.1f}%")
        logger.info(f"Total Test Time: {summary['total_test_time_ms']:.1f}ms")
        
        if "overall_ttfa_stats" in overall:
            ttfa = overall["overall_ttfa_stats"]
            logger.info("\nOverall TTFA (Time To First Audio) Statistics:")
            logger.info(f"  Mean: {ttfa['mean']:.1f}ms")
            logger.info(f"  Median: {ttfa['median']:.1f}ms")
            logger.info(f"  Range: {ttfa['min']:.1f}ms - {ttfa['max']:.1f}ms")
            logger.info(f"  Target Met: {ttfa['target_met']:.1f}%")
        
        if "overall_rtf_stats" in overall:
            rtf = overall["overall_rtf_stats"]
            logger.info("\nOverall RTF (Real Time Factor) Statistics:")
            logger.info(f"  Mean: {rtf['mean']:.2f}")
            logger.info(f"  Median: {rtf['median']:.2f}")
            logger.info(f"  Range: {rtf['min']:.2f} - {rtf['max']:.2f}")
            logger.info(f"  Real-time Achieved: {rtf['real_time_achieved']:.1f}%")
        
        if "by_provider" in test_summary:
            logger.info("\nProvider-Specific Performance:")
            for provider, stats in test_summary["by_provider"].items():
                logger.info(f"\n  {provider.upper()}:")
                logger.info(f"    Tests: {stats['test_count']}")
                
                if "ttfa_stats" in stats:
                    ttfa = stats["ttfa_stats"]
                    logger.info(f"    TTFA: {ttfa['mean']:.1f}ms avg, {ttfa['target_met']:.1f}% target met")
                
                if "rtf_stats" in stats:
                    rtf = stats["rtf_stats"]
                    logger.info(f"    RTF: {rtf['mean']:.2f} avg, {rtf['real_time_achieved']:.1f}% real-time")
        
        logger.info("=" * 70)
    
    def save_results(self, summary: Dict[str, Any], output_file: str = "performance_metrics_results.json"):
        try:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Test results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


async def main():
    """Main test execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test performance metrics collection")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for TTS API")
    parser.add_argument("--output", default="performance_metrics_results.json", help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if server is running
    logger.info(f"Testing performance metrics at: {args.url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{args.url}/health") as response:
                if response.status != 200:
                    logger.error(f"Server health check failed: {response.status}")
                    return
                logger.info("✅ Server health check passed")
    except Exception as e:
        logger.error(f"Failed to connect to server: {e}")
        logger.error("Make sure the TTS server is running and accessible")
        return
    
    tester = PerformanceMetricsTester(args.url)
    
    try:
        summary = await tester.run_comprehensive_test()
        tester.print_summary(summary)
        tester.save_results(summary, args.output)
        
        if summary["test_summary"]["overall"]["success_rate"] < 100:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
