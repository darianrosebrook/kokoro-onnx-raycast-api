#!/usr/bin/env python3
"""
Production Performance Monitor
@author @darianrosebrook

Real-time monitoring script for Kokoro TTS production deployment.
Monitors TTFA, memory usage, concurrent requests, and system health.
"""

import asyncio
import aiohttp
import psutil
import time
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/production_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionMonitor:
    """Real-time production performance monitor for Kokoro TTS."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", interval: int = 30):
        self.base_url = base_url
        self.interval = interval
        self.session = None
        self.metrics_history: List[Dict] = []
        self.alert_thresholds = {
            'ttfa_ms': 500,  # TTFA should be <500ms
            'memory_mb': 100,  # Memory should be <100MB
            'concurrent_requests': 4,  # Avoid >4 concurrent requests
            'cold_start_penalty': 5000,  # Cold start should be <5s
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_server_status(self) -> Optional[Dict]:
        """Get server status and health information."""
        try:
            async with self.session.get(f"{self.base_url}/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Server status failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to get server status: {e}")
            return None
    
    async def get_performance_status(self) -> Optional[Dict]:
        """Get detailed performance metrics."""
        try:
            async with self.session.get(f"{self.base_url}/performance/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Performance status failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to get performance status: {e}")
            return None
    
    async def test_ttfa(self, text: str = "Hello world") -> Tuple[float, bool]:
        """Test TTFA with a simple request."""
        start_time = time.time()
        try:
            payload = {
                "text": text,
                "voice": "af_heart",
                "speed": 1.0
            }
            
            async with self.session.post(
                f"{self.base_url}/v1/audio/speech",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    ttfa_ms = (time.time() - start_time) * 1000
                    is_cold_start = ttfa_ms > self.alert_thresholds['cold_start_penalty']
                    return ttfa_ms, is_cold_start
                else:
                    logger.error(f"TTFA test failed: {response.status}")
                    return float('inf'), False
        except Exception as e:
            logger.error(f"TTFA test error: {e}")
            return float('inf'), False
    
    def get_system_metrics(self) -> Dict:
        """Get system-level metrics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections()),
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    def check_alerts(self, metrics: Dict) -> List[str]:
        """Check for performance alerts."""
        alerts = []
        
        # TTFA alerts
        if metrics.get('ttfa_ms', 0) > self.alert_thresholds['ttfa_ms']:
            alerts.append(f"⚠️  High TTFA: {metrics['ttfa_ms']:.1f}ms > {self.alert_thresholds['ttfa_ms']}ms")
        
        # Memory alerts
        if metrics.get('rss_mb', 0) > self.alert_thresholds['memory_mb']:
            alerts.append(f"⚠️  High memory: {metrics['rss_mb']:.1f}MB > {self.alert_thresholds['memory_mb']}MB")
        
        # Cold start alerts
        if metrics.get('is_cold_start', False):
            alerts.append(f"⚠️  Cold start detected: {metrics['ttfa_ms']:.1f}ms")
        
        # Provider alerts
        if metrics.get('active_provider') != 'CPUExecutionProvider':
            alerts.append(f"⚠️  Non-optimal provider: {metrics.get('active_provider', 'unknown')}")
        
        return alerts
    
    def format_metrics(self, metrics: Dict) -> str:
        """Format metrics for display."""
        lines = [
            f"📊 Performance Metrics ({datetime.now().strftime('%H:%M:%S')})",
            f"   TTFA: {metrics.get('ttfa_ms', 'N/A'):.1f}ms",
            f"   Memory: {metrics.get('rss_mb', 'N/A'):.1f}MB",
            f"   Provider: {metrics.get('active_provider', 'N/A')}",
            f"   CPU: {metrics.get('cpu_percent', 'N/A'):.1f}%",
            f"   Threads: {metrics.get('num_threads', 'N/A')}",
        ]
        
        if metrics.get('is_cold_start'):
            lines.append(f"   🥶 Cold Start: {metrics['ttfa_ms']:.1f}ms")
        
        return "\n".join(lines)
    
    async def run_monitoring_cycle(self) -> Dict:
        """Run one complete monitoring cycle."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'ttfa_ms': float('inf'),
            'rss_mb': 0,
            'cpu_percent': 0,
            'num_threads': 0,
            'active_provider': 'unknown',
            'is_cold_start': False,
            'alerts': []
        }
        
        # Get server status
        status = await self.get_server_status()
        if status:
            tts_processing = status.get('tts_processing', {})
            metrics['active_provider'] = tts_processing.get('active_provider', 'unknown')
        
        # Get performance status
        perf_status = await self.get_performance_status()
        if perf_status:
            # Extract any performance metrics from the response
            pass
        
        # Test TTFA
        ttfa_ms, is_cold_start = await self.test_ttfa()
        metrics['ttfa_ms'] = ttfa_ms
        metrics['is_cold_start'] = is_cold_start
        
        # Get system metrics
        system_metrics = self.get_system_metrics()
        metrics.update(system_metrics)
        
        # Check for alerts
        metrics['alerts'] = self.check_alerts(metrics)
        
        # Store in history
        self.metrics_history.append(metrics)
        
        # Keep only last 100 entries
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        return metrics
    
    async def monitor_continuously(self):
        """Run continuous monitoring."""
        logger.info(f"🚀 Starting production monitoring for {self.base_url}")
        logger.info(f"📊 Monitoring interval: {self.interval} seconds")
        logger.info(f"🎯 Alert thresholds: TTFA<{self.alert_thresholds['ttfa_ms']}ms, Memory<{self.alert_thresholds['memory_mb']}MB")
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                logger.info(f"🔄 Monitoring cycle {cycle_count}")
                
                metrics = await self.run_monitoring_cycle()
                
                # Display metrics
                print("\n" + "="*60)
                print(self.format_metrics(metrics))
                
                # Display alerts
                if metrics['alerts']:
                    print("\n🚨 ALERTS:")
                    for alert in metrics['alerts']:
                        print(f"   {alert}")
                
                # Display summary
                if cycle_count > 1:
                    avg_ttfa = sum(m['ttfa_ms'] for m in self.metrics_history[-10:] if m['ttfa_ms'] != float('inf')) / len([m for m in self.metrics_history[-10:] if m['ttfa_ms'] != float('inf')])
                    avg_memory = sum(m['rss_mb'] for m in self.metrics_history[-10:]) / len(self.metrics_history[-10:])
                    print(f"\n📈 Last 10 cycles average: TTFA={avg_ttfa:.1f}ms, Memory={avg_memory:.1f}MB")
                
                print("="*60)
                
                # Wait for next cycle
                await asyncio.sleep(self.interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Monitoring cycle failed: {e}")
                await asyncio.sleep(self.interval)
    
    def save_metrics_report(self, filename: str = None):
        """Save metrics history to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"artifacts/monitoring/production_metrics_{timestamp}.json"
        
        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'monitoring_session': {
                'start_time': self.metrics_history[0]['timestamp'] if self.metrics_history else None,
                'end_time': datetime.now().isoformat(),
                'total_cycles': len(self.metrics_history),
                'alert_thresholds': self.alert_thresholds,
            },
            'metrics': self.metrics_history,
            'summary': self.calculate_summary()
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 Metrics report saved: {filename}")
        return filename
    
    def calculate_summary(self) -> Dict:
        """Calculate summary statistics from metrics history."""
        if not self.metrics_history:
            return {}
        
        valid_ttfa = [m['ttfa_ms'] for m in self.metrics_history if m['ttfa_ms'] != float('inf')]
        memory_values = [m['rss_mb'] for m in self.metrics_history if m['rss_mb'] > 0]
        cold_starts = sum(1 for m in self.metrics_history if m.get('is_cold_start', False))
        alerts = sum(len(m.get('alerts', [])) for m in self.metrics_history)
        
        return {
            'ttfa_stats': {
                'count': len(valid_ttfa),
                'mean': sum(valid_ttfa) / len(valid_ttfa) if valid_ttfa else 0,
                'min': min(valid_ttfa) if valid_ttfa else 0,
                'max': max(valid_ttfa) if valid_ttfa else 0,
            },
            'memory_stats': {
                'count': len(memory_values),
                'mean': sum(memory_values) / len(memory_values) if memory_values else 0,
                'min': min(memory_values) if memory_values else 0,
                'max': max(memory_values) if memory_values else 0,
            },
            'cold_starts': cold_starts,
            'total_alerts': alerts,
            'uptime_percentage': ((len(self.metrics_history) - alerts) / len(self.metrics_history) * 100) if self.metrics_history else 0
        }

async def main():
    """Main monitoring function."""
    parser = argparse.ArgumentParser(description="Kokoro TTS Production Monitor")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Server URL")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    parser.add_argument("--save-report", action="store_true", help="Save metrics report on exit")
    
    args = parser.parse_args()
    
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    async with ProductionMonitor(args.url, args.interval) as monitor:
        try:
            await monitor.monitor_continuously()
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring stopped")
        
        if args.save_report:
            report_file = monitor.save_metrics_report()
            print(f"\n📄 Metrics report saved: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())
