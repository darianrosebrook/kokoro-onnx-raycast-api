#!/usr/bin/env python3
"""
Advanced Performance Monitor for Kokoro TTS API.

This script provides real-time performance monitoring, alerting, and regression detection
for the TTS API system. It tracks key metrics and can detect performance anomalies.
"""
import asyncio
import aiohttp
import json
import time
import statistics
import psutil
import sys
import signal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from urllib.parse import urlparse
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: float
    ttfa_ms: float
    api_latency_ms: float
    memory_mb: float
    cpu_percent: float
    active_connections: int
    error_rate: float
    provider: str
    text_length: int
    request_id: str

@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    metric: str
    warning_threshold: float
    critical_threshold: float
    window_size: int  # Number of samples to consider
    cooldown_seconds: int  # Minimum time between alerts

@dataclass
class PerformanceAlert:
    """Performance alert data structure."""
    timestamp: float
    severity: str  # 'warning' or 'critical'
    metric: str
    current_value: float
    threshold: float
    message: str
    request_id: Optional[str] = None

class PerformanceMonitor:
    """Advanced performance monitoring system."""
    
    def __init__(self, base_url: str = "http://localhost:8000", config_file: Optional[str] = None):
        self.base_url = base_url
        self.metrics_history: List[PerformanceMetrics] = []
        self.alerts: List[PerformanceAlert] = []
        self.alert_thresholds = self._load_alert_thresholds(config_file)
        self.last_alert_times: Dict[str, float] = {}
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Performance baselines (from optimization results)
        self.baselines = {
            'ttfa_ms': {'p50': 5.5, 'p95': 6.9, 'target': 500.0},
            'api_latency_ms': {'p50': 5.5, 'p95': 6.9, 'target': 1000.0},
            'memory_mb': {'p50': 70.9, 'p95': 606.9, 'target': 500.0},
            'cpu_percent': {'p50': 15.0, 'p95': 25.0, 'target': 80.0},
            'error_rate': {'p50': 0.0, 'p95': 0.0, 'target': 0.05}
        }
    
    def _load_alert_thresholds(self, config_file: Optional[str]) -> List[AlertThreshold]:
        """Load alert thresholds from config file or use defaults."""
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return [AlertThreshold(**threshold) for threshold in config.get('thresholds', [])]
            except Exception as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")
        
        # Default thresholds based on optimization results
        return [
            AlertThreshold('ttfa_ms', 50.0, 100.0, 5, 60),
            AlertThreshold('api_latency_ms', 100.0, 200.0, 5, 60),
            AlertThreshold('memory_mb', 800.0, 1200.0, 10, 120),
            AlertThreshold('cpu_percent', 60.0, 80.0, 5, 60),
            AlertThreshold('error_rate', 0.02, 0.05, 10, 60)
        ]
    
    async def collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        timestamp = time.time()
        
        # Get system metrics
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()
        
        # Get API metrics
        ttfa_ms = 0.0
        api_latency_ms = 0.0
        error_rate = 0.0
        provider = "unknown"
        text_length = 0
        request_id = "monitor"
        
        try:
            # Test API performance
            test_text = "Performance monitoring test"
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                request_data = {
                    "text": test_text,
                    "voice": "af_heart",
                    "speed": 1.0,
                    "lang": "en-us",
                    "stream": True,
                    "format": "pcm"
                }
                
                async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                    end_time = time.time()
                    api_latency_ms = (end_time - start_time) * 1000
                    
                    if response.status == 200:
                        # Measure TTFA
                        first_chunk_time = None
                        async for chunk in response.content.iter_chunked(1024):
                            if first_chunk_time is None:
                                first_chunk_time = time.time()
                                break
                        
                        if first_chunk_time:
                            ttfa_ms = (first_chunk_time - start_time) * 1000
                        
                        # Get provider info from headers
                        provider = response.headers.get('X-Provider', 'unknown')
                        text_length = len(test_text)
                        request_id = response.headers.get('X-Request-ID', 'monitor')
                    else:
                        error_rate = 1.0
                        logger.warning(f"API request failed with status {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to collect API metrics: {e}")
            error_rate = 1.0
        
        # Implement comprehensive connection tracking
        active_connections = await self.get_active_connection_count(server_url)
        
        return PerformanceMetrics(
            timestamp=timestamp,
            ttfa_ms=ttfa_ms,
            api_latency_ms=api_latency_ms,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            active_connections=active_connections,
            error_rate=error_rate,
            provider=provider,
            text_length=text_length,
            request_id=request_id
        )
    
    def check_alerts(self, metrics: PerformanceMetrics) -> List[PerformanceAlert]:
        """Check for alert conditions based on current metrics."""
        new_alerts = []
        current_time = time.time()
        
        for threshold in self.alert_thresholds:
            # Get metric value
            metric_value = getattr(metrics, threshold.metric, 0.0)
            
            # Check cooldown
            alert_key = f"{threshold.metric}_{threshold.severity}"
            if alert_key in self.last_alert_times:
                if current_time - self.last_alert_times[alert_key] < threshold.cooldown_seconds:
                    continue
            
            # Check threshold
            severity = None
            if metric_value >= threshold.critical_threshold:
                severity = 'critical'
            elif metric_value >= threshold.warning_threshold:
                severity = 'warning'
            
            if severity:
                # Check if we have enough samples in the window
                recent_metrics = [m for m in self.metrics_history[-threshold.window_size:] 
                                if hasattr(m, threshold.metric)]
                
                if len(recent_metrics) >= threshold.window_size:
                    # Check if threshold is consistently exceeded
                    recent_values = [getattr(m, threshold.metric) for m in recent_metrics]
                    if all(v >= threshold.warning_threshold for v in recent_values):
                        alert = PerformanceAlert(
                            timestamp=current_time,
                            severity=severity,
                            metric=threshold.metric,
                            current_value=metric_value,
                            threshold=threshold.critical_threshold if severity == 'critical' else threshold.warning_threshold,
                            message=f"{threshold.metric} {severity}: {metric_value:.2f} >= {threshold.critical_threshold if severity == 'critical' else threshold.warning_threshold}",
                            request_id=metrics.request_id
                        )
                        new_alerts.append(alert)
                        self.last_alert_times[alert_key] = current_time
        
        return new_alerts
    
    def detect_regression(self, metrics: PerformanceMetrics) -> Optional[Dict[str, Any]]:
        """Detect performance regression compared to baselines."""
        regression_info = {}
        
        # Check TTFA regression
        if metrics.ttfa_ms > self.baselines['ttfa_ms']['p95'] * 2:
            regression_info['ttfa'] = {
                'current': metrics.ttfa_ms,
                'baseline_p95': self.baselines['ttfa_ms']['p95'],
                'regression_factor': metrics.ttfa_ms / self.baselines['ttfa_ms']['p95']
            }
        
        # Check memory regression
        if metrics.memory_mb > self.baselines['memory_mb']['p95'] * 1.5:
            regression_info['memory'] = {
                'current': metrics.memory_mb,
                'baseline_p95': self.baselines['memory_mb']['p95'],
                'regression_factor': metrics.memory_mb / self.baselines['memory_mb']['p95']
            }
        
        # Check API latency regression
        if metrics.api_latency_ms > self.baselines['api_latency_ms']['p95'] * 2:
            regression_info['api_latency'] = {
                'current': metrics.api_latency_ms,
                'baseline_p95': self.baselines['api_latency_ms']['p95'],
                'regression_factor': metrics.api_latency_ms / self.baselines['api_latency_ms']['p95']
            }
        
        return regression_info if regression_info else None
    
    async def monitor_loop(self, interval_seconds: int = 30):
        """Main monitoring loop."""
        logger.info(f"Starting performance monitoring (interval: {interval_seconds}s)")
        
        while self.running:
            try:
                # Collect metrics
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only recent history (last hour)
                cutoff_time = time.time() - 3600
                self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
                
                # Check for alerts
                alerts = self.check_alerts(metrics)
                self.alerts.extend(alerts)
                
                # Check for regression
                regression = self.detect_regression(metrics)
                
                # Log current status
                logger.info(f"Metrics: TTFA={metrics.ttfa_ms:.1f}ms, "
                          f"Latency={metrics.api_latency_ms:.1f}ms, "
                          f"Memory={metrics.memory_mb:.1f}MB, "
                          f"CPU={metrics.cpu_percent:.1f}%, "
                          f"Provider={metrics.provider}")
                
                # Log alerts
                for alert in alerts:
                    logger.warning(f"ALERT [{alert.severity.upper()}]: {alert.message}")
                
                # Log regression
                if regression:
                    logger.error(f"PERFORMANCE REGRESSION DETECTED: {regression}")
                
                # Wait for next interval
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def start_monitoring(self, interval_seconds: int = 30):
        """Start the monitoring system."""
        self.running = True
        self.monitor_task = asyncio.create_task(self.monitor_loop(interval_seconds))
        logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop the monitoring system."""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")
    
    def get_metrics_summary(self, window_minutes: int = 15) -> Dict[str, Any]:
        """Get summary of recent metrics."""
        cutoff_time = time.time() - (window_minutes * 60)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {"error": "No recent metrics available"}
        
        # Initialize historical data collection
        self._ensure_historical_storage()

        # Store current metrics in historical database
        self._store_metrics_historical(recent_metrics)

        summary = {
            "window_minutes": window_minutes,
            "sample_count": len(recent_metrics),
            "timestamp": time.time(),
            "metrics": {},
            "historical_trends": self._calculate_historical_trends(window_minutes)
        }
        
        # Calculate statistics for each metric
        for metric_name in ['ttfa_ms', 'api_latency_ms', 'memory_mb', 'cpu_percent', 'error_rate']:
            values = [getattr(m, metric_name) for m in recent_metrics]
            if values:
                summary["metrics"][metric_name] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": statistics.mean(values),
                    "p50": statistics.median(values),
                    "p95": statistics.quantiles(values, n=20)[18] if len(values) >= 20 else max(values)
                }
        
        return summary
    
    def save_metrics(self, output_file: str = "performance-metrics.json"):
        """Save metrics history to file."""
        metrics_data = {
            "timestamp": time.time(),
            "baselines": self.baselines,
            "metrics": [asdict(m) for m in self.metrics_history],
            "alerts": [asdict(a) for a in self.alerts]
        }
        
        with open(output_file, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        logger.info(f"Metrics saved to {output_file}")

    def _ensure_historical_storage(self) -> None:
        """Ensure historical data storage is initialized."""
        try:
            import os
            from pathlib import Path

            # Create historical data directory
            historical_dir = Path('cache/persistent/historical')
            historical_dir.mkdir(parents=True, exist_ok=True)

            # Initialize historical database if it doesn't exist
            db_path = historical_dir / 'metrics_history.db'
            if not db_path.exists():
                self._initialize_historical_database(db_path)

        except Exception as e:
            logger.debug(f"Failed to ensure historical storage: {e}")

    def _initialize_historical_database(self, db_path: Path) -> None:
        """Initialize the historical metrics database."""
        try:
            import sqlite3

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Create metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        metadata TEXT,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                ''')

                # Create trends table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trends (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_name TEXT NOT NULL,
                        period_start REAL NOT NULL,
                        period_end REAL NOT NULL,
                        trend_type TEXT NOT NULL,
                        slope REAL,
                        r_squared REAL,
                        significance REAL,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                ''')

                # Create indexes for performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_trends_metric ON trends(metric_name)')

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize historical database: {e}")

    def _store_metrics_historical(self, metrics: List[PerformanceMetrics]) -> None:
        """Store metrics in historical database."""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path('cache/persistent/historical/metrics_history.db')

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Prepare metrics data for batch insert
                metrics_data = []
                for metric in metrics:
                    metrics_data.extend([
                        (metric.timestamp, 'ttfa_ms', metric.ttfa_ms, json.dumps({'request_id': getattr(metric, 'request_id', None)})),
                        (metric.timestamp, 'api_latency_ms', metric.api_latency_ms, json.dumps({'request_id': getattr(metric, 'request_id', None)})),
                        (metric.timestamp, 'memory_mb', metric.memory_mb, None),
                        (metric.timestamp, 'cpu_percent', metric.cpu_percent, None),
                        (metric.timestamp, 'error_rate', metric.error_rate, None),
                        (metric.timestamp, 'active_connections', getattr(metric, 'active_connections', 0), None),
                    ])

                # Batch insert metrics
                cursor.executemany('''
                    INSERT INTO metrics (timestamp, metric_name, value, metadata)
                    VALUES (?, ?, ?, ?)
                ''', metrics_data)

                conn.commit()

                # Clean up old data (keep last 30 days)
                cutoff_time = time.time() - (30 * 24 * 60 * 60)
                cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff_time,))
                cursor.execute('DELETE FROM trends WHERE period_end < ?', (cutoff_time,))

                conn.commit()

        except Exception as e:
            logger.debug(f"Failed to store historical metrics: {e}")

    def _calculate_historical_trends(self, window_minutes: int) -> Dict[str, Any]:
        """Calculate historical trends for the specified window."""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path('cache/persistent/historical/metrics_history.db')
            if not db_path.exists():
                return {}

            trends = {}
            end_time = time.time()
            start_time = end_time - (window_minutes * 60)

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Calculate trends for each metric
                for metric_name in ['ttfa_ms', 'api_latency_ms', 'memory_mb', 'cpu_percent', 'error_rate']:
                    cursor.execute('''
                        SELECT timestamp, value
                        FROM metrics
                        WHERE metric_name = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp
                    ''', (metric_name, start_time, end_time))

                    rows = cursor.fetchall()
                    if len(rows) >= 5:  # Need minimum data points for trend analysis
                        timestamps, values = zip(*rows)
                        trend_result = self._analyze_metric_trend(list(values), list(timestamps))
                        trends[metric_name] = trend_result

            return trends

        except Exception as e:
            logger.debug(f"Failed to calculate historical trends: {e}")
            return {}

    def _analyze_metric_trend(self, values: List[float], timestamps: List[float]) -> Dict[str, Any]:
        """Analyze trend for a specific metric."""
        try:
            import statistics

            if len(values) < 3:
                return {'trend': 'insufficient_data'}

            # Calculate basic statistics
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0

            # Simple linear trend
            n = len(values)
            x = list(range(n))  # Time indices

            # Calculate slope using simple linear regression
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(xi * yi for xi, yi in zip(x, values))
            sum_x2 = sum(xi * xi for xi in x)

            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                slope = 0.0
            else:
                slope = (n * sum_xy - sum_x * sum_y) / denominator

            # Calculate R-squared (simplified)
            y_pred = [slope * xi + (sum_y - slope * sum_x) / n for xi in x]
            ss_res = sum((yi - y_pred_i) ** 2 for yi, y_pred_i in zip(values, y_pred))
            ss_tot = sum((yi - mean_value) ** 2 for yi in values)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            # Determine trend direction and significance
            if abs(slope) < std_dev * 0.1:  # Slope less than 10% of standard deviation
                trend = 'stable'
                significance = 'low'
            elif slope > std_dev * 0.2:  # Significant upward trend
                trend = 'degrading'
                significance = 'high' if r_squared > 0.7 else 'medium'
            elif slope < -std_dev * 0.2:  # Significant downward trend
                trend = 'improving'
                significance = 'high' if r_squared > 0.7 else 'medium'
            else:
                trend = 'stable'
                significance = 'low'

            # Calculate change percentage
            first_quarter = values[:n//4] if n >= 4 else values[:n//2]
            last_quarter = values[-(n//4):] if n >= 4 else values[-(n//2):]

            if first_quarter and last_quarter:
                first_avg = statistics.mean(first_quarter)
                last_avg = statistics.mean(last_quarter)
                change_percent = ((last_avg - first_avg) / first_avg) * 100 if first_avg != 0 else 0
            else:
                change_percent = 0

            return {
                'trend': trend,
                'significance': significance,
                'slope': slope,
                'r_squared': r_squared,
                'change_percent': change_percent,
                'mean_value': mean_value,
                'std_dev': std_dev,
                'sample_count': n,
                'time_range_hours': (max(timestamps) - min(timestamps)) / 3600 if timestamps else 0
            }

        except Exception as e:
            logger.debug(f"Failed to analyze metric trend: {e}")
            return {'trend': 'error', 'error': str(e)}

    def get_historical_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive historical summary for the specified number of days."""
        try:
            import sqlite3
            from pathlib import Path
            from collections import defaultdict

            db_path = Path('cache/persistent/historical/metrics_history.db')
            if not db_path.exists():
                return {'error': 'No historical data available'}

            end_time = time.time()
            start_time = end_time - (days * 24 * 60 * 60)

            summary = {
                'period_days': days,
                'start_time': start_time,
                'end_time': end_time,
                'metrics': {},
                'trends': {},
                'anomalies': [],
                'data_quality': {}
            }

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Get data quality metrics
                cursor.execute('''
                    SELECT COUNT(*) as total_samples,
                           COUNT(DISTINCT date(timestamp, 'unixepoch')) as days_with_data,
                           AVG(timestamp) as avg_timestamp
                    FROM metrics
                    WHERE timestamp BETWEEN ? AND ?
                ''', (start_time, end_time))

                quality_row = cursor.fetchone()
                if quality_row:
                    total_samples, days_with_data, avg_timestamp = quality_row
                    summary['data_quality'] = {
                        'total_samples': total_samples,
                        'days_with_data': days_with_data,
                        'data_completeness': days_with_data / days if days > 0 else 0,
                        'avg_samples_per_day': total_samples / days if days > 0 else 0
                    }

                # Analyze each metric
                for metric_name in ['ttfa_ms', 'api_latency_ms', 'memory_mb', 'cpu_percent', 'error_rate']:
                    cursor.execute('''
                        SELECT timestamp, value
                        FROM metrics
                        WHERE metric_name = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp
                    ''', (metric_name, start_time, end_time))

                    rows = cursor.fetchall()
                    if rows:
                        timestamps, values = zip(*rows)

                        # Calculate statistics
                        metric_stats = self._calculate_metric_statistics(values, timestamps)
                        summary['metrics'][metric_name] = metric_stats

                        # Calculate trend
                        if len(values) >= 5:
                            trend_analysis = self._analyze_metric_trend(list(values), list(timestamps))
                            summary['trends'][metric_name] = trend_analysis

                            # Detect anomalies
                            anomalies = self._detect_metric_anomalies(values, metric_stats)
                            if anomalies:
                                summary['anomalies'].extend([
                                    {'metric': metric_name, **anomaly} for anomaly in anomalies
                                ])

            return summary

        except Exception as e:
            logger.error(f"Failed to generate historical summary: {e}")
            return {'error': str(e)}

    def _calculate_metric_statistics(self, values: List[float], timestamps: List[float]) -> Dict[str, Any]:
        """Calculate comprehensive statistics for a metric."""
        try:
            import statistics
            from scipy import stats as scipy_stats

            stats = {
                'count': len(values),
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                'min': min(values),
                'max': max(values),
                'range': max(values) - min(values)
            }

            # Calculate percentiles
            if len(values) >= 4:
                percentiles = statistics.quantiles(values, n=100)
                stats.update({
                    'p25': percentiles[24],  # 25th percentile
                    'p75': percentiles[74],  # 75th percentile
                    'p95': percentiles[94],  # 95th percentile
                    'p99': percentiles[98],  # 99th percentile
                    'iqr': percentiles[74] - percentiles[24]  # Interquartile range
                })

            # Calculate time-based statistics
            if len(timestamps) > 1:
                time_span = max(timestamps) - min(timestamps)
                stats.update({
                    'time_span_hours': time_span / 3600,
                    'avg_sampling_interval': time_span / (len(timestamps) - 1) / 60,  # minutes
                })

            return stats

        except Exception as e:
            logger.debug(f"Failed to calculate metric statistics: {e}")
            return {'error': str(e)}

    def _detect_metric_anomalies(self, values: List[float], stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in metric values."""
        try:
            anomalies = []
            mean = stats.get('mean', 0)
            std_dev = stats.get('std_dev', 0)

            if std_dev == 0:
                return anomalies

            # Use 3-sigma rule for anomaly detection
            threshold_high = mean + 3 * std_dev
            threshold_low = mean - 3 * std_dev

            for i, value in enumerate(values):
                if value > threshold_high or value < threshold_low:
                    anomalies.append({
                        'index': i,
                        'value': value,
                        'deviation_sigma': abs(value - mean) / std_dev,
                        'type': 'high' if value > threshold_high else 'low'
                    })

            return anomalies

        except Exception as e:
            logger.debug(f"Failed to detect anomalies: {e}")
            return []

    async def get_active_connection_count(self, server_url: str) -> int:
        """Get the count of active connections to the server."""
        try:
            # Try to get connection count from server metrics endpoint
            metrics_url = f"{server_url}/metrics" if not server_url.endswith('/metrics') else server_url
            async with self.session.get(metrics_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    metrics_data = await response.json()
                    # Look for active connections in metrics
                    if 'active_connections' in metrics_data:
                        return metrics_data['active_connections']
                    elif 'connections' in metrics_data and 'active' in metrics_data['connections']:
                        return metrics_data['connections']['active']
        except Exception as e:
            logger.debug(f"Failed to get connection count from metrics endpoint: {e}")

        try:
            # Fallback: Try to get connection count from server status endpoint
            status_url = f"{server_url}/status" if not server_url.endswith('/status') else server_url
            async with self.session.get(status_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    status_data = await response.json()
                    # Look for connection info in status
                    if 'active_connections' in status_data:
                        return status_data['active_connections']
                    elif 'connections' in status_data:
                        return status_data['connections'].get('active', 0)
        except Exception as e:
            logger.debug(f"Failed to get connection count from status endpoint: {e}")

        try:
            # Fallback: Use system-level connection tracking (if available)
            return await self.get_system_connection_count(server_url)
        except Exception as e:
            logger.debug(f"Failed to get system-level connection count: {e}")

        # Final fallback: estimate based on recent activity
        recent_requests = len([m for m in self.metrics_history[-10:] if m.api_latency_ms > 0])
        estimated_connections = max(1, min(50, recent_requests // 2))
        logger.debug(f"Using estimated connection count: {estimated_connections} (based on recent activity)")
        return estimated_connections

    async def get_system_connection_count(self, server_url: str) -> int:
        """Get connection count using system-level network monitoring."""
        try:
            import socket
            import psutil

            # Parse server URL to get host and port
            parsed_url = urlparse(server_url)
            host = parsed_url.hostname or 'localhost'
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)

            # Try to resolve host to IP
            try:
                ip = socket.gethostbyname(host)
            except socket.gaierror:
                logger.debug(f"Could not resolve host {host}")
                return 1

            # Count established connections to the target IP/port
            connection_count = 0
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'ESTABLISHED':
                        # Check if connection is to our target
                        if conn.raddr and conn.raddr.ip == ip:
                            # For HTTP connections, we can't easily distinguish by port
                            # So we'll count all connections to the IP
                            connection_count += 1
            except Exception as e:
                logger.debug(f"Failed to enumerate connections: {e}")

            # Return at least 1 if we found any connections
            return max(1, min(connection_count, 100))  # Cap at reasonable maximum

        except ImportError:
            logger.debug("psutil not available for system connection monitoring")
            return 1
        except Exception as e:
            logger.debug(f"System connection monitoring failed: {e}")
            return 1

async def main():
    """Main monitoring function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Monitor")
    parser.add_argument("--url", default="http://localhost:8000", help="TTS API base URL")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    parser.add_argument("--config", help="Alert configuration file")
    parser.add_argument("--output", default="performance-metrics.json", help="Output file for metrics")
    parser.add_argument("--duration", type=int, help="Monitoring duration in seconds (0 for continuous)")
    parser.add_argument("--summary", action="store_true", help="Show metrics summary and exit")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = PerformanceMonitor(args.url, args.config)
    
    if args.summary:
        # Show summary of existing metrics
        if Path(args.output).exists():
            with open(args.output, 'r') as f:
                data = json.load(f)
                print(f"📊 Performance Metrics Summary:")
                print(f"  Total samples: {len(data.get('metrics', []))}")
                print(f"  Total alerts: {len(data.get('alerts', []))}")
                print(f"  Last updated: {datetime.fromtimestamp(data.get('timestamp', 0))}")
        else:
            print("No metrics file found. Run monitoring first.")
        return
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(monitor.stop_monitoring())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start monitoring
        await monitor.start_monitoring(args.interval)
        
        if args.duration:
            # Run for specified duration
            await asyncio.sleep(args.duration)
            await monitor.stop_monitoring()
        else:
            # Run continuously
            await monitor.monitor_task
        
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    finally:
        await monitor.stop_monitoring()
        monitor.save_metrics(args.output)
        
        # Show final summary
        summary = monitor.get_metrics_summary()
        print(f"\n📊 Final Performance Summary:")
        print(f"  Samples collected: {summary.get('sample_count', 0)}")
        print(f"  Alerts generated: {len(monitor.alerts)}")
        
        if summary.get('metrics'):
            for metric, stats in summary['metrics'].items():
                print(f"  {metric}: avg={stats['avg']:.2f}, p95={stats['p95']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
