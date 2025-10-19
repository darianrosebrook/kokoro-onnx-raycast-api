"""
TTFA (Time to First Audio) Performance Monitoring System

This module provides comprehensive TTFA monitoring and real-time performance
analysis for the Kokoro-ONNX TTS system. It tracks bottlenecks across the
entire pipeline and provides actionable optimization recommendations.

## Key Features

1. **Real-Time TTFA Tracking**: Measure and monitor TTFA against targets
2. **Bottleneck Identification**: Identify specific pipeline bottlenecks  
3. **Performance Trending**: Track performance over time
4. **Automated Alerting**: Alert on target misses or degradation
5. **Optimization Recommendations**: Provide specific improvement suggestions

## TTFA Targets

- **Primary Target**: <800ms for all requests
- **Optimal Target**: <400ms for short text (<50 chars)
- **Critical Threshold**: >2000ms triggers immediate investigation

@author: @darianrosebrook
@date: 2025-08-15
@version: 1.0.0
@license: MIT
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import threading

logger = logging.getLogger(__name__)


@dataclass
class TTFAMeasurement:
    """Single TTFA measurement with detailed timing breakdown"""
    request_id: str
    timestamp: datetime
    text_length: int
    voice: str
    speed: float
    
    # Timing stages (all in milliseconds)
    text_processing_time: Optional[float] = None
    model_inference_time: Optional[float] = None
    audio_generation_time: Optional[float] = None
    first_chunk_delivery_time: Optional[float] = None
    daemon_communication_time: Optional[float] = None
    total_ttfa: Optional[float] = None
    
    # Performance indicators
    target_ttfa: float = 800.0
    achieved_target: bool = False
    bottlenecks: List[str] = field(default_factory=list)
    provider_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'request_id': self.request_id,
            'timestamp': self.timestamp.isoformat(),
            'text_length': self.text_length,
            'voice': self.voice,
            'speed': self.speed,
            'timings': {
                'text_processing_ms': self.text_processing_time,
                'model_inference_ms': self.model_inference_time,
                'audio_generation_ms': self.audio_generation_time,
                'first_chunk_delivery_ms': self.first_chunk_delivery_time,
                'daemon_communication_ms': self.daemon_communication_time,
                'total_ttfa_ms': self.total_ttfa
            },
            'performance': {
                'target_ttfa_ms': self.target_ttfa,
                'achieved_target': self.achieved_target,
                'bottlenecks': self.bottlenecks,
                'provider_used': self.provider_used
            }
        }


@dataclass
class TTFAStats:
    """TTFA performance statistics with advanced moving average calculations"""
    total_requests: int = 0
    successful_requests: int = 0
    target_achieved_count: int = 0

    # Timing statistics (milliseconds)
    average_ttfa: float = 0.0
    median_ttfa: float = 0.0
    p95_ttfa: float = 0.0
    p99_ttfa: float = 0.0

    # Advanced moving averages
    ema_ttfa: float = 0.0  # Exponential moving average
    wma_ttfa: float = 0.0  # Weighted moving average
    simple_ma_ttfa: float = 0.0  # Simple moving average

    # Moving average configuration
    ma_window_size: int = 50  # Configurable window size
    ema_alpha: float = 0.1  # EMA smoothing factor (0.1 = 10% new, 90% old)

    # Historical data for calculations
    recent_values: List[float] = field(default_factory=list)
    weighted_values: List[Tuple[float, float]] = field(default_factory=list)  # (value, weight)
    min_ttfa: float = float('inf')
    max_ttfa: float = 0.0

    # Recent performance (last 10 requests)
    recent_ttfa_values: List[float] = field(default_factory=list)

    @property
    def average_ttfa(self) -> float:
        """
        DEPRECATED: Use p50_ttfa instead.

        Backward compatibility property that returns p50_ttfa (median) as the "average".
        The old simple average is still maintained in _legacy_average_ttfa for migration.
        """
        import warnings
        warnings.warn(
            "average_ttfa is deprecated. Use p50_ttfa (median) for central tendency.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.median_ttfa  # p50 is more robust than simple average

    @average_ttfa.setter
    def average_ttfa(self, value: float) -> None:
        """Allow setting for backward compatibility, but log deprecation."""
        import warnings
        warnings.warn(
            "Setting average_ttfa is deprecated. Use statistical measures directly.",
            DeprecationWarning,
            stacklevel=2
        )
        # Store in legacy field for migration tracking
        self._legacy_average_ttfa = value

    def _update_moving_averages(self, new_value: float) -> None:
        """Update all moving average calculations with new value."""
        if not self.recent_values:
            # Initialize all averages with first value
            self.ema_ttfa = new_value
            self.wma_ttfa = new_value
            self.simple_ma_ttfa = new_value
            return

        # Exponential Moving Average (EMA)
        self.ema_ttfa = self.ema_alpha * new_value + (1 - self.ema_alpha) * self.ema_ttfa

        # Simple Moving Average (SMA)
        if len(self.recent_values) >= 2:
            self.simple_ma_ttfa = sum(self.recent_values[-min(len(self.recent_values), 10):]) / min(len(self.recent_values), 10)

        # Weighted Moving Average (WMA) - more recent values have higher weight
        if self.weighted_values:
            total_weight = sum(weight for _, weight in self.weighted_values)
            if total_weight > 0:
                self.wma_ttfa = sum(value * weight for value, weight in self.weighted_values) / total_weight

    def _update_statistical_measures(self) -> None:
        """Update statistical measures (median, percentiles) from recent values."""
        if not self.recent_values:
            return

        sorted_values = sorted(self.recent_values)

        # Median
        n = len(sorted_values)
        if n % 2 == 1:
            self.median_ttfa = sorted_values[n // 2]
        else:
            mid1, mid2 = sorted_values[n // 2 - 1], sorted_values[n // 2]
            self.median_ttfa = (mid1 + mid2) / 2

        # Percentiles (simple interpolation)
        def percentile(p: float) -> float:
            k = (len(sorted_values) - 1) * (p / 100)
            f = int(k)
            c = k - f
            if f + 1 < len(sorted_values):
                return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
            else:
                return sorted_values[f]

        self.p95_ttfa = percentile(95)
        self.p99_ttfa = percentile(99)

    def configure_moving_averages(self, window_size: int = 50, ema_alpha: float = 0.1) -> None:
        """Configure moving average parameters."""
        self.ma_window_size = max(5, window_size)  # Minimum window of 5
        self.ema_alpha = max(0.01, min(1.0, ema_alpha))  # Clamp to valid range

        # Trim existing data to new window size
        if len(self.recent_values) > self.ma_window_size:
            self.recent_values = self.recent_values[-self.ma_window_size:]
        if len(self.weighted_values) > self.ma_window_size:
            self.weighted_values = self.weighted_values[-self.ma_window_size:]

    def detect_performance_drift(self, threshold_factor: float = 1.5) -> Optional[Dict[str, Any]]:
        """Detect performance drift using moving average trends."""
        if len(self.recent_values) < 10:
            return None  # Need minimum data for drift detection

        # Compare recent EMA with overall average
        if self.average_ttfa > 0:
            drift_ratio = self.ema_ttfa / self.average_ttfa
            if drift_ratio > threshold_factor:
                return {
                    "drift_detected": True,
                    "drift_ratio": drift_ratio,
                    "ema_ttfa": self.ema_ttfa,
                    "average_ttfa": self.average_ttfa,
                    "severity": "high" if drift_ratio > 2.0 else "medium",
                    "recommendation": "Investigate recent performance degradation"
                }
            elif drift_ratio < (1 / threshold_factor):
                return {
                    "drift_detected": False,
                    "drift_ratio": drift_ratio,
                    "improvement_ratio": 1 / drift_ratio,
                    "message": "Performance improvement detected"
                }

        return None

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary with all metrics."""
        drift_info = self.detect_performance_drift()

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / max(1, self.total_requests),

            # Basic statistics
            "average_ttfa": self.average_ttfa,
            "median_ttfa": self.median_ttfa,
            "min_ttfa": self.min_ttfa if self.min_ttfa != float('inf') else 0,
            "max_ttfa": self.max_ttfa,

            # Percentiles
            "p95_ttfa": self.p95_ttfa,
            "p99_ttfa": self.p99_ttfa,

            # Moving averages
            "ema_ttfa": self.ema_ttfa,
            "wma_ttfa": self.wma_ttfa,
            "simple_ma_ttfa": self.simple_ma_ttfa,

            # Configuration
            "ma_window_size": self.ma_window_size,
            "ema_alpha": self.ema_alpha,

            # Performance analysis
            "drift_analysis": drift_info,
            "data_points": len(self.recent_values)
        }
    
    def update(self, ttfa_ms: float):
        """Update statistics with new TTFA measurement"""
        self.total_requests += 1
        if ttfa_ms > 0:
            self.successful_requests += 1
            
            # Update min/max
            self.min_ttfa = min(self.min_ttfa, ttfa_ms)
            self.max_ttfa = max(self.max_ttfa, ttfa_ms)
            
            # Track recent values for statistical calculations
            self.recent_values.append(ttfa_ms)
            if len(self.recent_values) > self.ma_window_size:
                self.recent_values.pop(0)

            # Add weighted value (more recent = higher weight)
            weight = time.time()  # Use timestamp as weight for recency
            self.weighted_values.append((ttfa_ms, weight))
            if len(self.weighted_values) > self.ma_window_size:
                self.weighted_values.pop(0)

            # Update min/max
            self.min_ttfa = min(self.min_ttfa, ttfa_ms)
            self.max_ttfa = max(self.max_ttfa, ttfa_ms)

            # Calculate moving averages
            self._update_moving_averages(ttfa_ms)

            # Calculate statistical measures
            self._update_statistical_measures()

            # Migration from legacy simple average to statistical measures
            # DEPRECATED: Legacy simple averaging - use p50_ttfa instead
            import warnings
            warnings.warn(
                "Simple average TTFA calculation is deprecated. Use p50_ttfa or p95_ttfa instead.",
                DeprecationWarning,
                stacklevel=2
            )

            # Legacy support for backward compatibility (will be removed in future version)
            if hasattr(self, '_total_ttfa'):
                self._total_ttfa += ttfa_ms
                self.average_ttfa = self._total_ttfa / self.successful_requests
            else:
                self._total_ttfa = ttfa_ms
                self.average_ttfa = ttfa_ms


class TTFAMonitor:
    """
    Comprehensive TTFA monitoring and performance analysis system
    """
    
    def __init__(self, target_ttfa_ms: float = 800.0):
        self.target_ttfa_ms = target_ttfa_ms
        self.measurements: List[TTFAMeasurement] = []
        self.stats = TTFAStats()
        self.alert_callbacks: List[Callable[[TTFAMeasurement], None]] = []
        self._lock = threading.Lock()
        
        # Performance thresholds
        self.optimal_ttfa_ms = 400.0  # For short text
        self.critical_ttfa_ms = 2000.0  # Triggers immediate alert
        
        logger.info(f"TTFA Monitor initialized - Target: {target_ttfa_ms}ms")
    
    def start_measurement(self, request_id: str, text: str, voice: str, speed: float) -> TTFAMeasurement:
        """
        Start a new TTFA measurement
        """
        # Determine target based on text length
        target_ttfa = self.optimal_ttfa_ms if len(text) < 50 else self.target_ttfa_ms
        
        measurement = TTFAMeasurement(
            request_id=request_id,
            timestamp=datetime.now(),
            text_length=len(text),
            voice=voice,
            speed=speed,
            target_ttfa=target_ttfa
        )
        
        with self._lock:
            self.measurements.append(measurement)
        
        logger.debug(f"[{request_id}] TTFA measurement started - Target: {target_ttfa}ms")
        return measurement
    
    def record_stage_timing(self, measurement: TTFAMeasurement, stage: str, time_ms: float):
        """
        Record timing for a specific pipeline stage
        """
        if stage == 'text_processing':
            measurement.text_processing_time = time_ms
        elif stage == 'model_inference':
            measurement.model_inference_time = time_ms
        elif stage == 'audio_generation':
            measurement.audio_generation_time = time_ms
        elif stage == 'first_chunk_delivery':
            measurement.first_chunk_delivery_time = time_ms
        elif stage == 'daemon_communication':
            measurement.daemon_communication_time = time_ms
        
        logger.debug(f"[{measurement.request_id}] {stage}: {time_ms:.2f}ms")
    
    def finalize_measurement(self, measurement: TTFAMeasurement, total_ttfa_ms: float, provider_used: str = None):
        """
        Finalize TTFA measurement and analyze performance
        """
        measurement.total_ttfa = total_ttfa_ms
        measurement.provider_used = provider_used
        measurement.achieved_target = total_ttfa_ms <= measurement.target_ttfa
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(measurement)
        measurement.bottlenecks = bottlenecks
        
        # Update statistics
        with self._lock:
            self.stats.update(total_ttfa_ms)
            if measurement.achieved_target:
                self.stats.target_achieved_count += 1
        
        # Log result
        status = "✅ TARGET ACHIEVED" if measurement.achieved_target else " TARGET MISSED"
        logger.info(
            f"[{measurement.request_id}] TTFA: {total_ttfa_ms:.2f}ms - {status} "
            f"(Target: {measurement.target_ttfa}ms)"
        )
        
        if bottlenecks:
            logger.warning(f"[{measurement.request_id}] Bottlenecks identified: {', '.join(bottlenecks)}")
        
        # Trigger alerts if needed
        if total_ttfa_ms > self.critical_ttfa_ms or not measurement.achieved_target:
            self._trigger_alerts(measurement)
        
        return measurement
    
    def _identify_bottlenecks(self, measurement: TTFAMeasurement) -> List[str]:
        """
        Identify performance bottlenecks in the pipeline
        """
        bottlenecks = []
        
        # Model inference bottleneck (>50% of target)
        if measurement.model_inference_time and measurement.model_inference_time > (measurement.target_ttfa * 0.5):
            bottlenecks.append(f"model_inference ({measurement.model_inference_time:.0f}ms)")
        
        # Audio generation bottleneck (>30% of target)
        if measurement.audio_generation_time and measurement.audio_generation_time > (measurement.target_ttfa * 0.3):
            bottlenecks.append(f"audio_generation ({measurement.audio_generation_time:.0f}ms)")
        
        # First chunk delivery bottleneck (>20% of target)
        if measurement.first_chunk_delivery_time and measurement.first_chunk_delivery_time > (measurement.target_ttfa * 0.2):
            bottlenecks.append(f"chunk_delivery ({measurement.first_chunk_delivery_time:.0f}ms)")
        
        # Daemon communication bottleneck (>100ms)
        if measurement.daemon_communication_time and measurement.daemon_communication_time > 100:
            bottlenecks.append(f"daemon_communication ({measurement.daemon_communication_time:.0f}ms)")
        
        return bottlenecks
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary
        """
        with self._lock:
            target_achievement_rate = (
                (self.stats.target_achieved_count / self.stats.successful_requests * 100)
                if self.stats.successful_requests > 0 else 0
            )
            
            recent_trend = "stable"
            if len(self.stats.recent_ttfa_values) >= 3:
                recent_avg = sum(self.stats.recent_ttfa_values[-3:]) / 3
                older_avg = sum(self.stats.recent_ttfa_values[-6:-3]) / 3 if len(self.stats.recent_ttfa_values) >= 6 else recent_avg
                
                if recent_avg > older_avg * 1.2:
                    recent_trend = "degrading"
                elif recent_avg < older_avg * 0.8:
                    recent_trend = "improving"
            
            return {
                'target_ttfa_ms': self.target_ttfa_ms,
                'performance': {
                    'total_requests': self.stats.total_requests,
                    'successful_requests': self.stats.successful_requests,
                    'target_achievement_rate_percent': round(target_achievement_rate, 1),
                    'recent_trend': recent_trend
                },
                'timing_stats_ms': {
                    'average': round(self.stats.average_ttfa, 1),
                    'min': round(self.stats.min_ttfa, 1) if self.stats.min_ttfa != float('inf') else None,
                    'max': round(self.stats.max_ttfa, 1),
                    'recent_values': [round(v, 1) for v in self.stats.recent_ttfa_values]
                },
                'recommendations': self._generate_recommendations()
            }
    
    def _generate_recommendations(self) -> List[Dict[str, str]]:
        """
        Generate optimization recommendations based on performance data
        """
        recommendations = []
        
        # Low target achievement rate
        target_rate = (self.stats.target_achieved_count / self.stats.successful_requests * 100) if self.stats.successful_requests > 0 else 0
        if target_rate < 80:
            recommendations.append({
                'type': 'critical',
                'message': f'Target achievement rate is only {target_rate:.1f}%. Consider enabling aggressive optimization.',
                'action': 'Enable fast processing for all first segments'
            })
        
        # High average TTFA
        if self.stats.average_ttfa > self.target_ttfa_ms * 1.5:
            recommendations.append({
                'type': 'warning',
                'message': f'Average TTFA ({self.stats.average_ttfa:.1f}ms) is significantly above target.',
                'action': 'Review session routing and consider model optimization'
            })
        
        # Degrading trend
        if len(self.stats.recent_ttfa_values) >= 3:
            recent_avg = sum(self.stats.recent_ttfa_values[-3:]) / 3
            if recent_avg > self.target_ttfa_ms * 1.2:
                recommendations.append({
                    'type': 'warning',
                    'message': 'Recent performance shows degradation.',
                    'action': 'Check system load and memory usage'
                })
        
        # Good performance
        if target_rate >= 90 and self.stats.average_ttfa <= self.target_ttfa_ms:
            recommendations.append({
                'type': 'success',
                'message': 'TTFA performance is meeting targets consistently.',
                'action': 'Continue monitoring for any degradation'
            })
        
        return recommendations
    
    def add_alert_callback(self, callback: Callable[[TTFAMeasurement], None]):
        """
        Add callback to be triggered on performance alerts
        """
        self.alert_callbacks.append(callback)
    
    def _trigger_alerts(self, measurement: TTFAMeasurement):
        """
        Trigger performance alerts
        """
        for callback in self.alert_callbacks:
            try:
                callback(measurement)
            except Exception as e:
                logger.error(f"Error in TTFA alert callback: {e}")
    
    def export_measurements(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Export recent measurements for analysis
        """
        with self._lock:
            recent_measurements = self.measurements[-limit:] if limit else self.measurements
            return [m.to_dict() for m in recent_measurements]


# Global TTFA monitor instance
_ttfa_monitor: Optional[TTFAMonitor] = None


def get_ttfa_monitor() -> TTFAMonitor:
    """Get or create the global TTFA monitor instance"""
    global _ttfa_monitor
    if _ttfa_monitor is None:
        _ttfa_monitor = TTFAMonitor()
    return _ttfa_monitor


def setup_ttfa_monitoring(target_ttfa_ms: float = 800.0) -> TTFAMonitor:
    """Setup TTFA monitoring with specified target"""
    global _ttfa_monitor
    _ttfa_monitor = TTFAMonitor(target_ttfa_ms)
    
    # Add default alert for critical TTFA misses
    def critical_ttfa_alert(measurement: TTFAMeasurement):
        if measurement.total_ttfa and measurement.total_ttfa > 2000:
            logger.critical(
                f"CRITICAL TTFA MISS: {measurement.total_ttfa:.2f}ms > 2000ms "
                f"for request {measurement.request_id}"
            )
    
    _ttfa_monitor.add_alert_callback(critical_ttfa_alert)
    
    logger.info(f"TTFA monitoring setup complete - Target: {target_ttfa_ms}ms")
    return _ttfa_monitor


async def monitor_tts_request(request_id: str, text: str, voice: str, speed: float):
    """
    Context manager for monitoring a TTS request's TTFA performance
    
    Usage:
        async with monitor_tts_request(request_id, text, voice, speed) as monitor:
            # TTS processing happens here
            monitor.record_stage('model_inference', inference_time_ms)
            # ... other stages
            monitor.finalize(total_ttfa_ms, provider_used)
    """
    monitor = get_ttfa_monitor()
    measurement = monitor.start_measurement(request_id, text, voice, speed)
    
    class TTFAContext:
        def __init__(self, monitor_instance, measurement_instance):
            self.monitor = monitor_instance
            self.measurement = measurement_instance
        
        def record_stage(self, stage: str, time_ms: float):
            self.monitor.record_stage_timing(self.measurement, stage, time_ms)
        
        def finalize(self, total_ttfa_ms: float, provider_used: str = None):
            return self.monitor.finalize_measurement(self.measurement, total_ttfa_ms, provider_used)
    
    return TTFAContext(monitor, measurement)
