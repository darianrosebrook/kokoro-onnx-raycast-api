"""
Kokoro TTS API v2 - TTS Generation

Uses kokoro-mlx for Apple Silicon GPU-accelerated inference via Metal.
generate_stream yields per-batch audio segments as they complete, which the
client can begin playing while subsequent segments are still synthesizing.

All MLX inference is pinned to a single worker thread (see _mlx_executor)
because the Metal command-encoder is not safe for concurrent use across
threads.
"""

import asyncio
import concurrent.futures
import logging
import queue
import time
from typing import AsyncGenerator, Optional, Tuple

import numpy as np
from kokoro_mlx import KokoroTTS

from .config import (
    MODEL_ID,
    DEFAULT_VOICE,
    DEFAULT_SPEED,
    MIN_SPEED,
    MAX_SPEED,
    SAMPLE_RATE,
    WARMUP_TEXT,
)

logger = logging.getLogger(__name__)

# Global model instance
_model: Optional[KokoroTTS] = None
_model_ready: bool = False

# MLX is not safe for concurrent eval on the same Metal stream from multiple
# threads — two parallel inferences trip an AGX command-encoder assertion and
# abort the process (SIGABRT in -[AGXG13XFamilyCommandBuffer
# tryCoalescingPreviousComputeCommandEncoderWithConfig:]). Pin all inference
# to a single worker thread so concurrent requests serialize on one Metal
# stream. max_workers=1 is the only serialization primitive needed — adding
# a Lock on top would be redundant and would mislead anyone raising the
# worker count without removing the lock.
def _new_mlx_executor() -> concurrent.futures.ThreadPoolExecutor:
    return concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")


_mlx_executor: concurrent.futures.ThreadPoolExecutor = _new_mlx_executor()


def shutdown_executor() -> None:
    """Drain and shut down the MLX worker, then replace it with a fresh one.
    Call from the FastAPI lifespan teardown so in-flight generations finish
    before the process exits. Replacing the executor (rather than leaving it
    dead) keeps the module re-usable across lifecycle boundaries — uvicorn
    --reload, repeated TestClient lifespans, and integration tests all
    re-enter the app without a stale shutdown_lock blocking submissions."""
    global _mlx_executor
    _mlx_executor.shutdown(wait=True)
    _mlx_executor = _new_mlx_executor()


def get_model() -> KokoroTTS:
    """Get the global model instance."""
    global _model
    if _model is None:
        raise RuntimeError("Model not initialized. Call initialize_model() first.")
    return _model


def is_model_ready() -> bool:
    """Check if model is loaded and ready."""
    return _model_ready


def initialize_model() -> float:
    """
    Initialize the TTS model.

    Returns:
        Initialization time in seconds.
    """
    global _model, _model_ready

    start_time = time.perf_counter()

    logger.info(f"Loading MLX model: {MODEL_ID}")
    _model = KokoroTTS.from_pretrained(MODEL_ID)

    # Single warmup call to prime pipelines and voice cache. Run it on the
    # same single-worker executor so the worker thread that owns the Metal
    # stream is the same one that serves requests.
    logger.info("Warming up model...")

    def _warmup():
        result = _model.generate(WARMUP_TEXT, voice=DEFAULT_VOICE, speed=DEFAULT_SPEED)
        if hasattr(result, '__iter__') and not hasattr(result, 'audio'):
            for _ in result:
                pass

    _mlx_executor.submit(_warmup).result()

    init_time = time.perf_counter() - start_time
    _model_ready = True

    logger.info(f"Model initialized in {init_time:.2f}s")
    return init_time


def get_voices() -> list[str]:
    """Get list of available voices."""
    if _model is None:
        return []
    return _model.list_voices()


def generate_audio(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> Tuple[np.ndarray, int, float]:
    """
    Generate audio from text (blocking, all-at-once).

    Args:
        text: Text to synthesize.
        voice: Voice ID to use.
        speed: Speed multiplier (0.5-2.0).

    Returns:
        Tuple of (audio_array, sample_rate, generation_time).
    """
    model = get_model()

    speed = max(MIN_SPEED, min(MAX_SPEED, speed))

    available_voices = model.list_voices()
    if voice not in available_voices:
        logger.warning(f"Voice '{voice}' not found, using default '{DEFAULT_VOICE}'")
        voice = DEFAULT_VOICE

    start_time = time.perf_counter()

    # Serialize all MLX eval through the single worker thread to avoid
    # concurrent Metal command-encoder use across threads.
    def _run() -> list[np.ndarray]:
        collected: list[np.ndarray] = []
        for result in model.generate_stream(text, voice=voice, speed=speed):
            collected.append(np.asarray(result, dtype=np.float32))
        return collected

    segments = _mlx_executor.submit(_run).result()

    if segments:
        audio = np.concatenate(segments)
    else:
        audio = np.array([], dtype=np.float32)

    generation_time = time.perf_counter() - start_time
    audio_duration = len(audio) / SAMPLE_RATE
    rtf = generation_time / audio_duration if audio_duration > 0 else 0

    logger.debug(
        f"Generated {audio_duration:.2f}s audio in {generation_time:.2f}s "
        f"(RTF: {rtf:.3f})"
    )

    return audio, SAMPLE_RATE, generation_time


async def generate_audio_stream(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> AsyncGenerator[Tuple[np.ndarray, int], None]:
    """
    Stream audio segments as they're generated.

    Uses generate_stream() which splits text into phoneme batches and yields
    each batch's audio as it completes. With MLX RTF of 0.05-0.28, each
    segment generates far faster than real-time, so the client receives audio
    to play while subsequent segments are still being generated.

    Yields:
        Tuple of (audio_segment, sample_rate) for each generated segment.
    """
    model = get_model()

    speed = max(MIN_SPEED, min(MAX_SPEED, speed))

    available_voices = model.list_voices()
    if voice not in available_voices:
        logger.warning(f"Voice '{voice}' not found, using default '{DEFAULT_VOICE}'")
        voice = DEFAULT_VOICE

    # generate_stream is sync (MLX is not thread-safe for concurrent inference),
    # so we run it on a dedicated single-worker executor so concurrent requests
    # serialize on the same Metal stream.
    loop = asyncio.get_running_loop()

    # Use a queue to bridge sync generator → async generator
    q: queue.Queue = queue.Queue()
    sentinel = object()

    def _run_generation():
        try:
            for result in model.generate_stream(text, voice=voice, speed=speed):
                q.put((np.asarray(result, dtype=np.float32), SAMPLE_RATE))
        except Exception as e:
            q.put(e)
        finally:
            q.put(sentinel)

    # Start generation on the dedicated MLX worker
    future = loop.run_in_executor(_mlx_executor, _run_generation)

    # Yield segments as they arrive from the queue
    while True:
        # Poll the queue, yielding control to the event loop between checks
        try:
            item = q.get(timeout=0.01)
        except queue.Empty:
            await asyncio.sleep(0.01)
            continue

        if item is sentinel:
            break
        if isinstance(item, Exception):
            raise item
        yield item

    # Ensure the executor thread has completed
    await future
