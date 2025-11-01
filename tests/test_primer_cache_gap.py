#!/usr/bin/env python3
"""
Test script to verify primer cache gap fix.

This test simulates Raycast's streaming behavior:
1. Makes a first request to populate primer cache
2. Makes consecutive requests with the same text to trigger primer cache
3. Measures chunk timing to detect gaps
4. Verifies audio continuity

Usage:
    python tests/test_primer_cache_gap.py
"""

import time
import sys
import json
import urllib.request
import urllib.error
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ChunkTiming:
    """Timing information for a single chunk."""
    elapsed_ms: float
    size_bytes: int
    chunk_index: int


@dataclass
class StreamResult:
    """Result of a streaming request."""
    request_id: str
    ttfa_ms: Optional[float]
    total_time_ms: float
    total_bytes: int
    num_chunks: int
    chunks: List[ChunkTiming]
    gaps: List[Tuple[int, float]]  # (chunk_index, gap_ms)
    success: bool
    error: Optional[str] = None


# Test text that was causing the gap issue
TEST_TEXT = (
    "As you explore, notice how small changes ripple through your design: "
    "a narrow aperture might trip up \"c/e\" recognition at 12px, while a higher x‑height "
    "can unlock surprising readability in micro‑copy. Export your favorite axis settings as tokens, "
    "preview them across light/dark modes and device resolutions, then save and share presets "
    "directly into your design system.\n\n"
    "Ready to turn theory into practice? Jump in, experiment boldly, and let every tweak inform "
    "your next typographic decision—because true mastery comes from seeing anatomy in action."
)


def stream_tts_request(
    url: str,
    text: str,
    request_id: str,
    voice: str = "bm_fable",
    speed: float = 1.25,
) -> StreamResult:
    """
    Make a streaming request matching Raycast's format.
    
    Uses the same endpoint and headers as Raycast:
    - POST /v1/audio/speech
    - format: "pcm"
    - stream: true
    - Accept: audio/pcm header
    """
    payload = {
        "text": text,
        "voice": voice,
        "speed": speed,
        "stream": True,
        "format": "pcm",
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/pcm",
        "x-request-id": request_id,
    }
    
    start_time = time.perf_counter()
    chunks: List[ChunkTiming] = []
    gaps: List[Tuple[int, float]] = []
    ttfa_ms: Optional[float] = None
    total_bytes = 0
    error: Optional[str] = None
    success = False
    
    try:
        # Create request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        prev_chunk_time: Optional[float] = None
        chunk_index = 0
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {resp.reason}")
            
            # Read chunks
            chunk_size = 8192
            while True:
                chunk_data = resp.read(chunk_size)
                if not chunk_data:
                    break
                
                now = time.perf_counter()
                elapsed_ms = (now - start_time) * 1000.0
                
                if ttfa_ms is None:
                    ttfa_ms = elapsed_ms
                
                actual_chunk_size = len(chunk_data)
                total_bytes += actual_chunk_size
                
                # Detect gaps between chunks
                if prev_chunk_time is not None:
                    gap_ms = elapsed_ms - prev_chunk_time
                    # If gap is > 100ms, it's suspicious (chunks should arrive continuously)
                    if gap_ms > 100:
                        gaps.append((chunk_index - 1, gap_ms))
                        # Log large gaps for debugging
                        if gap_ms > 1000:
                            print(f"  ⚠️  Large gap detected: {gap_ms:.2f}ms between chunk {chunk_index - 1} and {chunk_index}")
                
                chunks.append(ChunkTiming(
                    elapsed_ms=elapsed_ms,
                    size_bytes=actual_chunk_size,
                    chunk_index=chunk_index
                ))
                
                prev_chunk_time = elapsed_ms
                chunk_index += 1
        
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        success = True
        
    except Exception as e:
        error = str(e)
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
    
    return StreamResult(
        request_id=request_id,
        ttfa_ms=ttfa_ms,
        total_time_ms=total_time_ms,
        total_bytes=total_bytes,
        num_chunks=len(chunks),
        chunks=chunks,
        gaps=gaps,
        success=success,
        error=error
    )


def analyze_stream_result(result: StreamResult) -> dict:
    """Analyze a stream result for issues."""
    analysis = {
        "success": result.success,
        "ttfa_ms": result.ttfa_ms,
        "total_time_ms": result.total_time_ms,
        "total_bytes": result.total_bytes,
        "num_chunks": result.num_chunks,
        "gaps_found": len(result.gaps),
        "large_gaps": [],  # Gaps > 500ms
        "critical_gaps": [],  # Gaps > 1000ms
        "chunk_rate": None,
        "avg_chunk_size": None,
    }
    
    if result.error:
        analysis["error"] = result.error
        return analysis
    
    if result.num_chunks > 0:
        # Calculate average chunk size
        analysis["avg_chunk_size"] = result.total_bytes / result.num_chunks
        
        # Calculate chunk rate (chunks per second)
        if result.total_time_ms > 0:
            analysis["chunk_rate"] = (result.num_chunks / result.total_time_ms) * 1000.0
    
    # Analyze gaps
    for chunk_idx, gap_ms in result.gaps:
        if gap_ms > 1000:
            analysis["critical_gaps"].append({
                "chunk_index": chunk_idx,
                "gap_ms": gap_ms,
                "chunk_size": result.chunks[chunk_idx].size_bytes if chunk_idx < len(result.chunks) else 0,
            })
        elif gap_ms > 500:
            analysis["large_gaps"].append({
                "chunk_index": chunk_idx,
                "gap_ms": gap_ms,
                "chunk_size": result.chunks[chunk_idx].size_bytes if chunk_idx < len(result.chunks) else 0,
            })
    
    return analysis


def run_test(base_url: str = "http://127.0.0.1:8000"):
    """Run the primer cache gap test."""
    url = f"{base_url}/v1/audio/speech"
    
    print("=" * 80)
    print("PRIMER CACHE GAP TEST")
    print("=" * 80)
    print(f"Endpoint: {url}")
    print(f"Test text length: {len(TEST_TEXT)} characters")
    print()
    
    # Test 1: First request (will populate primer cache)
    print("Test 1: First request (populates primer cache)")
    print("-" * 80)
    
    result1 = stream_tts_request(url, TEST_TEXT, "test-1-first")
    analysis1 = analyze_stream_result(result1)
    
    print(f"✓ Success: {result1.success}")
    if result1.ttfa_ms:
        print(f"✓ TTFA: {result1.ttfa_ms:.2f}ms")
    print(f"✓ Total time: {result1.total_time_ms:.2f}ms")
    print(f"✓ Total bytes: {result1.total_bytes:,}")
    print(f"✓ Chunks: {result1.num_chunks}")
    print(f"✓ Gaps detected: {len(result1.gaps)}")
    
    if result1.gaps:
        print(f"  ⚠️  Large gaps (>500ms): {len(analysis1['large_gaps'])}")
        print(f"  ⚠️  Critical gaps (>1000ms): {len(analysis1['critical_gaps'])}")
        for gap in analysis1['critical_gaps']:
            print(f"    - Chunk {gap['chunk_index']}: {gap['gap_ms']:.2f}ms gap")
    
    if result1.error:
        print(f"✗ Error: {result1.error}")
    
    print()
    
    # Wait a bit between requests
    time.sleep(2)
    
    # Test 2: Second request (should use primer cache)
    print("Test 2: Second request (should use primer cache)")
    print("-" * 80)
    
    result2 = stream_tts_request(url, TEST_TEXT, "test-2-cached")
    analysis2 = analyze_stream_result(result2)
    
    print(f"✓ Success: {result2.success}")
    if result2.ttfa_ms:
        print(f"✓ TTFA: {result2.ttfa_ms:.2f}ms")
    print(f"✓ Total time: {result2.total_time_ms:.2f}ms")
    print(f"✓ Total bytes: {result2.total_bytes:,}")
    print(f"✓ Chunks: {result2.num_chunks}")
    print(f"✓ Gaps detected: {len(result2.gaps)}")
    
    if result2.gaps:
        print(f"  ⚠️  Large gaps (>500ms): {len(analysis2['large_gaps'])}")
        print(f"  ⚠️  Critical gaps (>1000ms): {len(analysis2['critical_gaps'])}")
        for gap in analysis2['critical_gaps']:
            print(f"    - Chunk {gap['chunk_index']}: {gap['gap_ms']:.2f}ms gap")
    else:
        print("  ✓ No gaps detected - audio stream is continuous!")
    
    if result2.error:
        print(f"✗ Error: {result2.error}")
    
    print()
    
    # Test 3: Third request (another cached request)
    print("Test 3: Third request (another cached request)")
    print("-" * 80)
    
    result3 = stream_tts_request(url, TEST_TEXT, "test-3-cached-again")
    analysis3 = analyze_stream_result(result3)
    
    print(f"✓ Success: {result3.success}")
    if result3.ttfa_ms:
        print(f"✓ TTFA: {result3.ttfa_ms:.2f}ms")
    print(f"✓ Total time: {result3.total_time_ms:.2f}ms")
    print(f"✓ Total bytes: {result3.total_bytes:,}")
    print(f"✓ Chunks: {result3.num_chunks}")
    print(f"✓ Gaps detected: {len(result3.gaps)}")
    
    if result3.gaps:
        print(f"  ⚠️  Large gaps (>500ms): {len(analysis3['large_gaps'])}")
        print(f"  ⚠️  Critical gaps (>1000ms): {len(analysis3['critical_gaps'])}")
        for gap in analysis3['critical_gaps']:
            print(f"    - Chunk {gap['chunk_index']}: {gap['gap_ms']:.2f}ms gap")
    else:
        print("  ✓ No gaps detected - audio stream is continuous!")
    
    if result3.error:
        print(f"✗ Error: {result3.error}")
    
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_results = [result1, result2, result3]
    all_analyses = [analysis1, analysis2, analysis3]
    
    total_gaps = sum(len(r.gaps) for r in all_results)
    total_critical_gaps = sum(len(a['critical_gaps']) for a in all_analyses)
    total_large_gaps = sum(len(a['large_gaps']) for a in all_analyses)
    
    print(f"Total requests: {len(all_results)}")
    print(f"Successful requests: {sum(1 for r in all_results if r.success)}")
    print(f"Total gaps detected: {total_gaps}")
    print(f"Large gaps (>500ms): {total_large_gaps}")
    print(f"Critical gaps (>1000ms): {total_critical_gaps}")
    print()
    
    # Check for primer cache usage (TTFA should be much lower on cached requests)
    if result1.ttfa_ms and result2.ttfa_ms:
        ttfa_improvement = ((result1.ttfa_ms - result2.ttfa_ms) / result1.ttfa_ms) * 100
        print(f"TTFA improvement (cache hit): {ttfa_improvement:.1f}%")
        print(f"  First request: {result1.ttfa_ms:.2f}ms")
        print(f"  Cached request: {result2.ttfa_ms:.2f}ms")
    
    print()
    
    # Final verdict
    if total_critical_gaps > 0:
        print("❌ TEST FAILED: Critical gaps detected in audio stream")
        print("   This indicates the primer cache gap issue is NOT fixed.")
        return False
    elif total_large_gaps > 0:
        print("⚠️  TEST WARNING: Large gaps detected (>500ms)")
        print("   Gaps may be acceptable but should be investigated.")
        return True
    else:
        print("✅ TEST PASSED: No significant gaps detected")
        print("   Audio stream is continuous - primer cache gap issue appears fixed!")
        return True


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    
    try:
        success = run_test(base_url)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

