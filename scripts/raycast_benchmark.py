#!/usr/bin/env python3
"""
Raycast Path Benchmark Suite

Tests the TTS system through the same path that the Raycast demo uses,
for both streaming and non-streaming requests with various text lengths.

Author: @darianrosebrook
Date: 2025-10-31
"""

import argparse
import asyncio
import aiohttp
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("raycast_bench")


# Raycast-style request configuration
RAYCAST_CONFIG = {
    "voice": "af_heart",
    "speed": 1.25,  # Raycast validates speed >= 1.25
    "lang": "en-us",
}

# Text presets matching Raycast usage patterns
TEXT_PRESETS = {
    "short": "This is a short test sentence for TTFA and streaming cadence.",
    "medium": (
        "This is a medium length paragraph used to benchmark real-time factor "
        "and end-to-end latency across providers and modes in a reproducible way. "
        "It includes punctuation, numbers like 123 and 456, and varied content."
    ),
    "long": (
        "This is a long paragraph intended to exercise sustained synthesis performance, "
        "including punctuation, numerals such as 123 and 456, abbreviations like Dr. and St., "
        "and varied phonetic content. It should be long enough to measure RTF reliably. "
        "We test with multiple sentences, each containing different linguistic elements. "
        "The goal is to ensure consistent performance across different text patterns and lengths."
    ),
    "article": (
        "Artificial intelligence has revolutionized the way we interact with technology. "
        "From voice assistants to automated translation systems, AI has become an integral part "
        "of our daily lives. Text-to-speech technology, in particular, has made significant "
        "advancements in recent years. Modern TTS systems can generate natural-sounding speech "
        "that is nearly indistinguishable from human voices. These systems use deep learning "
        "models trained on vast amounts of audio data to capture the nuances of human speech, "
        "including intonation, rhythm, and emotional expression. The applications of TTS technology "
        "are vast and varied. Accessibility tools help individuals with visual impairments access "
        "written content through audio. Educational platforms use TTS to provide audio versions of "
        "textbooks and learning materials. Content creators leverage TTS for narration and "
        "audio production. Businesses use TTS for customer service automation and interactive "
        "voice response systems. As the technology continues to evolve, we can expect even more "
        "sophisticated and natural-sounding speech synthesis capabilities in the future."
    ),
}


async def raycast_streaming_request(
    session: aiohttp.ClientSession,
    url: str,
    text: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Make a streaming request matching Raycast's format.
    
    Raycast uses:
    - format: "pcm"
    - stream: true
    - Accept: audio/pcm header
    """
    payload = {
        **config,
        "text": text,
        "stream": True,
        "format": "pcm",  # Raycast uses PCM for streaming
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/pcm",  # Raycast header
    }
    
    t0 = time.perf_counter()
    chunks: List[Tuple[float, int]] = []
    total_bytes = 0
    ttfa_ms: Optional[float] = None
    
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            resp.raise_for_status()
            
            async for chunk in resp.content.iter_chunked(8192):
                now = time.perf_counter()
                elapsed_ms = (now - t0) * 1000.0
                
                if chunk and ttfa_ms is None:
                    ttfa_ms = elapsed_ms
                
                if chunk:
                    chunks.append((elapsed_ms, len(chunk)))
                    total_bytes += len(chunk)
            
            total_time_ms = (time.perf_counter() - t0) * 1000.0
            
            return {
                "ok": True,
                "ttfa_ms": ttfa_ms,
                "total_time_ms": total_time_ms,
                "total_bytes": total_bytes,
                "num_chunks": len(chunks),
                "chunks": chunks,
            }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "ttfa_ms": ttfa_ms,
            "total_time_ms": None,
            "total_bytes": total_bytes,
            "num_chunks": len(chunks),
            "chunks": chunks,
        }


async def raycast_nonstreaming_request(
    session: aiohttp.ClientSession,
    url: str,
    text: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Make a non-streaming request matching Raycast's format.
    
    For non-streaming, Raycast likely uses:
    - format: "wav"
    - stream: false
    """
    payload = {
        **config,
        "text": text,
        "stream": False,
        "format": "wav",  # WAV for non-streaming
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    t0 = time.perf_counter()
    
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            resp.raise_for_status()
            data = await resp.read()
            total_time_ms = (time.perf_counter() - t0) * 1000.0
            
            return {
                "ok": True,
                "total_time_ms": total_time_ms,
                "total_bytes": len(data),
            }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "total_time_ms": None,
            "total_bytes": 0,
        }


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate statistical metrics."""
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0}
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    return {
        "mean": sum(values) / n,
        "min": min(values),
        "max": max(values),
        "p50": sorted_vals[int(n * 0.50)] if n > 0 else 0.0,
        "p95": sorted_vals[int(n * 0.95)] if n > 0 else sorted_vals[-1],
    }


def stream_gap_stats(chunks: List[Tuple[float, int]]) -> Dict[str, Any]:
    """Calculate stream gap statistics."""
    if len(chunks) < 2:
        return {"max_gap_ms": None, "p95_gap_ms": None, "median_gap_ms": None}
    
    times = [t for t, _ in chunks]
    gaps = [t2 - t1 for t1, t2 in zip(times[:-1], times[1:])]
    
    if not gaps:
        return {"max_gap_ms": None, "p95_gap_ms": None, "median_gap_ms": None}
    
    sorted_gaps = sorted(gaps)
    n = len(sorted_gaps)
    
    return {
        "max_gap_ms": max(gaps),
        "p95_gap_ms": sorted_gaps[int(n * 0.95)] if n > 0 else sorted_gaps[-1],
        "median_gap_ms": sorted_gaps[n // 2],
    }


async def run_benchmark_suite(
    url: str,
    config: Dict[str, Any],
    text_lengths: List[str],
    modes: List[str],
    trials: int,
) -> Dict[str, Any]:
    """Run comprehensive benchmark suite."""
    results = {}
    
    async with aiohttp.ClientSession() as session:
        for text_length in text_lengths:
            if text_length not in TEXT_PRESETS:
                logger.warning(f"Unknown text length: {text_length}, skipping")
                continue
            
            text = TEXT_PRESETS[text_length]
            results[text_length] = {}
            
            for mode in modes:
                logger.info(f"\n{'='*60}")
                logger.info(f"Testing: {text_length} text, {mode} mode")
                logger.info(f"Text length: {len(text)} characters")
                logger.info(f"{'='*60}")
                
                mode_results = []
                
                for trial in range(1, trials + 1):
                    logger.info(f"Trial {trial}/{trials}...")
                    
                    if mode == "streaming":
                        result = await raycast_streaming_request(session, url, text, config)
                    else:
                        result = await raycast_nonstreaming_request(session, url, text, config)
                    
                    if not result["ok"]:
                        logger.error(f"Trial {trial} failed: {result.get('error', 'Unknown error')}")
                        continue
                    
                    mode_results.append(result)
                    
                    # Log trial results
                    if mode == "streaming":
                        logger.info(
                            f"  TTFA: {result['ttfa_ms']:.1f} ms, "
                            f"Total: {result['total_time_ms']:.1f} ms, "
                            f"Chunks: {result['num_chunks']}, "
                            f"Bytes: {result['total_bytes']}"
                        )
                    else:
                        logger.info(
                            f"  Total: {result['total_time_ms']:.1f} ms, "
                            f"Bytes: {result['total_bytes']}"
                        )
                    
                    # Small delay between trials
                    await asyncio.sleep(0.5)
                
                # Calculate statistics
                if mode == "streaming":
                    ttfa_values = [r["ttfa_ms"] for r in mode_results if r.get("ttfa_ms") is not None]
                    total_time_values = [r["total_time_ms"] for r in mode_results if r.get("total_time_ms") is not None]
                    
                    all_chunks = []
                    for r in mode_results:
                        all_chunks.extend(r.get("chunks", []))
                    
                    results[text_length][mode] = {
                        "ttfa": calculate_stats(ttfa_values),
                        "total_time": calculate_stats(total_time_values),
                        "stream_gaps": stream_gap_stats(all_chunks),
                        "avg_chunks": sum(r["num_chunks"] for r in mode_results) / len(mode_results) if mode_results else 0,
                        "avg_bytes": sum(r["total_bytes"] for r in mode_results) / len(mode_results) if mode_results else 0,
                        "trials": len(mode_results),
                    }
                else:
                    total_time_values = [r["total_time_ms"] for r in mode_results if r.get("total_time_ms") is not None]
                    
                    results[text_length][mode] = {
                        "total_time": calculate_stats(total_time_values),
                        "avg_bytes": sum(r["total_bytes"] for r in mode_results) / len(mode_results) if mode_results else 0,
                        "trials": len(mode_results),
                    }
    
    return results


def print_summary(results: Dict[str, Any]):
    """Print comprehensive benchmark summary."""
    logger.info("\n" + "="*80)
    logger.info(" RAYCAST PATH BENCHMARK SUMMARY")
    logger.info("="*80)
    
    for text_length in ["short", "medium", "long", "article"]:
        if text_length not in results:
            continue
        
        logger.info(f"\n{text_length.upper()} TEXT ({len(TEXT_PRESETS[text_length])} chars)")
        logger.info("-" * 80)
        
        # Streaming results
        if "streaming" in results[text_length]:
            stream_data = results[text_length]["streaming"]
            logger.info("Streaming Mode:")
            logger.info(f"  TTFA:  mean={stream_data['ttfa']['mean']:.1f}ms, "
                       f"p50={stream_data['ttfa']['p50']:.1f}ms, "
                       f"p95={stream_data['ttfa']['p95']:.1f}ms")
            logger.info(f"  Total: mean={stream_data['total_time']['mean']:.1f}ms, "
                       f"p50={stream_data['total_time']['p50']:.1f}ms, "
                       f"p95={stream_data['total_time']['p95']:.1f}ms")
            if stream_data['stream_gaps']['max_gap_ms'] is not None:
                logger.info(f"  Gaps:  max={stream_data['stream_gaps']['max_gap_ms']:.1f}ms, "
                           f"p95={stream_data['stream_gaps']['p95_gap_ms']:.1f}ms")
            logger.info(f"  Chunks: {stream_data['avg_chunks']:.1f} avg, "
                       f"Bytes: {stream_data['avg_bytes']:.0f} avg")
        
        # Non-streaming results
        if "non-streaming" in results[text_length]:
            nonstream_data = results[text_length]["non-streaming"]
            logger.info("Non-Streaming Mode:")
            logger.info(f"  Total: mean={nonstream_data['total_time']['mean']:.1f}ms, "
                       f"p50={nonstream_data['total_time']['p50']:.1f}ms, "
                       f"p95={nonstream_data['total_time']['p95']:.1f}ms")
            logger.info(f"  Bytes: {nonstream_data['avg_bytes']:.0f} avg")
    
    logger.info("\n" + "="*80)


async def main():
    parser = argparse.ArgumentParser(description="Raycast Path Benchmark Suite")
    parser.add_argument("--url", default="http://localhost:8000/v1/audio/speech", help="TTS endpoint URL")
    parser.add_argument("--trials", type=int, default=5, help="Number of trials per test")
    parser.add_argument("--text-lengths", nargs="+", default=["short", "medium", "long", "article"],
                       choices=["short", "medium", "long", "article"],
                       help="Text lengths to test")
    parser.add_argument("--modes", nargs="+", default=["streaming", "non-streaming"],
                       choices=["streaming", "non-streaming"],
                       help="Modes to test")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    
    args = parser.parse_args()
    
    logger.info("Starting Raycast Path Benchmark Suite")
    logger.info(f"URL: {args.url}")
    logger.info(f"Trials: {args.trials}")
    logger.info(f"Text lengths: {args.text_lengths}")
    logger.info(f"Modes: {args.modes}")
    
    results = await run_benchmark_suite(
        url=args.url,
        config=RAYCAST_CONFIG,
        text_lengths=args.text_lengths,
        modes=args.modes,
        trials=args.trials,
    )
    
    print_summary(results)
    
    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"artifacts/bench/raycast_benchmark_{timestamp}.json")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "config": {
                "url": args.url,
                "raycast_config": RAYCAST_CONFIG,
                "trials": args.trials,
                "text_lengths": args.text_lengths,
                "modes": args.modes,
            },
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2)
    
    logger.info(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())

