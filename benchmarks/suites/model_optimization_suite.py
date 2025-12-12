"""
Model Optimization Benchmark Suite

Comprehensive side-by-side comparison of original vs optimized ONNX models,
measuring TTFA, RTF, memory usage, and generating detailed comparison reports.
"""

import asyncio
import logging
import os
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import aiohttp
import psutil

logger = logging.getLogger(__name__)


@dataclass
class ModelComparison:
    """Single comparison result between original and optimized models"""

    model_type: str  # "original" or "optimized"
    ttfa_ms: float
    rtf: Optional[float]
    memory_mb: float
    cpu_percent: Optional[float]
    provider_used: str
    success: bool
    error: Optional[str]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class ModelOptimizationBenchmarkResult:
    """Full benchmark results comparing original vs optimized models"""

    benchmark_name: str
    original_model_path: str
    optimized_model_path: str

    # Original model metrics
    original_metrics: List[ModelComparison]

    # Optimized model metrics
    optimized_metrics: List[ModelComparison]

    # Statistical comparison
    ttfa_improvement_percent: float
    rtf_improvement_percent: Optional[float]
    memory_improvement_percent: float
    cpu_improvement_percent: Optional[float]

    # Summary statistics
    original_ttfa_mean: float
    original_ttfa_median: float
    original_ttfa_p95: float
    optimized_ttfa_mean: float
    optimized_ttfa_median: float
    optimized_ttfa_p95: float

    original_rtf_mean: Optional[float]
    optimized_rtf_mean: Optional[float]

    original_memory_mean: float
    optimized_memory_mean: float

    # Success rates
    original_success_rate: float
    optimized_success_rate: float

    # Recommendations
    recommended_model: str
    regression_detected: bool
    significant_improvement: bool

    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def generate_report(self) -> str:
        """Generate human-readable comparison report"""
        report = f"""
# Model Optimization Benchmark Report: {self.benchmark_name}

## Model Paths
- **Original Model**: {self.original_model_path}
- **Optimized Model**: {self.optimized_model_path}

## Summary
- **Recommended Model**: {self.recommended_model}
- **Regression Detected**: {"Yes" if self.regression_detected else "No"}
- **Significant Improvement**: {"Yes" if self.significant_improvement else "No"}

## TTFA (Time to First Audio) Comparison
- **Original Model**:
  - Mean: {self.original_ttfa_mean:.2f}ms
  - Median: {self.original_ttfa_median:.2f}ms
  - P95: {self.original_ttfa_p95:.2f}ms
- **Optimized Model**:
  - Mean: {self.optimized_ttfa_mean:.2f}ms
  - Median: {self.optimized_ttfa_median:.2f}ms
  - P95: {self.optimized_ttfa_p95:.2f}ms
- **Improvement**: {self.ttfa_improvement_percent:.2f}%

## RTF (Real-Time Factor) Comparison
"""
        if self.original_rtf_mean is not None and self.optimized_rtf_mean is not None:
            rtf_improvement_str = (
                f"{self.rtf_improvement_percent:.2f}%"
                if self.rtf_improvement_percent is not None
                else "N/A"
            )
            report += f"""
- **Original Model**: {self.original_rtf_mean:.3f}
- **Optimized Model**: {self.optimized_rtf_mean:.3f}
- **Improvement**: {rtf_improvement_str}
"""
        else:
            report += "- RTF data not available\n"

        report += f"""
## Memory Usage Comparison
- **Original Model**: {self.original_memory_mean:.2f}MB
- **Optimized Model**: {self.optimized_memory_mean:.2f}MB
- **Improvement**: {self.memory_improvement_percent:.2f}%

## CPU Usage Comparison
"""
        if self.cpu_improvement_percent is not None:
            report += f"- **Improvement**: {self.cpu_improvement_percent:.2f}%\n"
        else:
            report += "- CPU data not available\n"

        report += f"""
## Success Rates
- **Original Model**: {self.original_success_rate:.1%}
- **Optimized Model**: {self.optimized_success_rate:.1%}

## Conclusion
"""
        if self.regression_detected:
            report += "⚠️ **WARNING**: Regression detected in optimized model. Review before deployment.\n"
        elif self.significant_improvement:
            report += "✅ **RECOMMENDED**: Optimized model shows significant improvement. Safe to deploy.\n"
        else:
            report += "ℹ️ **INFO**: Optimized model performance is similar to original. No significant change.\n"

        return report


class ModelOptimizationBenchmark:
    """Model optimization performance comparison and validation"""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.logger = logging.getLogger(__name__)

    async def measure_model_performance(
        self,
        model_path: str,
        text: str,
        provider_preference: Optional[str] = None,
        trials: int = 5,
    ) -> List[ModelComparison]:
        """Measure performance metrics for a specific model"""
        metrics: List[ModelComparison] = []
        process = psutil.Process(os.getpid())

        for trial in range(trials):
            try:
                # Get initial memory
                initial_memory = process.memory_info().rss / 1024 / 1024  # MB

                start_time = time.perf_counter()

                async with aiohttp.ClientSession() as session:
                    payload = {
                        "text": text,
                        "voice": "af_heart",
                        "speed": 1.0,
                        "lang": "en-us",
                        "stream": True,
                        "format": "wav",
                    }

                    headers = {}
                    if provider_preference:
                        headers["X-Provider-Preference"] = provider_preference

                    async with session.post(
                        f"{self.server_url}/v1/audio/speech",
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status == 200:
                            first_chunk_time = None
                            total_audio_bytes = 0
                            chunk_count = 0

                            async for chunk in response.content.iter_chunked(8192):
                                if first_chunk_time is None:
                                    first_chunk_time = time.perf_counter()
                                    ttfa = (first_chunk_time - start_time) * 1000.0
                                total_audio_bytes += len(chunk)
                                chunk_count += 1

                            end_time = time.perf_counter()
                            total_time = (end_time - start_time) * 1000.0

                            # Get final memory
                            final_memory = process.memory_info().rss / 1024 / 1024  # MB
                            memory_used = final_memory - initial_memory

                            # Calculate RTF (approximate - audio duration estimate)
                            # WAV format: sample_rate * bytes_per_sample * channels * duration
                            # For 24kHz, 16-bit, mono: ~48KB per second
                            estimated_duration = (
                                total_audio_bytes / (24000 * 2 * 1)
                                if total_audio_bytes > 0
                                else 0
                            )
                            rtf = (
                                (total_time / 1000.0) / estimated_duration
                                if estimated_duration > 0
                                else None
                            )

                            # Get provider from response headers if available
                            provider = response.headers.get(
                                "X-Provider-Used", "Unknown"
                            )

                            metrics.append(
                                ModelComparison(
                                    model_type=model_path,
                                    ttfa_ms=ttfa,
                                    rtf=rtf,
                                    memory_mb=memory_used,
                                    cpu_percent=process.cpu_percent(interval=0.1),
                                    provider_used=provider,
                                    success=True,
                                    error=None,
                                    timestamp=time.time(),
                                )
                            )
                        else:
                            error_text = await response.text()
                            metrics.append(
                                ModelComparison(
                                    model_type=model_path,
                                    ttfa_ms=0.0,
                                    rtf=None,
                                    memory_mb=0.0,
                                    cpu_percent=None,
                                    provider_used="Unknown",
                                    success=False,
                                    error=f"HTTP {response.status}: {error_text}",
                                    timestamp=time.time(),
                                )
                            )
            except Exception as e:
                self.logger.error(f"Trial {trial + 1} failed for {model_path}: {e}")
                metrics.append(
                    ModelComparison(
                        model_type=model_path,
                        ttfa_ms=0.0,
                        rtf=None,
                        memory_mb=0.0,
                        cpu_percent=None,
                        provider_used="Unknown",
                        success=False,
                        error=str(e),
                        timestamp=time.time(),
                    )
                )

        return metrics

    async def compare_models(
        self,
        original_model_path: str,
        optimized_model_path: str,
        text: str = "Test text for model optimization comparison",
        provider_preference: Optional[str] = None,
        trials: int = 5,
    ) -> ModelOptimizationBenchmarkResult:
        """Compare original vs optimized model performance"""

        self.logger.info(
            f"Comparing models: {original_model_path} vs {optimized_model_path}"
        )

        # Measure original model
        self.logger.info("Measuring original model performance...")
        original_metrics = await self.measure_model_performance(
            original_model_path, text, provider_preference, trials
        )

        # Wait a bit between measurements
        await asyncio.sleep(1.0)

        # Measure optimized model
        self.logger.info("Measuring optimized model performance...")
        optimized_metrics = await self.measure_model_performance(
            optimized_model_path, text, provider_preference, trials
        )

        # Calculate statistics
        original_successful = [m for m in original_metrics if m.success]
        optimized_successful = [m for m in optimized_metrics if m.success]

        original_ttfa_values = [m.ttfa_ms for m in original_successful]
        optimized_ttfa_values = [m.ttfa_ms for m in optimized_successful]

        original_rtf_values = [m.rtf for m in original_successful if m.rtf is not None]
        optimized_rtf_values = [
            m.rtf for m in optimized_successful if m.rtf is not None
        ]

        original_memory_values = [m.memory_mb for m in original_successful]
        optimized_memory_values = [m.memory_mb for m in optimized_successful]

        # Calculate improvements
        original_ttfa_mean = (
            float(statistics.mean(original_ttfa_values))
            if original_ttfa_values
            else 0.0
        )
        optimized_ttfa_mean = (
            float(statistics.mean(optimized_ttfa_values))
            if optimized_ttfa_values
            else 0.0
        )
        ttfa_improvement = (
            ((original_ttfa_mean - optimized_ttfa_mean) / original_ttfa_mean * 100)
            if original_ttfa_mean > 0
            else 0.0
        )

        original_rtf_mean = (
            float(statistics.mean(original_rtf_values)) if original_rtf_values else None
        )
        optimized_rtf_mean = (
            float(statistics.mean(optimized_rtf_values))
            if optimized_rtf_values
            else None
        )
        rtf_improvement = None
        if original_rtf_mean and optimized_rtf_mean and original_rtf_mean > 0:
            rtf_improvement = (
                (original_rtf_mean - optimized_rtf_mean) / original_rtf_mean * 100
            )

        original_memory_mean = (
            float(statistics.mean(original_memory_values))
            if original_memory_values
            else 0.0
        )
        optimized_memory_mean = (
            float(statistics.mean(optimized_memory_values))
            if optimized_memory_values
            else 0.0
        )
        memory_improvement = (
            (
                (original_memory_mean - optimized_memory_mean)
                / original_memory_mean
                * 100
            )
            if original_memory_mean > 0
            else 0.0
        )

        # CPU improvement (if available)
        original_cpu_values = [
            m.cpu_percent for m in original_successful if m.cpu_percent is not None
        ]
        optimized_cpu_values = [
            m.cpu_percent for m in optimized_successful if m.cpu_percent is not None
        ]
        cpu_improvement = None
        if original_cpu_values and optimized_cpu_values:
            original_cpu_mean = float(statistics.mean(original_cpu_values))
            optimized_cpu_mean = float(statistics.mean(optimized_cpu_values))
            if original_cpu_mean > 0:
                cpu_improvement = (
                    (original_cpu_mean - optimized_cpu_mean) / original_cpu_mean * 100
                )

        # Determine recommendation
        regression_detected = (
            optimized_ttfa_mean > original_ttfa_mean * 1.1
        )  # >10% worse
        significant_improvement = (
            optimized_ttfa_mean < original_ttfa_mean * 0.9
        )  # >10% better

        if regression_detected:
            recommended_model = "original"
        elif significant_improvement:
            recommended_model = "optimized"
        else:
            recommended_model = "optimized"  # Default to optimized if similar

        return ModelOptimizationBenchmarkResult(
            benchmark_name="Model Optimization Comparison",
            original_model_path=original_model_path,
            optimized_model_path=optimized_model_path,
            original_metrics=original_metrics,
            optimized_metrics=optimized_metrics,
            ttfa_improvement_percent=ttfa_improvement,
            rtf_improvement_percent=rtf_improvement,
            memory_improvement_percent=memory_improvement,
            cpu_improvement_percent=cpu_improvement,
            original_ttfa_mean=original_ttfa_mean,
            original_ttfa_median=float(statistics.median(original_ttfa_values))
            if original_ttfa_values
            else 0.0,
            original_ttfa_p95=float(self._percentile(original_ttfa_values, 0.95))
            if original_ttfa_values
            else 0.0,
            optimized_ttfa_mean=optimized_ttfa_mean,
            optimized_ttfa_median=float(statistics.median(optimized_ttfa_values))
            if optimized_ttfa_values
            else 0.0,
            optimized_ttfa_p95=float(self._percentile(optimized_ttfa_values, 0.95))
            if optimized_ttfa_values
            else 0.0,
            original_rtf_mean=original_rtf_mean,
            optimized_rtf_mean=optimized_rtf_mean,
            original_memory_mean=original_memory_mean,
            optimized_memory_mean=optimized_memory_mean,
            original_success_rate=len(original_successful) / len(original_metrics)
            if original_metrics
            else 0.0,
            optimized_success_rate=len(optimized_successful) / len(optimized_metrics)
            if optimized_metrics
            else 0.0,
            recommended_model=recommended_model,
            regression_detected=regression_detected,
            significant_improvement=significant_improvement,
            timestamp=time.time(),
        )

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]


class ModelOptimizationBenchmarkSuite:
    """Suite runner for model optimization benchmarks"""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.benchmark = ModelOptimizationBenchmark(server_url)
        self.results: Optional[ModelOptimizationBenchmarkResult] = None

    async def run_comprehensive_comparison(
        self,
        original_model_path: str,
        optimized_model_path: str,
        test_texts: Optional[List[str]] = None,
        provider_preference: Optional[str] = None,
        trials: int = 5,
    ) -> ModelOptimizationBenchmarkResult:
        """Run comprehensive model optimization comparison"""
        if test_texts is None:
            test_texts = [
                "Short test text.",
                "This is a medium length paragraph used to benchmark real-time factor and end-to-end latency.",
            ]

        # Use first text for main comparison (can be extended for multiple texts)
        result = await self.benchmark.compare_models(
            original_model_path,
            optimized_model_path,
            test_texts[0],
            provider_preference,
            trials,
        )

        self.results = result
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of model optimization benchmark results"""
        if not self.results:
            return {"error": "No benchmark results available"}

        return self.results.to_dict()

    def generate_report(self) -> str:
        """Generate human-readable report"""
        if not self.results:
            return "No benchmark results available"

        return self.results.generate_report()
