#!/usr/bin/env python3
"""
Benchmark script to compare Raycast vs OpenWebUI endpoint performance.
This script measures latency, memory usage, and streaming characteristics.
"""

import asyncio
import aiohttp
import time
import json
import psutil
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkResult:
    endpoint: str
    voice: str
    text_length: int
    total_time_ms: float
    first_byte_time_ms: float
    audio_size_bytes: int
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    streaming: bool
    success: bool
    error: Optional[str] = None

class EndpointBenchmark:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    async def benchmark_raycast_endpoint(self, text: str, voice: str = "bm_fable") -> BenchmarkResult:
        """Benchmark the Raycast endpoint (/v1/audio/speech)"""
        memory_before = self.get_memory_usage()
        
        payload = {
            "text": text,
            "voice": voice,
            "speed": 1.0,
            "stream": True,
            "format": "pcm"
        }
        
        start_time = time.perf_counter()
        first_byte_time = None
        audio_size = 0
        success = False
        error = None
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/audio/speech",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    error = f"HTTP {response.status}: {await response.text()}"
                    return BenchmarkResult(
                        endpoint="raycast",
                        voice=voice,
                        text_length=len(text),
                        total_time_ms=0,
                        first_byte_time_ms=0,
                        audio_size_bytes=0,
                        memory_before_mb=memory_before,
                        memory_after_mb=memory_before,
                        memory_delta_mb=0,
                        streaming=True,
                        success=False,
                        error=error
                    )
                
                # Read streaming response
                async for chunk in response.content.iter_chunked(8192):
                    if first_byte_time is None:
                        first_byte_time = time.perf_counter()
                    audio_size += len(chunk)
                
                success = True
                
        except Exception as e:
            error = str(e)
        
        end_time = time.perf_counter()
        memory_after = self.get_memory_usage()
        
        total_time_ms = (end_time - start_time) * 1000
        first_byte_time_ms = ((first_byte_time - start_time) * 1000) if first_byte_time else 0
        
        return BenchmarkResult(
            endpoint="raycast",
            voice=voice,
            text_length=len(text),
            total_time_ms=total_time_ms,
            first_byte_time_ms=first_byte_time_ms,
            audio_size_bytes=audio_size,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_delta_mb=memory_after - memory_before,
            streaming=True,
            success=success,
            error=error
        )
    
    async def benchmark_openwebui_endpoint(self, text: str, voice: str = "fable") -> BenchmarkResult:
        """Benchmark the OpenWebUI endpoint (/audio/speech)"""
        memory_before = self.get_memory_usage()
        
        payload = {
            "input": text,
            "voice": voice,
            "model": "tts-1",
            "speed": 1.0
        }
        
        start_time = time.perf_counter()
        first_byte_time = None
        audio_size = 0
        success = False
        error = None
        
        try:
            async with self.session.post(
                f"{self.base_url}/audio/speech",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    error = f"HTTP {response.status}: {await response.text()}"
                    return BenchmarkResult(
                        endpoint="openwebui",
                        voice=voice,
                        text_length=len(text),
                        total_time_ms=0,
                        first_byte_time_ms=0,
                        audio_size_bytes=0,
                        memory_before_mb=memory_before,
                        memory_after_mb=memory_before,
                        memory_delta_mb=0,
                        streaming=False,
                        success=False,
                        error=error
                    )
                
                # Read complete response (non-streaming)
                first_byte_time = time.perf_counter()
                audio_data = await response.read()
                audio_size = len(audio_data)
                success = True
                
        except Exception as e:
            error = str(e)
        
        end_time = time.perf_counter()
        memory_after = self.get_memory_usage()
        
        total_time_ms = (end_time - start_time) * 1000
        first_byte_time_ms = ((first_byte_time - start_time) * 1000) if first_byte_time else 0
        
        return BenchmarkResult(
            endpoint="openwebui",
            voice=voice,
            text_length=len(text),
            total_time_ms=total_time_ms,
            first_byte_time_ms=first_byte_time_ms,
            audio_size_bytes=audio_size,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_delta_mb=memory_after - memory_before,
            streaming=False,
            success=success,
            error=error
        )

async def run_benchmark_suite():
    """Run comprehensive benchmark comparing both endpoints"""
    
    test_texts = [
        "Hello world",  # Short text
        "This is a medium length text that should take a few seconds to process and generate audio.",  # Medium text
        "This is a longer text that will be used to test the performance characteristics of both endpoints. It contains multiple sentences and should provide a good comparison of how each endpoint handles longer content. The goal is to see if there are significant differences in processing time, memory usage, and overall efficiency between the Raycast endpoint and the OpenWebUI compatibility endpoint."  # Long text
    ]
    
    results: List[BenchmarkResult] = []
    
    async with EndpointBenchmark() as benchmark:
        
        for i, text in enumerate(test_texts):
            text_type = ["short", "medium", "long"][i]
            logger.info(f"\n=== Benchmarking {text_type} text ({len(text)} chars) ===")
            
            # Test Raycast endpoint
            logger.info("Testing Raycast endpoint...")
            raycast_result = await benchmark.benchmark_raycast_endpoint(text)
            results.append(raycast_result)
            
            # Wait a bit between requests
            await asyncio.sleep(2)
            
            # Test OpenWebUI endpoint
            logger.info("Testing OpenWebUI endpoint...")
            openwebui_result = await benchmark.benchmark_openwebui_endpoint(text)
            results.append(openwebui_result)
            
            # Wait a bit between test sets
            await asyncio.sleep(3)
    
    return results

def analyze_results(results: List[BenchmarkResult]):
    """Analyze and display benchmark results"""
    
    print("\n" + "="*80)
    print("BENCHMARK RESULTS ANALYSIS")
    print("="*80)
    
    # Group results by endpoint
    raycast_results = [r for r in results if r.endpoint == "raycast"]
    openwebui_results = [r for r in results if r.endpoint == "openwebui"]
    
    # Success rates
    raycast_success = sum(1 for r in raycast_results if r.success)
    openwebui_success = sum(1 for r in openwebui_results if r.success)
    
    print(f"\nSUCCESS RATES:")
    print(f"Raycast:  {raycast_success}/{len(raycast_results)} ({raycast_success/len(raycast_results)*100:.1f}%)")
    print(f"OpenWebUI: {openwebui_success}/{len(openwebui_results)} ({openwebui_success/len(openwebui_results)*100:.1f}%)")
    
    # Performance comparison
    if raycast_success > 0 and openwebui_success > 0:
        successful_raycast = [r for r in raycast_results if r.success]
        successful_openwebui = [r for r in openwebui_results if r.success]
        
        print(f"\nPERFORMANCE METRICS:")
        print(f"{'Metric':<25} {'Raycast':<15} {'OpenWebUI':<15} {'Difference':<15}")
        print("-" * 70)
        
        # Total time
        raycast_total_avg = statistics.mean([r.total_time_ms for r in successful_raycast])
        openwebui_total_avg = statistics.mean([r.total_time_ms for r in successful_openwebui])
        total_diff = ((openwebui_total_avg - raycast_total_avg) / raycast_total_avg) * 100
        
        print(f"{'Total Time (ms)':<25} {raycast_total_avg:<15.1f} {openwebui_total_avg:<15.1f} {total_diff:+.1f}%")
        
        # First byte time
        raycast_fb_avg = statistics.mean([r.first_byte_time_ms for r in successful_raycast])
        openwebui_fb_avg = statistics.mean([r.first_byte_time_ms for r in successful_openwebui])
        fb_diff = ((openwebui_fb_avg - raycast_fb_avg) / raycast_fb_avg) * 100
        
        print(f"{'First Byte Time (ms)':<25} {raycast_fb_avg:<15.1f} {openwebui_fb_avg:<15.1f} {fb_diff:+.1f}%")
        
        # Memory usage
        raycast_mem_avg = statistics.mean([r.memory_delta_mb for r in successful_raycast])
        openwebui_mem_avg = statistics.mean([r.memory_delta_mb for r in successful_openwebui])
        
        print(f"{'Memory Delta (MB)':<25} {raycast_mem_avg:<15.1f} {openwebui_mem_avg:<15.1f}")
        
        # Audio size
        raycast_size_avg = statistics.mean([r.audio_size_bytes for r in successful_raycast])
        openwebui_size_avg = statistics.mean([r.audio_size_bytes for r in successful_openwebui])
        
        print(f"{'Audio Size (bytes)':<25} {raycast_size_avg:<15.0f} {openwebui_size_avg:<15.0f}")
    
    # Detailed results
    print(f"\nDETAILED RESULTS:")
    print(f"{'Endpoint':<12} {'Text Len':<8} {'Total(ms)':<10} {'First(ms)':<10} {'Audio(KB)':<10} {'Mem(MB)':<8} {'Success':<8}")
    print("-" * 80)
    
    for result in results:
        success_str = "✓" if result.success else "✗"
        audio_kb = result.audio_size_bytes / 1024
        
        print(f"{result.endpoint:<12} {result.text_length:<8} {result.total_time_ms:<10.1f} "
              f"{result.first_byte_time_ms:<10.1f} {audio_kb:<10.1f} {result.memory_delta_mb:<8.1f} {success_str:<8}")
        
        if result.error:
            print(f"  Error: {result.error}")
    
    # Errors
    errors = [r for r in results if not r.success]
    if errors:
        print(f"\nERRORS:")
        for error in errors:
            print(f"  {error.endpoint}: {error.error}")

async def main():
    """Main benchmark execution"""
    logger.info("Starting endpoint benchmark comparison...")
    
    try:
        results = await run_benchmark_suite()
        analyze_results(results)
        
        # Save results to file
        with open("benchmark_results.json", "w") as f:
            json.dump([
                {
                    "endpoint": r.endpoint,
                    "voice": r.voice,
                    "text_length": r.text_length,
                    "total_time_ms": r.total_time_ms,
                    "first_byte_time_ms": r.first_byte_time_ms,
                    "audio_size_bytes": r.audio_size_bytes,
                    "memory_before_mb": r.memory_before_mb,
                    "memory_after_mb": r.memory_after_mb,
                    "memory_delta_mb": r.memory_delta_mb,
                    "streaming": r.streaming,
                    "success": r.success,
                    "error": r.error
                }
                for r in results
            ], f, indent=2)
        
        logger.info("Benchmark results saved to benchmark_results.json")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
