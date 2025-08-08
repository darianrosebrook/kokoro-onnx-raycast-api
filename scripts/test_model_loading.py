#!/usr/bin/env python3
"""
Test script for model loading functionality.

This script tests if the Kokoro model can be loaded directly.
"""

import sys
import os
import time

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_model_loading():
    """Test if the Kokoro model can be loaded directly."""
    
    print("Testing Model Loading")
    print("=" * 30)
    
    # Test 1: Check if files exist
    print("=== Test 1: File Existence ===")
    model_path = "kokoro-v1.0.int8.onnx"
    voices_path = "voices-v1.0.bin"
    
    print(f"Model file: {model_path}")
    if os.path.exists(model_path):
        size = os.path.getsize(model_path) / (1024 * 1024)
        print(f"  ✅ Found ({size:.1f} MB)")
    else:
        print(f"  ❌ Not found")
        return
    
    print(f"Voices file: {voices_path}")
    if os.path.exists(voices_path):
        size = os.path.getsize(voices_path) / (1024 * 1024)
        print(f"  ✅ Found ({size:.1f} MB)")
    else:
        print(f"  ❌ Not found")
        return
    
    # Test 2: Check imports
    print("\n=== Test 2: Import Check ===")
    try:
        import onnxruntime as ort
        print(f"  ✅ onnxruntime imported (version: {ort.__version__})")
    except ImportError as e:
        print(f"  ❌ onnxruntime import failed: {e}")
        return
    
    try:
        from kokoro_onnx import Kokoro
        print(f"  ✅ kokoro_onnx imported successfully")
    except ImportError as e:
        print(f"  ❌ kokoro_onnx import failed: {e}")
        return
    
    # Test 3: Test ONNX Runtime session creation
    print("\n=== Test 3: ONNX Runtime Session ===")
    try:
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        
        print(f"  Creating session with model: {model_path}")
        session = ort.InferenceSession(model_path, sess_options=session_options)
        print(f"  ✅ Session created successfully")
        print(f"  Providers: {session.get_providers()}")
        print(f"  Input metadata: {session.get_inputs()}")
        print(f"  Output metadata: {session.get_outputs()}")
    except Exception as e:
        print(f"  ❌ Session creation failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        return
    
    # Test 4: Test Kokoro model creation
    print("\n=== Test 4: Kokoro Model Creation ===")
    try:
        print(f"  Creating Kokoro model with session and voices: {voices_path}")
        kokoro_model = Kokoro.from_session(session=session, voices_path=voices_path)
        print(f"  ✅ Kokoro model created successfully")
        
        # Test basic functionality
        print(f"  Testing basic inference...")
        test_text = "Hello world."
        start_time = time.time()
        
        # Get the model's inference method
        if hasattr(kokoro_model, 'synthesize'):
            audio = kokoro_model.synthesize(test_text, voice="af_alloy")
            inference_time = time.time() - start_time
            print(f"  ✅ Inference successful ({inference_time:.2f}s)")
            print(f"  Audio shape: {audio.shape if hasattr(audio, 'shape') else 'unknown'}")
        else:
            print(f"  ⚠️  No synthesize method found, checking available methods...")
            methods = [method for method in dir(kokoro_model) if not method.startswith('_')]
            print(f"  Available methods: {methods[:10]}...")  # Show first 10 methods
            
    except Exception as e:
        print(f"  ❌ Kokoro model creation failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n=== Summary ===")
    print("✅ All tests passed! Model loading is working correctly.")
    print("The issue might be in the server initialization or request processing.")

if __name__ == "__main__":
    test_model_loading()
