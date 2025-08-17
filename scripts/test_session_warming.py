#!/usr/bin/env python3
"""
Session warming effectiveness test script.

This script tests the effectiveness of session warming by comparing
cold start vs warmed session performance.

Author: @darianrosebrook
"""

import os
import sys
import time
import json
import logging
import statistics
from typing import Dict, List, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging():
    """Setup logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def test_cold_start_performance(logger: logging.Logger) -> Dict[str, Any]:
    """
    Test cold start performance by simulating a fresh server start.
    
    Returns:
        Dict containing cold start performance metrics
    """
    logger.info("Testing cold start performance...")
    
    try:
        # Import model components fresh
        from api.model.initialization.fast_init import initialize_model_fast
        from api.model.sessions import get_model, clear_model, is_model_loaded
        
        # Clear any existing model state
        clear_model()
        
        # Time the full initialization
        start_time = time.perf_counter()
        initialize_model_fast()
        init_time = (time.perf_counter() - start_time) * 1000
        
        if not is_model_loaded():
            raise RuntimeError("Model failed to load during cold start test")
        
        # Test first inference (cold)
        model = get_model()
        if not model:
            raise RuntimeError("Model not available after initialization")
        
        test_text = "Hello world"
        
        # First inference - should be warmed by our new warming system
        first_start = time.perf_counter()
        audio_data = model.create(test_text, "af_heart", 1.0, "en-us")
        first_inference_time = (time.perf_counter() - first_start) * 1000
        
        # Second inference - should be consistently fast  
        second_start = time.perf_counter()
        audio_data = model.create(test_text, "af_heart", 1.0, "en-us")
        second_inference_time = (time.perf_counter() - second_start) * 1000
        
        return {
            'success': True,
            'init_time_ms': init_time,
            'first_inference_ms': first_inference_time,
            'second_inference_ms': second_inference_time,
            'warming_effectiveness': second_inference_time / first_inference_time if first_inference_time > 0 else 1.0
        }
        
    except Exception as e:
        logger.error(f"Cold start test failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def test_warming_configurations(logger: logging.Logger) -> Dict[str, Any]:
    """
    Test different warming configurations.
    
    Returns:
        Dict containing warming configuration test results
    """
    logger.info("Testing warming configurations...")
    
    results = {}
    
    # Test with aggressive warming disabled
    logger.info("Testing with aggressive warming disabled...")
    os.environ['KOKORO_AGGRESSIVE_WARMING'] = 'false'
    results['aggressive_disabled'] = test_cold_start_performance(logger)
    
    # Test with aggressive warming enabled (default)
    logger.info("Testing with aggressive warming enabled...")
    os.environ['KOKORO_AGGRESSIVE_WARMING'] = 'true'
    results['aggressive_enabled'] = test_cold_start_performance(logger)
    
    return results

def test_session_types(logger: logging.Logger) -> Dict[str, Any]:
    """
    Test different session types and their warming behavior.
    
    Returns:
        Dict containing session type test results
    """
    logger.info("Testing session types...")
    
    try:
        from api.model.sessions import get_dual_session_manager
        
        dual_manager = get_dual_session_manager()
        if not dual_manager:
            logger.warning("Dual session manager not available")
            return {'success': False, 'error': 'Dual session manager not available'}
        
        test_texts = [
            ("Hi", "simple"),
            ("This is a more complex sentence.", "complex"),
            ("Very short", "short")
        ]
        
        results = {}
        
        for text, text_type in test_texts:
            try:
                # Test session routing
                complexity = dual_manager.calculate_segment_complexity(text)
                optimal_session = dual_manager.get_optimal_session(complexity)
                
                # Time the inference
                start_time = time.perf_counter()
                result = dual_manager.process_segment_concurrent(text, "af_heart", 1.0, "en-us")
                inference_time = (time.perf_counter() - start_time) * 1000
                
                results[text_type] = {
                    'text': text,
                    'complexity': complexity,
                    'optimal_session': optimal_session,
                    'inference_time_ms': inference_time,
                    'success': True
                }
                
            except Exception as e:
                logger.error(f"Session test failed for {text_type}: {e}")
                results[text_type] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'success': True,
            'session_tests': results
        }
        
    except Exception as e:
        logger.error(f"Session type test failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def run_performance_benchmark(logger: logging.Logger, trials: int = 5) -> Dict[str, Any]:
    """
    Run a comprehensive performance benchmark to measure warming effectiveness.
    
    Args:
        trials: Number of trials to run for statistical significance
        
    Returns:
        Dict containing benchmark results
    """
    logger.info(f"Running performance benchmark with {trials} trials...")
    
    try:
        from api.model.sessions import get_model
        
        model = get_model()
        if not model:
            raise RuntimeError("Model not available for benchmark")
        
        test_texts = [
            "Hi",
            "Hello world",
            "This is a test sentence.",
            "This is a longer sentence to test performance with more complex text."
        ]
        
        results = {}
        
        for text in test_texts:
            text_key = f"text_{len(text)}_chars"
            times = []
            
            for trial in range(trials):
                start_time = time.perf_counter()
                audio_data = model.create(text, "af_heart", 1.0, "en-us")
                inference_time = (time.perf_counter() - start_time) * 1000
                times.append(inference_time)
            
            results[text_key] = {
                'text': text,
                'trials': trials,
                'times_ms': times,
                'mean_ms': statistics.mean(times),
                'median_ms': statistics.median(times),
                'min_ms': min(times),
                'max_ms': max(times),
                'std_dev_ms': statistics.stdev(times) if len(times) > 1 else 0.0
            }
        
        return {
            'success': True,
            'benchmark_results': results
        }
        
    except Exception as e:
        logger.error(f"Performance benchmark failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def main():
    """Main test function."""
    logger = setup_logging()
    logger.info("Starting session warming effectiveness tests...")
    
    # Store all results
    all_results = {
        'timestamp': time.time(),
        'test_configuration': {
            'aggressive_warming': os.environ.get('KOKORO_AGGRESSIVE_WARMING', 'true'),
            'disable_dual_sessions': os.environ.get('KOKORO_DISABLE_DUAL_SESSIONS', 'false'),
            'skip_background': os.environ.get('KOKORO_SKIP_BACKGROUND_BENCHMARKING', 'false')
        }
    }
    
    # Test 1: Cold start performance
    logger.info("=" * 60)
    logger.info("Test 1: Cold Start Performance")
    logger.info("=" * 60)
    all_results['cold_start'] = test_cold_start_performance(logger)
    
    # Test 2: Warming configurations
    logger.info("=" * 60)
    logger.info("Test 2: Warming Configurations")
    logger.info("=" * 60)
    all_results['warming_configs'] = test_warming_configurations(logger)
    
    # Test 3: Session types
    logger.info("=" * 60)
    logger.info("Test 3: Session Types")
    logger.info("=" * 60)
    all_results['session_types'] = test_session_types(logger)
    
    # Test 4: Performance benchmark
    logger.info("=" * 60)
    logger.info("Test 4: Performance Benchmark")
    logger.info("=" * 60)
    all_results['performance_benchmark'] = run_performance_benchmark(logger, trials=3)
    
    # Save results
    timestamp = int(time.time())
    results_file = f"artifacts/bench/session_warming_test_{timestamp}.json"
    
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"Test results saved to: {results_file}")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    if all_results['cold_start']['success']:
        cs = all_results['cold_start']
        logger.info(f"Cold Start Performance:")
        logger.info(f"  Initialization: {cs['init_time_ms']:.1f}ms")
        logger.info(f"  First inference: {cs['first_inference_ms']:.1f}ms")
        logger.info(f"  Second inference: {cs['second_inference_ms']:.1f}ms")
        logger.info(f"  Warming effectiveness: {cs['warming_effectiveness']:.2f}x")
    
    if all_results['performance_benchmark']['success']:
        pb = all_results['performance_benchmark']['benchmark_results']
        logger.info(f"Performance Benchmark:")
        for text_key, data in pb.items():
            logger.info(f"  {data['text'][:20]}...: {data['mean_ms']:.1f}ms mean, {data['min_ms']:.1f}-{data['max_ms']:.1f}ms range")

if __name__ == "__main__":
    main()
