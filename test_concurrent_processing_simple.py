#!/usr/bin/env python3
"""
Simplified test script to debug concurrent processing issues.
"""

import sys
import os
import time
import asyncio

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def wait_for_model_initialization(max_wait=120):
    """Wait for model to be initialized."""
    
    print("Waiting for model initialization...")
    
    try:
        from api.model.loader import get_model_status, get_model
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if get_model_status() and get_model() is not None:
                print("✅ Model initialized successfully")
                return True
            else:
                print(f"⏳ Model not ready yet... ({time.time() - start_time:.1f}s)")
                time.sleep(2)
        
        print("❌ Model initialization timeout")
        return False
        
    except Exception as e:
        print(f"❌ Error waiting for model: {e}")
        return False

def test_simple_audio_generation():
    """Test simple audio generation without concurrent processing."""
    
    print("\nTesting simple audio generation...")
    
    try:
        from api.tts.core import _generate_audio_segment
        
        test_text = "Hello world."
        print(f"Testing with text: '{test_text}'")
        
        start_time = time.time()
        
        # Test simple audio generation
        idx, audio_np, provider = _generate_audio_segment(
            0, test_text, "af_alloy", 1.0, "en-us"
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if audio_np is not None and audio_np.size > 0:
            print(f"✅ Simple audio generation successful: {duration:.2f}s")
            print(f"   Provider: {provider}")
            print(f"   Audio size: {audio_np.size} samples")
            return True
        else:
            print(f"❌ Simple audio generation failed: {provider}")
            return False
            
    except Exception as e:
        print(f"❌ Simple audio generation test failed: {e}")
        return False

async def test_concurrent_processing():
    """Test concurrent processing with dual session manager."""
    
    print("\nTesting concurrent processing...")
    
    try:
        from api.tts.core import _generate_audio_segment
        from api.model.loader import get_dual_session_manager
        from fastapi.concurrency import run_in_threadpool
        
        dual_manager = get_dual_session_manager()
        if dual_manager is None:
            print("❌ Dual session manager not available")
            return False
        
        test_texts = [
            "Hello world.",
            "This is a test.",
            "Concurrent processing test."
        ]
        
        print(f"Testing with {len(test_texts)} segments...")
        
        # Create tasks for concurrent processing
        tasks = []
        for i, text in enumerate(test_texts):
            print(f"Creating task for segment {i+1}: '{text}'")
            task = run_in_threadpool(
                _generate_audio_segment, i, text, "af_alloy", 1.0, "en-us"
            )
            tasks.append((i, task))
        
        # Process tasks with timeout
        start_time = time.time()
        completed_segments = {}
        
        for i, task in tasks:
            try:
                print(f"Waiting for segment {i+1}...")
                result = await asyncio.wait_for(task, timeout=30.0)  # 30 second timeout
                idx, audio_np, provider = result
                
                if audio_np is not None and audio_np.size > 0:
                    completed_segments[i] = (audio_np, provider)
                    print(f"✅ Segment {i+1} completed: {provider}")
                else:
                    print(f"❌ Segment {i+1} failed: {provider}")
                    
            except asyncio.TimeoutError:
                print(f"❌ Segment {i+1} timed out after 30 seconds")
                return False
            except Exception as e:
                print(f"❌ Segment {i+1} failed: {e}")
                return False
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        print(f"✅ Concurrent processing completed: {total_duration:.2f}s")
        print(f"   Completed segments: {len(completed_segments)}/{len(test_texts)}")
        
        return len(completed_segments) == len(test_texts)
        
    except Exception as e:
        print(f"❌ Concurrent processing test failed: {e}")
        return False

async def main():
    """Run simplified concurrent processing tests."""
    
    print("=== Simplified Concurrent Processing Debug Test ===\n")
    
    # Wait for model initialization
    model_ok = wait_for_model_initialization()
    if not model_ok:
        print("❌ Cannot proceed without model initialization")
        return False
    
    # Test 1: Simple audio generation
    simple_ok = test_simple_audio_generation()
    
    # Test 2: Concurrent processing
    concurrent_ok = await test_concurrent_processing()
    
    print(f"\n=== Test Results ===")
    print(f"Model Initialization: {'✅ PASS' if model_ok else '❌ FAIL'}")
    print(f"Simple Audio Generation: {'✅ PASS' if simple_ok else '❌ FAIL'}")
    print(f"Concurrent Processing: {'✅ PASS' if concurrent_ok else '❌ FAIL'}")
    
    if model_ok and simple_ok and concurrent_ok:
        print("\n🎉 All tests passed! Concurrent processing is working.")
        return True
    else:
        print("\n⚠️ Some tests failed. Check the output above for issues.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
