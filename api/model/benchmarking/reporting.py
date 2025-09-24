"""
Performance reporting module.

This module provides functionality to generate detailed performance reports
from benchmark data.
"""

import time
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def generate_performance_report(benchmark_results: Dict[str, Any], 
                              optimal_provider: str) -> Dict[str, Any]:
    """
    Generate a comprehensive performance report from benchmark results.
    
    @param benchmark_results: Results from provider benchmarking
    @param optimal_provider: Name of the optimal provider selected
    @returns: Formatted performance report
    """
    report = {
        'timestamp': time.time(),
        'optimal_provider': optimal_provider,
        'summary': _generate_summary(benchmark_results, optimal_provider),
        'detailed_results': benchmark_results,
        'recommendations': _generate_recommendations(benchmark_results),
        'performance_metrics': _calculate_performance_metrics(benchmark_results)
    }
    
    return report


def _generate_summary(results: Dict[str, Any], optimal_provider: str) -> Dict[str, Any]:
    """Generate a summary of benchmark results."""
    available_providers = [p for p, r in results.items() if r.get('available', False)]
    total_providers_tested = len(results)
    
    summary = {
        'total_providers_tested': total_providers_tested,
        'available_providers': available_providers,
        'optimal_provider': optimal_provider,
        'performance_improvement': None
    }
    
    # Calculate performance improvement over CPU baseline
    if optimal_provider != 'CPUExecutionProvider' and 'CPUExecutionProvider' in results:
        cpu_time = results['CPUExecutionProvider'].get('time', 0)
        optimal_time = results[optimal_provider].get('time', 0)
        
        if cpu_time > 0 and optimal_time > 0:
            improvement = (cpu_time - optimal_time) / cpu_time * 100
            summary['performance_improvement'] = f"{improvement:.1f}%"
    
    return summary


def _generate_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate optimization recommendations based on results."""
    recommendations = []
    
    # Check if CoreML is available but not optimal
    if 'CoreMLExecutionProvider' in results:
        coreml_result = results['CoreMLExecutionProvider']
        if not coreml_result.get('available', False):
            recommendations.append(
                "CoreML provider is not available. Check macOS version and hardware compatibility."
            )
        elif coreml_result.get('time', float('inf')) > 2.0:
            recommendations.append(
                "CoreML performance is slower than expected. Consider checking ANE availability."
            )
    
    # Check overall performance
    fastest_time = min(
        r.get('time', float('inf')) for r in results.values() 
        if r.get('available', False)
    )
    
    if fastest_time > 1.0:
        recommendations.append(
            "Overall inference time is high. Consider model quantization or hardware upgrade."
        )
    
    return recommendations


def _calculate_performance_metrics(results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate performance metrics from benchmark results."""
    metrics = {}
    
    for provider, result in results.items():
        if result.get('available', False):
            inference_time = result.get('time', 0)
            metrics[provider] = {
                'inference_time_ms': inference_time * 1000,
                'throughput_fps': 1.0 / inference_time if inference_time > 0 else 0,
                'performance_score': result.get('score', 0)
            }
    
    return metrics

