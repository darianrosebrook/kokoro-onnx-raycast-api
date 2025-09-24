#!/usr/bin/env python3
"""
Performance Regression Detection System for Kokoro TTS API.

This script analyzes performance metrics over time to detect regressions,
trends, and anomalies in the TTS system performance.
"""
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RegressionResult:
    """Regression detection result."""
    metric: str
    severity: str  # 'minor', 'moderate', 'severe'
    current_value: float
    baseline_value: float
    regression_factor: float
    confidence: float
    trend: str  # 'improving', 'stable', 'degrading'
    recommendation: str

@dataclass
class PerformanceBaseline:
    """Performance baseline data."""
    metric: str
    p50: float
    p95: float
    p99: float
    sample_count: int
    timestamp: float
    conditions: Dict[str, Any]  # Provider, text_length, etc.

class RegressionDetector:
    """Detects performance regressions and trends."""
    
    def __init__(self, baseline_file: str = "performance-baselines.json"):
        self.baseline_file = baseline_file
        self.baselines = self._load_baselines()
        
        # Regression thresholds
        self.regression_thresholds = {
            'minor': 1.2,      # 20% degradation
            'moderate': 1.5,   # 50% degradation
            'severe': 2.0      # 100% degradation
        }
    
    def _load_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Load performance baselines from file."""
        if not Path(self.baseline_file).exists():
            logger.warning(f"Baseline file {self.baseline_file} not found. Using default baselines.")
            return self._get_default_baselines()
        
        try:
            with open(self.baseline_file, 'r') as f:
                data = json.load(f)
            
            baselines = {}
            for metric, baseline_data in data.items():
                baselines[metric] = PerformanceBaseline(
                    metric=metric,
                    p50=baseline_data['p50'],
                    p95=baseline_data['p95'],
                    p99=baseline_data['p99'],
                    sample_count=baseline_data['sample_count'],
                    timestamp=baseline_data['timestamp'],
                    conditions=baseline_data.get('conditions', {})
                )
            
            return baselines
        
        except Exception as e:
            logger.error(f"Failed to load baselines: {e}")
            return self._get_default_baselines()
    
    def _get_default_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Get default baselines based on optimization results."""
        return {
            'ttfa_ms': PerformanceBaseline(
                metric='ttfa_ms',
                p50=5.5,
                p95=6.9,
                p99=10.0,
                sample_count=100,
                timestamp=time.time(),
                conditions={'provider': 'CPUExecutionProvider', 'text_length': 'short'}
            ),
            'api_latency_ms': PerformanceBaseline(
                metric='api_latency_ms',
                p50=5.5,
                p95=6.9,
                p99=10.0,
                sample_count=100,
                timestamp=time.time(),
                conditions={'provider': 'CPUExecutionProvider', 'text_length': 'short'}
            ),
            'memory_mb': PerformanceBaseline(
                metric='memory_mb',
                p50=70.9,
                p95=606.9,
                p99=800.0,
                sample_count=100,
                timestamp=time.time(),
                conditions={'provider': 'CPUExecutionProvider', 'text_length': 'mixed'}
            ),
            'cpu_percent': PerformanceBaseline(
                metric='cpu_percent',
                p50=15.0,
                p95=25.0,
                p99=35.0,
                sample_count=100,
                timestamp=time.time(),
                conditions={'provider': 'CPUExecutionProvider', 'text_length': 'mixed'}
            )
        }
    
    def analyze_metrics(self, metrics_data: List[Dict[str, Any]]) -> List[RegressionResult]:
        """Analyze metrics for regressions."""
        if not metrics_data:
            return []
        
        # Group metrics by type
        metrics_by_type = {}
        for metric in metrics_data:
            for key, value in metric.items():
                if key in ['ttfa_ms', 'api_latency_ms', 'memory_mb', 'cpu_percent']:
                    if key not in metrics_by_type:
                        metrics_by_type[key] = []
                    metrics_by_type[key].append(value)
        
        regressions = []
        
        for metric_name, values in metrics_by_type.items():
            if metric_name not in self.baselines:
                continue
            
            baseline = self.baselines[metric_name]
            
            # Calculate current statistics
            current_p50 = statistics.median(values)
            current_p95 = statistics.quantiles(values, n=20)[18] if len(values) >= 20 else max(values)
            
            # Compare with baseline
            p95_regression = current_p95 / baseline.p95
            p50_regression = current_p50 / baseline.p50
            
            # Determine severity
            severity = 'stable'
            if p95_regression >= self.regression_thresholds['severe']:
                severity = 'severe'
            elif p95_regression >= self.regression_thresholds['moderate']:
                severity = 'moderate'
            elif p95_regression >= self.regression_thresholds['minor']:
                severity = 'minor'
            
            # Determine trend
            trend = 'stable'
            if p50_regression > 1.1:
                trend = 'degrading'
            elif p50_regression < 0.9:
                trend = 'improving'
            
            # Calculate confidence based on sample size
            confidence = min(1.0, len(values) / 50.0)  # Full confidence at 50+ samples
            
            # Generate recommendation
            recommendation = self._generate_recommendation(metric_name, severity, p95_regression)
            
            if severity != 'stable':
                regression = RegressionResult(
                    metric=metric_name,
                    severity=severity,
                    current_value=current_p95,
                    baseline_value=baseline.p95,
                    regression_factor=p95_regression,
                    confidence=confidence,
                    trend=trend,
                    recommendation=recommendation
                )
                regressions.append(regression)
        
        return regressions
    
    def _generate_recommendation(self, metric: str, severity: str, regression_factor: float) -> str:
        """Generate recommendations based on regression analysis."""
        recommendations = {
            'ttfa_ms': {
                'minor': 'Monitor TTFA trends. Consider provider optimization.',
                'moderate': 'Investigate TTFA degradation. Check provider selection and model performance.',
                'severe': 'CRITICAL: TTFA severely degraded. Immediate investigation required. Check CoreML vs CPU provider performance.'
            },
            'api_latency_ms': {
                'minor': 'Monitor API latency. Check for network or processing delays.',
                'moderate': 'Investigate API latency increase. Check server load and processing efficiency.',
                'severe': 'CRITICAL: API latency severely degraded. Check server health and resource usage.'
            },
            'memory_mb': {
                'minor': 'Monitor memory usage. Check for memory leaks.',
                'moderate': 'Investigate memory increase. Check for memory leaks or inefficient caching.',
                'severe': 'CRITICAL: Memory usage severely increased. Check for memory leaks and optimize memory management.'
            },
            'cpu_percent': {
                'minor': 'Monitor CPU usage. Check for inefficient processing.',
                'moderate': 'Investigate CPU increase. Check for processing bottlenecks.',
                'severe': 'CRITICAL: CPU usage severely increased. Check for infinite loops or inefficient algorithms.'
            }
        }
        
        return recommendations.get(metric, {}).get(severity, 'Investigate performance regression.')
    
    def detect_trends(self, metrics_data: List[Dict[str, Any]], window_hours: int = 24) -> Dict[str, str]:
        """Detect performance trends over time."""
        if len(metrics_data) < 10:
            return {}
        
        # Sort by timestamp
        sorted_metrics = sorted(metrics_data, key=lambda x: x.get('timestamp', 0))
        
        # Split into time windows
        window_size = max(1, len(sorted_metrics) // 4)  # 4 windows
        trends = {}
        
        for metric_name in ['ttfa_ms', 'api_latency_ms', 'memory_mb', 'cpu_percent']:
            values = [m.get(metric_name, 0) for m in sorted_metrics if metric_name in m]
            if len(values) < window_size * 2:
                continue
            
            # Calculate trend using linear regression (simplified)
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            
            first_avg = statistics.mean(first_half)
            second_avg = statistics.mean(second_half)
            
            if second_avg > first_avg * 1.1:
                trends[metric_name] = 'degrading'
            elif second_avg < first_avg * 0.9:
                trends[metric_name] = 'improving'
            else:
                trends[metric_name] = 'stable'
        
        return trends
    
    def generate_report(self, metrics_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive regression analysis report."""
        # Load metrics data
        if not Path(metrics_file).exists():
            logger.error(f"Metrics file {metrics_file} not found")
            return {"error": "Metrics file not found"}
        
        try:
            with open(metrics_file, 'r') as f:
                data = json.load(f)
            
            metrics_data = data.get('metrics', [])
            if not metrics_data:
                return {"error": "No metrics data found"}
            
            # Analyze regressions
            regressions = self.analyze_metrics(metrics_data)
            
            # Detect trends
            trends = self.detect_trends(metrics_data)
            
            # Generate report
            report = {
                "timestamp": datetime.now().isoformat(),
                "analysis_period": {
                    "start": min(m.get('timestamp', 0) for m in metrics_data),
                    "end": max(m.get('timestamp', 0) for m in metrics_data),
                    "sample_count": len(metrics_data)
                },
                "regressions": [
                    {
                        "metric": r.metric,
                        "severity": r.severity,
                        "current_value": r.current_value,
                        "baseline_value": r.baseline_value,
                        "regression_factor": r.regression_factor,
                        "confidence": r.confidence,
                        "trend": r.trend,
                        "recommendation": r.recommendation
                    }
                    for r in regressions
                ],
                "trends": trends,
                "summary": {
                    "total_regressions": len(regressions),
                    "severe_regressions": len([r for r in regressions if r.severity == 'severe']),
                    "moderate_regressions": len([r for r in regressions if r.severity == 'moderate']),
                    "minor_regressions": len([r for r in regressions if r.severity == 'minor']),
                    "overall_health": "healthy" if len(regressions) == 0 else "degraded"
                }
            }
            
            # Save report if output file specified
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"Regression report saved to {output_file}")
            
            return report
        
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return {"error": str(e)}

def main():
    """Main regression detection function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Regression Detector")
    parser.add_argument("--metrics", default="performance-metrics.json", help="Input metrics file")
    parser.add_argument("--baselines", default="performance-baselines.json", help="Baseline file")
    parser.add_argument("--output", help="Output report file")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Create detector
    detector = RegressionDetector(args.baselines)
    
    # Generate report
    report = detector.generate_report(args.metrics, args.output)
    
    if "error" in report:
        print(f"❌ Error: {report['error']}")
        sys.exit(1)
    
    # Print summary
    print(f"📊 Performance Regression Analysis Report")
    print(f"  Analysis Period: {report['analysis_period']['sample_count']} samples")
    print(f"  Overall Health: {report['summary']['overall_health']}")
    print(f"  Total Regressions: {report['summary']['total_regressions']}")
    
    if report['summary']['severe_regressions'] > 0:
        print(f"  🚨 Severe Regressions: {report['summary']['severe_regressions']}")
    
    if report['summary']['moderate_regressions'] > 0:
        print(f"  ⚠️  Moderate Regressions: {report['summary']['moderate_regressions']}")
    
    if report['summary']['minor_regressions'] > 0:
        print(f"  ℹ️  Minor Regressions: {report['summary']['minor_regressions']}")
    
    # Print detailed regressions
    if report['regressions']:
        print(f"\n📈 Detailed Regression Analysis:")
        for regression in report['regressions']:
            print(f"  {regression['metric']} [{regression['severity']}]: "
                  f"{regression['current_value']:.2f} vs {regression['baseline_value']:.2f} "
                  f"(x{regression['regression_factor']:.2f})")
            print(f"    Recommendation: {regression['recommendation']}")
    
    # Print trends
    if report['trends']:
        print(f"\n📊 Performance Trends:")
        for metric, trend in report['trends'].items():
            print(f"  {metric}: {trend}")

if __name__ == "__main__":
    import time
    main()
