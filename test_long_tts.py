#!/usr/bin/env python3
"""
Test script for long TTS processing with chunking.
This simulates how the Raycast client would handle long text by segmenting it
into 1800-character chunks and processing them sequentially.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import os
from pathlib import Path

def segment_text(text, chunk_size=1800):
    """Segment text into chunks of specified size."""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def test_tts_chunk(text, voice="bm_fable", speed=1.0, chunk_index=0, total_chunks=1):
    """Test TTS for a single chunk."""
    request_data = {
        "text": text,
        "voice": voice,
        "speed": speed,
        "lang": "en-us",
        "stream": True,
        "format": "wav"
    }
    
    request_id = f"tts-test-chunk{chunk_index+1}-{int(time.time())}"
    headers = {
        "Content-Type": "application/json",
        "x-request-id": request_id
    }
    
    print(f"  Chunk {chunk_index+1}/{total_chunks}: {len(text)} chars")
    print(f"    Request ID: {request_id}")
    
    start_time = time.time()
    
    try:
        # Prepare the request
        data = json.dumps(request_data).encode('utf-8')
        req = urllib.request.Request(
            "http://127.0.0.1:8000/v1/audio/speech",
            data=data,
            headers=headers,
            method='POST'
        )
        
        # Make the request
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                # Save audio to file
                output_file = f"/tmp/tts_chunk_{chunk_index+1}.wav"
                total_bytes = 0
                
                with open(output_file, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        total_bytes += len(chunk)
                
                # Calculate duration (WAV header is 44 bytes, 48kHz sample rate)
                duration_seconds = (total_bytes - 44) / 48000
                
                elapsed_time = time.time() - start_time
                
                print(f"    ✅ Success: {total_bytes} bytes (~{duration_seconds:.1f}s)")
                print(f"    ⏱️  Processing time: {elapsed_time:.1f}s")
                print(f"    💾 Saved to: {output_file}")
                
                return {
                    "success": True,
                    "bytes": total_bytes,
                    "duration_seconds": duration_seconds,
                    "processing_time": elapsed_time,
                    "file": output_file
                }
            else:
                print(f"    ❌ HTTP {response.status}")
                return {"success": False, "error": f"HTTP {response.status}"}
                
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {"success": False, "error": str(e)}

def main():
    """Main test function."""
    print("=== Long TTS Test with Chunking ===")
    print()
    
    # Read the text file
    text_file = Path("/Users/drosebrook/Desktop/Projects/kokoro-onnx-raycast-api/api/tts/arbitrarily-long-text.txt")
    if not text_file.exists():
        print(f"❌ Text file not found: {text_file}")
        return
    
    with open(text_file, 'r') as f:
        full_text = f.read()
    
    print(f"📄 Full text: {len(full_text):,} characters")
    
    # Segment the text
    chunks = segment_text(full_text, chunk_size=1800)
    print(f"✂️  Segmented into {len(chunks)} chunks of 1800 characters")
    print()
    
    # Test each chunk
    results = []
    total_duration = 0
    total_processing_time = 0
    
    for i, chunk in enumerate(chunks):
        print(f"🎵 Processing chunk {i+1}/{len(chunks)}...")
        result = test_tts_chunk(chunk, chunk_index=i, total_chunks=len(chunks))
        results.append(result)
        
        if result["success"]:
            total_duration += result["duration_seconds"]
            total_processing_time += result["processing_time"]
        
        print()
        time.sleep(1)  # Brief pause between chunks
    
    # Summary
    print("=== Test Summary ===")
    successful_chunks = sum(1 for r in results if r["success"])
    failed_chunks = len(results) - successful_chunks
    
    print(f"✅ Successful chunks: {successful_chunks}/{len(chunks)}")
    if failed_chunks > 0:
        print(f"❌ Failed chunks: {failed_chunks}")
    
    if successful_chunks > 0:
        print(f"🎵 Total audio duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        print(f"⏱️  Total processing time: {total_processing_time:.1f} seconds")
        print(f"🚀 Processing efficiency: {total_duration/total_processing_time:.1f}x real-time")
        
        # Estimate total duration for full text
        estimated_total = (len(full_text) / 1800) * (total_duration / successful_chunks)
        print(f"📊 Estimated full text duration: {estimated_total:.1f} seconds ({estimated_total/60:.1f} minutes)")
    
    print()
    print("🎯 This test demonstrates how the Raycast client handles long text:")
    print("   1. Segments text into 1800-char chunks (client limit)")
    print("   2. Sends each chunk to the server sequentially")
    print("   3. Server processes each chunk independently")
    print("   4. Client streams audio chunks to the daemon")
    print("   5. Daemon plays audio continuously across segments")

if __name__ == "__main__":
    main()
