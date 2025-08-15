#!/usr/bin/env python3
"""
TTFA (Time to First Audio) Benchmark Script

This script tests the TTFA performance improvements by making requests
to the TTS API and measuring time to first audio chunk delivery.

Usage:
    python scripts/ttfa_benchmark.py
    python scripts/ttfa_benchmark.py --server http://localhost:8000 --requests 10

@author: @darianrosebrook
@date: 2025-08-15
@version: 1.0.0
"""

import asyncio
import aiohttp
import time
import statistics
import json
import argparse
from typing import List, Dict, Any
from datetime import datetime


class TTFABenchmark:
    """TTFA benchmarking system"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.results: List[Dict[str, Any]] = []
        
        # Test cases of varying complexity
        self.test_cases = [
            {
                "name": "Short Text",
                "text": "Hello world",
                "expected_ttfa": 400,  # ms
                "voice": "af_heart"
            },
            {
                "name": "Medium Text", 
                "text": "This is a medium length sentence that should test our TTFA optimization for typical usage scenarios.",
                "expected_ttfa": 600,  # ms
                "voice": "af_heart"
            },
            {
                "name": "Long Text",
                "text": "This is a much longer piece of text that will test our streaming optimization under more demanding conditions. It includes multiple sentences and should thoroughly exercise the segment processing pipeline to ensure that our TTFA improvements work even with complex text inputs.",
                "expected_ttfa": 800,  # ms
                "voice": "af_heart"
            },
            {
                "name": "Complex Text",
                "text": "Testing complex scenarios: numbers like 12,345 and symbols @#$% with various punctuation! Does it handle URLs like https://example.com? And what about abbreviations like Dr. Smith or Mr. Jones?",
                "expected_ttfa": 800,  # ms
                "voice": "af_heart"
            }
        ]
    
    async def benchmark_single_request(self, session: aiohttp.ClientSession, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Benchmark a single TTS request"""
        
        request_data = {
            "text": test_case["text"],
            "voice": test_case["voice"],
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "wav"
        }
        
        start_time = time.perf_counter()
        first_chunk_time = None
        total_chunks = 0
        total_bytes = 0
        
        try:
            async with session.post(
                f"{self.server_url}/v1/audio/speech",
                json=request_data,
                headers={"Content-Type": "application/json", "Accept": "audio/wav"}
            ) as response:
                
                if response.status != 200:
                    return {
                        "test_case": test_case["name"],
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}",
                        "ttfa_ms": None
                    }
                
                async for chunk in response.content.iter_chunked(1024):
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttfa_ms = (first_chunk_time - start_time) * 1000
                    
                    total_chunks += 1
                    total_bytes += len(chunk)
                
                total_time = time.perf_counter() - start_time
                
                return {
                    "test_case": test_case["name"],
                    "success": True,
                    "text_length": len(test_case["text"]),
                    "expected_ttfa_ms": test_case["expected_ttfa"],
                    "actual_ttfa_ms": ttfa_ms,
                    "target_achieved": ttfa_ms <= test_case["expected_ttfa"],
                    "total_time_ms": total_time * 1000,
                    "total_chunks": total_chunks,
                    "total_bytes": total_bytes,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "test_case": test_case["name"],
                "success": False,
                "error": str(e),
                "ttfa_ms": None
            }
    
    async def run_benchmark(self, num_iterations: int = 5) -> Dict[str, Any]:
        """Run comprehensive TTFA benchmark"""
        
        print(f"🚀 Starting TTFA Benchmark - {num_iterations} iterations per test case")
        print(f"📡 Server: {self.server_url}")
        print("=" * 80)
        
        async with aiohttp.ClientSession() as session:
            all_results = []
            
            for test_case in self.test_cases:
                print(f"\n📝 Testing: {test_case['name']} (Target: {test_case['expected_ttfa']}ms)")
                print(f"   Text: '{test_case['text'][:50]}{'...' if len(test_case['text']) > 50 else ''}'")
                
                case_results = []
                
                for iteration in range(num_iterations):
                    print(f"   Iteration {iteration + 1}/{num_iterations}...", end=" ")
                    
                    result = await self.benchmark_single_request(session, test_case)
                    case_results.append(result)
                    all_results.append(result)
                    
                    if result["success"]:
                        ttfa = result["actual_ttfa_ms"]
                        status = "✅" if result["target_achieved"] else "❌"
                        print(f"{status} TTFA: {ttfa:.1f}ms")
                    else:
                        print(f"❌ Error: {result['error']}")
                
                # Calculate statistics for this test case
                successful_results = [r for r in case_results if r["success"]]
                if successful_results:
                    ttfa_values = [r["actual_ttfa_ms"] for r in successful_results]
                    target_achieved_count = sum(1 for r in successful_results if r["target_achieved"])
                    
                    print(f"   📊 Results: {len(successful_results)}/{num_iterations} successful")
                    print(f"   📈 TTFA: min={min(ttfa_values):.1f}ms, avg={statistics.mean(ttfa_values):.1f}ms, max={max(ttfa_values):.1f}ms")
                    print(f"   🎯 Target Achievement: {target_achieved_count}/{len(successful_results)} ({target_achieved_count/len(successful_results)*100:.1f}%)")
        
        return self.analyze_results(all_results)
    
    def analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze benchmark results and generate report"""
        
        successful_results = [r for r in results if r["success"]]
        
        if not successful_results:
            return {
                "summary": "No successful requests",
                "total_requests": len(results),
                "successful_requests": 0,
                "overall_success_rate": 0.0
            }
        
        # Calculate overall statistics
        ttfa_values = [r["actual_ttfa_ms"] for r in successful_results]
        target_achieved_count = sum(1 for r in successful_results if r["target_achieved"])
        
        by_test_case = {}
        for result in successful_results:
            case_name = result["test_case"]
            if case_name not in by_test_case:
                by_test_case[case_name] = []
            by_test_case[case_name].append(result)
        
        case_summaries = {}
        for case_name, case_results in by_test_case.items():
            case_ttfa_values = [r["actual_ttfa_ms"] for r in case_results]
            case_target_achieved = sum(1 for r in case_results if r["target_achieved"])
            
            case_summaries[case_name] = {
                "iterations": len(case_results),
                "ttfa_stats": {
                    "min_ms": min(case_ttfa_values),
                    "avg_ms": statistics.mean(case_ttfa_values),
                    "max_ms": max(case_ttfa_values),
                    "median_ms": statistics.median(case_ttfa_values),
                    "std_dev_ms": statistics.stdev(case_ttfa_values) if len(case_ttfa_values) > 1 else 0
                },
                "target_achievement": {
                    "count": case_target_achieved,
                    "total": len(case_results),
                    "percentage": (case_target_achieved / len(case_results)) * 100
                }
            }
        
        overall_analysis = {
            "summary": {
                "total_requests": len(results),
                "successful_requests": len(successful_results),
                "failed_requests": len(results) - len(successful_results),
                "overall_success_rate": (len(successful_results) / len(results)) * 100
            },
            "ttfa_performance": {
                "overall_stats": {
                    "min_ms": min(ttfa_values),
                    "avg_ms": statistics.mean(ttfa_values),
                    "max_ms": max(ttfa_values),
                    "median_ms": statistics.median(ttfa_values),
                    "std_dev_ms": statistics.stdev(ttfa_values) if len(ttfa_values) > 1 else 0
                },
                "target_achievement": {
                    "count": target_achieved_count,
                    "total": len(successful_results),
                    "percentage": (target_achieved_count / len(successful_results)) * 100
                }
            },
            "by_test_case": case_summaries,
            "recommendations": self.generate_recommendations(successful_results)
        }
        
        return overall_analysis
    
    def generate_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate optimization recommendations based on results"""
        recommendations = []
        
        ttfa_values = [r["actual_ttfa_ms"] for r in results]
        avg_ttfa = statistics.mean(ttfa_values)
        max_ttfa = max(ttfa_values)
        target_achievement_rate = sum(1 for r in results if r["target_achieved"]) / len(results) * 100
        
        if target_achievement_rate < 80:
            recommendations.append(f"⚠️ Target achievement rate is only {target_achievement_rate:.1f}% - consider aggressive optimization")
        
        if avg_ttfa > 800:
            recommendations.append(f"⚠️ Average TTFA ({avg_ttfa:.1f}ms) exceeds target - review session routing")
        
        if max_ttfa > 2000:
            recommendations.append(f"🚨 Maximum TTFA ({max_ttfa:.1f}ms) is critical - investigate bottlenecks")
        
        if target_achievement_rate >= 90 and avg_ttfa <= 600:
            recommendations.append("✅ Excellent TTFA performance - targets consistently achieved")
        
        return recommendations
    
    def print_report(self, analysis: Dict[str, Any]):
        """Print comprehensive benchmark report"""
        
        print("\n" + "=" * 80)
        print("📊 TTFA BENCHMARK REPORT")
        print("=" * 80)
        
        summary = analysis["summary"]
        print(f"\n📈 OVERALL SUMMARY:")
        print(f"   Total Requests: {summary['total_requests']}")
        print(f"   Successful: {summary['successful_requests']} ({summary['overall_success_rate']:.1f}%)")
        print(f"   Failed: {summary['failed_requests']}")
        
        if "ttfa_performance" in analysis:
            perf = analysis["ttfa_performance"]
            stats = perf["overall_stats"]
            target = perf["target_achievement"]
            
            print(f"\n⏱️ TTFA PERFORMANCE:")
            print(f"   Average: {stats['avg_ms']:.1f}ms")
            print(f"   Range: {stats['min_ms']:.1f}ms - {stats['max_ms']:.1f}ms")
            print(f"   Median: {stats['median_ms']:.1f}ms")
            print(f"   Std Dev: {stats['std_dev_ms']:.1f}ms")
            print(f"   Target Achievement: {target['count']}/{target['total']} ({target['percentage']:.1f}%)")
        
        if "by_test_case" in analysis:
            print(f"\n📝 BY TEST CASE:")
            for case_name, case_data in analysis["by_test_case"].items():
                stats = case_data["ttfa_stats"]
                target = case_data["target_achievement"]
                print(f"   {case_name}:")
                print(f"     TTFA: {stats['avg_ms']:.1f}ms avg ({stats['min_ms']:.1f}-{stats['max_ms']:.1f}ms)")
                print(f"     Target: {target['count']}/{target['total']} ({target['percentage']:.1f}%)")
        
        if "recommendations" in analysis and analysis["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in analysis["recommendations"]:
                print(f"   {rec}")
        
        print("\n" + "=" * 80)


async def main():
    """Main benchmark function"""
    parser = argparse.ArgumentParser(description="TTFA Benchmark for TTS API")
    parser.add_argument("--server", default="http://localhost:8000", help="TTS server URL")
    parser.add_argument("--requests", type=int, default=5, help="Number of requests per test case")
    parser.add_argument("--output", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    benchmark = TTFABenchmark(args.server)
    
    try:
        analysis = await benchmark.run_benchmark(args.requests)
        benchmark.print_report(analysis)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(analysis, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")
            
    except KeyboardInterrupt:
        print("\n⏹️ Benchmark interrupted by user")
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
