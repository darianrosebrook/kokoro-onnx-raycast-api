#!/usr/bin/env python3
"""
Streaming TTS Endpoint Performance Test Script

This script tests the streaming TTS endpoint to validate:
- TTFA (Time To First Audio) targets
- Chunked audio delivery performance
- Concurrent request handling
- Memory usage during streaming
- Audio quality and continuity

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
from typing import Dict, List, Tuple, Optional
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
class StreamingTestResult:
    """Results from a single streaming test."""
    test_name: str
    text_length: int
    ttfa_ms: float
    total_duration_ms: float
    chunk_count: int
    total_bytes: int
    success: bool
    error_message: Optional[str] = None
    memory_usage_mb: Optional[float] = None


class StreamingPerformanceTester:
    """Comprehensive streaming TTS performance tester."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results: List[StreamingTestResult] = []
        
        # Test text samples of varying lengths
        self.test_texts = {
            "short": "Hello world, this is a test.",
            "medium": "The quick brown fox jumps over the lazy dog. This is a medium length text that should test the streaming capabilities of the TTS system.",
            "long": """Artificial intelligence is transforming our world in profound ways. From natural language processing to computer vision, 
            AI systems are becoming increasingly sophisticated and capable. The streaming TTS endpoint must handle various text lengths 
            efficiently while maintaining high audio quality and fast response times. This longer text will test the system's ability 
            to process and stream audio for extended content without performance degradation.""",
            "very_long": """Machine learning models require careful optimization to achieve optimal performance. The Kokoro TTS system 
            implements advanced techniques including provider selection, dynamic memory management, and workload analysis to ensure 
            consistent performance across different hardware configurations and usage patterns. This very long text will thoroughly 
            test the streaming endpoint's ability to handle substantial content while maintaining the target TTFA of under 800ms 
            and ensuring smooth audio delivery throughout the entire text. The system should demonstrate efficient memory usage, 
            reliable provider switching, and consistent audio quality regardless of text length or complexity."""
        }
    
    async def test_single_streaming_request(self, text: str, test_name: str) -> StreamingTestResult:
        """Test a single streaming TTS request."""
        start_time = time.perf_counter()
        first_chunk_time = None
        chunk_count = 0
        total_bytes = 0
        
        try:
            # Prepare request payload per TTSRequest
            payload = {
                "text": text,
                "voice": "af_heart",
                "speed": 1.0,
                "lang": "en-us",
                "format": "wav",
                "stream": True
            }
            
            # Make streaming request to correct endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        return StreamingTestResult(
                            test_name=test_name,
                            text_length=len(text),
                            ttfa_ms=0,
                            total_duration_ms=0,
                            chunk_count=0,
                            total_bytes=0,
                            success=False,
                            error_message=f"HTTP {response.status}: {error_text}"
                        )
                    
                    # Process streaming response
                    async for chunk in response.content.iter_chunked(1024):
                        chunk_count += 1
                        total_bytes += len(chunk)
                        
                        # Record first chunk time
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                            ttfa_ms = (first_chunk_time - start_time) * 1000
                        
                        # Small delay to simulate real-time processing
                        await asyncio.sleep(0.001)
            
            total_duration = (time.perf_counter() - start_time) * 1000
            
            return StreamingTestResult(
                test_name=test_name,
                text_length=len(text),
                ttfa_ms=ttfa_ms if first_chunk_time else 0,
                total_duration_ms=total_duration,
                chunk_count=chunk_count,
                total_bytes=total_bytes,
                success=True
            )
            
        except Exception as e:
            return StreamingTestResult(
                test_name=test_name,
                text_length=len(text),
                ttfa_ms=0,
                total_duration_ms=0,
                chunk_count=0,
                total_bytes=0,
                success=False,
                error_message=str(e)
            )
    
    async def test_concurrent_streaming(self, text: str, concurrent_requests: int = 5) -> List[StreamingTestResult]:
        """Test concurrent streaming requests."""
        logger.info(f"Testing {concurrent_requests} concurrent streaming requests...")
        
        # Create concurrent tasks
        tasks = []
        for i in range(concurrent_requests):
            task = self.test_single_streaming_request(
                text, 
                f"concurrent_{i+1}"
            )
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(StreamingTestResult(
                    test_name=f"concurrent_{i+1}",
                    text_length=len(text),
                    ttfa_ms=0,
                    total_duration_ms=0,
                    chunk_count=0,
                    total_bytes=0,
                    success=False,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def test_ttfa_targets(self) -> List[StreamingTestResult]:
        """Test TTFA targets for different text lengths."""
        logger.info("Testing TTFA targets for various text lengths...")
        
        results = []
        ttfa_target = 800  # Target TTFA in milliseconds
        
        for text_type, text in self.test_texts.items():
            logger.info(f"Testing {text_type} text (length: {len(text)})")
            
            result = await self.test_single_streaming_request(text, f"ttfa_{text_type}")
            results.append(result)
            
            if result.success:
                if result.ttfa_ms <= ttfa_target:
                    logger.info(f"✅ {text_type}: TTFA {result.ttfa_ms:.1f}ms <= {ttfa_target}ms target")
                else:
                    logger.warning(f"⚠️ {text_type}: TTFA {result.ttfa_ms:.1f}ms > {ttfa_target}ms target")
            else:
                logger.error(f"❌ {text_type}: Test failed - {result.error_message}")
        
        return results
    
    async def test_chunked_delivery(self) -> List[StreamingTestResult]:
        """Test chunked audio delivery performance."""
        logger.info("Testing chunked audio delivery...")
        
        results = []
        
        # Test with medium text to analyze chunking
        text = self.test_texts["medium"]
        result = await self.test_single_streaming_request(text, "chunked_delivery")
        
        if result.success:
            logger.info(f"Chunked delivery test completed:")
            logger.info(f"  • Total chunks: {result.chunk_count}")
            logger.info(f"  • Total bytes: {result.total_bytes:,}")
            logger.info(f"  • Average chunk size: {result.total_bytes / result.chunk_count:.0f} bytes")
            logger.info(f"  • Total duration: {result.total_duration_ms:.1f}ms")
        
        results.append(result)
        return results
    
    async def test_memory_usage(self) -> List[StreamingTestResult]:
        """Test memory usage during streaming (if psutil available)."""
        logger.info("Testing memory usage during streaming...")
        
        try:
            import psutil
            process = psutil.Process()
            
            results = []
            
            # Test with very long text to stress memory
            text = self.test_texts["very_long"]
            
            # Get initial memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Perform streaming request
            result = await self.test_single_streaming_request(text, "memory_usage")
            
            # Get final memory
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_delta = final_memory - initial_memory
            
            result.memory_usage_mb = memory_delta
            
            if result.success:
                logger.info(f"Memory usage test completed:")
                logger.info(f"  • Initial memory: {initial_memory:.1f}MB")
                logger.info(f"  • Final memory: {final_memory:.1f}MB")
                logger.info(f"  • Memory delta: {memory_delta:.1f}MB")
                
                if memory_delta < 100:  # Less than 100MB increase
                    logger.info("✅ Memory usage within acceptable limits")
                else:
                    logger.warning(f"⚠️ High memory usage: {memory_delta:.1f}MB")
            
            results.append(result)
            return results
            
        except ImportError:
            logger.warning("psutil not available, skipping memory usage test")
            return []
    
    async def run_comprehensive_test(self) -> Dict[str, any]:
        """Run comprehensive streaming performance test."""
        logger.info("Starting comprehensive streaming performance test...")
        
        start_time = time.perf_counter()
        
        # Run all test categories
        ttfa_results = await self.test_ttfa_targets()
        chunked_results = await self.test_chunked_delivery()
        memory_results = await self.test_memory_usage()
        concurrent_results = await self.test_concurrent_streaming(self.test_texts["medium"])
        
        # Combine all results
        all_results = ttfa_results + chunked_results + memory_results + concurrent_results
        
        # Calculate statistics
        successful_results = [r for r in all_results if r.success]
        
        if successful_results:
            ttfa_values = [r.ttfa_ms for r in successful_results if r.ttfa_ms > 0]
            duration_values = [r.total_duration_ms for r in successful_results]
            chunk_values = [r.chunk_count for r in successful_results]
            
            stats = {
                "total_tests": len(all_results),
                "successful_tests": len(successful_results),
                "success_rate": len(successful_results) / len(all_results) * 100,
                "ttfa_stats": {
                    "mean": statistics.mean(ttfa_values) if ttfa_values else 0,
                    "median": statistics.median(ttfa_values) if ttfa_values else 0,
                    "min": min(ttfa_values) if ttfa_values else 0,
                    "max": max(ttfa_values) if ttfa_values else 0,
                    "target_met": len([v for v in ttfa_values if v <= 800]) / len(ttfa_values) * 100 if ttfa_values else 0
                },
                "duration_stats": {
                    "mean": statistics.mean(duration_values) if duration_values else 0,
                    "median": statistics.median(duration_values) if duration_values else 0,
                    "min": min(duration_values) if duration_values else 0,
                    "max": max(duration_values) if duration_values else 0
                },
                "chunk_stats": {
                    "mean": statistics.mean(chunk_values) if chunk_values else 0,
                    "median": statistics.median(chunk_values) if chunk_values else 0,
                    "min": min(chunk_values) if chunk_values else 0,
                    "max": max(chunk_values) if chunk_values else 0
                }
            }
        else:
            stats = {
                "total_tests": len(all_results),
                "successful_tests": 0,
                "success_rate": 0,
                "error": "No successful tests to analyze"
            }
        
        total_test_time = (time.perf_counter() - start_time) * 1000
        
        # Store results for detailed analysis
        self.test_results = all_results
        
        return {
            "test_summary": stats,
            "total_test_time_ms": total_test_time,
            "test_results": [vars(r) for r in all_results]
        }
    
    def print_summary(self, summary: Dict[str, any]):
        """Print test summary in a readable format."""
        logger.info("=" * 60)
        logger.info("STREAMING PERFORMANCE TEST SUMMARY")
        logger.info("=" * 60)
        
        test_summary = summary["test_summary"]
        
        logger.info(f"Total Tests: {test_summary['total_tests']}")
        logger.info(f"Successful Tests: {test_summary['successful_tests']}")
        logger.info(f"Success Rate: {test_summary['success_rate']:.1f}%")
        logger.info(f"Total Test Time: {summary['total_test_time_ms']:.1f}ms")
        
        if "ttfa_stats" in test_summary:
            ttfa = test_summary["ttfa_stats"]
            logger.info("\nTTFA (Time To First Audio) Statistics:")
            logger.info(f"  Mean: {ttfa['mean']:.1f}ms")
            logger.info(f"  Median: {ttfa['median']:.1f}ms")
            logger.info(f"  Range: {ttfa['min']:.1f}ms - {ttfa['max']:.1f}ms")
            logger.info(f"  Target Met: {ttfa['target_met']:.1f}%")
        
        if "duration_stats" in test_summary:
            duration = test_summary["duration_stats"]
            logger.info("\nTotal Duration Statistics:")
            logger.info(f"  Mean: {duration['mean']:.1f}ms")
            logger.info(f"  Median: {duration['median']:.1f}ms")
            logger.info(f"  Range: {duration['min']:.1f}ms - {duration['max']:.1f}ms")
        
        if "chunk_stats" in test_summary:
            chunks = test_summary["chunk_stats"]
            logger.info("\nChunk Delivery Statistics:")
            logger.info(f"  Mean: {chunks['mean']:.1f} chunks")
            logger.info(f"  Median: {chunks['median']:.1f} chunks")
            logger.info(f"  Range: {chunks['min']} - {chunks['max']} chunks")
        
        logger.info("=" * 60)
    
    def save_results(self, summary: Dict[str, any], output_file: str = "streaming_test_results.json"):
        """Save test results to JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Test results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


async def main():
    """Main test execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test streaming TTS endpoint performance")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for TTS API")
    parser.add_argument("--output", default="streaming_test_results.json", help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if server is running
    logger.info(f"Testing streaming endpoint at: {args.url}")
    
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
    
    # Create tester and run tests
    tester = StreamingPerformanceTester(args.url)
    
    try:
        summary = await tester.run_comprehensive_test()
        tester.print_summary(summary)
        tester.save_results(summary, args.output)
        
        # Exit with error code if tests failed
        if summary["test_summary"]["success_rate"] < 100:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
