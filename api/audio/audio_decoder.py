"""
Real-Time Audio Decoding and Playback Module

This module provides optimized audio decoding and playback capabilities
for real-time TTS streaming with minimal latency and high performance.

@sign: @darianrosebrook
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Callable, Any, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
import numpy as np

logger = logging.getLogger(__name__)


class RealTimeAudioDecoder:
    """
    Real-time audio decoder optimized for TTS streaming.

    Provides low-latency audio decoding with adaptive buffering,
    real-time playback synchronization, and performance monitoring.
    """

    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audio_decode")

        # Real-time optimization settings
        self.buffer_size_ms = 50  # 50ms buffer for minimal latency
        self.preload_chunks = 3   # Preload 3 chunks ahead
        self.adaptive_buffering = True

        # Performance monitoring
        self.decode_times = []
        self.playback_delays = []
        self.buffer_underruns = 0

        logger.info("🎵 Real-time audio decoder initialized")

    async def decode_stream_realtime(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        on_chunk_ready: Optional[Callable[[np.ndarray], None]] = None
    ) -> AsyncGenerator[np.ndarray, None]:
        """
        Decode audio stream in real-time with minimal latency.

        @param audio_generator: Async generator yielding audio chunks
        @param on_chunk_ready: Optional callback when chunk is ready for playback
        @yields np.ndarray: Decoded audio chunks ready for playback
        """
        buffer_queue = asyncio.Queue(maxsize=self.preload_chunks)
        decode_tasks = []

        try:
            # Start background decoding tasks
            decode_task = asyncio.create_task(self._background_decode(audio_generator, buffer_queue))

            # Stream decoded chunks with real-time playback
            while True:
                try:
                    # Get next decoded chunk with timeout to detect underruns
                    chunk = await asyncio.wait_for(
                        buffer_queue.get(),
                        timeout=self.buffer_size_ms / 1000.0
                    )

                    decode_start = time.perf_counter()

                    if on_chunk_ready:
                        on_chunk_ready(chunk)

                    yield chunk

                    # Monitor decode performance
                    decode_time = time.perf_counter() - decode_start
                    self.decode_times.append(decode_time)

                    # Keep only recent measurements
                    if len(self.decode_times) > 100:
                        self.decode_times.pop(0)

                except asyncio.TimeoutError:
                    # Buffer underrun detected
                    self.buffer_underruns += 1
                    logger.warning(f"🎵 Buffer underrun #{self.buffer_underruns} - playback may stutter")

                    # Try to get chunk anyway (may block)
                    try:
                        chunk = await buffer_queue.get()
                        if on_chunk_ready:
                            on_chunk_ready(chunk)
                        yield chunk
                    except Exception:
                        break

        except Exception as e:
            logger.error(f"Real-time decoding failed: {e}")
            raise
        finally:
            # Cleanup tasks
            decode_task.cancel()
            try:
                await decode_task
            except asyncio.CancelledError:
                pass

    async def _background_decode(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        buffer_queue: asyncio.Queue
    ):
        """Background task for decoding audio chunks."""
        try:
            async for chunk_bytes in audio_generator:
                # Decode chunk in thread pool to avoid blocking
                decoded_chunk = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._decode_chunk_sync,
                    chunk_bytes
                )

                # Add to buffer queue
                await buffer_queue.put(decoded_chunk)

        except Exception as e:
            logger.error(f"Background decoding failed: {e}")
            # Signal end of stream
            await buffer_queue.put(None)

    def _decode_chunk_sync(self, chunk_bytes: bytes) -> np.ndarray:
        """
        Synchronously decode audio chunk.

        This runs in a thread pool to avoid blocking the async event loop.
        """
        try:
            # Convert bytes to numpy array (assuming 16-bit PCM)
            if len(chunk_bytes) % 2 != 0:
                logger.warning(f"Odd chunk size: {len(chunk_bytes)} bytes")
                chunk_bytes = chunk_bytes[:-1]  # Remove last byte if odd

            audio_data = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)

            # Normalize to [-1, 1] range
            if audio_data.size > 0:
                max_val = np.max(np.abs(audio_data))
                if max_val > 0:
                    audio_data /= max_val

            return audio_data

        except Exception as e:
            logger.error(f"Chunk decode failed: {e}")
            return np.array([], dtype=np.float32)

    def get_performance_stats(self) -> dict:
        """Get real-time decoding performance statistics."""
        stats = {
            "buffer_underruns": self.buffer_underruns,
            "avg_decode_time_ms": 0.0,
            "max_decode_time_ms": 0.0,
            "decode_time_variance": 0.0,
            "buffer_health": "good"
        }

        if self.decode_times:
            decode_times_ms = [t * 1000 for t in self.decode_times]
            stats["avg_decode_time_ms"] = sum(decode_times_ms) / len(decode_times_ms)
            stats["max_decode_time_ms"] = max(decode_times_ms)

            if len(decode_times_ms) > 1:
                variance = sum((t - stats["avg_decode_time_ms"]) ** 2 for t in decode_times_ms) / len(decode_times_ms)
                stats["decode_time_variance"] = variance

        # Assess buffer health
        if self.buffer_underruns > 5:
            stats["buffer_health"] = "critical"
        elif self.buffer_underruns > 2:
            stats["buffer_health"] = "warning"
        else:
            stats["buffer_health"] = "good"

        return stats

    def reset_stats(self):
        """Reset performance statistics."""
        self.decode_times.clear()
        self.playback_delays.clear()
        self.buffer_underruns = 0


class PlaybackSynchronizer:
    """
    Synchronizes audio playback with real-time decoding for gapless audio.

    Ensures smooth playback by coordinating decode timing with playback scheduling.
    """

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.playback_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Timing synchronization
        self.playback_start_time: Optional[float] = None
        self.audio_position_samples = 0

        logger.info("🎵 Playback synchronizer initialized")

    def start_playback(
        self,
        audio_stream: AsyncGenerator[np.ndarray, None],
        on_playback_complete: Optional[Callable[[], None]] = None
    ):
        """
        Start synchronized audio playback.

        @param audio_stream: Stream of decoded audio chunks
        @param on_playback_complete: Callback when playback finishes
        """
        if self.playback_thread and self.playback_thread.is_alive():
            logger.warning("Playback already running, stopping first")
            self.stop_playback()

        self.stop_event.clear()
        self.playback_start_time = time.time()
        self.audio_position_samples = 0

        self.playback_thread = threading.Thread(
            target=self._playback_worker,
            args=(audio_stream, on_playback_complete),
            name="audio_playback"
        )
        self.playback_thread.daemon = True
        self.playback_thread.start()

        logger.info("🎵 Synchronized playback started")

    def stop_playback(self):
        """Stop audio playback."""
        if self.stop_event:
            self.stop_event.set()

        if self.playback_thread:
            self.playback_thread.join(timeout=1.0)
            if self.playback_thread.is_alive():
                logger.warning("Playback thread did not stop cleanly")

        logger.info("🎵 Playback stopped")

    def _playback_worker(
        self,
        audio_stream: AsyncGenerator[np.ndarray, None],
        on_complete: Optional[Callable[[], None]]
    ):
        """Worker thread for audio playback."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the async playback
            loop.run_until_complete(self._async_playback(audio_stream, on_complete))

        except Exception as e:
            logger.error(f"Playback worker failed: {e}")
        finally:
            loop.close()

    async def _async_playback(
        self,
        audio_stream: AsyncGenerator[np.ndarray, None],
        on_complete: Optional[Callable[[], None]]
    ):
        """Async audio playback with timing synchronization."""
        try:
            async for audio_chunk in audio_stream:
                if self.stop_event.is_set():
                    break

                if audio_chunk is None or len(audio_chunk) == 0:
                    continue

                # Calculate expected playback time
                chunk_duration = len(audio_chunk) / self.sample_rate
                expected_end_time = self.playback_start_time + (self.audio_position_samples / self.sample_rate)

                current_time = time.time()

                # Synchronize timing
                if current_time < expected_end_time:
                    # We're ahead, wait for the right time
                    await asyncio.sleep(expected_end_time - current_time)
                elif current_time > expected_end_time + chunk_duration:
                    # We're behind, skip timing synchronization for this chunk
                    logger.debug(f"Playback behind schedule by {(current_time - expected_end_time)*1000:.1f}ms")

                # "Play" the chunk (in a real implementation, this would send to audio device)
                await self._play_chunk(audio_chunk)

                # Update position
                self.audio_position_samples += len(audio_chunk)

        except Exception as e:
            logger.error(f"Async playback failed: {e}")
        finally:
            if on_complete:
                try:
                    on_complete()
                except Exception as e:
                    logger.error(f"Playback complete callback failed: {e}")

    async def _play_chunk(self, audio_chunk: np.ndarray):
        """
        "Play" an audio chunk.

        In a real implementation, this would send the audio to the system's
        audio output device. Here we simulate the playback timing.
        """
        # Simulate playback time
        playback_duration = len(audio_chunk) / self.sample_rate
        await asyncio.sleep(playback_duration)


# Global instances
_decoder = None
_synchronizer = None

def get_audio_decoder() -> RealTimeAudioDecoder:
    """Get the global real-time audio decoder instance."""
    global _decoder
    if _decoder is None:
        _decoder = RealTimeAudioDecoder()
    return _decoder

def get_playback_synchronizer() -> PlaybackSynchronizer:
    """Get the global playback synchronizer instance."""
    global _synchronizer
    if _synchronizer is None:
        _synchronizer = PlaybackSynchronizer()
    return _synchronizer
