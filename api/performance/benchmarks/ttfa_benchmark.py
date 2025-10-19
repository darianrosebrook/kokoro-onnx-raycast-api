"""
TTFA (Time to First Audio) Benchmark System

This module implements comprehensive TTFA benchmarking to identify and optimize
bottlenecks in the audio generation pipeline, specifically targeting the 800ms goal.
"""

import asyncio
import time
import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)

class TTFACategory(Enum):
    """TTFA performance categories with targets"""
    EXCELLENT = "excellent"     # <400ms
    GOOD = "good"              # 400-800ms  
    ACCEPTABLE = "acceptable"   # 800-1200ms
    POOR = "poor"              # 1200-2000ms
    CRITICAL = "critical"      # >2000ms

@dataclass
class TTFAMeasurement:
    """Single TTFA measurement with detailed timing breakdown"""
    request_id: str
    text: str
    text_length: int
    voice: str
    speed: float
    
    # Timing measurements (all in milliseconds)
    total_ttfa_ms: float
    text_processing_ms: float
    model_inference_ms: float
    audio_conversion_ms: float
    chunk_delivery_ms: float
    daemon_communication_ms: float
    
    # Performance metadata
    provider_used: str
    segment_count: int
    first_chunk_size: int
    processing_method: str
    
    # Success metrics
    target_met: bool
    category: TTFACategory
    bottleneck: str
    
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['category'] = self.category.value
        return result

@dataclass
class TTFABenchmarkResult:
    """Results from a TTFA benchmark run"""
    benchmark_name: str
    total_measurements: int
    
    # Statistical analysis
    average_ttfa_ms: float
    median_ttfa_ms: float
    p95_ttfa_ms: float
    min_ttfa_ms: float
    max_ttfa_ms: float
    std_dev_ms: float
    
    # Target achievement
    target_ms: float
    success_rate: float
    excellent_rate: float  # <400ms
    good_rate: float       # 400-800ms
    
    # Bottleneck analysis
    primary_bottleneck: str
    bottleneck_frequency: Dict[str, int]
    
    # Performance breakdown
    avg_text_processing_ms: float
    avg_model_inference_ms: float
    avg_audio_conversion_ms: float
    avg_chunk_delivery_ms: float
    avg_daemon_communication_ms: float
    
    measurements: List[TTFAMeasurement]
    timestamp: float
    
    def generate_report(self) -> str:
        """Generate human-readable benchmark report"""
        report = f"""
# TTFA Benchmark Report: {self.benchmark_name}

## Summary
- **Measurements**: {self.total_measurements}
- **Median TTFA (P50)**: {self.average_ttfa_ms:.1f}ms
- **Target**: {self.target_ms}ms
- **Success Rate**: {self.success_rate:.1%}

## Performance Distribution
- **Excellent (<400ms)**: {self.excellent_rate:.1%}
- **Good (400-800ms)**: {self.good_rate:.1%}
- **Target Achievement**: {self.success_rate:.1%}

## Timing Breakdown
- **Text Processing**: {self.avg_text_processing_ms:.1f}ms
- **Model Inference**: {self.avg_model_inference_ms:.1f}ms
- **Audio Conversion**: {self.avg_audio_conversion_ms:.1f}ms
- **Chunk Delivery**: {self.avg_chunk_delivery_ms:.1f}ms
- **Communication**: {self.avg_daemon_communication_ms:.1f}ms

## Bottleneck Analysis
Primary bottleneck: **{self.primary_bottleneck}**

Frequency distribution:
"""
        for bottleneck, count in sorted(self.bottleneck_frequency.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / self.total_measurements) * 100
            report += f"- {bottleneck}: {count} times ({percentage:.1f}%)\n"
        
        return report


class TTFABenchmark:
    """
    Advanced TTFA benchmarking system with detailed performance analysis.
    
    This class provides comprehensive TTFA testing across different scenarios
    and identifies specific bottlenecks in the audio generation pipeline.
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.measurements: List[TTFAMeasurement] = []