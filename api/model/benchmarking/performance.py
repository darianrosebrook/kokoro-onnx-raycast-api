"""
Performance benchmarking module.

This module provides comprehensive provider benchmarking capabilities
for optimal provider selection and performance validation.
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional

from api.model.hardware import detect_apple_silicon_capabilities, validate_provider
from api.model.providers import create_coreml_provider_options, create_optimized_session_options

logger = logging.getLogger(__name__)


def benchmark_providers(capabilities: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Benchmark available providers and return the optimal choice.
    
    @param capabilities: Hardware capabilities dictionary (auto-detected if not provided)
    @returns: Tuple of (optimal_provider_name, benchmark_results)
    """
    logger.info("Starting provider benchmarking...")
    
    if capabilities is None:
        capabilities = detect_apple_silicon_capabilities()
    results = {}
    
    # Test CoreML provider if available
    if capabilities.get("is_apple_silicon") and validate_provider("CoreMLExecutionProvider"):
        try:
            coreml_time = _benchmark_provider("CoreMLExecutionProvider", capabilities)
            results["CoreMLExecutionProvider"] = {
                "time": coreml_time,
                "available": True,
                "score": 1.0 / coreml_time if coreml_time > 0 else 0
            }
        except Exception as e:
            logger.warning(f"CoreML benchmarking failed: {e}")
            results["CoreMLExecutionProvider"] = {
                "time": float('inf'),
                "available": False,
                "error": str(e),
                "score": 0
            }
    
    # Test CPU provider (always available)
    try:
        cpu_time = _benchmark_provider("CPUExecutionProvider", capabilities)
        results["CPUExecutionProvider"] = {
            "time": cpu_time,
            "available": True,
            "score": 1.0 / cpu_time if cpu_time > 0 else 0
        }
    except Exception as e:
        logger.warning(f"CPU benchmarking failed: {e}")
        results["CPUExecutionProvider"] = {
            "time": float('inf'),
            "available": False,
            "error": str(e),
            "score": 0
        }
    
    # Select optimal provider
    optimal_provider = None
    best_score = 0
    
    for provider, result in results.items():
        if result.get("available") and result.get("score", 0) > best_score:
            best_score = result["score"]
            optimal_provider = provider
    
    logger.info(f"Benchmarking completed. Optimal provider: {optimal_provider}")
    
    return optimal_provider, results


def _benchmark_provider(provider_name: str, capabilities: Dict[str, Any]) -> float:
    """
    Benchmark a specific provider with a test inference.
    
    @param provider_name: Name of the provider to benchmark
    @param capabilities: Hardware capabilities dictionary
    @returns: Average inference time in seconds
    """
    import onnxruntime as ort
    from api.config import TTSConfig
    from kokoro_onnx import Kokoro
    
    session_options = create_optimized_session_options(capabilities)
    
    if provider_name == "CoreMLExecutionProvider":
        provider_options = create_coreml_provider_options(capabilities)
        providers = [(provider_name, provider_options)]
    else:
        providers = [provider_name]
    
    # Create session
    session = ort.InferenceSession(
        TTSConfig.MODEL_PATH,
        sess_options=session_options,
        providers=providers
    )
    
    model = Kokoro.from_session(session=session, voices_path=TTSConfig.VOICES_PATH)
    
    # Warm up
    model.create("Test", "af_heart", 1.0, "en-us")
    
    # Benchmark multiple runs
    test_text = "This is a benchmark test to measure inference performance."
    times = []
    
    for _ in range(3):
        start_time = time.perf_counter()
        model.create(test_text, "af_heart", 1.0, "en-us")
        end_time = time.perf_counter()
        times.append(end_time - start_time)
    
    return sum(times) / len(times)

