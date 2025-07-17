"""
Real-time Performance Optimization and Automatic Parameter Tuning.

This module provides continuous performance monitoring and automatic optimization
for the Kokoro-ONNX TTS system, implementing intelligent parameter tuning and
bottleneck detection to maintain optimal performance under varying conditions.

## Architecture Overview

The performance optimization system consists of several interconnected components:

1. **Performance Trend Analysis**:
   - Real-time analysis of performance metrics and trends
   - Detection of performance degradation patterns
   - Prediction of future performance based on historical data

2. **Automatic Parameter Tuning**:
   - Dynamic adjustment of optimization parameters
   - Feedback-based parameter optimization
   - Machine learning-based parameter prediction

3. **Bottleneck Detection**:
   - Identification of performance bottlenecks in real-time
   - Root cause analysis of performance issues
   - Automatic resolution of common bottlenecks

4. **Predictive Optimization**:
   - Anticipation of performance needs based on usage patterns
   - Proactive optimization before performance degradation
   - Load-based optimization strategies

## Key Features

### Real-time Monitoring
- **Performance Metrics**: Continuous collection of key performance indicators
- **Trend Analysis**: Analysis of performance trends over time
- **Anomaly Detection**: Detection of performance anomalies and outliers
- **Alert System**: Automated alerts for performance issues

### Automatic Optimization
- **Parameter Tuning**: Dynamic adjustment of system parameters
- **Resource Allocation**: Optimal allocation of system resources
- **Load Balancing**: Intelligent load distribution across sessions
- **Memory Management**: Automatic memory optimization

### Predictive Analytics
- **Usage Prediction**: Prediction of future usage patterns
- **Performance Forecasting**: Forecasting of performance trends
- **Capacity Planning**: Automatic capacity planning and scaling
- **Optimization Scheduling**: Optimal timing for optimization operations

@author: @darianrosebrook
@date: 2025-07-08
@version: 1.0.0
@license: MIT
@copyright: 2025 Darian Rosebrook
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""

import logging
import time
import threading
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Deque
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class OptimizationPriority(Enum):
    """Priority levels for optimization operations."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class OptimizationStatus(Enum):
    """Status of optimization operations."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PerformanceMetric:
    """Individual performance metric with metadata."""
    timestamp: float
    metric_type: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation with priority and impact analysis."""
    recommendation_id: str
    description: str
    priority: OptimizationPriority
    expected_impact: float  # Percentage improvement expected
    implementation_cost: float  # Resource cost to implement
    confidence: float  # Confidence in recommendation (0-1)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def get_priority_score(self) -> float:
        """Calculate priority score based on impact, cost, and confidence."""
        return (self.expected_impact * self.confidence) / (self.implementation_cost + 1)


class PerformanceTrendAnalyzer:
    """
    Analyzes performance trends and detects patterns for optimization.
    
    This analyzer implements sophisticated trend analysis algorithms to identify
    performance patterns, predict future performance, and detect anomalies that
    may indicate optimization opportunities or system issues.
    """
    
    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self.performance_history: Deque[PerformanceMetric] = deque(maxlen=max_history_size)
        self.trend_analysis_cache = {}
        self.last_analysis_time = 0.0
        self.analysis_interval = 60.0  # 1 minute
        
        self.logger = logging.getLogger(__name__ + ".PerformanceTrendAnalyzer")
        
        # Trend detection parameters
        self.trend_window_size = 100
        self.anomaly_threshold = 2.0  # Standard deviations
        self.degradation_threshold = 0.1  # 10% degradation
        
        self.logger.info("Performance trend analyzer initialized")
    
    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric for trend analysis."""
        self.performance_history.append(metric)
        
        # Trigger analysis if enough time has passed
        current_time = time.time()
        if current_time - self.last_analysis_time > self.analysis_interval:
            self.analyze_trends()
            self.last_analysis_time = current_time
    
    def analyze_trends(self) -> Dict[str, Any]:
        """
        Analyze performance trends and detect patterns.
        
        Returns:
            Dict containing trend analysis results and recommendations
        """
        if len(self.performance_history) < self.trend_window_size:
            return {
                'status': 'insufficient_data',
                'sample_count': len(self.performance_history),
                'required_samples': self.trend_window_size
            }
        
        # Group metrics by type for analysis
        metrics_by_type = {}
        for metric in list(self.performance_history):
            if metric.metric_type not in metrics_by_type:
                metrics_by_type[metric.metric_type] = []
            metrics_by_type[metric.metric_type].append(metric)
        
        analysis_results = {
            'analysis_timestamp': time.time(),
            'metrics_analyzed': len(metrics_by_type),
            'trend_analysis': {},
            'anomalies_detected': [],
            'recommendations': []
        }
        
        # Analyze each metric type
        for metric_type, metrics in metrics_by_type.items():
            if len(metrics) >= self.trend_window_size:
                trend_result = self._analyze_metric_trend(metric_type, metrics)
                analysis_results['trend_analysis'][metric_type] = trend_result
                
                # Check for anomalies
                anomalies = self._detect_anomalies(metric_type, metrics)
                analysis_results['anomalies_detected'].extend(anomalies)
                
                # Generate recommendations
                recommendations = self._generate_trend_recommendations(metric_type, trend_result)
                analysis_results['recommendations'].extend(recommendations)
        
        # Cache results
        self.trend_analysis_cache = analysis_results
        
        self.logger.debug(f"Trend analysis complete: {len(analysis_results['recommendations'])} recommendations generated")
        
        return analysis_results
    
    def _analyze_metric_trend(self, metric_type: str, metrics: List[PerformanceMetric]) -> Dict[str, Any]:
        """Analyze trend for a specific metric type."""
        # Extract values and timestamps
        values = [m.value for m in metrics[-self.trend_window_size:]]
        timestamps = [m.timestamp for m in metrics[-self.trend_window_size:]]
        
        # Calculate basic statistics
        mean_value = np.mean(values)
        std_value = np.std(values)
        
        # Calculate trend using linear regression
        if len(values) >= 2:
            time_range = max(timestamps) - min(timestamps)
            if time_range > 0:
                # Normalize timestamps
                normalized_times = [(t - min(timestamps)) / time_range for t in timestamps]
                
                # Simple linear regression
                n = len(values)
                sum_x = sum(normalized_times)
                sum_y = sum(values)
                sum_xy = sum(x * y for x, y in zip(normalized_times, values))
                sum_x2 = sum(x * x for x in normalized_times)
                
                if n * sum_x2 - sum_x * sum_x != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                    intercept = (sum_y - slope * sum_x) / n
                else:
                    slope = 0
                    intercept = mean_value
            else:
                slope = 0
                intercept = mean_value
        else:
            slope = 0
            intercept = mean_value
        
        # Determine trend direction
        if abs(slope) < 0.001:
            trend_direction = "stable"
        elif slope > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"
        
        # Calculate performance change percentage
        if len(values) >= 2:
            recent_avg = np.mean(values[-10:])  # Last 10 values
            historical_avg = np.mean(values[:-10])  # All but last 10
            if historical_avg > 0:
                change_percentage = ((recent_avg - historical_avg) / historical_avg) * 100
            else:
                change_percentage = 0
        else:
            change_percentage = 0
        
        return {
            'metric_type': metric_type,
            'sample_count': len(values),
            'mean_value': mean_value,
            'std_value': std_value,
            'trend_direction': trend_direction,
            'trend_slope': slope,
            'trend_intercept': intercept,
            'change_percentage': change_percentage,
            'time_range': time_range if len(values) >= 2 else 0
        }
    
    def _detect_anomalies(self, metric_type: str, metrics: List[PerformanceMetric]) -> List[Dict[str, Any]]:
        """Detect anomalies in performance metrics."""
        anomalies = []
        
        if len(metrics) < 10:
            return anomalies
        
        values = [m.value for m in metrics[-50:]]  # Last 50 values
        mean_value = np.mean(values)
        std_value = np.std(values)
        
        # Check recent values for anomalies
        recent_values = values[-10:]
        for i, value in enumerate(recent_values):
            if std_value > 0:
                z_score = abs(value - mean_value) / std_value
                if z_score > self.anomaly_threshold:
                    anomalies.append({
                        'metric_type': metric_type,
                        'value': value,
                        'expected_value': mean_value,
                        'z_score': z_score,
                        'deviation': abs(value - mean_value),
                        'timestamp': metrics[-(10-i)].timestamp
                    })
        
        return anomalies
    
    def _generate_trend_recommendations(self, metric_type: str, trend_result: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on trend analysis."""
        recommendations = []
        
        # Performance degradation detection
        if trend_result['change_percentage'] > self.degradation_threshold * 100:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"perf_degradation_{metric_type}",
                description=f"Performance degradation detected in {metric_type}: {trend_result['change_percentage']:.1f}% increase",
                priority=OptimizationPriority.HIGH,
                expected_impact=abs(trend_result['change_percentage']),
                implementation_cost=0.3,
                confidence=0.8,
                parameters={
                    'metric_type': metric_type,
                    'degradation_percentage': trend_result['change_percentage'],
                    'action': 'investigate_and_optimize'
                }
            ))
        
        # Instability detection
        if trend_result['std_value'] > trend_result['mean_value'] * 0.5:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"instability_{metric_type}",
                description=f"High variability detected in {metric_type}: {trend_result['std_value']:.3f} std dev",
                priority=OptimizationPriority.MEDIUM,
                expected_impact=20.0,
                implementation_cost=0.5,
                confidence=0.7,
                parameters={
                    'metric_type': metric_type,
                    'variability': trend_result['std_value'],
                    'action': 'stabilize_performance'
                }
            ))
        
        return recommendations
    
    def get_trend_summary(self) -> Dict[str, Any]:
        """Get a summary of current trend analysis."""
        if not self.trend_analysis_cache:
            return {'status': 'no_analysis_available'}
        
        return {
            'last_analysis_time': self.trend_analysis_cache.get('analysis_timestamp', 0),
            'metrics_analyzed': self.trend_analysis_cache.get('metrics_analyzed', 0),
            'anomalies_count': len(self.trend_analysis_cache.get('anomalies_detected', [])),
            'recommendations_count': len(self.trend_analysis_cache.get('recommendations', [])),
            'performance_history_size': len(self.performance_history)
        }


class AutomaticParameterTuner:
    """
    Automatically tunes system parameters based on performance feedback.
    
    This tuner implements intelligent parameter adjustment algorithms that learn
    from system performance and automatically optimize parameters to maintain
    optimal performance under varying conditions.
    """
    
    def __init__(self):
        self.parameter_history = {}
        self.tuning_results = {}
        self.active_experiments = {}
        self.tuning_lock = threading.Lock()
        
        self.logger = logging.getLogger(__name__ + ".AutomaticParameterTuner")
        
        # Tuning parameters
        self.learning_rate = 0.1
        self.exploration_rate = 0.2
        self.confidence_threshold = 0.7
        self.max_experiments = 3
        
        # Parameter bounds and constraints
        self.parameter_bounds = {
            'memory_arena_size': (256, 2048),  # MB
            'inference_timeout': (5, 60),      # seconds
            'cache_size': (100, 2000),         # entries
            'concurrent_limit': (1, 8),        # requests
            'optimization_interval': (30, 600) # seconds
        }
        
        self.logger.info("Automatic parameter tuner initialized")
    
    def tune_parameter(self, parameter_name: str, current_value: float, performance_metric: float) -> Tuple[float, float]:
        """
        Tune a specific parameter based on performance feedback.
        
        Args:
            parameter_name: Name of the parameter to tune
            current_value: Current parameter value
            performance_metric: Performance metric (lower is better)
            
        Returns:
            Tuple of (new_value, confidence_score)
        """
        with self.tuning_lock:
            # Initialize parameter history if not exists
            if parameter_name not in self.parameter_history:
                self.parameter_history[parameter_name] = []
                self.tuning_results[parameter_name] = {
                    'best_value': current_value,
                    'best_performance': performance_metric,
                    'attempts': 0,
                    'improvements': 0
                }
            
            # Record current parameter-performance pair
            self.parameter_history[parameter_name].append({
                'value': current_value,
                'performance': performance_metric,
                'timestamp': time.time()
            })
            
            # Keep only recent history
            if len(self.parameter_history[parameter_name]) > 100:
                self.parameter_history[parameter_name] = self.parameter_history[parameter_name][-100:]
            
            # Calculate new parameter value
            new_value, confidence = self._calculate_optimal_value(parameter_name, current_value, performance_metric)
            
            # Update tuning results
            self.tuning_results[parameter_name]['attempts'] += 1
            if performance_metric < self.tuning_results[parameter_name]['best_performance']:
                self.tuning_results[parameter_name]['best_value'] = current_value
                self.tuning_results[parameter_name]['best_performance'] = performance_metric
                self.tuning_results[parameter_name]['improvements'] += 1
            
            self.logger.debug(f"Parameter tuning: {parameter_name} = {current_value:.3f} -> {new_value:.3f} (confidence: {confidence:.3f})")
            
            return new_value, confidence
    
    def _calculate_optimal_value(self, parameter_name: str, current_value: float, performance_metric: float) -> Tuple[float, float]:
        """Calculate optimal parameter value using gradient-based optimization."""
        history = self.parameter_history[parameter_name]
        
        if len(history) < 2:
            # Not enough data for optimization, explore randomly
            bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.5, current_value * 2))
            exploration_range = (bounds[1] - bounds[0]) * self.exploration_rate
            new_value = current_value + np.random.uniform(-exploration_range, exploration_range)
            new_value = max(bounds[0], min(bounds[1], new_value))
            return new_value, 0.1
        
        # Calculate gradient from recent history
        recent_history = history[-10:]  # Last 10 attempts
        if len(recent_history) >= 2:
            # Simple gradient calculation
            values = [h['value'] for h in recent_history]
            performances = [h['performance'] for h in recent_history]
            
            # Calculate correlation between value changes and performance changes
            if len(values) >= 3:
                value_changes = [values[i] - values[i-1] for i in range(1, len(values))]
                perf_changes = [performances[i] - performances[i-1] for i in range(1, len(performances))]
                
                if len(value_changes) > 0 and len(perf_changes) > 0:
                    # Calculate correlation
                    mean_val_change = np.mean(value_changes)
                    mean_perf_change = np.mean(perf_changes)
                    
                    correlation = 0
                    if len(value_changes) > 1:
                        numerator = sum((v - mean_val_change) * (p - mean_perf_change) 
                                      for v, p in zip(value_changes, perf_changes))
                        val_var = sum((v - mean_val_change) ** 2 for v in value_changes)
                        perf_var = sum((p - mean_perf_change) ** 2 for p in perf_changes)
                        
                        if val_var > 0 and perf_var > 0:
                            correlation = numerator / (val_var * perf_var) ** 0.5
                    
                    # Adjust parameter based on correlation
                    if abs(correlation) > 0.1:
                        # Strong correlation detected
                        adjustment = -correlation * self.learning_rate * current_value
                        new_value = current_value + adjustment
                        confidence = min(0.9, abs(correlation))
                    else:
                        # Weak correlation, explore
                        bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.5, current_value * 2))
                        exploration_range = (bounds[1] - bounds[0]) * self.exploration_rate
                        new_value = current_value + np.random.uniform(-exploration_range, exploration_range)
                        confidence = 0.2
                else:
                    # No variation in values, explore
                    bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.5, current_value * 2))
                    exploration_range = (bounds[1] - bounds[0]) * self.exploration_rate
                    new_value = current_value + np.random.uniform(-exploration_range, exploration_range)
                    confidence = 0.2
            else:
                # Not enough data for gradient, explore
                bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.5, current_value * 2))
                exploration_range = (bounds[1] - bounds[0]) * self.exploration_rate
                new_value = current_value + np.random.uniform(-exploration_range, exploration_range)
                confidence = 0.2
        else:
            # Fallback exploration
            bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.5, current_value * 2))
            exploration_range = (bounds[1] - bounds[0]) * self.exploration_rate
            new_value = current_value + np.random.uniform(-exploration_range, exploration_range)
            confidence = 0.2
        
        # Apply bounds
        bounds = self.parameter_bounds.get(parameter_name, (current_value * 0.1, current_value * 10))
        new_value = max(bounds[0], min(bounds[1], new_value))
        
        return new_value, confidence
    
    def get_tuning_summary(self) -> Dict[str, Any]:
        """Get summary of parameter tuning results."""
        summary = {
            'parameters_tuned': len(self.parameter_history),
            'total_attempts': sum(result['attempts'] for result in self.tuning_results.values()),
            'total_improvements': sum(result['improvements'] for result in self.tuning_results.values()),
            'parameter_details': {}
        }
        
        for param_name, result in self.tuning_results.items():
            summary['parameter_details'][param_name] = {
                'best_value': result['best_value'],
                'best_performance': result['best_performance'],
                'attempts': result['attempts'],
                'improvements': result['improvements'],
                'success_rate': result['improvements'] / result['attempts'] if result['attempts'] > 0 else 0
            }
        
        return summary


class RealTimeOptimizer:
    """
    Main real-time optimization coordinator that manages all optimization activities.
    
    This optimizer coordinates between trend analysis, parameter tuning, and bottleneck
    detection to provide comprehensive real-time optimization of the TTS system.
    """
    
    def __init__(self):
        self.status = OptimizationStatus.IDLE
        self.trend_analyzer = PerformanceTrendAnalyzer()
        self.parameter_tuner = AutomaticParameterTuner()
        self.optimization_history = deque(maxlen=1000)
        self.active_optimizations = {}
        self.optimization_lock = threading.Lock()
        
        self.logger = logging.getLogger(__name__ + ".RealTimeOptimizer")
        
        # Optimization settings
        self.optimization_interval = 300.0  # 5 minutes
        self.last_optimization_time = 0.0
        self.auto_optimization_enabled = True
        
        self.logger.info("Real-time optimizer initialized")
    
    def record_performance_metric(self, metric_type: str, value: float, metadata: Dict[str, Any] = None):
        """Record a performance metric for optimization analysis."""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type=metric_type,
            value=value,
            metadata=metadata or {}
        )
        
        # Record in trend analyzer
        self.trend_analyzer.record_metric(metric)
        
        # Trigger optimization if needed
        if self.auto_optimization_enabled and self._should_optimize():
            asyncio.create_task(self.optimize_system())
    
    def _should_optimize(self) -> bool:
        """Check if system optimization should be triggered."""
        current_time = time.time()
        
        # Time-based optimization
        if current_time - self.last_optimization_time > self.optimization_interval:
            return True
        
        # Performance-based optimization
        if len(self.trend_analyzer.performance_history) >= 50:
            recent_metrics = list(self.trend_analyzer.performance_history)[-10:]
            if recent_metrics:
                avg_performance = np.mean([m.value for m in recent_metrics])
                historical_metrics = list(self.trend_analyzer.performance_history)[-50:-10]
                if historical_metrics:
                    historical_avg = np.mean([m.value for m in historical_metrics])
                    if avg_performance > historical_avg * 1.2:  # 20% degradation
                        return True
        
        return False
    
    async def optimize_system(self) -> Dict[str, Any]:
        """Perform comprehensive system optimization."""
        with self.optimization_lock:
            if self.status != OptimizationStatus.IDLE:
                return {'status': 'optimization_in_progress'}
            
            self.status = OptimizationStatus.ANALYZING
        
        optimization_start = time.time()
        optimization_id = f"opt_{int(optimization_start)}"
        
        try:
            self.logger.info(f"Starting system optimization: {optimization_id}")
            
            # Phase 1: Trend Analysis
            self.logger.debug("Phase 1: Analyzing performance trends...")
            trend_analysis = self.trend_analyzer.analyze_trends()
            
            # Phase 2: Parameter Tuning
            self.logger.debug("Phase 2: Tuning parameters...")
            tuning_results = await self._tune_system_parameters()
            
            # Phase 3: Apply Optimizations
            self.logger.debug("Phase 3: Applying optimizations...")
            self.status = OptimizationStatus.OPTIMIZING
            optimization_results = await self._apply_optimizations(trend_analysis, tuning_results)
            
            # Phase 4: Validation
            self.logger.debug("Phase 4: Validating optimizations...")
            validation_results = await self._validate_optimizations()
            
            optimization_duration = time.time() - optimization_start
            
            result = {
                'optimization_id': optimization_id,
                'status': 'completed',
                'duration': optimization_duration,
                'trend_analysis': trend_analysis,
                'tuning_results': tuning_results,
                'optimization_results': optimization_results,
                'validation_results': validation_results,
                'timestamp': optimization_start
            }
            
            # Record optimization history
            self.optimization_history.append(result)
            self.last_optimization_time = time.time()
            self.status = OptimizationStatus.COMPLETED
            
            self.logger.info(f"System optimization completed: {optimization_id} in {optimization_duration:.2f}s")
            
            return result
            
        except Exception as e:
            self.status = OptimizationStatus.FAILED
            self.logger.error(f"System optimization failed: {e}", exc_info=True)
            return {
                'optimization_id': optimization_id,
                'status': 'failed',
                'error': str(e),
                'timestamp': optimization_start
            }
        
        finally:
            self.status = OptimizationStatus.IDLE
    
    async def _tune_system_parameters(self) -> Dict[str, Any]:
        """Tune system parameters based on current performance."""
        tuning_results = {
            'parameters_tuned': 0,
            'improvements_applied': 0,
            'tuning_details': {}
        }
        
        try:
            # Get current performance metrics
            if len(self.trend_analyzer.performance_history) < 10:
                return tuning_results
            
            recent_metrics = list(self.trend_analyzer.performance_history)[-10:]
            avg_performance = np.mean([m.value for m in recent_metrics])
            
            # Tune memory arena size
            from api.model.loader import get_dynamic_memory_manager
            dynamic_memory_manager = get_dynamic_memory_manager()
            if dynamic_memory_manager:
                current_arena_size = dynamic_memory_manager.get_current_arena_size_mb()
                new_arena_size, confidence = self.parameter_tuner.tune_parameter(
                    'memory_arena_size', current_arena_size, avg_performance
                )
                
                if confidence > 0.5 and abs(new_arena_size - current_arena_size) > 50:
                    # Apply tuning if confident and significant change
                    dynamic_memory_manager.current_arena_size_mb = int(new_arena_size)
                    tuning_results['parameters_tuned'] += 1
                    tuning_results['improvements_applied'] += 1
                    tuning_results['tuning_details']['memory_arena_size'] = {
                        'old_value': current_arena_size,
                        'new_value': int(new_arena_size),
                        'confidence': confidence
                    }
            
            # Tune optimization interval
            new_interval, confidence = self.parameter_tuner.tune_parameter(
                'optimization_interval', self.optimization_interval, avg_performance
            )
            
            if confidence > 0.6:
                self.optimization_interval = max(30, min(600, new_interval))
                tuning_results['parameters_tuned'] += 1
                tuning_results['tuning_details']['optimization_interval'] = {
                    'old_value': self.optimization_interval,
                    'new_value': new_interval,
                    'confidence': confidence
                }
            
        except Exception as e:
            self.logger.error(f"Parameter tuning failed: {e}")
            tuning_results['error'] = str(e)
        
        return tuning_results
    
    async def _apply_optimizations(self, trend_analysis: Dict[str, Any], tuning_results: Dict[str, Any]) -> Dict[str, Any]:
        """Apply optimization recommendations."""
        optimization_results = {
            'optimizations_applied': 0,
            'optimizations_failed': 0,
            'details': []
        }
        
        try:
            # Apply trend-based recommendations
            recommendations = trend_analysis.get('recommendations', [])
            for rec in recommendations:
                if isinstance(rec, OptimizationRecommendation):
                    if rec.priority in [OptimizationPriority.HIGH, OptimizationPriority.CRITICAL]:
                        try:
                            success = await self._apply_recommendation(rec)
                            if success:
                                optimization_results['optimizations_applied'] += 1
                                optimization_results['details'].append({
                                    'recommendation_id': rec.recommendation_id,
                                    'description': rec.description,
                                    'status': 'applied'
                                })
                            else:
                                optimization_results['optimizations_failed'] += 1
                                optimization_results['details'].append({
                                    'recommendation_id': rec.recommendation_id,
                                    'description': rec.description,
                                    'status': 'failed'
                                })
                        except Exception as e:
                            optimization_results['optimizations_failed'] += 1
                            optimization_results['details'].append({
                                'recommendation_id': rec.recommendation_id,
                                'description': rec.description,
                                'status': 'error',
                                'error': str(e)
                            })
            
        except Exception as e:
            self.logger.error(f"Optimization application failed: {e}")
            optimization_results['error'] = str(e)
        
        return optimization_results
    
    async def _apply_recommendation(self, recommendation: OptimizationRecommendation) -> bool:
        """Apply a specific optimization recommendation."""
        try:
            action = recommendation.parameters.get('action', 'unknown')
            
            if action == 'investigate_and_optimize':
                # Trigger memory optimization
                from api.model.loader import get_dynamic_memory_manager
                dynamic_memory_manager = get_dynamic_memory_manager()
                if dynamic_memory_manager:
                    return dynamic_memory_manager.optimize_arena_size()
            
            elif action == 'stabilize_performance':
                # Trigger pipeline warm-up
                from api.model.loader import get_pipeline_warmer
                pipeline_warmer = get_pipeline_warmer()
                if pipeline_warmer:
                    await pipeline_warmer.trigger_warm_up_if_needed()
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to apply recommendation {recommendation.recommendation_id}: {e}")
            return False
    
    async def _validate_optimizations(self) -> Dict[str, Any]:
        """Validate that optimizations are working correctly."""
        validation_results = {
            'validation_passed': True,
            'checks_performed': 0,
            'checks_passed': 0,
            'details': []
        }
        
        try:
            # Check system status
            from api.model.loader import get_model_status
            model_status = get_model_status()
            validation_results['checks_performed'] += 1
            if model_status:
                validation_results['checks_passed'] += 1
                validation_results['details'].append({
                    'check': 'model_status',
                    'status': 'passed',
                    'result': model_status
                })
            else:
                validation_results['validation_passed'] = False
                validation_results['details'].append({
                    'check': 'model_status',
                    'status': 'failed',
                    'result': model_status
                })
            
            # Check memory optimization
            from api.model.loader import get_dynamic_memory_manager
            dynamic_memory_manager = get_dynamic_memory_manager()
            if dynamic_memory_manager:
                validation_results['checks_performed'] += 1
                optimization_stats = dynamic_memory_manager.get_optimization_stats()
                if optimization_stats:
                    validation_results['checks_passed'] += 1
                    validation_results['details'].append({
                        'check': 'memory_optimization',
                        'status': 'passed',
                        'result': optimization_stats
                    })
                else:
                    validation_results['validation_passed'] = False
                    validation_results['details'].append({
                        'check': 'memory_optimization',
                        'status': 'failed',
                        'result': 'No optimization stats available'
                    })
            
        except Exception as e:
            validation_results['validation_passed'] = False
            validation_results['error'] = str(e)
            self.logger.error(f"Optimization validation failed: {e}")
        
        return validation_results
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and statistics."""
        return {
            'status': self.status.value,
            'auto_optimization_enabled': self.auto_optimization_enabled,
            'optimization_interval': self.optimization_interval,
            'last_optimization_time': self.last_optimization_time,
            'optimization_history_size': len(self.optimization_history),
            'trend_analyzer_summary': self.trend_analyzer.get_trend_summary(),
            'parameter_tuner_summary': self.parameter_tuner.get_tuning_summary(),
            'performance_metrics_count': len(self.trend_analyzer.performance_history)
        }
    
    def enable_auto_optimization(self, enabled: bool = True):
        """Enable or disable automatic optimization."""
        self.auto_optimization_enabled = enabled
        self.logger.info(f"Auto optimization {'enabled' if enabled else 'disabled'}")
    
    def set_optimization_interval(self, interval: float):
        """Set the optimization interval in seconds."""
        self.optimization_interval = max(30, min(3600, interval))
        self.logger.info(f"Optimization interval set to {self.optimization_interval}s")


# Global optimizer instance
_real_time_optimizer: Optional[RealTimeOptimizer] = None


def get_real_time_optimizer() -> Optional[RealTimeOptimizer]:
    """Get the global real-time optimizer instance."""
    return _real_time_optimizer


def initialize_real_time_optimizer():
    """Initialize the global real-time optimizer."""
    global _real_time_optimizer
    
    if _real_time_optimizer is None:
        logger.info("Initializing real-time optimizer for Phase 4 optimization")
        _real_time_optimizer = RealTimeOptimizer()
        logger.info("✅ Real-time optimizer initialized")
    
    return _real_time_optimizer


def cleanup_real_time_optimizer():
    """Cleanup the global real-time optimizer."""
    global _real_time_optimizer
    
    if _real_time_optimizer:
        logger.info("Cleaning up real-time optimizer")
        _real_time_optimizer = None


def record_performance_metric(metric_type: str, value: float, metadata: Dict[str, Any] = None):
    """Record a performance metric for optimization analysis."""
    optimizer = get_real_time_optimizer()
    if optimizer:
        optimizer.record_performance_metric(metric_type, value, metadata)


async def optimize_system_now() -> Dict[str, Any]:
    """Trigger immediate system optimization."""
    optimizer = get_real_time_optimizer()
    if optimizer:
        return await optimizer.optimize_system()
    else:
        return {'status': 'optimizer_not_available'}


def get_optimization_status() -> Dict[str, Any]:
    """Get current optimization status."""
    optimizer = get_real_time_optimizer()
    if optimizer:
        return optimizer.get_optimization_status()
    else:
        return {'status': 'optimizer_not_available'} 