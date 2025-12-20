"""
Kokoro TTS API v2 - Audio Streaming

Simple audio streaming with chunked transfer encoding.
No complex buffering or adaptive management.
"""

import struct
from typing import AsyncGenerator
import numpy as np

from .config import SAMPLE_RATE, CHUNK_SIZE_SAMPLES


def audio_to_pcm_bytes(audio: np.ndarray) -> bytes:
    """
    Convert float32 audio array to 16-bit PCM bytes.
    
    Args:
        audio: Float32 audio array with values in [-1, 1].
    
    Returns:
        Raw PCM bytes (16-bit signed, little-endian).
    """
    # Normalize and convert to int16
    audio_normalized = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_normalized * 32767).astype(np.int16)
    return audio_int16.tobytes()


def create_wav_header(num_samples: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    """
    Create a WAV file header for streaming.
    
    Args:
        num_samples: Total number of audio samples.
        sample_rate: Audio sample rate in Hz.
    
    Returns:
        44-byte WAV header.
    """
    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = num_samples * block_align
    file_size = 36 + data_size
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',           # ChunkID
        file_size,         # ChunkSize
        b'WAVE',           # Format
        b'fmt ',           # Subchunk1ID
        16,                # Subchunk1Size (PCM)
        1,                 # AudioFormat (PCM = 1)
        channels,          # NumChannels
        sample_rate,       # SampleRate
        byte_rate,         # ByteRate
        block_align,       # BlockAlign
        bits_per_sample,   # BitsPerSample
        b'data',           # Subchunk2ID
        data_size,         # Subchunk2Size
    )
    
    return header


async def stream_audio_chunks(
    audio: np.ndarray,
    include_wav_header: bool = False,
) -> AsyncGenerator[bytes, None]:
    """
    Stream audio in chunks for chunked transfer encoding.
    
    Args:
        audio: Float32 audio array.
        include_wav_header: Whether to include WAV header as first chunk.
    
    Yields:
        Audio data chunks as bytes.
    """
    if include_wav_header:
        yield create_wav_header(len(audio))
    
    # Convert full audio to PCM
    pcm_data = audio_to_pcm_bytes(audio)
    
    # Stream in chunks
    chunk_size_bytes = CHUNK_SIZE_SAMPLES * 2  # 2 bytes per sample (16-bit)
    
    for i in range(0, len(pcm_data), chunk_size_bytes):
        yield pcm_data[i:i + chunk_size_bytes]


def get_audio_duration(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    """Calculate audio duration in seconds."""
    return len(audio) / sample_rate
