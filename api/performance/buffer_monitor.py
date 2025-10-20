"""
Buffer Utilization Monitoring System

This module provides comprehensive monitoring of streaming audio buffer utilization,
identifying performance bottlenecks, underruns, and optimization opportunities.

@sign: @darianrosebrook
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class BufferMetrics:
    """Real-time buffer utilization metrics."""
    buffer_size_bytes: int = 0
    buffer_utilization_percent: float = 0.0
    chunk_queue_length: int = 0
    average_chunk_size_bytes: int = 0
    underrun_events: int = 0
    overrun_events: int = 0
    avg_fill_time_ms: float = 0.0
    max_fill_time_ms: float = 0.0
    buffer_health_score: float = 100.0  # 0-100, higher is better
    timestamp: float = field(default_factory=time.time)


@dataclass
class BufferUtilizationReport:
    """Comprehensive buffer utilization analysis report."""
    session_id: str
    total_chunks_processed: int = 0
    total_bytes_processed: int = 0
    avg_buffer_utilization: float = 0.0
    peak_buffer_utilization: float = 0.0
    underrun_count: int = 0
    overrun_count: int = 0
    avg_chunk_processing_time_ms: float = 0.0
    buffer_efficiency_score: float = 0.0  # 0-100
    recommendations: List[str] = field(default_factory=list)
    performance_trends: Dict[str, Any] = field(default_factory=dict)


class StreamingBufferMonitor:
    """
    Monitors streaming audio buffer utilization in real-time.

    Tracks buffer fill levels, chunk processing times, and identifies
    performance bottlenecks that could cause audio stuttering or gaps.
    """

    def __init__(self, max_history_samples: int = 1000):
        self.max_history_samples = max_history_samples

        # Real-time metrics
        self.current_buffer_size = 0
        self.buffer_capacity = 0
        self.chunk_queue = deque(maxlen=100)

        # Historical data
        self.buffer_utilization_history = deque(maxlen=max_history_samples)
        self.chunk_processing_times = deque(maxlen=max_history_samples)
        self.underrun_events = []
        self.overrun_events = []

        # Performance thresholds
        self.low_utilization_threshold = 20.0  # % buffer utilization
        self.high_utilization_threshold = 90.0  # % buffer utilization
        self.critical_utilization_threshold = 95.0  # % buffer utilization

        # Monitoring state
        self.monitoring_active = False
        self.session_start_time = time.time()
        self.chunks_processed = 0
        self.bytes_processed = 0

        logger.info("🧮 Buffer utilization monitor initialized")

    def start_monitoring(self, buffer_capacity_bytes: int, session_id: str = None):
        """
        Start buffer utilization monitoring.

        @param buffer_capacity_bytes: Maximum buffer capacity in bytes
        @param session_id: Optional session identifier for tracking
        """
        self.buffer_capacity = buffer_capacity_bytes
        self.session_id = session_id or f"session_{int(time.time())}"
        self.monitoring_active = True
        self.session_start_time = time.time()

        # Reset counters
        self.chunks_processed = 0
        self.bytes_processed = 0
        self.underrun_events.clear()
        self.overrun_events.clear()

        logger.info(f"🧮 Started buffer monitoring for session {self.session_id}")

    def stop_monitoring(self) -> BufferUtilizationReport:
        """
        Stop monitoring and generate final report.

        @returns BufferUtilizationReport: Complete utilization analysis
        """
        self.monitoring_active = False

        report = self._generate_report()
        logger.info(f"🧮 Stopped buffer monitoring - efficiency: {report.buffer_efficiency_score:.1f}%")

        return report

    def record_chunk_processed(self, chunk_size_bytes: int, processing_time_ms: float):
        """
        Record a chunk processing event.

        @param chunk_size_bytes: Size of the processed chunk in bytes
        @param processing_time_ms: Time taken to process the chunk
        """
        if not self.monitoring_active:
            return

        self.chunks_processed += 1
        self.bytes_processed += chunk_size_bytes
        self.chunk_processing_times.append(processing_time_ms)

        # Update buffer utilization (simulate buffer state)
        self._update_buffer_utilization(chunk_size_bytes)

        # Check for performance issues
        self._check_buffer_health()

    def record_buffer_level(self, current_bytes: int, max_capacity_bytes: Optional[int] = None):
        """
        Record current buffer fill level.

        @param current_bytes: Current buffer fill in bytes
        @param max_capacity_bytes: Optional buffer capacity override
        """
        if not self.monitoring_active:
            return

        if max_capacity_bytes:
            self.buffer_capacity = max_capacity_bytes

        self.current_buffer_size = current_bytes

        if self.buffer_capacity > 0:
            utilization_percent = (current_bytes / self.buffer_capacity) * 100.0
            self.buffer_utilization_history.append(utilization_percent)

    def record_underrun(self, severity: str = "minor"):
        """
        Record a buffer underrun event.

        @param severity: Severity level ("minor", "moderate", "critical")
        """
        if not self.monitoring_active:
            return

        event = {
            "timestamp": time.time(),
            "severity": severity,
            "buffer_level": self.current_buffer_size,
            "session_time": time.time() - self.session_start_time
        }

        self.underrun_events.append(event)
        logger.warning(f"🧮 Buffer underrun detected ({severity}) - level: {self.current_buffer_size} bytes")

    def record_overrun(self, severity: str = "minor"):
        """
        Record a buffer overrun event.

        @param severity: Severity level ("minor", "moderate", "critical")
        """
        if not self.monitoring_active:
            return

        event = {
            "timestamp": time.time(),
            "severity": severity,
            "buffer_level": self.current_buffer_size,
            "session_time": time.time() - self.session_start_time
        }

        self.overrun_events.append(event)
        logger.warning(f"🧮 Buffer overrun detected ({severity}) - level: {self.current_buffer_size} bytes")

    def get_current_metrics(self) -> BufferMetrics:
        """Get current buffer utilization metrics."""
        utilization_percent = 0.0
        if self.buffer_capacity > 0:
            utilization_percent = (self.current_buffer_size / self.buffer_capacity) * 100.0

        avg_chunk_size = 0
        if self.chunk_processing_times:
            # Estimate chunk size from processing history
            avg_chunk_size = self.bytes_processed // max(1, self.chunks_processed)

        avg_fill_time = 0.0
        max_fill_time = 0.0
        if self.chunk_processing_times:
            avg_fill_time = statistics.mean(self.chunk_processing_times)
            max_fill_time = max(self.chunk_processing_times)

        # Calculate health score (0-100)
        health_score = 100.0

        # Deduct for underruns (more severe)
        if self.underrun_events:
            health_score -= len(self.underrun_events) * 10

        # Deduct for low utilization
        if utilization_percent < self.low_utilization_threshold:
            health_score -= (self.low_utilization_threshold - utilization_percent) * 0.5

        # Deduct for high utilization (risk of overrun)
        if utilization_percent > self.high_utilization_threshold:
            health_score -= (utilization_percent - self.high_utilization_threshold) * 0.3

        health_score = max(0.0, min(100.0, health_score))

        return BufferMetrics(
            buffer_size_bytes=self.current_buffer_size,
            buffer_utilization_percent=utilization_percent,
            chunk_queue_length=len(self.chunk_queue),
            average_chunk_size_bytes=avg_chunk_size,
            underrun_events=len(self.underrun_events),
            overrun_events=len(self.overrun_events),
            avg_fill_time_ms=avg_fill_time,
            max_fill_time_ms=max_fill_time,
            buffer_health_score=health_score
        )

    def _update_buffer_utilization(self, chunk_size_bytes: int):
        """Update buffer utilization based on chunk processing."""
        # Simulate buffer dynamics (in real implementation, this would come from actual buffer)
        # For now, assume chunks are consumed at a steady rate
        consumption_rate = 0.8  # Assume 80% of chunk is consumed by the time next arrives

        # Update buffer level
        self.current_buffer_size = max(0, self.current_buffer_size - int(chunk_size_bytes * consumption_rate))
        self.current_buffer_size += chunk_size_bytes

        # Cap at buffer capacity
        if self.buffer_capacity > 0:
            self.current_buffer_size = min(self.current_buffer_size, self.buffer_capacity)

    def _check_buffer_health(self):
        """Check for buffer health issues and log warnings."""
        if self.buffer_capacity == 0:
            return

        utilization_percent = (self.current_buffer_size / self.buffer_capacity) * 100.0

        # Check for critical underrun risk
        if utilization_percent < 5.0:
            self.record_underrun("critical")
            logger.error(f"🧮 CRITICAL: Buffer utilization critically low: {utilization_percent:.1f}%")

        # Check for underrun risk
        elif utilization_percent < 15.0:
            self.record_underrun("moderate")
            logger.warning(f"🧮 WARNING: Buffer utilization low: {utilization_percent:.1f}%")

        # Check for overrun risk
        elif utilization_percent > self.critical_utilization_threshold:
            self.record_overrun("moderate")
            logger.warning(f"🧮 WARNING: Buffer utilization high: {utilization_percent:.1f}%")

    def _generate_report(self) -> BufferUtilizationReport:
        """Generate comprehensive utilization report."""
        # Calculate averages
        avg_utilization = 0.0
        peak_utilization = 0.0

        if self.buffer_utilization_history:
            avg_utilization = statistics.mean(self.buffer_utilization_history)
            peak_utilization = max(self.buffer_utilization_history)

        avg_processing_time = 0.0
        if self.chunk_processing_times:
            avg_processing_time = statistics.mean(self.chunk_processing_times)

        # Calculate efficiency score
        efficiency_score = 100.0

        # Deduct for underruns (significant impact)
        efficiency_score -= len(self.underrun_events) * 15

        # Deduct for overruns
        efficiency_score -= len(self.overrun_events) * 10

        # Deduct for poor utilization consistency
        if self.buffer_utilization_history:
            utilization_variance = statistics.variance(self.buffer_utilization_history) if len(self.buffer_utilization_history) > 1 else 0
            efficiency_score -= min(utilization_variance * 0.1, 20)  # Cap deduction

        efficiency_score = max(0.0, min(100.0, efficiency_score))

        # Generate recommendations
        recommendations = self._generate_recommendations(avg_utilization, efficiency_score)

        # Performance trends
        trends = {
            "utilization_stability": self._analyze_utilization_stability(),
            "processing_time_trend": self._analyze_processing_trend(),
            "underrun_frequency": self._calculate_event_frequency(self.underrun_events),
            "overrun_frequency": self._calculate_event_frequency(self.overrun_events)
        }

        return BufferUtilizationReport(
            session_id=self.session_id,
            total_chunks_processed=self.chunks_processed,
            total_bytes_processed=self.bytes_processed,
            avg_buffer_utilization=avg_utilization,
            peak_buffer_utilization=peak_utilization,
            underrun_count=len(self.underrun_events),
            overrun_count=len(self.overrun_events),
            avg_chunk_processing_time_ms=avg_processing_time,
            buffer_efficiency_score=efficiency_score,
            recommendations=recommendations,
            performance_trends=trends
        )

    def _generate_recommendations(self, avg_utilization: float, efficiency_score: float) -> List[str]:
        """Generate optimization recommendations based on performance data."""
        recommendations = []

        # Buffer utilization recommendations
        if avg_utilization < 30.0:
            recommendations.append("Increase buffer size or reduce chunk consumption rate - utilization too low")
        elif avg_utilization > 80.0:
            recommendations.append("Consider reducing buffer size or increasing chunk consumption rate - utilization too high")

        # Efficiency recommendations
        if efficiency_score < 70.0:
            recommendations.append("Buffer efficiency is poor - investigate underruns and overruns")

        # Underrun recommendations
        if self.underrun_events:
            if len(self.underrun_events) > 10:
                recommendations.append("Frequent underruns detected - increase buffer size or optimize chunk generation")
            else:
                recommendations.append("Occasional underruns detected - monitor buffer sizing")

        # Overrun recommendations
        if self.overrun_events:
            recommendations.append("Buffer overruns detected - reduce buffer size or increase consumption rate")

        # Processing time recommendations
        if self.chunk_processing_times:
            avg_time = statistics.mean(self.chunk_processing_times)
            if avg_time > 50.0:  # >50ms per chunk
                recommendations.append(".2f")
            elif avg_time > 20.0:  # >20ms per chunk
                recommendations.append(".2f")

        return recommendations

    def _analyze_utilization_stability(self) -> Dict[str, Any]:
        """Analyze buffer utilization stability."""
        if len(self.buffer_utilization_history) < 10:
            return {"stability": "insufficient_data"}

        try:
            mean_utilization = statistics.mean(self.buffer_utilization_history)
            std_dev = statistics.stdev(self.buffer_utilization_history)
            cv = (std_dev / mean_utilization) * 100 if mean_utilization > 0 else 0  # Coefficient of variation

            if cv < 20:
                stability = "excellent"
            elif cv < 40:
                stability = "good"
            elif cv < 60:
                stability = "fair"
            else:
                stability = "poor"

            return {
                "stability": stability,
                "coefficient_of_variation": cv,
                "mean_utilization": mean_utilization,
                "standard_deviation": std_dev
            }
        except:
            return {"stability": "calculation_error"}

    def _analyze_processing_trend(self) -> Dict[str, Any]:
        """Analyze chunk processing time trends."""
        if len(self.chunk_processing_times) < 10:
            return {"trend": "insufficient_data"}

        try:
            # Simple linear trend analysis
            times_list = list(self.chunk_processing_times)
            n = len(times_list)

            # Calculate trend slope
            x = list(range(n))
            slope = statistics.linear_regression(x, times_list).slope

            if slope > 0.1:
                trend = "increasing"
                concern = "Processing times are increasing - potential performance degradation"
            elif slope < -0.1:
                trend = "decreasing"
                concern = "Processing times are improving"
            else:
                trend = "stable"
                concern = "Processing times are stable"

            return {
                "trend": trend,
                "slope": slope,
                "concern": concern,
                "avg_time": statistics.mean(times_list),
                "trend_confidence": min(1.0, n / 50.0)  # Confidence based on sample size
            }
        except:
            return {"trend": "calculation_error"}

    def _calculate_event_frequency(self, events: List[Dict]) -> Dict[str, Any]:
        """Calculate frequency of events (underruns/overruns)."""
        if not events:
            return {"frequency": 0, "severity": "none"}

        session_duration = time.time() - self.session_start_time
        if session_duration <= 0:
            return {"frequency": 0, "severity": "invalid"}

        frequency_per_minute = (len(events) / session_duration) * 60

        # Classify frequency severity
        if frequency_per_minute > 10:
            severity = "critical"
        elif frequency_per_minute > 5:
            severity = "high"
        elif frequency_per_minute > 1:
            severity = "moderate"
        elif frequency_per_minute > 0.1:
            severity = "low"
        else:
            severity = "minimal"

        return {
            "frequency_per_minute": frequency_per_minute,
            "severity": severity,
            "total_events": len(events),
            "session_duration_minutes": session_duration / 60
        }


# Global monitor instance
_buffer_monitor = None

def get_buffer_monitor() -> StreamingBufferMonitor:
    """Get the global buffer utilization monitor instance."""
    global _buffer_monitor
    if _buffer_monitor is None:
        _buffer_monitor = StreamingBufferMonitor()
    return _buffer_monitor
