#!/usr/bin/env python3
"""
Simple model comparison benchmark for Kokoro TTS models.
Compares performance between original and quantized models.

Author: @darianrosebrook
"""

import time
import json
import logging
import os
from typing import Dict, Any, List
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def benchmark_direct_requests(base_url: str, num_requests: int = 10) -> Dict[str, Any]:
    """
    Benchmark the TTS API directly with HTTP requests.
    """
    import requests
    
    test_text = "Real-time synthesis performance test for quantization comparison."
    times = []
    errors = 0
    
    logger.info(f"Running {num_requests} requests to {base_url}")
    
    for i in range(num_requests):
        try:
            start_time = time.perf_counter()
            
            response = requests.post(
                f"{base_url}/v1/audio/speech",
                json={
                    "text": test_text,
                    "voice": "af_heart", 
                    "speed": 1.0
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            end_time = time.perf_counter()
            request_time = (end_time - start_time) * 1000  # Convert to ms
            
            if response.status_code == 200:
                times.append(request_time)
                logger.info(f"Request {i+1}: {request_time:.2f}ms")
            else:
                errors += 1
                logger.warning(f"Request {i+1} failed: {response.status_code}")
                
        except Exception as e:
            errors += 1
            logger.error(f"Request {i+1} error: {e}")
    
    if not times:
        return {"error": "No successful requests", "errors": errors}
    
    import statistics
    
    return {
        "num_requests": len(times),
        "errors": errors,
        "times_ms": times,
        "min_ms": min(times),
        "max_ms": max(times),
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
        "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0
    }

def get_model_info(base_url: str) -> Dict[str, Any]:
    """Get model information from the server status endpoint."""
    import requests
    
    try:
        response = requests.get(f"{base_url}/status", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status request failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Status request error: {e}"}

def main():
    """Main benchmark function."""
    logger.info("Starting model comparison benchmark...")
    
    # Configuration
    base_url = "http://127.0.0.1:8000"
    num_requests = 10
    
    # Get current model info
    model_info = get_model_info(base_url)
    logger.info(f"Current model info: {model_info.get('model_path', 'unknown')}")
    
    # Run benchmark on current model (quantized)
    logger.info("Benchmarking current model (quantized)...")
    quantized_results = benchmark_direct_requests(base_url, num_requests)
    
    # Get model file sizes
    file_sizes = {}
    for model_path in ["kokoro.onnx", "kokoro-v1.0.int8.onnx"]:
        if os.path.exists(model_path):
            size_mb = os.path.getsize(model_path) / (1024 * 1024)
            file_sizes[model_path] = size_mb
    
    # Prepare results
    results = {
        "timestamp": time.time(),
        "test_config": {
            "base_url": base_url,
            "num_requests": num_requests,
            "test_text_length": len("Real-time synthesis performance test for quantization comparison.")
        },
        "model_info": model_info,
        "file_sizes_mb": file_sizes,
        "quantized_model_benchmark": quantized_results
    }
    
    # Calculate size reduction if both files exist
    if "kokoro.onnx" in file_sizes and "kokoro-v1.0.int8.onnx" in file_sizes:
        original_size = file_sizes["kokoro.onnx"]
        quantized_size = file_sizes["kokoro-v1.0.int8.onnx"]
        size_reduction = ((original_size - quantized_size) / original_size) * 100
        results["size_reduction_percent"] = size_reduction
        logger.info(f"Model size reduction: {size_reduction:.1f}% ({original_size:.1f}MB → {quantized_size:.1f}MB)")
    
    # Print summary
    if "error" not in quantized_results:
        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"Mean response time: {quantized_results['mean_ms']:.2f}ms")
        logger.info(f"Median response time: {quantized_results['median_ms']:.2f}ms") 
        logger.info(f"P95 response time: {quantized_results['p95_ms']:.2f}ms")
        logger.info(f"Min/Max: {quantized_results['min_ms']:.2f}ms / {quantized_results['max_ms']:.2f}ms")
        logger.info(f"Success rate: {(quantized_results['num_requests']/(quantized_results['num_requests']+quantized_results['errors']))*100:.1f}%")
    
    # Save results
    timestamp = int(time.time())
    results_file = f"artifacts/bench/model_comparison_{timestamp}.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to: {results_file}")
    return results

if __name__ == "__main__":
    main()
