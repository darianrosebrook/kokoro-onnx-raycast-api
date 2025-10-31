"""
Provider Benchmark Suite

Comprehensive provider comparison benchmarking (CoreML vs CPU) with M-series Mac optimization validation.
"""

import time
import logging
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class ProviderComparison:
    """Comparison between different providers"""
    coreml_avg_time_ms: float
    cpu_avg_time_ms: float
    coreml_success_rate: float
    cpu_success_rate: float
    recommended_provider: str
    performance_ratio: float  # CoreML vs CPU speed ratio
    m_series_optimized: bool
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class ProviderBenchmark:
    """Provider performance comparison and optimization validation"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.logger = logging.getLogger(__name__)
    
    async def compare_providers(
        self,
        text: str = "Test text for provider comparison",
        trials: int = 5
    ) -> ProviderComparison:
        """Compare CoreML vs CPU provider performance"""
        
        # Test CoreML provider
        coreml_times: List[float] = []
        coreml_successes = 0
        
        for _ in range(trials):
            try:
                start_time = time.perf_counter()
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "text": text,
                        "voice": "af_heart",
                        "speed": 1.0,
                        "lang": "en-us",
                        "stream": True,
                        "format": "wav"
                    }
                    
                    async with session.post(
                        f"{self.server_url}/v1/audio/speech",
                        json=payload,
                        headers={"X-Provider-Preference": "CoreMLExecutionProvider"}
                    ) as response:
                        if response.status == 200:
                            first_chunk_time = None
                            async for chunk in response.content.iter_chunked(8192):
                                if first_chunk_time is None:
                                    first_chunk_time = time.perf_counter()
                                    ttfa = (first_chunk_time - start_time) * 1000.0
                                    coreml_times.append(ttfa)
                                    coreml_successes += 1
                                break
                        else:
                            self.logger.warning(f"CoreML request failed: {response.status}")
            except Exception as e:
                self.logger.error(f"CoreML benchmark failed: {e}")
        
        # Test CPU provider
        cpu_times: List[float] = []
        cpu_successes = 0
        
        for _ in range(trials):
            try:
                start_time = time.perf_counter()
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "text": text,
                        "voice": "af_heart",
                        "speed": 1.0,
                        "lang": "en-us",
                        "stream": True,
                        "format": "wav"
                    }
                    
                    async with session.post(
                        f"{self.server_url}/v1/audio/speech",
                        json=payload,
                        headers={"X-Provider-Preference": "CPUExecutionProvider"}
                    ) as response:
                        if response.status == 200:
                            first_chunk_time = None
                            async for chunk in response.content.iter_chunked(8192):
                                if first_chunk_time is None:
                                    first_chunk_time = time.perf_counter()
                                    ttfa = (first_chunk_time - start_time) * 1000.0
                                    cpu_times.append(ttfa)
                                    cpu_successes += 1
                                break
                        else:
                            self.logger.warning(f"CPU request failed: {response.status}")
            except Exception as e:
                self.logger.error(f"CPU benchmark failed: {e}")
        
        # Calculate statistics
        coreml_avg = float(statistics.mean(coreml_times)) if coreml_times else float('inf')
        cpu_avg = float(statistics.mean(cpu_times)) if cpu_times else float('inf')
        
        coreml_success_rate = coreml_successes / trials if trials > 0 else 0.0
        cpu_success_rate = cpu_successes / trials if trials > 0 else 0.0
        
        # Determine recommended provider
        if coreml_avg < cpu_avg * 0.9:  # CoreML is >10% faster
            recommended = "CoreMLExecutionProvider"
            performance_ratio = cpu_avg / coreml_avg if coreml_avg > 0 else 1.0
        elif cpu_avg < coreml_avg * 0.9:  # CPU is >10% faster
            recommended = "CPUExecutionProvider"
            performance_ratio = coreml_avg / cpu_avg if cpu_avg > 0 else 1.0
        else:
            recommended = "CPUExecutionProvider"  # Default to CPU for consistency
            performance_ratio = 1.0
        
        # Check if M-series optimized (CoreML available and performing well)
        m_series_optimized = (
            recommended == "CoreMLExecutionProvider" and
            coreml_avg < 10.0  # M-series target: <10ms TTFA
        )
        
        return ProviderComparison(
            coreml_avg_time_ms=coreml_avg,
            cpu_avg_time_ms=cpu_avg,
            coreml_success_rate=coreml_success_rate,
            cpu_success_rate=cpu_success_rate,
            recommended_provider=recommended,
            performance_ratio=performance_ratio,
            m_series_optimized=m_series_optimized,
            timestamp=time.time()
        )
    
    async def run_comprehensive_provider_benchmark(
        self,
        test_texts: Optional[List[str]] = None
    ) -> Dict[str, ProviderComparison]:
        """Run comprehensive provider comparison across multiple texts"""
        if test_texts is None:
            test_texts = [
                "Short test text.",
                "This is a medium length paragraph used to benchmark real-time factor and end-to-end latency.",
                "This is a long paragraph intended to exercise sustained synthesis performance, including punctuation, numerals such as 123 and 456, abbreviations like Dr. and St., and varied phonetic content."
            ]
        
        results: Dict[str, ProviderComparison] = {}
        
        for i, text in enumerate(test_texts):
            text_type = ["short", "medium", "long"][i] if i < 3 else f"text_{i}"
            self.logger.info(f"Comparing providers for {text_type} text...")
            
            comparison = await self.compare_providers(text, trials=5)
            results[text_type] = comparison
        
        return results


class ProviderBenchmarkSuite:
    """Suite runner for provider benchmarks"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.benchmark = ProviderBenchmark(server_url)
        self.comprehensive_results: Optional[Dict[str, ProviderComparison]] = None
    
    async def run_comprehensive_provider_benchmark(
        self,
        test_texts: Optional[List[str]] = None
    ) -> Dict[str, ProviderComparison]:
        """Run comprehensive provider benchmark suite"""
        results = await self.benchmark.run_comprehensive_provider_benchmark(test_texts)
        self.comprehensive_results = results
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of provider benchmark results"""
        if not self.comprehensive_results:
            return {"error": "No benchmark results available"}
        
        summary = {
            "provider_comparisons": {},
            "overall_recommendation": None,
            "m_series_optimized_count": 0
        }
        
        for text_type, comparison in self.comprehensive_results.items():
            summary["provider_comparisons"][text_type] = comparison.to_dict()
            if comparison.m_series_optimized:
                summary["m_series_optimized_count"] += 1
        
        # Determine overall recommendation
        recommendations = [c.recommended_provider for c in self.comprehensive_results.values()]
        if recommendations:
            summary["overall_recommendation"] = max(set(recommendations), key=recommendations.count)
        
        return summary




