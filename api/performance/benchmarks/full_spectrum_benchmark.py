"""
Full Spectrum Performance Benchmark System

This module provides comprehensive benchmarking across the entire TTS system,
including TTFA, streaming efficiency, memory usage, and provider performance.
"""

import asyncio
import time
import logging
import psutil
import tracemalloc
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
import json

from .ttfa_benchmark import TTFABenchmark, TTFABenchmarkResult
from .streaming_benchmark import StreamingBenchmark, StreamingMetrics  
from .provider_benchmark import ProviderBenchmark, ProviderComparison

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System resource usage metrics"""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    available_memory_mb: float
    process_memory_mb: float
    thread_count: int
    timestamp: float

@dataclass
class PerformanceProfile:
    """Complete performance profile for a test scenario"""
    scenario_name: str
    text_length: int
    voice: str
    speed: float
    
    # TTFA metrics
    ttfa_ms: float
    ttfa_target_met: bool
    
    # Streaming metrics
    streaming_efficiency: float
    chunk_count: int
    avg_chunk_size: int
    
    # System metrics
    peak_cpu_percent: float
    peak_memory_mb: float
    memory_delta_mb: float
    
    # Provider metrics
    provider_used: str
    inference_time_ms: float
    provider_efficiency: float
    
    timestamp: float

@dataclass
class BenchmarkSummary:
    """Summary of full spectrum benchmark results"""
    total_scenarios: int
    benchmark_duration_s: float
    
    # TTFA performance
    avg_ttfa_ms: float
    ttfa_success_rate: float
    ttfa_target_ms: float
    
    # Streaming performance
    avg_streaming_efficiency: float
    streaming_success_rate: float
    
    # System performance
    avg_cpu_percent: float
    peak_memory_mb: float
    memory_efficiency_score: float
    
    # Provider performance
    provider_distribution: Dict[str, int]
    provider_performance: Dict[str, float]
    
    # Optimization recommendations
    recommendations: List[str]
    critical_issues: List[str]
    
    timestamp: float

class FullSpectrumBenchmark:
    """
    Comprehensive performance benchmarking across all TTS system components.
    
    This benchmark measures:
    - TTFA performance across text varieties
    - Streaming efficiency and buffering
    - System resource utilization
    - Provider performance comparison
    - Memory usage and leak detection
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.ttfa_benchmark = TTFABenchmark(server_url)
        self.streaming_benchmark = StreamingBenchmark(server_url)
        self.provider_benchmark = ProviderBenchmark(server_url)
        
        self.profiles: List[PerformanceProfile] = []
        self.system_metrics_history: List[SystemMetrics] = []
        
    async def run_comprehensive_benchmark(self) -> BenchmarkSummary:
        """
        Run comprehensive benchmark covering all performance aspects.
        
        This executes a full spectrum test that measures performance
        across different scenarios and provides optimization recommendations.
        """
        benchmark_start = time.perf_counter()
        logger.info("Starting comprehensive full-spectrum benchmark...")
        
        # Start memory tracking
        tracemalloc.start()
        
        try:
            # Define benchmark scenarios
            scenarios = self._get_benchmark_scenarios()
            
            # Run each scenario with full instrumentation
            for scenario in scenarios:
                await self._run_scenario_benchmark(scenario)
            
            # Analyze results and generate summary
            summary = self._analyze_benchmark_results(benchmark_start)
            
            logger.info(f"Comprehensive benchmark completed: {summary.benchmark_duration_s:.1f}s")
            return summary
            
        except Exception as e:
            logger.error(f"Comprehensive benchmark failed: {e}")
            raise
        finally:
            tracemalloc.stop()
    
    def _get_benchmark_scenarios(self) -> List[Dict[str, Any]]:
        """Define comprehensive benchmark scenarios"""
        return [
            # TTFA optimization scenarios
            {
                "name": "short_text_ttfa",
                "text": "Hello world!",
                "voice": "af_heart",
                "speed": 1.0,
                "category": "ttfa",
                "target_ttfa_ms": 400
            },
            {
                "name": "medium_text_ttfa", 
                "text": "This is a medium-length sentence for testing TTS performance characteristics.",
                "voice": "bm_fable",
                "speed": 1.0,
                "category": "ttfa",
                "target_ttfa_ms": 600
            },
            {
                "name": "long_text_streaming",
                "text": "We identified 7 core capabilities, supported by 35 implementations across our product units. For example, Summarization alone has 10 separate implementations distributed across product units, with some leveraging the Insights Engine capabilities and others developing bespoke solutions. This analysis underscores both the duplication across business units and the opportunity for consolidation.",
                "voice": "cf_dream",
                "speed": 1.25,
                "category": "streaming",
                "target_ttfa_ms": 800
            },
            # Speed variation scenarios
            {
                "name": "fast_speech",
                "text": "Testing fast speech synthesis for performance analysis.",
                "voice": "dm_sage",
                "speed": 1.5,
                "category": "speed",
                "target_ttfa_ms": 800
            },
            {
                "name": "slow_speech",
                "text": "Testing slow speech synthesis for performance analysis.",
                "voice": "af_heart",
                "speed": 0.75,
                "category": "speed", 
                "target_ttfa_ms": 800
            },
            # Voice variety scenarios
            {
                "name": "voice_variety_1",
                "text": "Testing different voices for performance consistency.",
                "voice": "bf_emma",
                "speed": 1.0,
                "category": "voice",
                "target_ttfa_ms": 800
            },
            {
                "name": "voice_variety_2", 
                "text": "Testing different voices for performance consistency.",
                "voice": "df_sarah",
                "speed": 1.0,
                "category": "voice",
                "target_ttfa_ms": 800
            }
        ]
    
    async def _run_scenario_benchmark(self, scenario: Dict[str, Any]):
        """Run benchmark for a single scenario with full instrumentation"""
        scenario_name = scenario["name"]
        logger.info(f"Running scenario: {scenario_name}")
        
        # Capture system state before
        system_before = self._capture_system_metrics()
        memory_before = tracemalloc.get_traced_memory()[0]
        
        try:
            # Run TTFA measurement
            ttfa_measurement = await self.ttfa_benchmark.measure_single_ttfa(
                text=scenario["text"],
                voice=scenario["voice"],
                speed=scenario["speed"],
                request_id=f"bench-{scenario_name}"
            )
            
            # Run streaming measurement  
            streaming_metrics = await self.streaming_benchmark.measure_streaming_performance(
                text=scenario["text"],
                voice=scenario["voice"],
                speed=scenario["speed"]
            )
            
            # Capture system state after
            system_after = self._capture_system_metrics()
            memory_after = tracemalloc.get_traced_memory()[0]
            
            # Create performance profile
            profile = PerformanceProfile(
                scenario_name=scenario_name,
                text_length=len(scenario["text"]),
                voice=scenario["voice"],
                speed=scenario["speed"],
                ttfa_ms=ttfa_measurement.total_ttfa_ms,
                ttfa_target_met=ttfa_measurement.target_met,
                streaming_efficiency=streaming_metrics.efficiency,
                chunk_count=streaming_metrics.total_chunks,
                avg_chunk_size=streaming_metrics.avg_chunk_size,
                peak_cpu_percent=max(system_before.cpu_percent, system_after.cpu_percent),
                peak_memory_mb=max(system_before.memory_mb, system_after.memory_mb),
                memory_delta_mb=(memory_after - memory_before) / 1024 / 1024,
                provider_used=ttfa_measurement.provider_used,
                inference_time_ms=ttfa_measurement.model_inference_ms,
                provider_efficiency=1.0 if ttfa_measurement.target_met else 0.5,
                timestamp=time.time()
            )
            
            self.profiles.append(profile)
            self.system_metrics_history.extend([system_before, system_after])
            
            logger.info(f"Scenario {scenario_name} completed: TTFA={profile.ttfa_ms:.1f}ms, Efficiency={profile.streaming_efficiency:.1%}")
            
        except Exception as e:
            logger.error(f"Scenario {scenario_name} failed: {e}")
    
    def _capture_system_metrics(self) -> SystemMetrics:
        """Capture current system resource metrics"""
        process = psutil.Process()
        system_memory = psutil.virtual_memory()
        
        return SystemMetrics(
            cpu_percent=process.cpu_percent(),
            memory_mb=process.memory_info().rss / 1024 / 1024,
            memory_percent=process.memory_percent(),
            available_memory_mb=system_memory.available / 1024 / 1024,
            process_memory_mb=process.memory_info().rss / 1024 / 1024,
            thread_count=process.num_threads(),
            timestamp=time.time()
        )
    
    def _analyze_benchmark_results(self, benchmark_start: float) -> BenchmarkSummary:
        """Analyze benchmark results and generate comprehensive summary"""
        benchmark_duration = time.perf_counter() - benchmark_start
        
        if not self.profiles:
            raise ValueError("No benchmark profiles available for analysis")
        
        # TTFA analysis
        ttfa_values = [p.ttfa_ms for p in self.profiles]
        avg_ttfa = statistics.mean(ttfa_values)
        ttfa_success_count = sum(1 for p in self.profiles if p.ttfa_target_met)
        ttfa_success_rate = ttfa_success_count / len(self.profiles)
        
        # Streaming analysis  
        streaming_efficiencies = [p.streaming_efficiency for p in self.profiles]
        avg_streaming_efficiency = statistics.mean(streaming_efficiencies)
        streaming_success_count = sum(1 for e in streaming_efficiencies if e >= 0.9)
        streaming_success_rate = streaming_success_count / len(self.profiles)
        
        # System resource analysis
        cpu_values = [p.peak_cpu_percent for p in self.profiles]
        memory_values = [p.peak_memory_mb for p in self.profiles]
        avg_cpu = statistics.mean(cpu_values) if cpu_values else 0
        peak_memory = max(memory_values) if memory_values else 0
        
        # Memory efficiency score (lower memory delta is better)
        memory_deltas = [abs(p.memory_delta_mb) for p in self.profiles]
        memory_efficiency = 1.0 - min(1.0, statistics.mean(memory_deltas) / 100)
        
        # Provider analysis
        provider_counts = {}
        provider_performance = {}
        
        for profile in self.profiles:
            provider = profile.provider_used
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            if provider not in provider_performance:
                provider_performance[provider] = []
            provider_performance[provider].append(profile.inference_time_ms)
        
        # Average provider performance
        for provider, times in provider_performance.items():
            provider_performance[provider] = statistics.mean(times)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            avg_ttfa, ttfa_success_rate, avg_streaming_efficiency, 
            streaming_success_rate, avg_cpu, peak_memory
        )
        
        # Identify critical issues
        critical_issues = self._identify_critical_issues(
            avg_ttfa, ttfa_success_rate, avg_streaming_efficiency, peak_memory
        )
        
        return BenchmarkSummary(
            total_scenarios=len(self.profiles),
            benchmark_duration_s=benchmark_duration,
            avg_ttfa_ms=avg_ttfa,
            ttfa_success_rate=ttfa_success_rate,
            ttfa_target_ms=800,
            avg_streaming_efficiency=avg_streaming_efficiency,
            streaming_success_rate=streaming_success_rate,
            avg_cpu_percent=avg_cpu,
            peak_memory_mb=peak_memory,
            memory_efficiency_score=memory_efficiency,
            provider_distribution=provider_counts,
            provider_performance=provider_performance,
            recommendations=recommendations,
            critical_issues=critical_issues,
            timestamp=time.time()
        )
    
    def _generate_recommendations(
        self, 
        avg_ttfa: float, 
        ttfa_success_rate: float,
        avg_streaming_efficiency: float,
        streaming_success_rate: float,
        avg_cpu: float,
        peak_memory: float
    ) -> List[str]:
        """Generate optimization recommendations based on benchmark results"""
        recommendations = []
        
        # TTFA recommendations
        if avg_ttfa > 1200:
            recommendations.append("CRITICAL: TTFA severely exceeds target. Implement streaming optimization immediately.")
        elif avg_ttfa > 800:
            recommendations.append("HIGH: TTFA above target. Enable fast-path processing and optimize model inference.")
        elif ttfa_success_rate < 0.8:
            recommendations.append("MEDIUM: TTFA consistency issues. Review text processing pipeline.")
        
        # Streaming recommendations
        if avg_streaming_efficiency < 0.8:
            recommendations.append("HIGH: Streaming efficiency low. Optimize chunk delivery and buffer management.")
        elif streaming_success_rate < 0.9:
            recommendations.append("MEDIUM: Streaming consistency issues. Review daemon communication.")
        
        # Resource recommendations
        if avg_cpu > 80:
            recommendations.append("MEDIUM: High CPU utilization. Consider provider optimization or load balancing.")
        if peak_memory > 2000:
            recommendations.append("MEDIUM: High memory usage. Review memory management and cleanup.")
        
        # Provider recommendations
        if avg_ttfa > 800:
            recommendations.append("HIGH: Consider CoreML provider optimization or CPU fallback tuning.")
        
        return recommendations
    
    def _identify_critical_issues(
        self,
        avg_ttfa: float,
        ttfa_success_rate: float, 
        avg_streaming_efficiency: float,
        peak_memory: float
    ) -> List[str]:
        """Identify critical performance issues requiring immediate attention"""
        issues = []
        
        if avg_ttfa > 2000:
            issues.append("CRITICAL: TTFA exceeds 2000ms - user experience severely impacted")
        if ttfa_success_rate < 0.5:
            issues.append("CRITICAL: TTFA target missed in >50% of requests")
        if avg_streaming_efficiency < 0.7:
            issues.append("CRITICAL: Streaming efficiency below 70% - audio playback issues likely")
        if peak_memory > 3000:
            issues.append("CRITICAL: Memory usage exceeds 3GB - potential memory leak")
        
        return issues


class BenchmarkRunner:
    """
    Orchestrates comprehensive benchmark execution and reporting.
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.benchmark = FullSpectrumBenchmark(server_url)
        
    async def run_full_benchmark_suite(self) -> Dict[str, Any]:
        """Run complete benchmark suite and return comprehensive results"""
        
        logger.info("Starting full benchmark suite execution...")
        suite_start = time.perf_counter()
        
        try:
            # Run comprehensive benchmark
            summary = await self.benchmark.run_comprehensive_benchmark()
            
            suite_duration = time.perf_counter() - suite_start
            
            # Compile results
            results = {
                'suite_execution_time_s': suite_duration,
                'summary': asdict(summary),
                'detailed_profiles': [asdict(p) for p in self.benchmark.profiles],
                'system_metrics': [asdict(m) for m in self.benchmark.system_metrics_history],
                'execution_timestamp': time.time(),
                'benchmark_version': '1.0.0'
            }
            
            logger.info(f"Full benchmark suite completed in {suite_duration:.1f}s")
            return results
            
        except Exception as e:
            logger.error(f"Full benchmark suite failed: {e}")
            raise
    
    def save_benchmark_results(self, results: Dict[str, Any], filepath: str):
        """Save comprehensive benchmark results to file"""
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Benchmark results saved to {filepath}")
    
    def generate_performance_report(self, results: Dict[str, Any]) -> str:
        """Generate human-readable performance report"""
        summary = results['summary']
        
        report = f"""
# Comprehensive TTS Performance Benchmark Report

## Executive Summary
- **Benchmark Duration**: {results['suite_execution_time_s']:.1f}s
- **Scenarios Tested**: {summary['total_scenarios']}
- **Overall TTFA**: {summary['avg_ttfa_ms']:.1f}ms (Target: {summary['ttfa_target_ms']}ms)
- **TTFA Success Rate**: {summary['ttfa_success_rate']:.1%}
- **Streaming Efficiency**: {summary['avg_streaming_efficiency']:.1%}

## Performance Analysis

### TTFA Performance
- **Average**: {summary['avg_ttfa_ms']:.1f}ms
- **Target Achievement**: {summary['ttfa_success_rate']:.1%}
- **Status**: {'✅ MEETING TARGET' if summary['avg_ttfa_ms'] <= summary['ttfa_target_ms'] else ' ABOVE TARGET'}

### Streaming Performance  
- **Efficiency**: {summary['avg_streaming_efficiency']:.1%}
- **Consistency**: {summary['streaming_success_rate']:.1%}
- **Status**: {'✅ OPTIMAL' if summary['avg_streaming_efficiency'] >= 0.9 else ' NEEDS OPTIMIZATION'}

### System Resources
- **Peak Memory**: {summary['peak_memory_mb']:.1f}MB
- **Average CPU**: {summary['avg_cpu_percent']:.1f}%
- **Memory Efficiency**: {summary['memory_efficiency_score']:.1%}

### Provider Performance
"""
        
        for provider, performance in summary['provider_performance'].items():
            usage = summary['provider_distribution'].get(provider, 0)
            report += f"- **{provider}**: {performance:.1f}ms avg ({usage} uses)\n"
        
        report += "\n## Optimization Recommendations\n"
        for i, rec in enumerate(summary['recommendations'], 1):
            report += f"{i}. {rec}\n"
        
        if summary['critical_issues']:
            report += "\n##  Critical Issues\n"
            for issue in summary['critical_issues']:
                report += f"- {issue}\n"
        
        return report
