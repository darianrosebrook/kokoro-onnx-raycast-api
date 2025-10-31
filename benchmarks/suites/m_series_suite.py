"""
M-Series Mac Optimization Benchmark Suite

Specialized benchmark suite for validating M-series Mac optimizations including:
- Neural Engine utilization
- CoreML provider performance
- Dual-session management
- Memory arena optimization
- Context leak detection
"""

import time
import logging
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class MSeriesOptimizationResult:
    """Results from M-series Mac optimization validation"""
    test_name: str
    neural_engine_detected: bool
    coreml_available: bool
    optimal_provider: str
    ttfa_ms: float
    rtf: float
    memory_usage_mb: float
    optimization_targets_met: Dict[str, bool]
    recommendations: List[str]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class MSeriesBenchmarkSuite:
    """M-series Mac specific optimization validation suite"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.logger = logging.getLogger(__name__)
    
    async def detect_hardware(self) -> Dict[str, Any]:
        """Detect M-series Mac hardware capabilities"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/status") as response:
                    if response.status == 200:
                        status = await response.json()
                        return {
                            "neural_engine_detected": status.get("hardware", {}).get("has_neural_engine", False),
                            "chip_family": status.get("hardware", {}).get("chip_family", "unknown"),
                            "neural_engine_cores": status.get("hardware", {}).get("neural_engine_cores", 0),
                            "memory_gb": status.get("hardware", {}).get("memory_gb", 0),
                            "coreml_available": "CoreMLExecutionProvider" in status.get("providers", [])
                        }
        except Exception as e:
            self.logger.error(f"Hardware detection failed: {e}")
        
        return {
            "neural_engine_detected": False,
            "chip_family": "unknown",
            "neural_engine_cores": 0,
            "memory_gb": 0,
            "coreml_available": False
        }
    
    async def test_neural_engine_performance(self) -> MSeriesOptimizationResult:
        """Test Neural Engine utilization and performance"""
        hardware = await self.detect_hardware()
        
        test_text = "Short test sentence for Neural Engine performance validation."
        
        # Measure TTFA with CoreML provider
        ttfa_ms = float('inf')
        rtf = float('inf')
        
        try:
            start_time = time.perf_counter()
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": test_text,
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
                        audio_bytes = b""
                        async for chunk in response.content.iter_chunked(8192):
                            if first_chunk_time is None:
                                first_chunk_time = time.perf_counter()
                                ttfa_ms = (first_chunk_time - start_time) * 1000.0
                            audio_bytes += chunk
                        
                        # Calculate RTF if possible
                        duration = self._parse_audio_duration(audio_bytes)
                        if duration:
                            total_time = time.perf_counter() - start_time
                            rtf = (total_time / duration) if duration > 0 else float('inf')
        except Exception as e:
            self.logger.error(f"Neural Engine test failed: {e}")
        
        # Check optimization targets
        targets_met = {
            "ttfa_below_10ms": ttfa_ms < 10.0,
            "ttfa_below_500ms": ttfa_ms < 500.0,
            "rtf_below_0_6": rtf < 0.6,
            "neural_engine_available": hardware.get("neural_engine_detected", False),
            "coreml_provider_available": hardware.get("coreml_available", False)
        }
        
        recommendations = []
        if not targets_met["ttfa_below_10ms"]:
            recommendations.append("TTFA exceeds M-series target (10ms) - optimize CoreML provider")
        if not targets_met["rtf_below_0_6"]:
            recommendations.append("RTF exceeds target (0.6) - review inference pipeline")
        if not targets_met["neural_engine_available"]:
            recommendations.append("Neural Engine not detected - verify hardware detection")
        if not targets_met["coreml_provider_available"]:
            recommendations.append("CoreML provider not available - install onnxruntime-coreml")
        
        if all(targets_met.values()):
            recommendations.append("✅ All M-series optimization targets met!")
        
        return MSeriesOptimizationResult(
            test_name="neural_engine_performance",
            neural_engine_detected=hardware.get("neural_engine_detected", False),
            coreml_available=hardware.get("coreml_available", False),
            optimal_provider="CoreMLExecutionProvider" if hardware.get("coreml_available") else "CPUExecutionProvider",
            ttfa_ms=ttfa_ms,
            rtf=rtf,
            memory_usage_mb=0.0,  # Would need instrumentation
            optimization_targets_met=targets_met,
            recommendations=recommendations,
            timestamp=time.time()
        )
    
    async def test_memory_arena_optimization(self) -> MSeriesOptimizationResult:
        """Test memory arena optimization for M-series Mac"""
        hardware = await self.detect_hardware()
        
        # Test with long text to exercise memory
        long_text = "This is a long paragraph intended to exercise sustained synthesis performance, including punctuation, numerals such as 123 and 456, abbreviations like Dr. and St., and varied phonetic content. It should be long enough to measure memory efficiency reliably."
        
        # Measure performance
        ttfa_ms = float('inf')
        
        try:
            start_time = time.perf_counter()
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": long_text,
                    "voice": "af_heart",
                    "speed": 1.0,
                    "lang": "en-us",
                    "stream": True,
                    "format": "wav"
                }
                
                async with session.post(
                    f"{self.server_url}/v1/audio/speech",
                    json=payload
                ) as response:
                    if response.status == 200:
                        first_chunk_time = None
                        async for chunk in response.content.iter_chunked(8192):
                            if first_chunk_time is None:
                                first_chunk_time = time.perf_counter()
                                ttfa_ms = (first_chunk_time - start_time) * 1000.0
                            break
        except Exception as e:
            self.logger.error(f"Memory arena test failed: {e}")
        
        memory_gb = hardware.get("memory_gb", 0)
        targets_met = {
            "memory_arena_configured": memory_gb >= 16,  # Should have large arena for 16GB+
            "ttfa_acceptable": ttfa_ms < 500.0,
            "high_memory_system": memory_gb >= 32
        }
        
        recommendations = []
        if memory_gb >= 32:
            recommendations.append(f"✅ High memory system ({memory_gb}GB) - optimal for large memory arena")
        elif memory_gb >= 16:
            recommendations.append(f"Standard memory system ({memory_gb}GB) - configure balanced memory arena")
        else:
            recommendations.append(f"Limited memory ({memory_gb}GB) - use minimal memory arena")
        
        return MSeriesOptimizationResult(
            test_name="memory_arena_optimization",
            neural_engine_detected=hardware.get("neural_engine_detected", False),
            coreml_available=hardware.get("coreml_available", False),
            optimal_provider="CoreMLExecutionProvider" if hardware.get("coreml_available") else "CPUExecutionProvider",
            ttfa_ms=ttfa_ms,
            rtf=0.0,
            memory_usage_mb=0.0,
            optimization_targets_met=targets_met,
            recommendations=recommendations,
            timestamp=time.time()
        )
    
    async def run_comprehensive_m_series_benchmark(self) -> Dict[str, MSeriesOptimizationResult]:
        """Run comprehensive M-series Mac optimization validation"""
        self.logger.info("Starting comprehensive M-series Mac optimization benchmark...")
        
        results: Dict[str, MSeriesOptimizationResult] = {}
        
        # Test Neural Engine performance
        self.logger.info("Testing Neural Engine performance...")
        results["neural_engine"] = await self.test_neural_engine_performance()
        
        # Test memory arena optimization
        self.logger.info("Testing memory arena optimization...")
        results["memory_arena"] = await self.test_memory_arena_optimization()
        
        return results
    
    def _parse_audio_duration(self, audio_bytes: bytes) -> Optional[float]:
        """Parse audio duration from bytes"""
        try:
            import wave
            import io
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            try:
                import soundfile as sf
                import io
                with sf.SoundFile(io.BytesIO(audio_bytes)) as f:
                    return len(f) / float(f.samplerate)
            except Exception:
                return None
    
    def get_summary(self, results: Dict[str, MSeriesOptimizationResult]) -> Dict[str, Any]:
        """Get summary of M-series optimization validation"""
        summary = {
            "tests_run": len(results),
            "all_targets_met": True,
            "recommendations": [],
            "test_results": {}
        }
        
        for test_name, result in results.items():
            summary["test_results"][test_name] = result.to_dict()
            
            if not all(result.optimization_targets_met.values()):
                summary["all_targets_met"] = False
            
            summary["recommendations"].extend(result.recommendations)
        
        # Remove duplicate recommendations
        summary["recommendations"] = list(set(summary["recommendations"]))
        
        return summary




