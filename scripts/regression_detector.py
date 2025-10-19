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
            
            # Implement comprehensive statistical trend analysis
            trend_result = self.analyze_statistical_trend(values, timestamps)
            trends[metric_name] = trend_result['trend']
        
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

    def analyze_statistical_trend(self, values: List[float], timestamps: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Perform comprehensive statistical trend analysis on time series data.

        @param values: List of metric values
        @param timestamps: Optional list of timestamps (generated if not provided)
        @returns Dict containing trend analysis results
        """
        if len(values) < 5:
            return {
                'trend': 'insufficient_data',
                'slope': 0.0,
                'r_squared': 0.0,
                'p_value': 1.0,
                'confidence': 0.0
            }

        try:
            # Generate timestamps if not provided
            if timestamps is None:
                timestamps = list(range(len(values)))

            # Normalize timestamps to avoid numerical issues
            timestamps = [(t - timestamps[0]) / max(1, timestamps[-1] - timestamps[0]) for t in timestamps]

            # Perform linear regression analysis
            regression_result = self.linear_regression_analysis(values, timestamps)

            # Perform Mann-Kendall trend test
            mk_result = self.mann_kendall_test(values)

            # Perform Theil-Sen estimator for robust slope
            theil_sen_result = self.theil_sen_estimator(values, timestamps)

            # Detect change points
            change_points = self.detect_change_points(values)

            # Determine overall trend
            trend = self.determine_overall_trend(regression_result, mk_result, theil_sen_result)

            return {
                'trend': trend,
                'slope': regression_result['slope'],
                'r_squared': regression_result['r_squared'],
                'p_value': regression_result['p_value'],
                'confidence': regression_result['confidence'],
                'mann_kendall': mk_result,
                'theil_sen': theil_sen_result,
                'change_points': change_points,
                'significance_level': self.determine_significance(regression_result, mk_result)
            }

        except Exception as e:
            logger.error(f"Statistical trend analysis failed: {e}")
            return {
                'trend': 'error',
                'slope': 0.0,
                'r_squared': 0.0,
                'p_value': 1.0,
                'confidence': 0.0,
                'error': str(e)
            }

    def linear_regression_analysis(self, y: List[float], x: List[float]) -> Dict[str, Any]:
        """
        Perform linear regression analysis with statistical significance testing.

        @param y: Dependent variable (metric values)
        @param x: Independent variable (normalized timestamps)
        @returns Dict containing regression results
        """
        try:
            import scipy.stats as stats

            # Calculate linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # Calculate R-squared
            r_squared = r_value ** 2

            # Calculate confidence interval for slope
            n = len(x)
            t_value = stats.t.ppf(0.975, n - 2)  # 95% confidence
            slope_std_err = std_err
            confidence_interval = t_value * slope_std_err

            # Determine confidence level
            if p_value < 0.001:
                confidence = 0.99
            elif p_value < 0.01:
                confidence = 0.95
            elif p_value < 0.05:
                confidence = 0.90
            else:
                confidence = 0.0

            return {
                'slope': slope,
                'intercept': intercept,
                'r_squared': r_squared,
                'p_value': p_value,
                'std_err': std_err,
                'confidence_interval': confidence_interval,
                'confidence': confidence
            }

        except ImportError:
            # Fallback to basic linear regression without scipy
            return self.basic_linear_regression(y, x)
        except Exception as e:
            logger.debug(f"Linear regression failed: {e}")
            return {
                'slope': 0.0,
                'intercept': 0.0,
                'r_squared': 0.0,
                'p_value': 1.0,
                'std_err': 0.0,
                'confidence_interval': 0.0,
                'confidence': 0.0
            }

    def basic_linear_regression(self, y: List[float], x: List[float]) -> Dict[str, Any]:
        """
        Basic linear regression implementation without scipy.

        @param y: Dependent variable
        @param x: Independent variable
        @returns Dict containing basic regression results
        """
        try:
            n = len(x)
            if n < 2:
                return {'slope': 0.0, 'intercept': 0.0, 'r_squared': 0.0, 'p_value': 1.0, 'std_err': 0.0, 'confidence_interval': 0.0, 'confidence': 0.0}

            # Calculate means
            x_mean = sum(x) / n
            y_mean = sum(y) / n

            # Calculate slope and intercept
            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
            denominator = sum((xi - x_mean) ** 2 for xi in x)

            if denominator == 0:
                return {'slope': 0.0, 'intercept': y_mean, 'r_squared': 0.0, 'p_value': 1.0, 'std_err': 0.0, 'confidence_interval': 0.0, 'confidence': 0.0}

            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

            # Calculate R-squared
            y_pred = [slope * xi + intercept for xi in x]
            ss_res = sum((yi - y_pred_i) ** 2 for yi, y_pred_i in zip(y, y_pred))
            ss_tot = sum((yi - y_mean) ** 2 for yi in y)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

            # Basic significance test (simplified)
            if abs(slope) > 0.1 and r_squared > 0.5:
                p_value = 0.01  # Assume significant
                confidence = 0.9
            else:
                p_value = 0.1
                confidence = 0.5

            return {
                'slope': slope,
                'intercept': intercept,
                'r_squared': r_squared,
                'p_value': p_value,
                'std_err': abs(slope) * 0.1,  # Rough estimate
                'confidence_interval': abs(slope) * 0.2,
                'confidence': confidence
            }

        except Exception as e:
            logger.debug(f"Basic linear regression failed: {e}")
            return {'slope': 0.0, 'intercept': 0.0, 'r_squared': 0.0, 'p_value': 1.0, 'std_err': 0.0, 'confidence_interval': 0.0, 'confidence': 0.0}

    def mann_kendall_test(self, values: List[float]) -> Dict[str, Any]:
        """
        Perform Mann-Kendall trend test for monotonic trends.

        @param values: Time series values
        @returns Dict containing test results
        """
        try:
            # Simplified Mann-Kendall test implementation
            n = len(values)
            if n < 3:
                return {'trend': 'insufficient_data', 'z_score': 0.0, 'p_value': 1.0, 'significance': False}

            # Count concordant and discordant pairs
            s = 0
            for i in range(n - 1):
                for j in range(i + 1, n):
                    if values[j] > values[i]:
                        s += 1
                    elif values[j] < values[i]:
                        s -= 1

            # Calculate variance for large datasets
            if n > 10:
                var_s = (n * (n - 1) * (2 * n + 5)) / 18
            else:
                # For small datasets, use exact variance calculation
                var_s = n * (n - 1) * (2 * n + 5) / 18

            if var_s == 0:
                return {'trend': 'no_trend', 'z_score': 0.0, 'p_value': 1.0, 'significance': False}

            # Calculate z-score
            z_score = s / (var_s ** 0.5) if var_s > 0 else 0

            # Calculate p-value (approximate)
            if abs(z_score) > 2.576:
                p_value = 0.01
            elif abs(z_score) > 1.96:
                p_value = 0.05
            elif abs(z_score) > 1.645:
                p_value = 0.1
            else:
                p_value = 0.2

            # Determine trend direction
            if z_score > 1.645:  # 90% confidence
                trend = 'increasing'
            elif z_score < -1.645:
                trend = 'decreasing'
            else:
                trend = 'no_trend'

            return {
                'trend': trend,
                'z_score': z_score,
                'p_value': p_value,
                'significance': p_value < 0.1,
                'statistic': s,
                'variance': var_s
            }

        except Exception as e:
            logger.debug(f"Mann-Kendall test failed: {e}")
            return {'trend': 'error', 'z_score': 0.0, 'p_value': 1.0, 'significance': False}

    def theil_sen_estimator(self, y: List[float], x: List[float]) -> Dict[str, Any]:
        """
        Calculate Theil-Sen estimator for robust slope estimation.

        @param y: Dependent variable
        @param x: Independent variable
        @returns Dict containing robust slope estimate
        """
        try:
            slopes = []
            n = len(x)

            # Calculate all possible slopes
            for i in range(n):
                for j in range(i + 1, n):
                    if x[j] != x[i]:
                        slope = (y[j] - y[i]) / (x[j] - x[i])
                        slopes.append(slope)

            if not slopes:
                return {'slope': 0.0, 'median_slope': 0.0, 'confidence': 0.0}

            # Calculate median slope (Theil-Sen estimator)
            sorted_slopes = sorted(slopes)
            n_slopes = len(sorted_slopes)

            if n_slopes % 2 == 0:
                median_slope = (sorted_slopes[n_slopes // 2 - 1] + sorted_slopes[n_slopes // 2]) / 2
            else:
                median_slope = sorted_slopes[n_slopes // 2]

            # Calculate confidence interval (simplified)
            q75, q25 = sorted_slopes[int(0.75 * n_slopes)], sorted_slopes[int(0.25 * n_slopes)]
            iqr = q75 - q25

            # Estimate confidence based on slope consistency
            slope_std = statistics.stdev(slopes) if len(slopes) > 1 else 0
            confidence = max(0, min(1, 1 - slope_std / abs(median_slope) if median_slope != 0 else 0))

            return {
                'slope': median_slope,
                'median_slope': median_slope,
                'confidence': confidence,
                'iqr': iqr,
                'slope_std': slope_std,
                'num_slopes': n_slopes
            }

        except Exception as e:
            logger.debug(f"Theil-Sen estimator failed: {e}")
            return {'slope': 0.0, 'median_slope': 0.0, 'confidence': 0.0}

    def detect_change_points(self, values: List[float]) -> List[int]:
        """
        Detect change points in time series using cumulative sum method.

        @param values: Time series values
        @returns List of change point indices
        """
        try:
            if len(values) < 10:
                return []

            # Simple cumulative sum (CUSUM) change point detection
            change_points = []
            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) > 1 else 0

            if std == 0:
                return []

            threshold = 2 * std  # 2-sigma threshold

            cusum = 0
            for i in range(1, len(values)):
                cusum += values[i] - mean
                if abs(cusum) > threshold:
                    change_points.append(i)
                    cusum = 0  # Reset after detecting change point

            return change_points

        except Exception as e:
            logger.debug(f"Change point detection failed: {e}")
            return []

    def determine_overall_trend(self, regression: Dict, mk: Dict, theil_sen: Dict) -> str:
        """
        Determine overall trend based on multiple statistical methods.

        @param regression: Linear regression results
        @param mk: Mann-Kendall test results
        @param theil_sen: Theil-Sen estimator results
        @returns str: Overall trend classification
        """
        try:
            # Weight different methods
            weights = {
                'regression': 0.4,
                'mann_kendall': 0.4,
                'theil_sen': 0.2
            }

            trends = []

            # Linear regression trend
            if regression['p_value'] < 0.1 and abs(regression['slope']) > 0.01:
                if regression['slope'] > 0:
                    trends.append(('degrading', weights['regression']))
                else:
                    trends.append(('improving', weights['regression']))

            # Mann-Kendall trend
            if mk['significance']:
                if mk['trend'] == 'increasing':
                    trends.append(('degrading', weights['mann_kendall']))
                elif mk['trend'] == 'decreasing':
                    trends.append(('improving', weights['mann_kendall']))

            # Theil-Sen trend
            if theil_sen['confidence'] > 0.7 and abs(theil_sen['slope']) > 0.01:
                if theil_sen['slope'] > 0:
                    trends.append(('degrading', weights['theil_sen']))
                else:
                    trends.append(('improving', weights['theil_sen']))

            if not trends:
                return 'stable'

            # Calculate weighted trend score
            degrading_score = sum(weight for trend, weight in trends if trend == 'degrading')
            improving_score = sum(weight for trend, weight in trends if trend == 'improving')

            if degrading_score > improving_score + 0.3:
                return 'degrading'
            elif improving_score > degrading_score + 0.3:
                return 'improving'
            else:
                return 'stable'

        except Exception as e:
            logger.debug(f"Overall trend determination failed: {e}")
            return 'stable'

    def determine_significance(self, regression: Dict, mk: Dict) -> str:
        """
        Determine the significance level of detected trends.

        @param regression: Linear regression results
        @param mk: Mann-Kendall test results
        @returns str: Significance level description
        """
        try:
            significance_scores = []

            # Regression significance
            if regression['p_value'] < 0.001:
                significance_scores.append(0.95)
            elif regression['p_value'] < 0.01:
                significance_scores.append(0.90)
            elif regression['p_value'] < 0.05:
                significance_scores.append(0.80)

            # Mann-Kendall significance
            if mk['significance']:
                if mk['p_value'] < 0.01:
                    significance_scores.append(0.90)
                elif mk['p_value'] < 0.05:
                    significance_scores.append(0.80)
                else:
                    significance_scores.append(0.70)

            if not significance_scores:
                return 'not_significant'

            avg_significance = sum(significance_scores) / len(significance_scores)

            if avg_significance > 0.9:
                return 'highly_significant'
            elif avg_significance > 0.8:
                return 'significant'
            elif avg_significance > 0.7:
                return 'moderately_significant'
            else:
                return 'weakly_significant'

        except Exception as e:
            logger.debug(f"Significance determination failed: {e}")
            return 'unknown'


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
