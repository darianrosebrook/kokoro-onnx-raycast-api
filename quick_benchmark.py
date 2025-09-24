#!/usr/bin/env python3
"""
Quick benchmark to test the optimized OpenWebUI endpoint
"""

import asyncio
import aiohttp
import time

async def test_endpoints():
    async with aiohttp.ClientSession() as session:
        test_text = "Testing the optimized OpenWebUI endpoint performance"
        
        print("Testing optimized OpenWebUI endpoint...")
        start = time.perf_counter()
        async with session.post(
            "http://localhost:8000/audio/speech",
            json={"input": test_text, "voice": "fable"}
        ) as response:
            audio_data = await response.read()
            headers = dict(response.headers)
        
        end = time.perf_counter()
        
        print(f"OpenWebUI Optimized:")
        print(f"  Time: {(end-start)*1000:.1f}ms")
        print(f"  Audio size: {len(audio_data)} bytes")
        print(f"  Optimized: {headers.get('x-openwebui-optimized', 'false')}")
        print(f"  Streaming collected: {headers.get('x-streaming-collected', 'false')}")
        print(f"  Content type: {headers.get('content-type', 'unknown')}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
