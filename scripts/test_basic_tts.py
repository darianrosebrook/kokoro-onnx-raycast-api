#!/usr/bin/env python3
"""
Basic TTS functionality test.

This script tests basic TTS functionality to ensure the server is working properly.
"""

import requests
import json
import time

def test_basic_tts():
    """Test basic TTS functionality."""
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check server health
    print("=== Test 1: Server Health ===")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"Server health: {json.dumps(health, indent=2)}")
        else:
            print(f"Server health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"Error checking server health: {e}")
        return
    
    # Test 2: Simple non-streaming request
    print("\n=== Test 2: Simple Non-Streaming Request ===")
    try:
        response = requests.post(
            f"{base_url}/v1/audio/speech",
            json={
                "text": "Hello world. This is a test.",
                "voice": "af_alloy",
                "stream": False
            }
        )
        
        if response.status_code == 200:
            print(f"Non-streaming request successful")
            print(f"Response length: {len(response.content)} bytes")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        else:
            print(f"Non-streaming request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return
    except Exception as e:
        print(f"Error making non-streaming request: {e}")
        return
    
    # Test 3: Simple streaming request
    print("\n=== Test 3: Simple Streaming Request ===")
    try:
        response = requests.post(
            f"{base_url}/v1/audio/speech",
            json={
                "text": "Hello world. This is a streaming test.",
                "voice": "af_alloy",
                "stream": True
            },
            stream=True
        )
        
        if response.status_code == 200:
            print("Streaming request successful")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            # Read chunks
            chunk_count = 0
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=1024):
                chunk_count += 1
                total_bytes += len(chunk)
                if chunk_count >= 10:  # Read first 10 chunks
                    break
            
            print(f"Read {chunk_count} chunks, {total_bytes} total bytes")
        else:
            print(f"Streaming request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return
    except Exception as e:
        print(f"Error making streaming request: {e}")
        return
    
    # Test 4: Check status
    print("\n=== Test 4: Server Status ===")
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            status = response.json()
            print("Server status retrieved successfully")
            # Print key stats
            if 'session_utilization' in status:
                session_stats = status['session_utilization']
                print(f"Total requests: {session_stats.get('total_requests', 0)}")
                print(f"Dual session available: {session_stats.get('dual_session_available', False)}")
        else:
            print(f"Status request failed: {response.status_code}")
    except Exception as e:
        print(f"Error getting status: {e}")

if __name__ == "__main__":
    print("Testing Basic TTS Functionality")
    print("=" * 40)
    test_basic_tts()
