"""
Core TTS functionality for the Kokoro-ONNX API.

This module handles the core TTS functionality, including:
- Text processing and segmentation
- Audio generation
- Streaming audio

@author: @darianrosebrook
@date: 2025-07-08
@version: 1.0.0
@license: MIT
@copyright: 2025 Darian Rosebrook
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""
import asyncio
import io
import logging
import re
import struct
import time
from typing import AsyncGenerator, Dict, Optional, Tuple

import numpy as np
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from kokoro_onnx import Kokoro

from api.config import TTSConfig
from api.model.loader import get_model, get_model_status, get_active_provider
from api.performance.stats import update_performance_stats
from api.tts.text_processing import (
    segment_text,
)

logger = logging.getLogger(__name__)


def _generate_audio_segment(
    idx: int, text: str, voice: str, speed: float, lang: str
) -> Tuple[int, Optional[np.ndarray], str]:
    """
    Generates a single audio segment in a thread-safe manner by creating
    a new model instance for each thread.
    """
    if not text or len(text.strip()) < 3:
        return idx, None, "Text too short"

    try:
        # Each thread creates its own model instance to ensure thread safety.
        # This is less memory-efficient but prevents critical race conditions.
        provider = get_active_provider()
        local_model = Kokoro(
            model_path=TTSConfig.MODEL_PATH,
            voices_path=TTSConfig.VOICES_PATH,
            providers=[provider]
        )

        logger.debug(f"[{idx}] Generating audio for: {text[:50]}...")
        start_time = time.perf_counter()

        samples, _ = local_model.create(text, voice, speed, lang)
        
        inference_time = time.perf_counter() - start_time
        update_performance_stats(inference_time, provider)
        
        if samples is not None and samples.size > 0:
            logger.info(f"[{idx}] Segment processed in {inference_time:.4f}s using {provider}")
            return idx, samples, provider
        else:
            logger.warning(f"[{idx}] TTS model returned empty audio for text: {text[:50]}...")
            return idx, None, "Empty audio returned"

    except Exception as e:
        logger.error(f"[{idx}] TTS generation failed for text '{text[:50]}...': {e}", exc_info=True)
        return idx, None, str(e)


async def stream_tts_audio(
    text: str, voice: str, speed: float, lang: str, format: str, request: Request
) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously generates and streams TTS audio.
    This function processes text in segments, generates audio for each in parallel,
    and streams the resulting audio bytes back to the client as they become available.
    """
    request_id = request.headers.get("x-request-id", "no-id")
    logger.info(
        f"[{request_id}] Starting stream request: voice='{voice}', speed={speed}, format='{format}', text='{text[:30]}...'"
    )

    model_loaded = get_model_status()
    if not model_loaded:
        logger.error(f"[{request_id}] TTS model not ready, raising 503 error.")
        raise HTTPException(status_code=503, detail="TTS model not ready.")

    segments = segment_text(text, TTSConfig.MAX_SEGMENT_LENGTH)
    if not segments:
        logger.warning(f"[{request_id}] No segments generated from text, ending stream early.")
        return

    total_segments = len(segments)
    logger.info(f"[{request_id}] Text split into {total_segments} segments.")
    results_buffer: Dict[int, Optional[np.ndarray]] = {}
    tasks: Dict[int, asyncio.Task] = {}
    next_idx = 0

    for i, seg_text in enumerate(segments):
        task = asyncio.create_task(
            run_in_threadpool(_generate_audio_segment, i, seg_text, voice, speed, lang)
        )
        tasks[i] = task

    if format == "wav":
        try:
            header_size = 44
            data_size = 0xFFFFFFFF - header_size
            wav_header = bytearray(header_size)
            struct.pack_into(
                "<4sI4s", wav_header, 0, b"RIFF", data_size + 36, b"WAVE"
            )
            struct.pack_into(
                "<4sIHHIIHH",
                wav_header,
                12,
                b"fmt ",
                16,
                1,
                1,
                TTSConfig.SAMPLE_RATE,
                TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE * 1,
                TTSConfig.BYTES_PER_SAMPLE * 1,
                TTSConfig.BYTES_PER_SAMPLE * 8,
            )
            struct.pack_into("<4sI", wav_header, 36, b"data", data_size)
            yield bytes(wav_header)
        except Exception as e:
            logger.error(f"Failed to generate WAV header: {e}")
            format = "pcm"

    last_yield_time = time.monotonic()
    successful_segments = 0
    audio_output_buffer = io.BytesIO()

    try:
        while True:
            tasks_to_remove = []
            for i in sorted(tasks.keys()):
                if tasks[i].done():
                    try:
                        idx, audio_np, provider = tasks[i].result()
                        if audio_np is not None and audio_np.size > 0:
                            results_buffer[idx] = audio_np
                            logger.debug(f"[{request_id}] Segment {idx} completed successfully by {provider}.")
                        else:
                            segment_text_log = (
                                segments[idx] if idx < len(segments) else "unknown"
                            )
                            logger.warning(
                                f"[{request_id}] Segment {idx} ('{segment_text_log[:30]}...') produced no audio and will be skipped."
                            )
                    except Exception as e:
                        logger.error(f"[{request_id}] Task for segment {i} failed: {e}", exc_info=True)
                    tasks_to_remove.append(i)

            for i in tasks_to_remove:
                del tasks[i]

            while next_idx < total_segments and next_idx in results_buffer:
                audio_np = results_buffer.pop(next_idx)
                if audio_np is not None:
                    scaled_audio = np.int16(audio_np * 32767)
                    segment_bytes = scaled_audio.tobytes()
                    audio_output_buffer.write(segment_bytes)
                    successful_segments += 1
                next_idx += 1

            audio_output_buffer.seek(0)
            while True:
                chunk = audio_output_buffer.read(TTSConfig.CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                logger.debug(f"[{request_id}] Yielding chunk of {len(chunk)} bytes.")
                yield chunk
                last_yield_time = time.monotonic()

            remaining_data = audio_output_buffer.read()
            audio_output_buffer.seek(0)
            audio_output_buffer.truncate(0)
            if remaining_data:
                audio_output_buffer.write(remaining_data)
            audio_output_buffer.flush()

            if await request.is_disconnected():
                logger.info(f"[{request_id}] Client disconnected, stopping stream.")
                break

            if (
                next_idx >= total_segments
                and len(audio_output_buffer.getvalue()) == 0
                and not tasks
            ):
                logger.info(f"[{request_id}] All segments processed and buffer empty, completing stream.")
                break

            if (
                time.monotonic() - last_yield_time
                > TTSConfig.STREAM_IDLE_TIMEOUT_SECONDS
            ):
                logger.warning(
                    f"[{request_id}] Stream idle timeout ({TTSConfig.STREAM_IDLE_TIMEOUT_SECONDS}s), stopping stream."
                )
                break

            if (
                len(audio_output_buffer.getvalue()) < TTSConfig.CHUNK_SIZE_BYTES
                and (next_idx < total_segments or tasks)
            ):
                await asyncio.sleep(0.005)

    except Exception as e:
        logger.error(f"Error in audio streaming: {e}", exc_info=True)
    finally:
        logger.info(f"[{request_id}] Cleaning up stream resources.")
        for task in list(tasks.values()):
            if not task.done():
                task.cancel()
        try:
            await asyncio.gather(
                *[t for t in tasks.values() if not t.done()], return_exceptions=True
            )
        except Exception as e:
            logger.debug(f"Task cleanup completed with exceptions: {e}") 