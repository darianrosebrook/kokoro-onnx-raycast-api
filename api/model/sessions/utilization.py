"""
Session utilization tracking and monitoring.

This module provides comprehensive tracking of session usage patterns,
performance metrics, and resource utilization for optimization purposes.
"""

import time
import threading
from dataclasses import dataclass
from typing import Dict, Any, List
from collections import defaultdict, deque


@dataclass 
class SessionMetrics:
    """Individual session performance metrics."""
    total_requests: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    last_used: float = 0.0
    
    def update(self, processing_time: float, success: bool = True):
        """Update metrics with new request data."""
        self.total_requests += 1
        self.total_time += processing_time
        self.avg_time = self.total_time / self.total_requests
        self.min_time = min(self.min_time, processing_time)
        self.max_time = max(self.max_time, processing_time)
        self.last_used = time.time()
        
        if not success:
            self.error_count += 1


class SessionUtilizationTracker:
    """
    Advanced session utilization tracking and analysis.
    
    This tracker provides comprehensive monitoring of session usage patterns,
    performance trends, and resource utilization across all session types.
    """
    
    def __init__(self):
        self.metrics = defaultdict(SessionMetrics)
        self.concurrent_tracking = {
            'active_sessions': set(),
            'peak_concurrent': 0,
            'current_concurrent': 0
        }
        self.performance_history = deque(maxlen=1000)  # Last 1000 requests
        self.lock = threading.Lock()
        
        # Time-based tracking
        self.hourly_stats = defaultdict(lambda: defaultdict(int))
        self.daily_stats = defaultdict(lambda: defaultdict(int))
        
    def start_request(self, session_type: str, request_id: str):
        """Mark the start of a request for a session."""
        with self.lock:
            self.concurrent_tracking['active_sessions'].add(request_id)
            current = len(self.concurrent_tracking['active_sessions'])
            self.concurrent_tracking['current_concurrent'] = current
            self.concurrent_tracking['peak_concurrent'] = max(
                self.concurrent_tracking['peak_concurrent'], current
            )
    
    def complete_request(self, session_type: str, request_id: str, 
                        processing_time: float, success: bool = True):
        """Mark the completion of a request."""
        with self.lock:
            # Update session metrics
            self.metrics[session_type].update(processing_time, success)
            
            # Remove from active tracking
            self.concurrent_tracking['active_sessions'].discard(request_id)
            self.concurrent_tracking['current_concurrent'] = len(
                self.concurrent_tracking['active_sessions']
            )
            
            # Add to performance history
            self.performance_history.append({
                'timestamp': time.time(),
                'session_type': session_type,
                'processing_time': processing_time,
                'success': success
            })
            
            # Update time-based stats
            current_hour = int(time.time() // 3600)
            current_day = int(time.time() // 86400)
            
            self.hourly_stats[current_hour][session_type] += 1
            self.daily_stats[current_day][session_type] += 1
    
    def get_session_stats(self, session_type: str) -> Dict[str, Any]:
        """Get statistics for a specific session type."""
        with self.lock:
            metrics = self.metrics[session_type]
            
            return {
                'total_requests': metrics.total_requests,
                'total_time': metrics.total_time,
                'avg_time': metrics.avg_time,
                'min_time': metrics.min_time if metrics.min_time != float('inf') else 0.0,
                'max_time': metrics.max_time,
                'error_count': metrics.error_count,
                'error_rate': (metrics.error_count / metrics.total_requests * 100) if metrics.total_requests > 0 else 0.0,
                'last_used': metrics.last_used,
                'requests_per_hour': self._calculate_requests_per_hour(session_type)
            }
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall utilization statistics."""
        with self.lock:
            total_requests = sum(m.total_requests for m in self.metrics.values())
            total_time = sum(m.total_time for m in self.metrics.values())
            total_errors = sum(m.error_count for m in self.metrics.values())
            
            # Calculate session distribution
            session_distribution = {}
            for session_type, metrics in self.metrics.items():
                if total_requests > 0:
                    session_distribution[session_type] = {
                        'requests': metrics.total_requests,
                        'percentage': (metrics.total_requests / total_requests) * 100,
                        'avg_time': metrics.avg_time
                    }
            
            return {
                'total_requests': total_requests,
                'total_processing_time': total_time,
                'overall_error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0.0,
                'session_distribution': session_distribution,
                'concurrent_stats': {
                    'current_concurrent': self.concurrent_tracking['current_concurrent'],
                    'peak_concurrent': self.concurrent_tracking['peak_concurrent'],
                    'active_sessions': len(self.concurrent_tracking['active_sessions'])
                },
                'performance_trends': self._calculate_performance_trends()
            }
    
    def _calculate_requests_per_hour(self, session_type: str) -> float:
        """Calculate requests per hour for a session type."""
        current_hour = int(time.time() // 3600)
        recent_hours = [current_hour - i for i in range(3)]  # Last 3 hours
        
        total_requests = sum(
            self.hourly_stats.get(hour, {}).get(session_type, 0) 
            for hour in recent_hours
        )
        
        return total_requests / 3.0  # Average over 3 hours
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends from recent history."""
        if len(self.performance_history) < 10:
            return {'trend': 'insufficient_data'}
        
        # Split history into two halves for trend analysis
        mid_point = len(self.performance_history) // 2
        first_half = list(self.performance_history)[:mid_point]
        second_half = list(self.performance_history)[mid_point:]
        
        # Calculate average times for each half
        first_avg = sum(r['processing_time'] for r in first_half) / len(first_half)
        second_avg = sum(r['processing_time'] for r in second_half) / len(second_half)
        
        # Determine trend
        if second_avg < first_avg * 0.95:  # 5% improvement threshold
            trend = 'improving'
        elif second_avg > first_avg * 1.05:  # 5% degradation threshold
            trend = 'degrading'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'first_half_avg': first_avg,
            'second_half_avg': second_avg,
            'change_percentage': ((second_avg - first_avg) / first_avg) * 100
        }
    
    def get_session_efficiency_ranking(self) -> List[Dict[str, Any]]:
        """Get sessions ranked by efficiency (requests per second)."""
        with self.lock:
            rankings = []
            
            for session_type, metrics in self.metrics.items():
                if metrics.total_requests > 0 and metrics.total_time > 0:
                    efficiency = metrics.total_requests / metrics.total_time
                    rankings.append({
                        'session_type': session_type,
                        'efficiency': efficiency,
                        'avg_time': metrics.avg_time,
                        'total_requests': metrics.total_requests,
                        'error_rate': (metrics.error_count / metrics.total_requests) * 100
                    })
            
            # Sort by efficiency (descending)
            rankings.sort(key=lambda x: x['efficiency'], reverse=True)
            return rankings
    
    def reset_stats(self):
        """Reset all utilization statistics."""
        with self.lock:
            self.metrics.clear()
            self.concurrent_tracking = {
                'active_sessions': set(),
                'peak_concurrent': 0,
                'current_concurrent': 0
            }
            self.performance_history.clear()
            self.hourly_stats.clear()
            self.daily_stats.clear()
    
    def export_stats(self) -> Dict[str, Any]:
        """Export all statistics for reporting or analysis."""
        return {
            'timestamp': time.time(),
            'session_stats': {
                session_type: self.get_session_stats(session_type)
                for session_type in self.metrics.keys()
            },
            'overall_stats': self.get_overall_stats(),
            'efficiency_ranking': self.get_session_efficiency_ranking(),
            'recent_history': list(self.performance_history)[-100:]  # Last 100 requests
        }
