"""
Unified Benchmark Core Architecture

This module provides the core infrastructure for all benchmark suites,
ensuring consistency across CLI and API benchmarks.
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution"""

    server_url: str = "http://localhost:8000"
    voice: str = "af_heart"
    lang: str = "en-us"
    speed: float = 1.0
    timeout: int = 120
    trials: int = 5
    verbose: bool = False
    save_audio: bool = False
    stream: bool = True
    model_path: Optional[str] = None  # Optional model path override
    compare_models: bool = False  # Enable model comparison mode


@dataclass
class BenchmarkMetrics:
    """Core metrics collected during benchmarking"""

    ttfa_ms: Optional[float] = None
    rtf: Optional[float] = None
    total_time_ms: Optional[float] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    provider_used: Optional[str] = None
    chunks_delivered: Optional[int] = None
    audio_duration_s: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    timestamp: float = 0.0
    model_version: Optional[str] = (
        None  # "original" or "optimized" for model comparison
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""

    benchmark_name: str
    config: BenchmarkConfig
    metrics: List[BenchmarkMetrics]
    timestamp: float

    def get_summary(self) -> Dict[str, Any]:
        """Generate statistical summary"""
        if not self.metrics:
            return {"error": "No metrics collected"}

        successful_metrics = [m for m in self.metrics if m.success]

        if not successful_metrics:
            return {"error": "No successful measurements"}

        ttfa_values = [m.ttfa_ms for m in successful_metrics if m.ttfa_ms is not None]
        rtf_values = [m.rtf for m in successful_metrics if m.rtf is not None]

        summary = {
            "benchmark_name": self.benchmark_name,
            "total_trials": len(self.metrics),
            "successful_trials": len(successful_metrics),
            "success_rate": len(successful_metrics) / len(self.metrics)
            if self.metrics
            else 0,
        }

        if ttfa_values:
            summary["ttfa"] = {
                "mean": float(statistics.mean(ttfa_values)),
                "median": float(statistics.median(ttfa_values)),
                "min": float(min(ttfa_values)),
                "max": float(max(ttfa_values)),
                "p95": float(self._percentile(ttfa_values, 0.95)),
                "p50": float(self._percentile(ttfa_values, 0.50)),
            }

        if rtf_values:
            summary["rtf"] = {
                "mean": float(statistics.mean(rtf_values)),
                "median": float(statistics.median(rtf_values)),
                "min": float(min(rtf_values)),
                "max": float(max(rtf_values)),
                "p95": float(self._percentile(rtf_values, 0.95)),
            }

        return summary

    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "benchmark_name": self.benchmark_name,
            "config": asdict(self.config),
            "metrics": [m.to_dict() for m in self.metrics],
            "summary": self.get_summary(),
            "timestamp": self.timestamp,
        }


class BenchmarkRunner:
    """Core benchmark runner for unified execution"""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def run_streaming_benchmark(self, text: str) -> BenchmarkMetrics:
        """Run a single streaming benchmark"""
        metrics = BenchmarkMetrics(timestamp=time.time())

        payload = {
            "text": text,
            "voice": self.config.voice,
            "speed": self.config.speed,
            "lang": self.config.lang,
            "stream": True,
            "format": "wav",
        }

        start_time = time.perf_counter()
        first_chunk_time = None
        chunks_delivered = 0
        audio_bytes = b""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.server_url}/v1/audio/speech",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                ) as response:
                    if response.status != 200:
                        metrics.success = False
                        metrics.error = (
                            f"HTTP {response.status}: {await response.text()}"
                        )
                        return metrics

                    async for chunk in response.content.iter_chunked(8192):
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                            metrics.ttfa_ms = (first_chunk_time - start_time) * 1000.0

                        chunks_delivered += 1
                        audio_bytes += chunk

                    total_time = time.perf_counter() - start_time
                    metrics.total_time_ms = total_time * 1000.0
                    metrics.chunks_delivered = chunks_delivered

                    # Parse audio duration if possible
                    duration = self._parse_audio_duration(audio_bytes)
                    if duration:
                        metrics.audio_duration_s = duration
                        metrics.rtf = (total_time / duration) if duration > 0 else None

        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            self.logger.error(f"Streaming benchmark failed: {e}")

        return metrics

    async def run_nonstreaming_benchmark(self, text: str) -> BenchmarkMetrics:
        """Run a single non-streaming benchmark"""
        metrics = BenchmarkMetrics(timestamp=time.time())

        payload = {
            "text": text,
            "voice": self.config.voice,
            "speed": self.config.speed,
            "lang": self.config.lang,
            "stream": False,
            "format": "wav",
        }

        start_time = time.perf_counter()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.server_url}/v1/audio/speech",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                ) as response:
                    if response.status != 200:
                        metrics.success = False
                        metrics.error = (
                            f"HTTP {response.status}: {await response.text()}"
                        )
                        return metrics

                    audio_bytes = await response.read()
                    total_time = time.perf_counter() - start_time

                    metrics.total_time_ms = total_time * 1000.0
                    metrics.ttfa_ms = (
                        total_time * 1000.0
                    )  # For non-streaming, TTFA = total time

                    # Parse audio duration
                    duration = self._parse_audio_duration(audio_bytes)
                    if duration:
                        metrics.audio_duration_s = duration
                        metrics.rtf = (total_time / duration) if duration > 0 else None

        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            self.logger.error(f"Non-streaming benchmark failed: {e}")

        return metrics

    def _parse_audio_duration(self, audio_bytes: bytes) -> Optional[float]:
        """Parse audio duration from bytes"""
        try:
            import io
            import wave

            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            try:
                import soundfile as sf

                with sf.SoundFile(io.BytesIO(audio_bytes)) as f:
                    return len(f) / float(f.samplerate)
            except Exception:
                return None

    async def run_benchmark_suite(
        self, texts: List[str], benchmark_name: str
    ) -> BenchmarkResult:
        """Run a suite of benchmarks"""
        all_metrics: List[BenchmarkMetrics] = []

        for i, text in enumerate(texts):
            self.logger.info(
                f"Running trial {i + 1}/{len(texts) * self.config.trials}..."
            )

            for trial in range(self.config.trials):
                if self.config.stream:
                    metrics = await self.run_streaming_benchmark(text)
                else:
                    metrics = await self.run_nonstreaming_benchmark(text)

                all_metrics.append(metrics)

                if self.config.verbose:
                    if metrics.success:
                        self.logger.debug(
                            f"  Trial {trial + 1}: TTFA={metrics.ttfa_ms:.1f}ms, RTF={metrics.rtf:.3f if metrics.rtf else 'N/A'}"
                        )
                    else:
                        self.logger.warning(
                            f"  Trial {trial + 1}: Failed - {metrics.error}"
                        )

        return BenchmarkResult(
            benchmark_name=benchmark_name,
            config=self.config,
            metrics=all_metrics,
            timestamp=time.time(),
        )

    async def compare_models(
        self,
        original_model_path: str,
        optimized_model_path: str,
        text: str,
        benchmark_name: str = "Model Comparison",
    ) -> Dict[str, BenchmarkResult]:
        """Run benchmarks for both models and return comparison results"""
        original_result = None
        optimized_result = None

        # Temporarily override model path for original
        original_config = BenchmarkConfig(
            **{k: v for k, v in asdict(self.config).items()},
            model_path=original_model_path,
        )
        original_runner = BenchmarkRunner(original_config)
        original_result = await original_runner.run_benchmark_suite(
            [text], f"{benchmark_name} - Original"
        )

        # Mark metrics with model version
        for metric in original_result.metrics:
            metric.model_version = "original"

        # Wait between model tests
        await asyncio.sleep(1.0)

        # Temporarily override model path for optimized
        optimized_config = BenchmarkConfig(
            **{k: v for k, v in asdict(self.config).items()},
            model_path=optimized_model_path,
        )
        optimized_runner = BenchmarkRunner(optimized_config)
        optimized_result = await optimized_runner.run_benchmark_suite(
            [text], f"{benchmark_name} - Optimized"
        )

        # Mark metrics with model version
        for metric in optimized_result.metrics:
            metric.model_version = "optimized"

        return {"original": original_result, "optimized": optimized_result}
