"""
TTFA Benchmark Suite

Comprehensive TTFA (Time to First Audio) benchmarking with M-series Mac optimizations testing.
"""

import time
import logging
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from benchmarks.core.benchmark_runner import BenchmarkRunner, BenchmarkConfig, BenchmarkResult, BenchmarkMetrics

logger = logging.getLogger(__name__)


class TTFACategory(Enum):
    """TTFA performance categories with targets"""
    EXCELLENT = "excellent"     # <400ms (M-series target: <10ms)
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
    
    # M-series Mac specific (defaults must come after non-defaults)
    neural_engine_used: bool = False
    coreml_compute_units: Optional[str] = None
    session_type: Optional[str] = None  # 'ane', 'gpu', 'cpu'
    
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
    p50_ttfa_ms: float
    min_ttfa_ms: float
    max_ttfa_ms: float
    std_dev_ms: float
    
    # Target achievement
    target_ms: float
    success_rate: float
    excellent_rate: float  # <400ms
    good_rate: float       # 400-800ms
    m_series_target_rate: float  # <10ms for M-series
    
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
    
    # M-series Mac specific metrics (defaults last)
    neural_engine_usage_rate: float = 0.0
    coreml_provider_rate: float = 0.0
    
    def generate_report(self) -> str:
        """Generate human-readable benchmark report"""
        report = f"""
# TTFA Benchmark Report: {self.benchmark_name}

## Summary
- **Measurements**: {self.total_measurements}
- **Average TTFA**: {self.average_ttfa_ms:.1f}ms
- **Target**: {self.target_ms}ms
- **Success Rate**: {self.success_rate:.1%}
- **M-series Target (<10ms)**: {self.m_series_target_rate:.1%}

## Performance Distribution
- **Excellent (<400ms)**: {self.excellent_rate:.1%}
- **Good (400-800ms)**: {self.good_rate:.1%}
- **M-series Optimized (<10ms)**: {self.m_series_target_rate:.1%}
- **Target Achievement**: {self.success_rate:.1%}

## Timing Breakdown
- **Text Processing**: {self.avg_text_processing_ms:.1f}ms
- **Model Inference**: {self.avg_model_inference_ms:.1f}ms
- **Audio Conversion**: {self.avg_audio_conversion_ms:.1f}ms
- **Chunk Delivery**: {self.avg_chunk_delivery_ms:.1f}ms
- **Communication**: {self.avg_daemon_communication_ms:.1f}ms

## M-series Mac Optimizations
- **Neural Engine Usage**: {self.neural_engine_usage_rate:.1%}
- **CoreML Provider**: {self.coreml_provider_rate:.1%}

## Bottleneck Analysis
Primary bottleneck: **{self.primary_bottleneck}**

Frequency distribution:
"""
        for bottleneck, count in sorted(self.bottleneck_frequency.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / self.total_measurements) * 100
            report += f"- {bottleneck}: {count} times ({percentage:.1f}%)\n"
        
        return report


class TTFABenchmark:
    """Advanced TTFA benchmarking system with M-series Mac optimizations"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.measurements: List[TTFAMeasurement] = []
        self.logger = logging.getLogger(__name__)
        
        # M-series Mac test texts
        self.test_texts = {
            "short": "This is a short test sentence for TTFA and streaming cadence.",
            "medium": "This is a medium length paragraph used to benchmark real-time factor and end-to-end latency across providers and modes in a reproducible way.",
            "long": (
                "This is a long paragraph intended to exercise sustained synthesis performance, "
                "including punctuation, numerals such as 123 and 456, abbreviations like Dr. and St., "
                "and varied phonetic content. It should be long enough to measure RTF reliably."
            ),
            "complex": (
                "Testing complex scenarios: numbers like 12,345 and symbols @#$% with various punctuation! "
                "Does it handle URLs like https://example.com? And what about abbreviations like Dr. Smith or Mr. Jones?"
            ),
        }
    
    async def measure_single_ttfa(
        self,
        text: str,
        voice: str = "af_heart",
        speed: float = 1.0
    ) -> TTFAMeasurement:
        """Measure TTFA for a single request"""
        import aiohttp
        
        request_id = f"ttfa_{int(time.time() * 1000)}"
        start_time = time.perf_counter()
        
        payload = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "lang": "en-us",
            "stream": True,
            "format": "wav"
        }
        
        total_ttfa = 0.0
        provider_used = "unknown"
        first_chunk_time = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/v1/audio/speech",
                    json=payload
                ) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    # Try to get provider info from headers
                    provider_used = response.headers.get("X-Provider-Used", "unknown")
                    
                    async for chunk in response.content.iter_chunked(8192):
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                            total_ttfa = (first_chunk_time - start_time) * 1000.0
                            break
        
        except Exception as e:
            self.logger.error(f"TTFA measurement failed: {e}")
            total_ttfa = float('inf')
        
        # Categorize performance
        if total_ttfa < 10:
            category = TTFACategory.EXCELLENT
            target_met = True
        elif total_ttfa < 400:
            category = TTFACategory.EXCELLENT
            target_met = True
        elif total_ttfa < 800:
            category = TTFACategory.GOOD
            target_met = True
        elif total_ttfa < 1200:
            category = TTFACategory.ACCEPTABLE
            target_met = False
        elif total_ttfa < 2000:
            category = TTFACategory.POOR
            target_met = False
        else:
            category = TTFACategory.CRITICAL
            target_met = False
        
        measurement = TTFAMeasurement(
            request_id=request_id,
            text=text,
            text_length=len(text),
            voice=voice,
            speed=speed,
            total_ttfa_ms=total_ttfa,
            text_processing_ms=0.0,  # Would need instrumentation
            model_inference_ms=0.0,  # Would need instrumentation
            audio_conversion_ms=0.0,  # Would need instrumentation
            chunk_delivery_ms=0.0,  # Would need instrumentation
            daemon_communication_ms=0.0,  # Would need instrumentation
            provider_used=provider_used,
            segment_count=1,
            first_chunk_size=8192,
            processing_method="streaming",
            target_met=target_met,
            category=category,
            bottleneck="unknown",  # Would need analysis
            timestamp=time.time()
        )
        
        self.measurements.append(measurement)
        return measurement
    
    async def run_comprehensive_ttfa_benchmark(
        self,
        include_m_series_tests: bool = True
    ) -> TTFABenchmarkResult:
        """Run comprehensive TTFA benchmark suite"""
        self.logger.info("Starting comprehensive TTFA benchmark...")
        
        # Run measurements for each test text
        for text_name, text in self.test_texts.items():
            self.logger.info(f"Testing {text_name} text...")
            for _ in range(5):  # 5 trials per text type
                await self.measure_single_ttfa(text)
        
        # Calculate statistics
        successful_measurements = [m for m in self.measurements if m.total_ttfa_ms != float('inf')]
        
        if not successful_measurements:
            raise Exception("No successful TTFA measurements")
        
        ttfa_values = [m.total_ttfa_ms for m in successful_measurements]
        
        return TTFABenchmarkResult(
            benchmark_name="comprehensive_ttfa",
            total_measurements=len(self.measurements),
            average_ttfa_ms=float(statistics.mean(ttfa_values)),
            median_ttfa_ms=float(statistics.median(ttfa_values)),
            p95_ttfa_ms=float(self._percentile(ttfa_values, 0.95)),
            p50_ttfa_ms=float(self._percentile(ttfa_values, 0.50)),
            min_ttfa_ms=float(min(ttfa_values)),
            max_ttfa_ms=float(max(ttfa_values)),
            std_dev_ms=float(statistics.stdev(ttfa_values)) if len(ttfa_values) > 1 else 0.0,
            target_ms=800.0,
            success_rate=sum(1 for m in successful_measurements if m.target_met) / len(successful_measurements),
            excellent_rate=sum(1 for m in successful_measurements if m.total_ttfa_ms < 400) / len(successful_measurements),
            good_rate=sum(1 for m in successful_measurements if 400 <= m.total_ttfa_ms < 800) / len(successful_measurements),
            m_series_target_rate=sum(1 for m in successful_measurements if m.total_ttfa_ms < 10) / len(successful_measurements),
            primary_bottleneck="unknown",
            bottleneck_frequency={},
            avg_text_processing_ms=0.0,
            avg_model_inference_ms=0.0,
            avg_audio_conversion_ms=0.0,
            avg_chunk_delivery_ms=0.0,
            avg_daemon_communication_ms=0.0,
            measurements=self.measurements,
            timestamp=time.time(),
            neural_engine_usage_rate=0.0,
            coreml_provider_rate=sum(1 for m in successful_measurements if "coreml" in m.provider_used.lower()) / len(successful_measurements) if successful_measurements else 0.0
        )
    
    async def run_quick_ttfa_benchmark(self) -> TTFABenchmarkResult:
        """Run quick TTFA benchmark with reduced trials"""
        self.logger.info("Starting quick TTFA benchmark...")
        
        # Run measurements for short text only
        for _ in range(3):  # 3 trials
            await self.measure_single_ttfa(self.test_texts["short"])
        
        # Calculate statistics
        successful_measurements = [m for m in self.measurements if m.total_ttfa_ms != float('inf')]
        
        if not successful_measurements:
            raise Exception("No successful TTFA measurements")
        
        ttfa_values = [m.total_ttfa_ms for m in successful_measurements]
        
        return TTFABenchmarkResult(
            benchmark_name="quick_ttfa",
            total_measurements=len(self.measurements),
            average_ttfa_ms=float(statistics.mean(ttfa_values)),
            median_ttfa_ms=float(statistics.median(ttfa_values)),
            p95_ttfa_ms=float(self._percentile(ttfa_values, 0.95)),
            p50_ttfa_ms=float(self._percentile(ttfa_values, 0.50)),
            min_ttfa_ms=float(min(ttfa_values)),
            max_ttfa_ms=float(max(ttfa_values)),
            std_dev_ms=float(statistics.stdev(ttfa_values)) if len(ttfa_values) > 1 else 0.0,
            target_ms=800.0,
            success_rate=sum(1 for m in successful_measurements if m.target_met) / len(successful_measurements),
            excellent_rate=sum(1 for m in successful_measurements if m.total_ttfa_ms < 400) / len(successful_measurements),
            good_rate=sum(1 for m in successful_measurements if 400 <= m.total_ttfa_ms < 800) / len(successful_measurements),
            m_series_target_rate=sum(1 for m in successful_measurements if m.total_ttfa_ms < 10) / len(successful_measurements),
            primary_bottleneck="unknown",
            bottleneck_frequency={},
            avg_text_processing_ms=0.0,
            avg_model_inference_ms=0.0,
            avg_audio_conversion_ms=0.0,
            avg_chunk_delivery_ms=0.0,
            avg_daemon_communication_ms=0.0,
            measurements=self.measurements,
            timestamp=time.time(),
            neural_engine_usage_rate=0.0,
            coreml_provider_rate=sum(1 for m in successful_measurements if "coreml" in m.provider_used.lower()) / len(successful_measurements) if successful_measurements else 0.0
        )
    
    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]


class TTFABenchmarkSuite:
    """Suite runner for TTFA benchmarks"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.benchmark = TTFABenchmark(server_url)
        self.comprehensive_result: Optional[TTFABenchmarkResult] = None
    
    async def run_full_suite(self) -> Dict[str, TTFABenchmarkResult]:
        """Run full TTFA benchmark suite"""
        comprehensive = await self.benchmark.run_comprehensive_ttfa_benchmark()
        self.comprehensive_result = comprehensive
        return {
            "comprehensive": comprehensive
        }
    
    def generate_consolidated_report(self) -> str:
        """Generate consolidated report"""
        if self.comprehensive_result:
            return self.comprehensive_result.generate_report()
        return "No benchmark results available. Run benchmark suite first."
