#!/usr/bin/env python3
"""
Quick Benchmark Script for Kokoro TTS

This script provides a lightweight alternative to the full benchmark when
the main benchmark script hangs. It performs minimal testing to verify
the system is working correctly.

@author @darianrosebrook
"""

import os
import sys
import time
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.model.loader import initialize_model, get_model_status, get_model
from api.config import TTSConfig

def setup_logging():
    """Setup simple logging for quick benchmark"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def quick_benchmark():
    """Run a quick benchmark test"""
    logger = logging.getLogger(__name__)
    
    print(" Quick Benchmark for Kokoro TTS")
    print("=" * 50)
    
    # Initialize model
    print("1. Initializing model...")
    start_time = time.perf_counter()
    
    try:
        initialize_model()
        init_time = time.perf_counter() - start_time
        print(f"   ✅ Model initialized in {init_time:.3f}s")
    except Exception as e:
        print(f"   ❌ Model initialization failed: {e}")
        return False
    
    # Check model status
    print("2. Checking model status...")
    if get_model_status():
        print("   ✅ Model is ready")
    else:
        print("   ❌ Model is not ready")
        return False
    
    # Get model instance
    model = get_model()
    if not model:
        print("   ❌ Cannot get model instance")
        return False
    
    # Test basic inference
    print("3. Testing basic inference...")
    test_text = "Hello, this is a quick test."
    
    try:
        start_time = time.perf_counter()
        samples, _ = model.create(test_text, "af_heart", 1.0, "en-us")
        inference_time = time.perf_counter() - start_time
        
        if samples is not None:
            print(f"   ✅ Inference successful in {inference_time:.3f}s")
        else:
            print("   ❌ Inference returned None")
            return False
            
    except Exception as e:
        print(f"   ❌ Inference failed: {e}")
        return False
    
    # Test provider detection
    print("4. Checking provider information...")
    try:
        if hasattr(model, 'sess') and hasattr(model.sess, 'get_providers'):
            providers = model.sess.get_providers()
            print(f"   ✅ Active providers: {providers}")
        else:
            print("   ⚠️ Cannot determine providers")
    except Exception as e:
        print(f"   ⚠️ Provider detection failed: {e}")
    
    print("\n Quick benchmark completed successfully!")
    return True

def main():
    """Main function"""
    setup_logging()
    
    success = quick_benchmark()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 