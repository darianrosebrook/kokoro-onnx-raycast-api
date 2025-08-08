#!/usr/bin/env python3
"""
Test script for primer micro-cache functionality.

This script tests the primer micro-cache to understand why it's not populating.
"""

import requests
import json
import time
import sys

def test_primer_microcache():
    """Test the primer micro-cache functionality."""
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check initial status
    print("=== Test 1: Initial Status ===")
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            status = response.json()
            primer_stats = status.get('primer_microcache', {})
            print(f"Initial primer micro-cache stats: {json.dumps(primer_stats, indent=2)}")
        else:
            print(f"Failed to get status: {response.status_code}")
            return
    except Exception as e:
        print(f"Error getting status: {e}")
        return
    
    # Test 2: Send a long text that should trigger segmentation and primer split
    print("\n=== Test 2: Long Text Request ===")
    long_text = """This is a very long text that should definitely trigger the segmentation logic and then the primer split functionality. It needs to be long enough to cause the text to be split into multiple segments, and then the first segment should be long enough to trigger the early TTFA optimization to split it into a primer and the rest. This text should be at least 800 characters to ensure the segmentation logic is triggered properly, and then the first segment should be long enough to trigger the primer split. Let me add more content to make sure this text is long enough. I will continue writing until we have enough characters to trigger the segmentation. This is important for testing the primer micro-cache functionality. The primer micro-cache should store the first part of the first segment so that subsequent requests with similar text can use the cached primer. This optimization is part of the Phase 1 TTFA improvements. The goal is to reduce the time to first audio by having a fast path for common primer text patterns. Now let me add even more content to ensure this text is definitely long enough to trigger segmentation. I will continue writing until we have well over 1000 characters. This should force the segmentation logic to split the text into multiple segments. Once that happens, the first segment should be long enough to trigger the primer split logic. The primer split logic looks for segments longer than 60 characters and then splits them into a primer (10-15% of the text) and the rest. This primer is then cached for future use. Let me add more content to make sure we have enough text to trigger all the logic properly. This is a comprehensive test of the segmentation and primer split functionality. We want to ensure that the text is long enough to be split into multiple segments, and that the first segment is long enough to trigger the primer split. The primer split should create a small primer that can be cached and reused for similar text patterns. This optimization is designed to improve the time to first audio by having a fast path for common primer text patterns. Let me continue adding content to make sure this text is definitely long enough to trigger all the segmentation and primer split logic."""
    
    print(f"Text length: {len(long_text)} characters")
    
    try:
        response = requests.post(
            f"{base_url}/v1/audio/speech",
            json={
                "text": long_text,
                "voice": "af_alloy",
                "stream": True
            },
            stream=True
        )
        
        if response.status_code == 200:
            print("Request successful, streaming response...")
            # Read a few chunks to ensure processing
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=1024):
                chunk_count += 1
                if chunk_count >= 5:  # Read first 5 chunks
                    break
            print(f"Read {chunk_count} chunks from response")
        else:
            print(f"Request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return
    except Exception as e:
        print(f"Error making request: {e}")
        return
    
    # Test 3: Check status after request
    print("\n=== Test 3: Status After Request ===")
    time.sleep(2)  # Give server time to process
    
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            status = response.json()
            primer_stats = status.get('primer_microcache', {})
            print(f"Primer micro-cache stats after request: {json.dumps(primer_stats, indent=2)}")
        else:
            print(f"Failed to get status: {response.status_code}")
    except Exception as e:
        print(f"Error getting status: {e}")
    
    # Test 4: Send same request again to test cache hit
    print("\n=== Test 4: Repeat Request (Cache Hit Test) ===")
    try:
        response = requests.post(
            f"{base_url}/v1/audio/speech",
            json={
                "text": long_text,
                "voice": "af_alloy",
                "stream": True
            },
            stream=True
        )
        
        if response.status_code == 200:
            print("Repeat request successful, streaming response...")
            # Read a few chunks to ensure processing
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=1024):
                chunk_count += 1
                if chunk_count >= 5:  # Read first 5 chunks
                    break
            print(f"Read {chunk_count} chunks from repeat response")
        else:
            print(f"Repeat request failed: {response.status_code}")
            return
    except Exception as e:
        print(f"Error making repeat request: {e}")
        return
    
    # Test 5: Check final status
    print("\n=== Test 5: Final Status ===")
    time.sleep(2)  # Give server time to process
    
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            status = response.json()
            primer_stats = status.get('primer_microcache', {})
            print(f"Final primer micro-cache stats: {json.dumps(primer_stats, indent=2)}")
            
            # Analysis
            print("\n=== Analysis ===")
            if primer_stats.get('entries', 0) > 0:
                print("✅ Primer micro-cache is working - entries found!")
            else:
                print("❌ Primer micro-cache is not populating - no entries found")
                print("   This suggests the primer split logic is not being triggered or storage is failing")
            
            if primer_stats.get('hits', 0) > 0:
                print("✅ Cache hits detected - primer is being reused!")
            else:
                print("⚠️  No cache hits detected - primer may not be cached properly")
                
        else:
            print(f"Failed to get final status: {response.status_code}")
    except Exception as e:
        print(f"Error getting final status: {e}")

if __name__ == "__main__":
    print("Testing Primer Micro-Cache Functionality")
    print("=" * 50)
    test_primer_microcache()
