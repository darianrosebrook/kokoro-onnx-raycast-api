#!/usr/bin/env python3
"""
Test script for optimization features

This script tests the cold-start warm-up, primer micro-cache, and scheduled benchmark features.

@author: @darianrosebrook
@date: 2025-01-27
"""

import asyncio
import requests
import time
import json
from typing import Dict, Any

def test_server_status():
    """Test the server status endpoint and check optimization features."""
    try:
        response = requests.get("http://localhost:8000/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Server status endpoint working")
            
            # Check cold-start warm-up
            cold_start = data.get('cold_start_warmup', {})
            print(f"Cold-start warm-up: {cold_start}")
            
            # Check primer micro-cache
            primer_cache = data.get('primer_microcache', {})
            print(f"Primer micro-cache: {primer_cache}")
            
            # Check scheduled benchmark
            scheduled_benchmark = data.get('scheduled_benchmark', {})
            print(f"Scheduled benchmark: {scheduled_benchmark}")
            
            return data
        else:
            print(f"❌ Server status failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error testing server status: {e}")
        return None

def test_tts_request():
    """Test a TTS request to trigger primer micro-cache."""
    try:
        # Test streaming request
        response = requests.post(
            "http://localhost:8000/v1/audio/speech",
            json={
                "text": "This is a test request to trigger the primer micro-cache functionality.",
                "voice": "af_alloy",
                "stream": True
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Streaming TTS request successful")
            return True
        else:
            print(f"❌ Streaming TTS request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing TTS request: {e}")
        return False

def test_cold_start_warmup():
    """Test the cold-start warm-up functionality."""
    try:
        # Import and test the warm-up function directly
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from api.main import perform_cold_start_warmup
        
        print("Testing cold-start warm-up function...")
        asyncio.run(perform_cold_start_warmup())
        
        # Check status after warm-up
        time.sleep(2)
        status_data = test_server_status()
        if status_data:
            cold_start = status_data.get('cold_start_warmup', {})
            if cold_start.get('completed'):
                print(f"✅ Cold-start warm-up completed in {cold_start.get('warmup_time_ms', 0):.2f}ms")
            else:
                print(f"❌ Cold-start warm-up failed: {cold_start.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"❌ Error testing cold-start warm-up: {e}")

def main():
    """Main test function."""
    print("Testing optimization features...")
    print("=" * 50)
    
    # Test 1: Server status
    print("\n1. Testing server status...")
    status_data = test_server_status()
    
    if not status_data:
        print("❌ Cannot proceed without server status")
        return
    
    # Test 2: TTS request
    print("\n2. Testing TTS request...")
    tts_success = test_tts_request()
    
    if tts_success:
        # Wait a moment and check primer micro-cache
        time.sleep(2)
        print("\n3. Checking primer micro-cache after TTS request...")
        updated_status = test_server_status()
        if updated_status:
            primer_cache = updated_status.get('primer_microcache', {})
            if primer_cache.get('entries', 0) > 0:
                print(f"✅ Primer micro-cache populated: {primer_cache['entries']} entries")
            else:
                print(f"⚠️ Primer micro-cache not populated: {primer_cache}")
    
    # Test 3: Cold-start warm-up
    print("\n4. Testing cold-start warm-up...")
    test_cold_start_warmup()
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    main()
