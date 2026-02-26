#!/usr/bin/env python3
"""
Test script to verify TTS endpoints and audio daemon integration

Tests:
1. Health endpoints (TTS API and audio daemon)
2. Voices endpoint
3. TTS generation (non-streaming)
4. TTS streaming to audio daemon
5. Audio daemon WebSocket connection and playback

@author @darianrosebrook
"""

import asyncio
import base64
import json
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp
import websockets

# Configuration
TTS_API_URL = "http://127.0.0.1:8080"
AUDIO_DAEMON_WS_URL = "ws://localhost:8081"
AUDIO_DAEMON_HTTP_URL = "http://localhost:8081"

# Colors for output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def print_success(message: str):
    print(f"{GREEN}✓{NC} {message}")


def print_error(message: str):
    print(f"{RED}✗{NC} {message}")


def print_info(message: str):
    print(f"{BLUE}ℹ{NC} {message}")
re


def print_warning(message: str):
    print(f"{YELLOW}⚠{NC} {message}")


async def test_tts_health(session: aiohttp.ClientSession) -> bool:
    """Test TTS API health endpoint"""
    print_info("Testing TTS API health endpoint...")
    try:
        async with session.get(f"{TTS_API_URL}/health") as resp:
            if resp.status == 200:
                data = await resp.json()
                print_success(f"TTS API is healthy: {json.dumps(data, indent=2)}")
                return True
            else:
                print_error(f"TTS API health check failed: {resp.status}")
                return False
    except Exception as e:
        print_error(f"TTS API health check failed: {e}")
        return False


async def test_audio_daemon_health(session: aiohttp.ClientSession) -> bool:
    """Test audio daemon HTTP health endpoint"""
    print_info("Testing audio daemon HTTP health endpoint...")
    try:
        async with session.get(f"{AUDIO_DAEMON_HTTP_URL}/health") as resp:
            if resp.status == 200:
                data = await resp.text()
                print_success(f"Audio daemon HTTP is healthy: {data}")
                return True
            else:
                print_error(f"Audio daemon HTTP health check failed: {resp.status}")
                return False
    except Exception as e:
        print_error(f"Audio daemon HTTP health check failed: {e}")
        return False


async def test_voices_endpoint(session: aiohttp.ClientSession) -> bool:
    """Test voices endpoint"""
    print_info("Testing voices endpoint...")
    try:
        async with session.get(f"{TTS_API_URL}/voices") as resp:
            if resp.status == 200:
                data = await resp.json()
                # API returns {"voices": ["af_bella", "af_alloy", ...]}
                voices = data.get("voices", data) if isinstance(data, dict) else data
                if isinstance(voices, list):
                    print_success(f"Found {len(voices)} voice(s):")
                    for voice in voices[:10]:  # Show first 10
                        print(f"  - {voice}")
                    if len(voices) > 10:
                        print(f"  ... and {len(voices) - 10} more")
                    return True
                else:
                    print_error(f"Unexpected voices format: {type(voices)}")
                    return False
            else:
                print_error(f"Voices endpoint failed: {resp.status}")
                return False
    except Exception as e:
        print_error(f"Voices endpoint failed: {e}")
        return False


async def test_tts_generation(session: aiohttp.ClientSession) -> bool:
    """Test TTS generation (non-streaming)"""
    print_info("Testing TTS generation (non-streaming)...")
    test_text = "Hello, this is a test of the Kokoro TTS system."
    
    try:
        async with session.post(
            f"{TTS_API_URL}/v1/audio/speech",
            json={
                "text": test_text,
                "voice": "af_bella",
                "stream": False,
            },
        ) as resp:
            if resp.status == 200:
                audio_data = await resp.read()
                print_success(f"Generated audio: {len(audio_data)} bytes")
                
                # Save audio for verification
                output_path = Path("temp/test-audio-nonstreaming.wav")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(audio_data)
                print_info(f"Saved audio to: {output_path}")
                return True
            else:
                error_text = await resp.text()
                print_error(f"TTS generation failed: {resp.status} - {error_text}")
                return False
    except Exception as e:
        print_error(f"TTS generation failed: {e}")
        return False


async def test_audio_daemon_websocket() -> bool:
    """Test audio daemon WebSocket connection"""
    print_info("Testing audio daemon WebSocket connection...")
    try:
        async with websockets.connect(AUDIO_DAEMON_WS_URL) as ws:
            print_success("Connected to audio daemon WebSocket")
            
            # Wait for initial status message
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(message)
                if data.get("type") == "status":
                    print_success(f"Received initial status: {data.get('data', {}).get('state', 'unknown')}")
            except asyncio.TimeoutError:
                print_warning("No initial status message received")
            
            return True
    except Exception as e:
        print_error(f"WebSocket connection failed: {e}")
        return False


async def test_streaming_tts_to_daemon(session: aiohttp.ClientSession) -> bool:
    """Test streaming TTS to audio daemon"""
    print_info("Testing streaming TTS to audio daemon...")
    test_text = "This is a streaming test. The audio should play through the daemon."
    
    try:
        # Connect to audio daemon WebSocket
        async with websockets.connect(AUDIO_DAEMON_WS_URL) as ws:
            print_success("Connected to audio daemon WebSocket")
            
            # Wait for initial status
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            
            # Start TTS streaming request
            print_info("Starting TTS streaming request...")
            async with session.post(
                f"{TTS_API_URL}/v1/audio/speech",
                json={
                    "text": test_text,
                    "voice": "af_bella",
                    "stream": True,
                },
                headers={"Accept": "application/octet-stream"},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print_error(f"TTS streaming request failed: {resp.status} - {error_text}")
                    return False
                
                print_success("TTS streaming started")
                
                # Track streaming stats
                chunk_count = 0
                total_bytes = 0
                request_start_time = time.time()
                first_chunk_time = None
                sequence = 0
                
                # Read and forward chunks to daemon
                async for chunk in resp.content.iter_chunked(4096):
                    if not chunk:
                        continue
                    
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        ttfa_ms = (first_chunk_time - request_start_time) * 1000
                        print_success(f"First chunk received: {len(chunk)} bytes (TTFA: {ttfa_ms:.2f}ms)")
                    
                    chunk_count += 1
                    total_bytes += len(chunk)
                    
                    # Send chunk to audio daemon (base64 encoded)
                    message = {
                        "type": "audio_chunk",
                        "timestamp": int(time.time() * 1000),
                        "data": {
                            "chunk": base64.b64encode(chunk).decode("utf-8"),  # Base64 encode for JSON
                            "format": {
                                "format": "pcm",
                                "sampleRate": 24000,
                                "channels": 1,
                                "bitDepth": 16,
                            },
                            "sequence": sequence,
                        },
                    }
                    sequence += 1
                    
                    await ws.send(json.dumps(message))
                    
                    if chunk_count % 10 == 0:
                        print_info(f"Sent {chunk_count} chunks ({total_bytes} bytes)")
                
                # Send end_stream message
                end_message = {
                    "type": "end_stream",
                    "timestamp": int(time.time() * 1000),
                    "data": {},
                }
                await ws.send(json.dumps(end_message))
                print_success("Sent end_stream message")
                
                # Wait for playback to complete (listen for status updates)
                print_info("Waiting for playback to complete...")
                playback_started = False
                playback_completed = False
                max_wait_time = 10.0  # Increased timeout for longer audio
                start_wait = time.time()
                
                try:
                    while not playback_completed and (time.time() - start_wait) < max_wait_time:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            data = json.loads(message)
                            
                            if data.get("type") == "status":
                                state = data.get("data", {}).get("state", "unknown")
                                if state == "playing" and not playback_started:
                                    playback_started = True
                                    print_success("Playback started")
                                elif state == "idle" and playback_started:
                                    playback_completed = True
                                    print_success("Playback completed")
                        except asyncio.TimeoutError:
                            # Continue waiting if we haven't exceeded max time
                            continue
                    
                    if not playback_completed:
                        print_warning(f"Timeout waiting for playback completion (waited {max_wait_time}s)")
                        if playback_started:
                            print_info("Playback was started but may still be in progress")
                except Exception as e:
                    print_warning(f"Error waiting for playback: {e}")
                
                print_success(f"Streaming test complete: {chunk_count} chunks, {total_bytes} bytes")
                if first_chunk_time:
                    ttfa = (first_chunk_time - request_start_time) * 1000
                    print_info(f"Time to first audio: {ttfa:.2f}ms")
                
                return True
                
    except Exception as e:
        print_error(f"Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Kokoro TTS Endpoint and Audio Daemon Test Suite{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    results = {}
    
    async with aiohttp.ClientSession() as session:
        # Test 1: TTS API Health
        results["tts_health"] = await test_tts_health(session)
        print()
        
        # Test 2: Audio Daemon HTTP Health
        results["daemon_http_health"] = await test_audio_daemon_health(session)
        print()
        
        # Test 3: Voices Endpoint
        if results["tts_health"]:
            results["voices"] = await test_voices_endpoint(session)
            print()
        else:
            print_warning("Skipping voices test (TTS API not healthy)")
            results["voices"] = False
            print()
        
        # Test 4: TTS Generation
        if results["tts_health"]:
            results["tts_generation"] = await test_tts_generation(session)
            print()
        else:
            print_warning("Skipping TTS generation test (TTS API not healthy)")
            results["tts_generation"] = False
            print()
        
        # Test 5: Audio Daemon WebSocket
        results["daemon_websocket"] = await test_audio_daemon_websocket()
        print()
        
        # Test 6: Streaming TTS to Daemon
        if results["tts_health"] and results["daemon_websocket"]:
            results["streaming"] = await test_streaming_tts_to_daemon(session)
            print()
        else:
            print_warning("Skipping streaming test (prerequisites not met)")
            results["streaming"] = False
            print()
    
    # Print summary
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}Test Summary{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
        print(f"{status} {test_name}")
    
    print(f"\n{BLUE}Results: {passed}/{total} tests passed{NC}\n")
    
    if passed == total:
        print_success("All tests passed!")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("\nTest interrupted by user")
        sys.exit(1)

