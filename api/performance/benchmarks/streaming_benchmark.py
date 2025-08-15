"""
Streaming Performance Benchmark System

This module measures streaming efficiency, buffer management, and audio delivery performance.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class StreamingMetrics:
    """Metrics for streaming performance analysis"""
    total_chunks: int
    avg_chunk_size: int
    min_chunk_size: int
    max_chunk_size: int
    
    # Timing metrics
    total_duration_ms: float
    time_to_first_chunk_ms: float
    avg_chunk_interval_ms: float
    max_chunk_gap_ms: float
    
    # Efficiency metrics
    efficiency: float           # 0-1 score for streaming smoothness
    buffer_underruns: int      # Number of potential audio gaps
    data_rate_kbps: float      # Data delivery rate
    
    # Quality metrics
    continuity_score: float    # How continuous the stream was
    latency_consistency: float # How consistent chunk delivery was
    
    timestamp: float

class StreamingBenchmark:
    """
    Streaming performance measurement and analysis.
    
    This class measures how effectively the TTS system streams audio,
    focusing on continuity, latency, and buffer management.
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
    
    async def measure_streaming_performance(
        self,
        text: str,
        voice: str = "af_heart",
        speed: float = 1.0
    ) -> StreamingMetrics:
        """
        Measure comprehensive streaming performance for a TTS request.
        """
        start_time = time.perf_counter()
        logger.debug(f"Measuring streaming performance for: '{text[:30]}...'")
        
        chunk_times = []
        chunk_sizes = []
        total_data = 0
        first_chunk_time = None
        
        payload = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "format": "pcm"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/v1/audio/speech",
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    chunk_count = 0
                    async for chunk in response.content.iter_chunked(1024):
                        chunk_time = time.perf_counter()
                        
                        if first_chunk_time is None:
                            first_chunk_time = chunk_time
                        
                        chunk_times.append(chunk_time)
                        chunk_sizes.append(len(chunk))
                        total_data += len(chunk)
                        chunk_count += 1
        
        except Exception as e:
            logger.error(f"Streaming measurement failed: {e}")
            raise
        
        end_time = time.perf_counter()
        
        # Calculate metrics
        total_duration_ms = (end_time - start_time) * 1000
        time_to_first_chunk_ms = ((first_chunk_time or start_time) - start_time) * 1000
        
        # Chunk timing analysis
        if len(chunk_times) > 1:
            intervals = []
            for i in range(1, len(chunk_times)):
                interval = (chunk_times[i] - chunk_times[i-1]) * 1000
                intervals.append(interval)
            
            avg_chunk_interval_ms = sum(intervals) / len(intervals)
            max_chunk_gap_ms = max(intervals)
        else:
            avg_chunk_interval_ms = 0
            max_chunk_gap_ms = 0
        
        # Calculate efficiency and quality scores
        efficiency = self._calculate_efficiency(chunk_sizes, intervals if len(chunk_times) > 1 else [])
        buffer_underruns = sum(1 for interval in (intervals if len(chunk_times) > 1 else []) if interval > 100)
        data_rate_kbps = (total_data * 8) / (total_duration_ms / 1000) / 1000 if total_duration_ms > 0 else 0
        
        continuity_score = max(0, 1.0 - (buffer_underruns / max(1, len(chunk_times))))
        latency_consistency = self._calculate_latency_consistency(intervals if len(chunk_times) > 1 else [])
        
        return StreamingMetrics(
            total_chunks=len(chunk_sizes),
            avg_chunk_size=int(sum(chunk_sizes) / len(chunk_sizes)) if chunk_sizes else 0,
            min_chunk_size=min(chunk_sizes) if chunk_sizes else 0,
            max_chunk_size=max(chunk_sizes) if chunk_sizes else 0,
            total_duration_ms=total_duration_ms,
            time_to_first_chunk_ms=time_to_first_chunk_ms,
            avg_chunk_interval_ms=avg_chunk_interval_ms,
            max_chunk_gap_ms=max_chunk_gap_ms,
            efficiency=efficiency,
            buffer_underruns=buffer_underruns,
            data_rate_kbps=data_rate_kbps,
            continuity_score=continuity_score,
            latency_consistency=latency_consistency,
            timestamp=time.time()
        )
    
    def _calculate_efficiency(self, chunk_sizes: List[int], intervals: List[float]) -> float:
        """Calculate streaming efficiency score (0-1)"""
        if not chunk_sizes:
            return 0.0
        
        # Base efficiency on chunk size consistency and timing
        size_consistency = 1.0 - (self._coefficient_of_variation(chunk_sizes) if len(chunk_sizes) > 1 else 0)
        
        if intervals:
            timing_consistency = 1.0 - min(1.0, self._coefficient_of_variation(intervals))
        else:
            timing_consistency = 1.0
        
        # Penalize for very small or very large chunks
        avg_size = sum(chunk_sizes) / len(chunk_sizes)
        size_penalty = 0
        if avg_size < 100:  # Too small chunks
            size_penalty = 0.2
        elif avg_size > 2000:  # Too large chunks
            size_penalty = 0.1
        
        efficiency = (size_consistency + timing_consistency) / 2 - size_penalty
        return max(0.0, min(1.0, efficiency))
    
    def _calculate_latency_consistency(self, intervals: List[float]) -> float:
        """Calculate how consistent chunk delivery timing is"""
        if not intervals or len(intervals) < 2:
            return 1.0
        
        cv = self._coefficient_of_variation(intervals)
        return max(0.0, 1.0 - cv)
    
    def _coefficient_of_variation(self, values: List[float]) -> float:
        """Calculate coefficient of variation (std dev / mean)"""
        if not values or len(values) < 2:
            return 0.0
        
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return 0.0
        
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        return std_dev / mean_val