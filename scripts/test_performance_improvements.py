#!/usr/bin/env python3
"""
Test Performance Improvements

This script tests the performance improvements by measuring:
1. Current TTFA performance
2. ANE utilization
3. Startup time analysis
4. Cache performance

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import time
import requests
import json
import os
from typing import Dict, Any

def test_ttfa_performance() -> Dict[str, Any]:
    """Test TTFA performance with different text lengths."""
    print("🧪 Testing TTFA Performance...")
    
    test_cases = [
        {"text": "Hi", "description": "Ultra-short (2 chars)"},
        {"text": "Hello world!", "description": "Short (12 chars)"},
        {"text": "This is a medium-length sentence for testing TTS performance.", "description": "Medium (65 chars)"},
        {"text": "This is a longer test to measure how the system performs with more complex text that requires segmentation and multiple processing steps for comprehensive analysis.", "description": "Long (150+ chars)"}
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"  Testing {test_case['description']}...")
        
        # Test streaming mode (TTFA)
        start_time = time.perf_counter()
        try:
            response = requests.post(
                "http://127.0.0.1:8000/v1/audio/speech",
                json={
                    "text": test_case["text"],
                    "voice": "af_heart",
                    "speed": 1.0,
                    "stream": True,
                    "format": "wav"
                },
                timeout=10
            )
            ttfa = (time.perf_counter() - start_time) * 1000
            
            if response.status_code == 200:
                results.append({
                    "text_length": len(test_case["text"]),
                    "description": test_case["description"],
                    "ttfa_ms": ttfa,
                    "status": "success"
                })
                print(f"    ✅ TTFA: {ttfa:.1f}ms")
            else:
                results.append({
                    "text_length": len(test_case["text"]),
                    "description": test_case["description"],
                    "ttfa_ms": ttfa,
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                })
                print(f"    ❌ Error: HTTP {response.status_code}")
                
        except Exception as e:
            ttfa = (time.perf_counter() - start_time) * 1000
            results.append({
                "text_length": len(test_case["text"]),
                "description": test_case["description"],
                "ttfa_ms": ttfa,
                "status": "error",
                "error": str(e)
            })
            print(f"    ❌ Error: {e}")
    
    return {"ttfa_tests": results}

def test_ane_utilization() -> Dict[str, Any]:
    """Test ANE utilization and provider distribution."""
    print("🧠 Testing ANE Utilization...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            
            session_util = status.get('performance', {}).get('session_utilization', {})
            ane_percentage = session_util.get('ane_percentage', 0)
            total_requests = session_util.get('total_requests', 0)
            ane_requests = session_util.get('ane_requests', 0)
            
            print(f"  ANE Utilization: {ane_percentage:.1f}%")
            print(f"  Total Requests: {total_requests}")
            print(f"  ANE Requests: {ane_requests}")
            
            # Check environment variables
            env_vars = {
                'KOKORO_COREML_COMPUTE_UNITS': os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'not_set'),
                'COREML_NEURAL_ENGINE_OPTIMIZATION': os.environ.get('COREML_NEURAL_ENGINE_OPTIMIZATION', 'not_set'),
            }
            
            print(f"  Environment Variables:")
            for key, value in env_vars.items():
                print(f"    {key}: {value}")
            
            return {
                "ane_utilization_percent": ane_percentage,
                "total_requests": total_requests,
                "ane_requests": ane_requests,
                "environment_variables": env_vars,
                "status": "success"
            }
        else:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_cache_performance() -> Dict[str, Any]:
    """Test cache performance and hit rates."""
    print("💾 Testing Cache Performance...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            
            tts_processing = status.get('tts_processing', {})
            phoneme_cache = tts_processing.get('phoneme_cache', {})
            inference_cache = tts_processing.get('inference_cache', {})
            
            phoneme_hit_rate = phoneme_cache.get('cache_hit_rate', 0)
            inference_hit_rate = inference_cache.get('hit_rate', 0)
            
            print(f"  Phoneme Cache Hit Rate: {phoneme_hit_rate:.1f}%")
            print(f"  Inference Cache Hit Rate: {inference_hit_rate:.1f}%")
            print(f"  Phoneme Cache Size: {phoneme_cache.get('cache_size', 0)}")
            print(f"  Inference Cache Entries: {inference_cache.get('total_entries', 0)}")
            
            return {
                "phoneme_cache": {
                    "hit_rate": phoneme_hit_rate,
                    "cache_size": phoneme_cache.get('cache_size', 0),
                    "max_cache_size": phoneme_cache.get('max_cache_size', 0)
                },
                "inference_cache": {
                    "hit_rate": inference_hit_rate,
                    "total_entries": inference_cache.get('total_entries', 0),
                    "hits": inference_cache.get('hits', 0),
                    "misses": inference_cache.get('misses', 0)
                },
                "status": "success"
            }
        else:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_startup_analysis() -> Dict[str, Any]:
    """Analyze startup timing from status endpoint."""
    print("🚀 Analyzing Startup Performance...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            
            startup_timings = status.get('startup_timings', {})
            cold_start_warmup = status.get('cold_start_warmup', {})
            
            total_startup_time = sum(startup_timings.values()) if startup_timings else 0
            warmup_time = cold_start_warmup.get('warmup_time_ms', 0)
            
            print(f"  Total Startup Time: {total_startup_time:.1f}s")
            print(f"  Cold Start Warmup: {warmup_time:.1f}ms")
            print(f"  Startup Components:")
            for component, timing in startup_timings.items():
                print(f"    {component}: {timing:.3f}s")
            
            return {
                "total_startup_time_seconds": total_startup_time,
                "cold_start_warmup_ms": warmup_time,
                "component_timings": startup_timings,
                "status": "success"
            }
        else:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

def generate_performance_report(results: Dict[str, Any]) -> None:
    """Generate comprehensive performance report."""
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE TEST RESULTS")
    print("=" * 60)
    
    # TTFA Analysis
    ttfa_results = results.get('ttfa_tests', [])
    if ttfa_results:
        print("\n🎯 TTFA Performance:")
        for result in ttfa_results:
            if result['status'] == 'success':
                target_met = "✅" if result['ttfa_ms'] < 800 else "⚠️"
                print(f"  {target_met} {result['description']}: {result['ttfa_ms']:.1f}ms")
            else:
                print(f"  ❌ {result['description']}: {result['error']}")
    
    # ANE Utilization
    ane_result = results.get('ane_utilization', {})
    if ane_result.get('status') == 'success':
        ane_percent = ane_result['ane_utilization_percent']
        ane_status = "✅" if ane_percent > 25 else "⚠️" if ane_percent > 0 else "❌"
        print(f"\n🧠 ANE Utilization: {ane_status} {ane_percent:.1f}%")
        print(f"  Total Requests: {ane_result['total_requests']}")
        print(f"  ANE Requests: {ane_result['ane_requests']}")
    
    # Cache Performance
    cache_result = results.get('cache_performance', {})
    if cache_result.get('status') == 'success':
        phoneme_hit = cache_result['phoneme_cache']['hit_rate']
        inference_hit = cache_result['inference_cache']['hit_rate']
        print(f"\n💾 Cache Performance:")
        print(f"  Phoneme Cache Hit Rate: {phoneme_hit:.1f}%")
        print(f"  Inference Cache Hit Rate: {inference_hit:.1f}%")
    
    # Startup Analysis
    startup_result = results.get('startup_analysis', {})
    if startup_result.get('status') == 'success':
        startup_time = startup_result['total_startup_time_seconds']
        startup_status = "✅" if startup_time < 15 else "⚠️" if startup_time < 30 else "❌"
        print(f"\n🚀 Startup Performance: {startup_status} {startup_time:.1f}s")
    
    # Recommendations
    print(f"\n📋 OPTIMIZATION RECOMMENDATIONS:")
    
    # ANE recommendations
    if ane_result.get('ane_utilization_percent', 0) < 10:
        print("  🔴 HIGH: ANE utilization is very low - check CoreML configuration")
        print("     Action: Ensure KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine")
    
    # Cache recommendations
    if cache_result.get('inference_cache', {}).get('hit_rate', 0) < 20:
        print("  🟡 MEDIUM: Cache hit rate is low - enable cache pre-warming")
        print("     Action: Set KOKORO_CACHE_PREWARM=1")
    
    # Startup recommendations
    if startup_result.get('total_startup_time_seconds', 0) > 30:
        print("  🔴 HIGH: Startup time is too long - enable background initialization")
        print("     Action: Set KOKORO_DEFER_BACKGROUND_INIT=true")
    
    print("=" * 60)

def main():
    """Main test function."""
    print("🧪 Kokoro-ONNX Performance Test Suite")
    print("=" * 60)
    
    # Run all tests
    results = {}
    
    # Test TTFA performance
    results.update(test_ttfa_performance())
    
    # Test ANE utilization
    results['ane_utilization'] = test_ane_utilization()
    
    # Test cache performance
    results['cache_performance'] = test_cache_performance()
    
    # Test startup analysis
    results['startup_analysis'] = test_startup_analysis()
    
    # Generate report
    generate_performance_report(results)
    
    # Save results
    with open('performance_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: performance_test_results.json")

if __name__ == "__main__":
    main()
