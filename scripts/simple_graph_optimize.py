#!/usr/bin/env python3
"""
Simple ONNX Graph Optimization for Kokoro TTS

This script applies ONNX Runtime graph optimizations to improve inference performance
using the built-in optimization capabilities without requiring complex dependencies.

Author: @darianrosebrook
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import onnx
import onnxruntime as ort

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_model_size_mb(model_path: str) -> float:
    """Get model file size in MB."""
    try:
        return os.path.getsize(model_path) / (1024 * 1024)
    except:
        return 0.0

def apply_ort_graph_optimizations(input_model_path: str, output_model_path: str) -> bool:
    """
    Apply ONNX Runtime graph optimizations to the model.
    
    Args:
        input_model_path: Path to input model
        output_model_path: Path to save optimized model
        
    Returns:
        True if optimization successful, False otherwise
    """
    try:
        logger.info(f"Applying ORT graph optimizations to: {input_model_path}")
        
        # Create session options with graph optimization
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.optimized_model_filepath = output_model_path
        
        # Use only CPU provider for graph optimization to avoid compiled node serialization issues
        providers = ["CPUExecutionProvider"]
        
        # Create session to trigger optimization
        logger.info("Creating inference session to apply graph optimizations...")
        session = ort.InferenceSession(input_model_path, sess_options=sess_options, providers=providers)
        
        # Verify optimized model was saved
        if os.path.exists(output_model_path):
            logger.info(f"✅ Optimized model saved to: {output_model_path}")
            return True
        else:
            logger.error("❌ Optimized model was not saved")
            return False
            
    except Exception as e:
        logger.error(f"Graph optimization failed: {e}")
        return False

def validate_optimized_model(model_path: str) -> bool:
    """Validate the optimized model can be loaded and used."""
    try:
        logger.info(f"Validating optimized model: {model_path}")
        
        # Load and check model
        model = onnx.load(model_path)
        onnx.checker.check_model(model)
        
        # Try to create a session
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        
        logger.info("✅ Model validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Model validation failed: {e}")
        return False

def benchmark_model_basic(model_path: str, num_runs: int = 5) -> dict:
    """Basic model benchmarking with dummy inputs."""
    try:
        logger.info(f"Benchmarking model: {model_path}")
        
        # Create session
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        
        # Create dummy inputs based on model signature
        inputs = {}
        for input_info in session.get_inputs():
            shape = input_info.shape
            # Replace dynamic dimensions with reasonable values
            concrete_shape = []
            for dim in shape:
                if isinstance(dim, str) or dim == -1:
                    concrete_shape.append(1)  # batch size
                elif dim is None:
                    concrete_shape.append(128)  # sequence length
                else:
                    concrete_shape.append(dim)
            
            if input_info.type == 'tensor(int64)':
                # Token inputs - use small positive integers within vocab range
                inputs[input_info.name] = np.random.randint(0, 100, size=concrete_shape, dtype=np.int64)
            elif input_info.type == 'tensor(float)':
                inputs[input_info.name] = np.random.randn(*concrete_shape).astype(np.float32)
            else:
                # Default to float
                inputs[input_info.name] = np.random.randn(*concrete_shape).astype(np.float32)
        
        # Warmup
        for _ in range(2):
            session.run(None, inputs)
        
        # Benchmark
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            session.run(None, inputs)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms
        
        results = {
            'num_runs': num_runs,
            'times_ms': times,
            'avg_ms': sum(times) / len(times),
            'min_ms': min(times),
            'max_ms': max(times)
        }
        
        logger.info(f"Benchmark results: avg={results['avg_ms']:.2f}ms, min={results['min_ms']:.2f}ms, max={results['max_ms']:.2f}ms")
        return results
        
    except Exception as e:
        logger.error(f"Benchmarking failed: {e}")
        return {}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Simple ONNX graph optimization")
    parser.add_argument("--input", "-i", required=True, help="Input model path")
    parser.add_argument("--output", "-o", required=True, help="Output model path") 
    parser.add_argument("--benchmark", action="store_true", help="Benchmark both models")
    parser.add_argument("--validate", action="store_true", help="Validate optimized model")
    parser.add_argument("--results-json", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    results = {
        'timestamp': time.time(),
        'input_model': args.input,
        'output_model': args.output,
        'input_size_mb': get_model_size_mb(args.input)
    }
    
    # Apply optimization
    logger.info("Starting graph optimization...")
    start_time = time.time()
    
    success = apply_ort_graph_optimizations(args.input, args.output)
    
    optimization_time = time.time() - start_time
    results['optimization_time_seconds'] = optimization_time
    results['optimization_success'] = success
    
    if not success:
        logger.error("Graph optimization failed")
        return 1
    
    # Get optimized model size
    results['output_size_mb'] = get_model_size_mb(args.output)
    if results['input_size_mb'] > 0:
        size_reduction = ((results['input_size_mb'] - results['output_size_mb']) / results['input_size_mb']) * 100
        results['size_reduction_percent'] = size_reduction
        logger.info(f"Model size: {results['input_size_mb']:.2f}MB → {results['output_size_mb']:.2f}MB ({size_reduction:.2f}% reduction)")
    
    # Validate if requested
    if args.validate:
        results['validation_passed'] = validate_optimized_model(args.output)
    
    # Benchmark if requested
    if args.benchmark:
        logger.info("Benchmarking original model...")
        results['original_benchmark'] = benchmark_model_basic(args.input)
        
        logger.info("Benchmarking optimized model...")
        results['optimized_benchmark'] = benchmark_model_basic(args.output)
        
        # Calculate performance improvement
        if results['original_benchmark'] and results['optimized_benchmark']:
            original_avg = results['original_benchmark']['avg_ms']
            optimized_avg = results['optimized_benchmark']['avg_ms']
            improvement = ((original_avg - optimized_avg) / original_avg) * 100
            results['performance_improvement_percent'] = improvement
            logger.info(f"Performance: {original_avg:.2f}ms → {optimized_avg:.2f}ms ({improvement:.2f}% improvement)")
    
    # Save results
    if args.results_json:
        with open(args.results_json, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to: {args.results_json}")
    
    logger.info(f"✅ Graph optimization completed in {optimization_time:.2f}s")
    return 0

if __name__ == "__main__":
    import numpy as np
    sys.exit(main())