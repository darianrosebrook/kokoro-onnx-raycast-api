#!/usr/bin/env python3
"""
Quantization Functionality Test Script

This script tests the quantization functionality to validate:
- quantize_model.py script functionality
- Quantized model performance vs original (label-only)
- Memory usage comparison
- Inference speed comparison (via TTFA/total time)
- Model quality validation (basic timing comparison)

@author: @darianrosebrook
@date: 2025-01-27
@version: 1.0.1
"""

import asyncio
import aiohttp
import time
import json
import logging
import statistics
import subprocess
import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QuantizationTestResult:
    """Results from a single quantization test."""
    test_name: str
    model_type: str  # "original" or "quantized" (labels)
    provider: str
    text_length: int
    ttfa_ms: float
    total_duration_ms: float
    memory_usage_mb: Optional[float] = None
    model_size_mb: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class QuantizationTester:
    """Comprehensive quantization functionality tester."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results: List[QuantizationTestResult] = []
        
        # Test text samples
        self.test_texts = {
            "short": "Hello world, this is a test.",
            "medium": "The quick brown fox jumps over the lazy dog. This is a medium length text that should test the quantization performance.",
            "long": """Artificial intelligence is transforming our world in profound ways. From natural language processing to computer vision, 
            AI systems are becoming increasingly sophisticated and capable. The quantization system must maintain audio quality while 
            reducing model size and improving inference speed."""
        }
        
        # Provider labels for comparison only
        self.providers = ["default"]
        
        # Model paths
        self.model_paths = {
            "original": None,
            "quantized": None
        }
    
    def detect_model_paths(self) -> bool:
        """Detect available model paths (best-effort)."""
        logger.info("Detecting available model paths...")
        
        original_path = os.environ.get("KOKORO_MODEL_PATH")
        if original_path and os.path.exists(original_path):
            self.model_paths["original"] = original_path
            logger.info(f"✅ Original model found at: {original_path}")
        else:
            # Try common locations
            for path in [
                "kokoro-v1_0.onnx", "kokoro-v1.0.onnx", "kokoro.onnx", "kokoro-v1_0.pth", "kokoro-v1.0.pth"
            ]:
                if os.path.exists(path):
                    self.model_paths["original"] = path
                    logger.info(f"✅ Original model found at: {path}")
                    break
        
        if not self.model_paths["original"]:
            logger.error("❌ No original model found")
            return False
        
        return True
    
    def run_quantization_script(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """Run the quantize_model.py script."""
        logger.info(f"Running quantization script on {input_path}...")
        
        try:
            script_path = "scripts/quantize_model.py"
            if not os.path.exists(script_path):
                return False, f"Quantization script not found at {script_path}"
            
            cmd = [
                sys.executable, script_path,
                "--input", input_path,
                "--output", output_path,
                "--optimize",
                "--benchmark",
                "--validate",
                "--compare"
            ]
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                logger.info("✅ Quantization completed successfully")
                return True, result.stdout
            else:
                return False, result.stderr or "Quantization failed"
        except subprocess.TimeoutExpired:
            return False, "Quantization timed out"
        except Exception as e:
            return False, f"Quantization error: {str(e)}"
    
    def compare_model_sizes(self, original_path: str, quantized_path: str) -> Dict[str, float]:
        try:
            original_size = os.path.getsize(original_path) / (1024 * 1024)
            quantized_size = os.path.getsize(quantized_path) / (1024 * 1024)
            compression_ratio = original_size / quantized_size if quantized_size > 0 else 0
            size_reduction = ((original_size - quantized_size) / original_size) * 100
            return {
                "original_size_mb": original_size,
                "quantized_size_mb": quantized_size,
                "compression_ratio": compression_ratio,
                "size_reduction_percent": size_reduction
            }
        except Exception as e:
            logger.error(f"Failed to compare model sizes: {e}")
            return {}
    
    async def test_model_performance(self, text: str, provider: str, model_type: str, test_name: str) -> QuantizationTestResult:
        start_time = time.perf_counter()
        first_chunk_time = None
        
        try:
            payload = {
                "text": text,
                "voice": "af_heart",
                "speed": 1.0,
                "lang": "en-us",
                "format": "wav",
                "stream": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return QuantizationTestResult(
                            test_name=test_name,
                            model_type=model_type,
                            provider=provider,
                            text_length=len(text),
                            ttfa_ms=0,
                            total_duration_ms=0,
                            success=False,
                            error_message=f"HTTP {response.status}: {error_text}"
                        )
                    
                    async for chunk in response.content.iter_chunked(1024):
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                            ttfa_ms = (first_chunk_time - start_time) * 1000
                        await asyncio.sleep(0.001)
            
            total_duration = (time.perf_counter() - start_time) * 1000
            
            return QuantizationTestResult(
                test_name=test_name,
                model_type=model_type,
                provider=provider,
                text_length=len(text),
                ttfa_ms=ttfa_ms if first_chunk_time else 0,
                total_duration_ms=total_duration,
                success=True
            )
        except Exception as e:
            return QuantizationTestResult(
                test_name=test_name,
                model_type=model_type,
                provider=provider,
                text_length=len(text),
                ttfa_ms=0,
                total_duration_ms=0,
                success=False,
                error_message=str(e)
            )
    
    async def test_quantization_script(self) -> bool:
        logger.info("Testing quantization script functionality...")
        if not self.model_paths["original"]:
            logger.error("❌ No original model available for quantization")
            return False
        
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as tmp_file:
            quantized_path = tmp_file.name
        
        success = False
        try:
            success, message = self.run_quantization_script(self.model_paths["original"], quantized_path)
            if success and os.path.exists(quantized_path) and os.path.getsize(quantized_path) > 0:
                self.model_paths["quantized"] = quantized_path
                logger.info("✅ Quantization script test passed")
                size = self.compare_model_sizes(self.model_paths["original"], quantized_path)
                if size:
                    logger.info(f"  • Size reduction: {size['size_reduction_percent']:.1f}% (ratio {size['compression_ratio']:.2f}x)")
                return True
            else:
                logger.error(f"❌ Quantization script test failed: {message}")
                return False
        finally:
            if not success and os.path.exists(quantized_path):
                try:
                    os.unlink(quantized_path)
                except Exception:
                    pass
    
    async def test_quantized_vs_original_performance(self) -> List[QuantizationTestResult]:
        logger.info("Testing quantized vs original model performance (labels only)...")
        if not self.model_paths["quantized"]:
            logger.error("❌ No quantized model available for performance comparison")
            return []
        
        results = []
        text = self.test_texts["medium"]
        for provider in self.providers:
            original_result = await self.test_model_performance(text, provider, "original", f"original_{provider}")
            results.append(original_result)
            quantized_result = await self.test_model_performance(text, provider, "quantized", f"quantized_{provider}")
            results.append(quantized_result)
        return results
    
    async def test_memory_usage_comparison(self) -> List[QuantizationTestResult]:
        logger.info("Testing memory usage comparison...")
        try:
            import psutil
            process = psutil.Process()
            results = []
            text = self.test_texts["long"]
            for provider in self.providers:
                initial = process.memory_info().rss / 1024 / 1024
                original_result = await self.test_model_performance(text, provider, "original", f"memory_original_{provider}")
                after = process.memory_info().rss / 1024 / 1024
                original_result.memory_usage_mb = after - initial
                results.append(original_result)
                initial = process.memory_info().rss / 1024 / 1024
                quantized_result = await self.test_model_performance(text, provider, "quantized", f"memory_quantized_{provider}")
                after = process.memory_info().rss / 1024 / 1024
                quantized_result.memory_usage_mb = after - initial
                results.append(quantized_result)
            return results
        except ImportError:
            logger.warning("psutil not available, skipping memory usage comparison")
            return []
    
    async def test_model_quality(self) -> List[QuantizationTestResult]:
        logger.info("Testing model quality (basic timing comparison)...")
        results = []
        text = self.test_texts["short"]
        for provider in self.providers:
            original_result = await self.test_model_performance(text, provider, "original", f"quality_original_{provider}")
            results.append(original_result)
            quantized_result = await self.test_model_performance(text, provider, "quantized", f"quality_quantized_{provider}")
            results.append(quantized_result)
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        logger.info("Starting comprehensive quantization test...")
        start_time = time.perf_counter()
        if not self.detect_model_paths():
            return {"test_summary": {"error": "Failed to detect model paths", "total_tests": 0, "successful_tests": 0, "success_rate": 0}, "total_test_time_ms": 0, "test_results": []}
        if not await self.test_quantization_script():
            return {"test_summary": {"error": "Quantization script test failed", "total_tests": 0, "successful_tests": 0, "success_rate": 0}, "total_test_time_ms": 0, "test_results": []}
        performance_results = await self.test_quantized_vs_original_performance()
        memory_results = await self.test_memory_usage_comparison()
        quality_results = await self.test_model_quality()
        all_results = performance_results + memory_results + quality_results
        successful_results = [r for r in all_results if r.success]
        if successful_results:
            original_results = [r for r in successful_results if r.model_type == "original"]
            quantized_results = [r for r in successful_results if r.model_type == "quantized"]
            provider_stats = {}
            for provider in self.providers:
                pr = [r for r in successful_results if r.provider == provider]
                if pr:
                    ttfa_values = [r.ttfa_ms for r in pr if r.ttfa_ms > 0]
                    duration_values = [r.total_duration_ms for r in pr]
                    provider_stats[provider] = {
                        "test_count": len(pr),
                        "ttfa_stats": {
                            "mean": statistics.mean(ttfa_values) if ttfa_values else 0,
                            "median": statistics.median(ttfa_values) if ttfa_values else 0,
                            "min": min(ttfa_values) if ttfa_values else 0,
                            "max": max(ttfa_values) if ttfa_values else 0
                        },
                        "duration_stats": {
                            "mean": statistics.mean(duration_values) if duration_values else 0,
                            "median": statistics.median(duration_values) if duration_values else 0,
                            "min": min(duration_values) if duration_values else 0,
                            "max": max(duration_values) if duration_values else 0
                        }
                    }
            all_ttfa_values = [r.ttfa_ms for r in successful_results if r.ttfa_ms > 0]
            all_duration_values = [r.total_duration_ms for r in successful_results]
            overall_stats = {
                "total_tests": len(all_results),
                "successful_tests": len(successful_results),
                "success_rate": len(successful_results) / len(all_results) * 100,
                "original_model_tests": len(original_results),
                "quantized_model_tests": len(quantized_results),
                "overall_ttfa_stats": {
                    "mean": statistics.mean(all_ttfa_values) if all_ttfa_values else 0,
                    "median": statistics.median(all_ttfa_values) if all_ttfa_values else 0,
                    "min": min(all_ttfa_values) if all_ttfa_values else 0,
                    "max": max(all_ttfa_values) if all_ttfa_values else 0
                },
                "overall_duration_stats": {
                    "mean": statistics.mean(all_duration_values) if all_duration_values else 0,
                    "median": statistics.median(all_duration_values) if all_duration_values else 0,
                    "min": min(all_duration_values) if all_duration_values else 0,
                    "max": max(all_duration_values) if all_duration_values else 0
                }
            }
        else:
            provider_stats = {}
            overall_stats = {"total_tests": len(all_results), "successful_tests": 0, "success_rate": 0, "error": "No successful tests to analyze"}
        total_test_time = (time.perf_counter() - start_time) * 1000
        self.test_results = all_results
        return {
            "test_summary": {"overall": overall_stats, "by_provider": provider_stats},
            "total_test_time_ms": total_test_time,
            "test_results": [vars(r) for r in all_results],
            "model_paths": self.model_paths
        }
    
    def print_summary(self, summary: Dict[str, Any]):
        logger.info("=" * 70)
        logger.info("QUANTIZATION TEST SUMMARY")
        logger.info("=" * 70)
        overall = summary["test_summary"]["overall"]
        logger.info(f"Total Tests: {overall['total_tests']}")
        logger.info(f"Successful Tests: {overall['successful_tests']}")
        logger.info(f"Success Rate: {overall['success_rate']:.1f}%")
        logger.info(f"Total Test Time: {summary['total_test_time_ms']:.1f}ms")
        if "overall_ttfa_stats" in overall:
            ttfa = overall["overall_ttfa_stats"]
            logger.info("\nOverall TTFA (Time To First Audio) Statistics:")
            logger.info(f"  Mean: {ttfa['mean']:.1f}ms")
            logger.info(f"  Median: {ttfa['median']:.1f}ms")
            logger.info(f"  Range: {ttfa['min']:.1f}ms - {ttfa['max']:.1f}ms")
        if "overall_duration_stats" in overall:
            duration = overall["overall_duration_stats"]
            logger.info("\nOverall Duration Statistics:")
            logger.info(f"  Mean: {duration['mean']:.1f}ms")
            logger.info(f"  Median: {duration['median']:.1f}ms")
            logger.info(f"  Range: {duration['min']:.1f}ms - {duration['max']:.1f}ms")
        if "model_paths" in summary:
            logger.info("\nModel Paths:")
            for model_type, path in summary["model_paths"].items():
                if path:
                    logger.info(f"  {model_type.capitalize()}: {path}")
        logger.info("=" * 70)
    
    def save_results(self, summary: Dict[str, Any], output_file: str = "quantization_test_results.json"):
        try:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Test results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test quantization functionality")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for TTS API")
    parser.add_argument("--output", default="quantization_test_results.json", help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    logger.info(f"Testing quantization at: {args.url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{args.url}/health") as response:
                if response.status != 200:
                    logger.error(f"Server health check failed: {response.status}")
                    return
                logger.info("✅ Server health check passed")
    except Exception as e:
        logger.error(f"Failed to connect to server: {e}")
        logger.error("Make sure the TTS server is running and accessible")
        return
    tester = QuantizationTester(args.url)
    try:
        summary = await tester.run_comprehensive_test()
        tester.print_summary(summary)
        tester.save_results(summary, args.output)
        if summary["test_summary"]["overall"]["success_rate"] < 100:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
