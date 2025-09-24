"""
Comprehensive Performance Benchmark Suite

This module orchestrates all benchmark types to provide a complete performance
analysis of the Kokoro-ONNX TTS system, including TTFA, streaming, provider
comparison, and system health metrics.

@author: @darianrosebrook
@date: 2025-08-15
@version: 1.0.0
@license: MIT
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import os

from .ttfa_benchmark import TTFABenchmark, TTFABenchmarkSuite
from .streaming_benchmark import StreamingBenchmark, StreamingBenchmarkSuite
from .provider_benchmark import ProviderBenchmark, ProviderBenchmarkSuite

logger = logging.getLogger(__name__)


@dataclass
class ComprehensiveBenchmarkResult:
    """Results from comprehensive benchmark including all test types"""
    benchmark_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Individual benchmark results
    ttfa_results: Optional[TTFABenchmarkSuite] = None
    streaming_results: Optional[StreamingBenchmarkSuite] = None
    provider_results: Optional[ProviderBenchmarkSuite] = None
    
    # System health during benchmark
    system_health: Dict[str, Any] = field(default_factory=dict)
    
    # Overall benchmark status
    completed_successfully: bool = False
    errors: List[str] = field(default_factory=list)
    
    def get_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary of all benchmark results"""
        summary = {
            'benchmark_id': self.benchmark_id,
            'execution_time': {
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_minutes': ((self.end_time - self.start_time).total_seconds() / 60) if self.end_time else None
            },
            'completion_status': {
                'completed_successfully': self.completed_successfully,
                'errors': self.errors
            },
            'performance_overview': {},
            'critical_findings': [],
            'optimization_priorities': []
        }
        
        # TTFA Performance Overview
        if self.ttfa_results:
            ttfa_summary = self.ttfa_results.get_summary()
            summary['performance_overview']['ttfa'] = {
                'average_ms': ttfa_summary['overall_statistics']['average_ttfa_ms'],
                'target_achievement_rate': ttfa_summary['overall_statistics']['target_achievement_rate_percent'],
                'status': self._categorize_ttfa_performance(
                    ttfa_summary['overall_statistics']['average_ttfa_ms'],
                    ttfa_summary['overall_statistics']['target_achievement_rate_percent']
                )
            }
            
            # Add critical findings for TTFA
            if ttfa_summary['overall_statistics']['target_achievement_rate_percent'] < 70:
                summary['critical_findings'].append({
                    'category': 'TTFA',
                    'severity': 'high',
                    'finding': f"TTFA target achievement rate is only {ttfa_summary['overall_statistics']['target_achievement_rate_percent']:.1f}%",
                    'impact': 'Poor user experience due to slow audio delivery'
                })
        
        # Streaming Performance Overview  
        if self.streaming_results:
            streaming_summary = self.streaming_results.get_summary()
            summary['performance_overview']['streaming'] = {
                'efficiency_percent': streaming_summary['overall_statistics']['average_efficiency_percent'],
                'underrun_rate': streaming_summary['overall_statistics']['underrun_rate_percent'],
                'status': self._categorize_streaming_performance(
                    streaming_summary['overall_statistics']['average_efficiency_percent'],
                    streaming_summary['overall_statistics']['underrun_rate_percent']
                )
            }
        
        # Provider Performance Overview
        if self.provider_results:
            provider_summary = self.provider_results.get_summary()
            summary['performance_overview']['providers'] = provider_summary['provider_comparison']
            
            # Identify best performing provider
            if 'best_provider' in provider_summary:
                summary['optimization_priorities'].append({
                    'priority': 'high',
                    'action': f"Optimize routing to favor {provider_summary['best_provider']['name']} provider",
                    'expected_improvement': f"{provider_summary['best_provider']['advantage_percent']:.1f}% performance gain"
                })
        
        # System Health Overview
        if self.system_health:
            summary['performance_overview']['system_health'] = self.system_health
        
        # Generate optimization priorities
        summary['optimization_priorities'].extend(self._generate_optimization_priorities())
        
        return summary
    
    def _categorize_ttfa_performance(self, avg_ttfa: float, achievement_rate: float) -> str:
        """Categorize TTFA performance level"""
        if avg_ttfa <= 800 and achievement_rate >= 90:
            return "excellent"
        elif avg_ttfa <= 1000 and achievement_rate >= 80:
            return "good"
        elif avg_ttfa <= 1500 and achievement_rate >= 60:
            return "needs_improvement"
        else:
            return "critical"
    
    def _categorize_streaming_performance(self, efficiency: float, underrun_rate: float) -> str:
        """Categorize streaming performance level"""
        if efficiency >= 95 and underrun_rate <= 5:
            return "excellent"
        elif efficiency >= 90 and underrun_rate <= 10:
            return "good"
        elif efficiency >= 80 and underrun_rate <= 20:
            return "needs_improvement"
        else:
            return "critical"
    
    def _generate_optimization_priorities(self) -> List[Dict[str, str]]:
        """Generate optimization priorities based on benchmark results"""
        priorities = []
        
        # Analyze TTFA performance
        if self.ttfa_results:
            ttfa_summary = self.ttfa_results.get_summary()
            avg_ttfa = ttfa_summary['overall_statistics']['average_ttfa_ms']
            achievement_rate = ttfa_summary['overall_statistics']['target_achievement_rate_percent']
            
            if avg_ttfa > 1200:
                priorities.append({
                    'priority': 'critical',
                    'action': 'Implement aggressive fast-path processing for all first segments',
                    'rationale': f'Average TTFA ({avg_ttfa:.1f}ms) is 50% above target'
                })
            elif achievement_rate < 80:
                priorities.append({
                    'priority': 'high',
                    'action': 'Optimize audio generation pipeline to reduce bottlenecks',
                    'rationale': f'Only {achievement_rate:.1f}% of requests meet TTFA targets'
                })
        
        # Analyze streaming performance
        if self.streaming_results:
            streaming_summary = self.streaming_results.get_summary()
            efficiency = streaming_summary['overall_statistics']['average_efficiency_percent']
            
            if efficiency < 85:
                priorities.append({
                    'priority': 'high',
                    'action': 'Improve streaming buffer management and chunk delivery',
                    'rationale': f'Streaming efficiency ({efficiency:.1f}%) is below optimal threshold'
                })
        
        return priorities


class ComprehensiveBenchmark:
    """
    Orchestrates comprehensive performance benchmarking across all system components
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize individual benchmark components
        self.ttfa_benchmark = TTFABenchmark()
        self.streaming_benchmark = StreamingBenchmark()
        self.provider_benchmark = ProviderBenchmark()
    
    async def run_full_benchmark_suite(self, include_provider_comparison: bool = True) -> ComprehensiveBenchmarkResult:
        """
        Run complete benchmark suite including all performance tests
        
        Args:
            include_provider_comparison: Whether to include provider comparison tests
            
        Returns:
            ComprehensiveBenchmarkResult with all benchmark data
        """
        benchmark_id = f"comprehensive_{int(time.time())}"
        self.logger.info(f"Starting comprehensive benchmark suite: {benchmark_id}")
        
        result = ComprehensiveBenchmarkResult(
            benchmark_id=benchmark_id,
            start_time=datetime.now()
        )
        
        try:
            # Record initial system health
            result.system_health['initial'] = await self._capture_system_health()
            
            # Run TTFA benchmarks
            self.logger.info("Running TTFA benchmark suite...")
            try:
                result.ttfa_results = await self.ttfa_benchmark.run_comprehensive_ttfa_benchmark()
                self.logger.info("✅ TTFA benchmarks completed")
            except Exception as e:
                error_msg = f"TTFA benchmark failed: {e}"
                self.logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)
            
            # Run streaming benchmarks
            self.logger.info("Running streaming benchmark suite...")
            try:
                result.streaming_results = await self.streaming_benchmark.run_comprehensive_streaming_benchmark()
                self.logger.info("✅ Streaming benchmarks completed")
            except Exception as e:
                error_msg = f"Streaming benchmark failed: {e}"
                self.logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)
            
            # Run provider comparison benchmarks
            if include_provider_comparison:
                self.logger.info("Running provider comparison benchmarks...")
                try:
                    result.provider_results = await self.provider_benchmark.run_comprehensive_provider_benchmark()
                    self.logger.info("✅ Provider benchmarks completed")
                except Exception as e:
                    error_msg = f"Provider benchmark failed: {e}"
                    self.logger.error(error_msg, exc_info=True)
                    result.errors.append(error_msg)
            
            # Record final system health
            result.system_health['final'] = await self._capture_system_health()
            
            # Mark as completed successfully if no critical errors
            result.completed_successfully = len(result.errors) == 0
            
        except Exception as e:
            error_msg = f"Comprehensive benchmark failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            result.completed_successfully = False
        
        finally:
            result.end_time = datetime.now()
            duration = (result.end_time - result.start_time).total_seconds()
            self.logger.info(f"Comprehensive benchmark completed in {duration:.1f}s")
        
        return result
    
    async def run_quick_benchmark(self) -> ComprehensiveBenchmarkResult:
        """
        Run a quick benchmark with reduced test coverage for faster feedback
        """
        benchmark_id = f"quick_{int(time.time())}"
        self.logger.info(f"Starting quick benchmark suite: {benchmark_id}")
        
        result = ComprehensiveBenchmarkResult(
            benchmark_id=benchmark_id,
            start_time=datetime.now()
        )
        
        try:
            # Record initial system health
            result.system_health['initial'] = await self._capture_system_health()
            
            # Run quick TTFA benchmarks
            try:
                result.ttfa_results = await self.ttfa_benchmark.run_quick_ttfa_benchmark()
                self.logger.info("✅ Quick TTFA benchmarks completed")
            except Exception as e:
                error_msg = f"Quick TTFA benchmark failed: {e}"
                self.logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)
            
            # Run quick streaming benchmarks
            try:
                result.streaming_results = await self.streaming_benchmark.run_quick_streaming_benchmark()
                self.logger.info("✅ Quick streaming benchmarks completed")
            except Exception as e:
                error_msg = f"Quick streaming benchmark failed: {e}"
                self.logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)
            
            # Record final system health
            result.system_health['final'] = await self._capture_system_health()
            
            result.completed_successfully = len(result.errors) == 0
            
        except Exception as e:
            error_msg = f"Quick benchmark failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            result.completed_successfully = False
        
        finally:
            result.end_time = datetime.now()
            duration = (result.end_time - result.start_time).total_seconds()
            self.logger.info(f"Quick benchmark completed in {duration:.1f}s")
        
        return result
    
    async def _capture_system_health(self) -> Dict[str, Any]:
        """Capture current system health metrics"""
        try:
            import psutil
            
            # Get memory info
            memory = psutil.virtual_memory()
            
            # Get CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get TTS-specific metrics
            from api.performance.stats import coreml_performance_stats
            
            return {
                'timestamp': datetime.now().isoformat(),
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_percent': memory.percent
                },
                'cpu': {
                    'usage_percent': cpu_percent
                },
                'tts_stats': dict(coreml_performance_stats)
            }
        except Exception as e:
            self.logger.warning(f"Failed to capture system health: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def save_comprehensive_results(self, result: ComprehensiveBenchmarkResult, filename: Optional[str] = None) -> str:
        """
        Save comprehensive benchmark results to JSON file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"comprehensive_benchmark_{result.benchmark_id}_{timestamp}.json"
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        filepath = os.path.join('reports', filename)
        
        # Prepare data for JSON serialization
        data = {
            'executive_summary': result.get_executive_summary(),
            'detailed_results': {
                'ttfa_benchmark': result.ttfa_results.get_summary() if result.ttfa_results else None,
                'streaming_benchmark': result.streaming_results.get_summary() if result.streaming_results else None,
                'provider_benchmark': result.provider_results.get_summary() if result.provider_results else None
            },
            'system_health': result.system_health,
            'raw_data': {
                'ttfa_results': [r.to_dict() for r in result.ttfa_results.results] if result.ttfa_results else [],
                'streaming_results': [r.to_dict() for r in result.streaming_results.results] if result.streaming_results else [],
                'provider_results': [r.to_dict() for r in result.provider_results.results] if result.provider_results else []
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Comprehensive benchmark results saved to: {filepath}")
        return filepath
    
    async def run_regression_test(self, baseline_file: str) -> Dict[str, Any]:
        """
        Run benchmark and compare against baseline to detect performance regressions
        
        Args:
            baseline_file: Path to baseline benchmark results file
            
        Returns:
            Regression analysis results
        """
        self.logger.info(f"Running regression test against baseline: {baseline_file}")
        
        # Load baseline data
        try:
            with open(baseline_file, 'r') as f:
                baseline_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load baseline file: {e}")
            return {'error': f'Failed to load baseline: {e}'}
        
        # Run current benchmark
        current_result = await self.run_quick_benchmark()
        current_summary = current_result.get_executive_summary()
        
        # Compare results
        regression_analysis = {
            'baseline_file': baseline_file,
            'current_benchmark_id': current_result.benchmark_id,
            'comparison_timestamp': datetime.now().isoformat(),
            'regressions_detected': [],
            'improvements_detected': [],
            'overall_status': 'unknown'
        }
        
        try:
            baseline_summary = baseline_data['executive_summary']
            
            # Compare TTFA performance
            if ('ttfa' in baseline_summary['performance_overview'] and 
                'ttfa' in current_summary['performance_overview']):
                
                baseline_ttfa = baseline_summary['performance_overview']['ttfa']['average_ms']
                current_ttfa = current_summary['performance_overview']['ttfa']['average_ms']
                
                # Check for regression (>10% slower)
                if current_ttfa > baseline_ttfa * 1.1:
                    regression_analysis['regressions_detected'].append({
                        'metric': 'TTFA Average',
                        'baseline_value': baseline_ttfa,
                        'current_value': current_ttfa,
                        'regression_percent': ((current_ttfa - baseline_ttfa) / baseline_ttfa) * 100,
                        'severity': 'high' if current_ttfa > baseline_ttfa * 1.25 else 'medium'
                    })
                
                # Check for improvement (>5% faster)
                elif current_ttfa < baseline_ttfa * 0.95:
                    regression_analysis['improvements_detected'].append({
                        'metric': 'TTFA Average',
                        'baseline_value': baseline_ttfa,
                        'current_value': current_ttfa,
                        'improvement_percent': ((baseline_ttfa - current_ttfa) / baseline_ttfa) * 100
                    })
            
            # Determine overall status
            if regression_analysis['regressions_detected']:
                high_severity_regressions = [r for r in regression_analysis['regressions_detected'] if r['severity'] == 'high']
                regression_analysis['overall_status'] = 'regression_critical' if high_severity_regressions else 'regression_detected'
            elif regression_analysis['improvements_detected']:
                regression_analysis['overall_status'] = 'improvement_detected'
            else:
                regression_analysis['overall_status'] = 'stable'
        
        except Exception as e:
            self.logger.error(f"Error during regression analysis: {e}")
            regression_analysis['analysis_error'] = str(e)
        
        self.logger.info(f"Regression test completed: {regression_analysis['overall_status']}")
        return regression_analysis


# Convenience functions for external use
async def run_comprehensive_benchmark(include_providers: bool = True) -> ComprehensiveBenchmarkResult:
    """Run comprehensive benchmark and return results"""
    benchmark = ComprehensiveBenchmark()
    return await benchmark.run_full_benchmark_suite(include_providers)


async def run_quick_benchmark() -> ComprehensiveBenchmarkResult:
    """Run quick benchmark for faster feedback"""
    benchmark = ComprehensiveBenchmark()
    return await benchmark.run_quick_benchmark()


async def run_regression_test(baseline_file: str) -> Dict[str, Any]:
    """Run regression test against baseline"""
    benchmark = ComprehensiveBenchmark()
    return await benchmark.run_regression_test(baseline_file)
