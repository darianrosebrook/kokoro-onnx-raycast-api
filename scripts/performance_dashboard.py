#!/usr/bin/env python3
"""
Real-time Performance Dashboard for Kokoro TTS API.

This script provides a web-based dashboard for monitoring TTS performance
in real-time, including metrics, alerts, and system health.
"""
import asyncio
import aiohttp
import json
import time
import psutil
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from aiohttp import web, WSMsgType
import aiohttp_cors

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DashboardMetrics:
    """Dashboard metrics data structure."""
    timestamp: float
    ttfa_ms: float
    api_latency_ms: float
    memory_mb: float
    cpu_percent: float
    active_connections: int
    error_rate: float
    provider: str
    cache_hit_rate: float
    requests_per_minute: float

class PerformanceDashboard:
    """Real-time performance dashboard."""
    
    def __init__(self, tts_url: str = "http://localhost:8000", port: int = 8080):
        self.tts_url = tts_url
        self.port = port
        self.metrics_history: List[DashboardMetrics] = []
        self.websocket_clients: List[web.WebSocketResponse] = []
        self.app = web.Application()
        self.cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # Performance baselines
        self.baselines = {
            'ttfa_ms': {'target': 500.0, 'current': 5.5},
            'api_latency_ms': {'target': 1000.0, 'current': 6.9},
            'memory_mb': {'target': 500.0, 'current': 70.9},
            'cpu_percent': {'target': 80.0, 'current': 15.0},
            'error_rate': {'target': 0.05, 'current': 0.0}
        }
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup web routes."""
        # Static files
        self.app.router.add_static('/', path=Path(__file__).parent / 'dashboard_static', name='static')
        
        # API routes
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/status', self.get_status)
        self.app.router.add_get('/api/history', self.get_history)
        self.app.router.add_get('/api/baselines', self.get_baselines)
        self.app.router.add_get('/ws', self.websocket_handler)
        
        # Main dashboard
        self.app.router.add_get('/', self.dashboard_handler)
        
        # Add CORS to all routes
        for route in list(self.app.router.routes()):
            self.cors.add(route)
    
    async def collect_metrics(self) -> DashboardMetrics:
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
        cache_hit_rate = 0.0
        
        try:
            # Test API performance
            test_text = "Dashboard performance test"
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
                
                async with session.post(f"{self.tts_url}/v1/audio/speech", json=request_data) as response:
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
                        cache_hit_rate = float(response.headers.get('X-Cache-Hit-Rate', '0.0'))
                    else:
                        error_rate = 1.0
                        logger.warning(f"API request failed with status {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to collect API metrics: {e}")
            error_rate = 1.0
        
        # TODO: Implement proper requests per minute calculation
        # - [ ] Track actual request counts over time windows (1min, 5min, 15min)
        # - [ ] Implement sliding window calculation for accurate throughput metrics
        # - [ ] Add percentile calculations for request rate distribution
        # - [ ] Implement burst detection and rate limiting monitoring
        # - [ ] Add historical trending for request rate patterns
        requests_per_minute = 0.0
        if len(self.metrics_history) > 1:
            time_diff = timestamp - self.metrics_history[-1].timestamp
            if time_diff > 0:
                requests_per_minute = 60.0 / time_diff
        
        return DashboardMetrics(
            timestamp=timestamp,
            ttfa_ms=ttfa_ms,
            api_latency_ms=api_latency_ms,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            active_connections=len(self.websocket_clients),
            error_rate=error_rate,
            provider=provider,
            cache_hit_rate=cache_hit_rate,
            requests_per_minute=requests_per_minute
        )
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websocket_clients.append(ws)
        logger.info(f"WebSocket client connected. Total clients: {len(self.websocket_clients)}")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        finally:
            self.websocket_clients.remove(ws)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.websocket_clients)}")
        
        return ws
    
    async def broadcast_metrics(self, metrics: DashboardMetrics):
        """Broadcast metrics to all WebSocket clients."""
        if not self.websocket_clients:
            return
        
        data = {
            'type': 'metrics',
            'data': asdict(metrics)
        }
        
        message = json.dumps(data)
        
        # Send to all connected clients
        disconnected_clients = []
        for ws in self.websocket_clients:
            try:
                await ws.send_str(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected_clients.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected_clients:
            if ws in self.websocket_clients:
                self.websocket_clients.remove(ws)
    
    async def get_metrics(self, request):
        """Get current metrics."""
        metrics = await self.collect_metrics()
        return web.json_response(asdict(metrics))
    
    async def get_status(self, request):
        """Get system status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.tts_url}/status") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        return web.json_response(status_data)
                    else:
                        return web.json_response({"error": "TTS service unavailable"}, status=503)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=503)
    
    async def get_history(self, request):
        """Get metrics history."""
        # Get query parameters
        window_minutes = int(request.query.get('window', 60))
        cutoff_time = time.time() - (window_minutes * 60)
        
        # Filter recent metrics
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        return web.json_response([asdict(m) for m in recent_metrics])
    
    async def get_baselines(self, request):
        """Get performance baselines."""
        return web.json_response(self.baselines)
    
    async def dashboard_handler(self, request):
        """Serve the main dashboard HTML."""
        html_content = self._generate_dashboard_html()
        return web.Response(text=html_content, content_type='text/html')
    
    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kokoro TTS Performance Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f7;
            color: #1d1d1f;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 600;
        }
        .header p {
            margin: 10px 0 0 0;
            color: #86868b;
            font-size: 1.1rem;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e5e7;
        }
        .metric-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: #86868b;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .metric-status {
            font-size: 0.9rem;
            font-weight: 500;
        }
        .status-good { color: #30d158; }
        .status-warning { color: #ff9f0a; }
        .status-critical { color: #ff453a; }
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e5e7;
            margin-bottom: 20px;
        }
        .chart-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 20px;
        }
        .chart {
            height: 200px;
            background: #f5f5f7;
            border-radius: 8px;
            display: flex;
            align-items: end;
            padding: 10px;
            gap: 2px;
        }
        .chart-bar {
            background: #007aff;
            border-radius: 2px 2px 0 0;
            min-height: 2px;
            flex: 1;
        }
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background: #30d158; }
        .status-offline { background: #ff453a; }
        .connection-status {
            text-align: center;
            margin-bottom: 20px;
        }
        .connection-status span {
            font-size: 1.1rem;
            font-weight: 500;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Kokoro TTS Performance Dashboard</h1>
        <p>Real-time monitoring and analytics</p>
    </div>
    
    <div class="connection-status">
        <span id="connection-status">
            <span class="status-indicator status-offline"></span>
            Connecting...
        </span>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-title">Time to First Audio</div>
            <div class="metric-value" id="ttfa-value">--</div>
            <div class="metric-status" id="ttfa-status">--</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-title">API Latency</div>
            <div class="metric-value" id="latency-value">--</div>
            <div class="metric-status" id="latency-status">--</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-title">Memory Usage</div>
            <div class="metric-value" id="memory-value">--</div>
            <div class="metric-status" id="memory-status">--</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-title">CPU Usage</div>
            <div class="metric-value" id="cpu-value">--</div>
            <div class="metric-status" id="cpu-status">--</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-title">Error Rate</div>
            <div class="metric-value" id="error-value">--</div>
            <div class="metric-status" id="error-status">--</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-title">Provider</div>
            <div class="metric-value" id="provider-value">--</div>
            <div class="metric-status" id="provider-status">--</div>
        </div>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">TTFA Trend (Last 60 samples)</div>
        <div class="chart" id="ttfa-chart"></div>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">Memory Usage Trend (Last 60 samples)</div>
        <div class="chart" id="memory-chart"></div>
    </div>
    
    <script>
        let ws = null;
        let metricsHistory = [];
        const maxHistoryLength = 60;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                document.getElementById('connection-status').innerHTML = 
                    '<span class="status-indicator status-online"></span>Connected';
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'metrics') {
                    updateMetrics(data.data);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                document.getElementById('connection-status').innerHTML = 
                    '<span class="status-indicator status-offline"></span>Disconnected';
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateMetrics(metrics) {
            // Update metric values
            document.getElementById('ttfa-value').textContent = metrics.ttfa_ms.toFixed(1) + 'ms';
            document.getElementById('latency-value').textContent = metrics.api_latency_ms.toFixed(1) + 'ms';
            document.getElementById('memory-value').textContent = metrics.memory_mb.toFixed(1) + 'MB';
            document.getElementById('cpu-value').textContent = metrics.cpu_percent.toFixed(1) + '%';
            document.getElementById('error-value').textContent = (metrics.error_rate * 100).toFixed(2) + '%';
            document.getElementById('provider-value').textContent = metrics.provider;
            
            // Update status indicators
            updateStatus('ttfa', metrics.ttfa_ms, 500, 100);
            updateStatus('latency', metrics.api_latency_ms, 1000, 200);
            updateStatus('memory', metrics.memory_mb, 500, 800);
            updateStatus('cpu', metrics.cpu_percent, 80, 60);
            updateStatus('error', metrics.error_rate * 100, 5, 2);
            
            // Update charts
            updateChart('ttfa-chart', metrics.ttfa_ms, 500);
            updateChart('memory-chart', metrics.memory_mb, 500);
            
            // Store in history
            metricsHistory.push(metrics);
            if (metricsHistory.length > maxHistoryLength) {
                metricsHistory.shift();
            }
        }
        
        function updateStatus(metric, value, critical, warning) {
            const statusElement = document.getElementById(metric + '-status');
            let status, className;
            
            if (value >= critical) {
                status = 'Critical';
                className = 'status-critical';
            } else if (value >= warning) {
                status = 'Warning';
                className = 'status-warning';
            } else {
                status = 'Good';
                className = 'status-good';
            }
            
            statusElement.textContent = status;
            statusElement.className = 'metric-status ' + className;
        }
        
        function updateChart(chartId, value, maxValue) {
            const chart = document.getElementById(chartId);
            const height = Math.min(100, (value / maxValue) * 100);
            
            // Create new bar
            const bar = document.createElement('div');
            bar.className = 'chart-bar';
            bar.style.height = height + '%';
            
            // Add to chart
            chart.appendChild(bar);
            
            // Remove old bars
            while (chart.children.length > maxHistoryLength) {
                chart.removeChild(chart.firstChild);
            }
        }
        
        // Initialize
        connectWebSocket();
        
        // Fetch initial data
        fetch('/api/metrics')
            .then(response => response.json())
            .then(data => updateMetrics(data))
            .catch(error => console.error('Error fetching initial metrics:', error));
    </script>
</body>
</html>
        """
    
    async def monitoring_loop(self, interval_seconds: int = 5):
        """Main monitoring loop."""
        logger.info(f"Starting performance monitoring (interval: {interval_seconds}s)")
        
        while True:
            try:
                # Collect metrics
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only recent history (last hour)
                cutoff_time = time.time() - 3600
                self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
                
                # Broadcast to WebSocket clients
                await self.broadcast_metrics(metrics)
                
                # Log current status
                logger.info(f"Metrics: TTFA={metrics.ttfa_ms:.1f}ms, "
                          f"Latency={metrics.api_latency_ms:.1f}ms, "
                          f"Memory={metrics.memory_mb:.1f}MB, "
                          f"CPU={metrics.cpu_percent:.1f}%, "
                          f"Provider={metrics.provider}")
                
                # Wait for next interval
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def start_dashboard(self):
        """Start the dashboard server."""
        logger.info(f"Starting performance dashboard on port {self.port}")
        
        # Start monitoring loop in background
        monitoring_task = asyncio.create_task(self.monitoring_loop())
        
        # Start web server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        
        logger.info(f"Dashboard available at: http://localhost:{self.port}")
        
        try:
            # Keep running
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down dashboard...")
        finally:
            monitoring_task.cancel()
            await runner.cleanup()

async def main():
    """Main dashboard function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Dashboard")
    parser.add_argument("--url", default="http://localhost:8000", help="TTS API base URL")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard port")
    parser.add_argument("--interval", type=int, default=5, help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = PerformanceDashboard(args.url, args.port)
    
    # Start dashboard
    await dashboard.start_dashboard()

if __name__ == "__main__":
    asyncio.run(main())
