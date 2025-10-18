#!/usr/bin/env python3
"""
Performance benchmark script for Kokoro TTS system
Tests latency, startup time, and identifies optimization opportunities
"""

import time
import requests
import json
import sys
import os
from typing import Dict, List, Any

class PerformanceBenchmark:
    """Comprehensive performance benchmarking for TTS system"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
        
    def test_health(self) -> bool:
        """Test if server is healthy and model is ready"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Server health: {health_data}")
                return health_data.get("model_ready", False)
            else:
                print(f"❌ Server health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Server health check error: {e}")
            return False
    
    def benchmark_ttfa(self, text: str, voice: str = "af_heart", trials: int = 5) -> Dict[str, Any]:
        """Benchmark Time To First Audio (TTFA)"""
        print(f"\n🎯 Benchmarking TTFA for text: '{text[:30]}...'")
        
        ttfa_times = []
        total_times = []
        
        for i in range(trials):
            print(f"  Trial {i+1}/{trials}...", end=" ")
            
            start_time = time.perf_counter()
            
            try:
                response = requests.post(
                    f"{self.base_url}/audio/speech",
                    json={
                        "input": text,
                        "voice": voice,
                        "speed": 1.0
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Calculate TTFA (time to first byte)
                    ttfa_time = time.perf_counter() - start_time
                    ttfa_times.append(ttfa_time * 1000)  # Convert to ms
                    
                    # Calculate total time
                    total_time = time.perf_counter() - start_time
                    total_times.append(total_time * 1000)
                    
                    audio_size = len(response.content)
                    print(f"TTFA: {ttfa_time*1000:.1f}ms, Total: {total_time*1000:.1f}ms, Size: {audio_size} bytes")
                else:
                    print(f"❌ Failed: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
        
        if ttfa_times:
            results = {
                "text_length": len(text),
                "voice": voice,
                "trials": len(ttfa_times),
                "ttfa_ms": {
                    "min": min(ttfa_times),
                    "max": max(ttfa_times),
                    "avg": sum(ttfa_times) / len(ttfa_times),
                    "p95": sorted(ttfa_times)[int(len(ttfa_times) * 0.95)] if len(ttfa_times) > 1 else ttfa_times[0]
                },
                "total_ms": {
                    "min": min(total_times),
                    "max": max(total_times),
                    "avg": sum(total_times) / len(total_times),
                    "p95": sorted(total_times)[int(len(total_times) * 0.95)] if len(total_times) > 1 else total_times[0]
                }
            }
            
            print(f"\n📊 TTFA Results:")
            print(f"  Average TTFA: {results['ttfa_ms']['avg']:.1f}ms")
            print(f"  P95 TTFA: {results['ttfa_ms']['p95']:.1f}ms")
            print(f"  Average Total: {results['total_ms']['avg']:.1f}ms")
            print(f"  P95 Total: {results['total_ms']['p95']:.1f}ms")
            
            return results
        else:
            return {"error": "No successful trials"}
    
    def benchmark_streaming(self, text: str, voice: str = "af_heart") -> Dict[str, Any]:
        """Benchmark streaming performance"""
        print(f"\n🌊 Benchmarking streaming for text: '{text[:30]}...'")
        
        try:
            start_time = time.perf_counter()
            
            response = requests.post(
                f"{self.base_url}/audio/speech",
                json={
                    "input": text,
                    "voice": voice,
                    "speed": 1.0,
                    "stream": True
                },
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                first_chunk_time = None
                chunk_times = []
                total_size = 0
                
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        current_time = time.perf_counter()
                        if first_chunk_time is None:
                            first_chunk_time = current_time - start_time
                        chunk_times.append(current_time - start_time)
                        total_size += len(chunk)
                
                total_time = time.perf_counter() - start_time
                
                results = {
                    "text_length": len(text),
                    "voice": voice,
                    "first_chunk_ms": first_chunk_time * 1000 if first_chunk_time else None,
                    "total_time_ms": total_time * 1000,
                    "chunk_count": len(chunk_times),
                    "total_size_bytes": total_size,
                    "avg_chunk_size": total_size / len(chunk_times) if chunk_times else 0
                }
                
                print(f"📊 Streaming Results:")
                print(f"  First chunk: {results['first_chunk_ms']:.1f}ms")
                print(f"  Total time: {results['total_time_ms']:.1f}ms")
                print(f"  Chunks: {results['chunk_count']}")
                print(f"  Total size: {results['total_size_bytes']} bytes")
                print(f"  Avg chunk size: {results['avg_chunk_size']:.0f} bytes")
                
                return results
            else:
                print(f"❌ Streaming failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"❌ Streaming error: {e}")
            return {"error": str(e)}
    
    def benchmark_different_text_lengths(self) -> Dict[str, Any]:
        """Benchmark performance across different text lengths"""
        print(f"\n📏 Benchmarking different text lengths...")
        
        test_cases = [
            ("Short", "Hello world!", 12),
            ("Medium", "This is a medium-length sentence for testing TTS performance characteristics and latency.", 95),
            ("Long", "This is a much longer text that will test the system's ability to handle extended content. It includes multiple sentences and should provide a good test of the streaming capabilities and overall performance under more realistic conditions. The system should maintain good responsiveness even with longer content.", 300),
            ("Very Long", "We identified 7 core capabilities, supported by 35 implementations across our product units. For example, Summarization alone has 10 separate implementations distributed across product units, with some leveraging the Insights Engine capabilities and others developing bespoke solutions. This analysis underscores both the duplication across business units and the opportunity for consolidation. The performance characteristics of longer text processing are critical for real-world applications where users may need to synthesize substantial amounts of content efficiently.", 500)
        ]
        
        results = {}
        
        for name, text, length in test_cases:
            print(f"\n--- {name} Text ({length} chars) ---")
            ttfa_result = self.benchmark_ttfa(text, trials=3)
            streaming_result = self.benchmark_streaming(text)
            
            results[name.lower().replace(" ", "_")] = {
                "text_length": length,
                "ttfa": ttfa_result,
                "streaming": streaming_result
            }
        
        return results
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information and configuration"""
        print(f"\n🔧 Getting system information...")
        
        try:
            # Try to get system info from the API
            response = requests.get(f"{self.base_url}/system/info", timeout=5)
            if response.status_code == 200:
                system_info = response.json()
                print(f"✅ System info retrieved")
                return system_info
            else:
                print(f"⚠️ System info endpoint not available: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"⚠️ System info error: {e}")
            return {"error": str(e)}
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive performance benchmark"""
        print("🚀 Starting comprehensive performance benchmark...")
        print("=" * 60)
        
        # Check server health
        if not self.test_health():
            print("❌ Server not ready, aborting benchmark")
            return {"error": "Server not ready"}
        
        # Get system info
        system_info = self.get_system_info()
        
        # Benchmark different text lengths
        text_length_results = self.benchmark_different_text_lengths()
        
        # Compile results
        results = {
            "timestamp": time.time(),
            "system_info": system_info,
            "text_length_analysis": text_length_results,
            "summary": self._generate_summary(text_length_results)
        }
        
        print("\n" + "=" * 60)
        print("📋 BENCHMARK SUMMARY")
        print("=" * 60)
        self._print_summary(results["summary"])
        
        return results
    
    def _generate_summary(self, text_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate performance summary"""
        summary = {
            "performance_trends": {},
            "optimization_opportunities": [],
            "recommendations": []
        }
        
        # Analyze TTFA trends
        ttfa_trends = []
        for name, data in text_results.items():
            if "ttfa" in data and "ttfa_ms" in data["ttfa"]:
                ttfa_trends.append({
                    "length": data["text_length"],
                    "avg_ttfa": data["ttfa"]["ttfa_ms"]["avg"],
                    "p95_ttfa": data["ttfa"]["ttfa_ms"]["p95"]
                })
        
        if ttfa_trends:
            summary["performance_trends"]["ttfa"] = ttfa_trends
            
            # Check for performance degradation
            if len(ttfa_trends) >= 2:
                short_ttfa = ttfa_trends[0]["avg_ttfa"]
                long_ttfa = ttfa_trends[-1]["avg_ttfa"]
                degradation = (long_ttfa - short_ttfa) / short_ttfa * 100
                
                if degradation > 50:
                    summary["optimization_opportunities"].append(
                        f"High TTFA degradation with long text: {degradation:.1f}% increase"
                    )
                    summary["recommendations"].append(
                        "Consider implementing text segmentation optimization for long text"
                    )
        
        # Check TTFA targets
        for trend in ttfa_trends:
            if trend["p95_ttfa"] > 500:  # 500ms target
                summary["optimization_opportunities"].append(
                    f"TTFA exceeds 500ms target for {trend['length']} char text: {trend['p95_ttfa']:.1f}ms"
                )
                summary["recommendations"].append(
                    "Optimize model initialization and first-chunk generation"
                )
        
        return summary
    
    def _print_summary(self, summary: Dict[str, Any]):
        """Print benchmark summary"""
        if "performance_trends" in summary and "ttfa" in summary["performance_trends"]:
            print("\n📈 TTFA Performance Trends:")
            for trend in summary["performance_trends"]["ttfa"]:
                print(f"  {trend['length']} chars: {trend['avg_ttfa']:.1f}ms avg, {trend['p95_ttfa']:.1f}ms p95")
        
        if summary["optimization_opportunities"]:
            print("\n⚠️ Optimization Opportunities:")
            for opp in summary["optimization_opportunities"]:
                print(f"  • {opp}")
        
        if summary["recommendations"]:
            print("\n💡 Recommendations:")
            for rec in summary["recommendations"]:
                print(f"  • {rec}")

def main():
    """Main benchmark execution"""
    benchmark = PerformanceBenchmark()
    results = benchmark.run_comprehensive_benchmark()
    
    # Save results
    timestamp = int(time.time())
    results_file = f"benchmark_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {results_file}")

if __name__ == "__main__":
    main()
