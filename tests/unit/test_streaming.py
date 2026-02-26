"""
Tests for api/streaming.py — PCM conversion, WAV headers, and chunk streaming.

This module had zero test coverage and is the most likely source of
silent audio corruption (wrong byte order, clipping, malformed headers).
"""

import asyncio
import struct

import numpy as np
import pytest

from api.streaming import (
    audio_to_pcm_bytes,
    create_wav_header,
    get_audio_duration,
    stream_audio_chunks,
)
from api.config import CHUNK_SIZE_SAMPLES, SAMPLE_RATE


# --- audio_to_pcm_bytes ---

class TestAudioToPcmBytes:
    def test_normal_audio(self, sample_audio):
        result = audio_to_pcm_bytes(sample_audio)
        assert isinstance(result, bytes)
        assert len(result) == len(sample_audio) * 2  # 16-bit = 2 bytes per sample

    def test_silence(self):
        silence = np.zeros(100, dtype=np.float32)
        result = audio_to_pcm_bytes(silence)
        assert result == b'\x00\x00' * 100

    def test_full_scale_positive(self):
        audio = np.array([1.0], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == 32767

    def test_full_scale_negative(self):
        audio = np.array([-1.0], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == -32767

    def test_clipping_above_one(self):
        audio = np.array([2.5], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == 32767  # clipped to 1.0

    def test_clipping_below_negative_one(self):
        audio = np.array([-3.0], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == -32767  # clipped to -1.0

    def test_nan_produces_zero(self):
        """NaN values should produce 0 (silence) — np.clip doesn't affect NaN."""
        audio = np.array([float('nan')], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == 0

    def test_inf_clipped(self):
        audio = np.array([float('inf')], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == 32767  # clipped to 1.0

    def test_negative_inf_clipped(self):
        audio = np.array([float('-inf')], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        value = struct.unpack('<h', result)[0]
        assert value == -32767  # clipped to -1.0

    def test_empty_array(self):
        audio = np.array([], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        assert result == b''

    def test_single_sample(self):
        audio = np.array([0.5], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        assert len(result) == 2
        value = struct.unpack('<h', result)[0]
        assert value == int(0.5 * 32767)

    def test_little_endian_byte_order(self):
        """Verify output is little-endian (required by WAV/PCM)."""
        audio = np.array([0.5], dtype=np.float32)
        result = audio_to_pcm_bytes(audio)
        expected = int(0.5 * 32767)
        assert result[0] == expected & 0xFF  # low byte first
        assert result[1] == (expected >> 8) & 0xFF


# --- create_wav_header ---

class TestCreateWavHeader:
    def test_header_size(self):
        header = create_wav_header(24000)
        assert len(header) == 44

    def test_riff_marker(self):
        header = create_wav_header(24000)
        assert header[0:4] == b'RIFF'

    def test_wave_format(self):
        header = create_wav_header(24000)
        assert header[8:12] == b'WAVE'

    def test_fmt_chunk(self):
        header = create_wav_header(24000)
        assert header[12:16] == b'fmt '

    def test_data_marker(self):
        header = create_wav_header(24000)
        assert header[36:40] == b'data'

    def test_data_size_field(self):
        """Data size should be num_samples * 2 (16-bit mono)."""
        header = create_wav_header(24000)
        data_size = struct.unpack('<I', header[40:44])[0]
        assert data_size == 24000 * 2

    def test_file_size_field(self):
        """File size should be 36 + data_size."""
        header = create_wav_header(24000)
        file_size = struct.unpack('<I', header[4:8])[0]
        assert file_size == 36 + 24000 * 2

    def test_sample_rate_field(self):
        header = create_wav_header(24000, sample_rate=44100)
        sample_rate = struct.unpack('<I', header[24:28])[0]
        assert sample_rate == 44100

    def test_pcm_format(self):
        """Audio format should be 1 (PCM)."""
        header = create_wav_header(100)
        audio_fmt = struct.unpack('<H', header[20:22])[0]
        assert audio_fmt == 1

    def test_mono_channel(self):
        header = create_wav_header(100)
        channels = struct.unpack('<H', header[22:24])[0]
        assert channels == 1

    def test_bits_per_sample(self):
        header = create_wav_header(100)
        bps = struct.unpack('<H', header[34:36])[0]
        assert bps == 16

    def test_zero_samples(self):
        """Zero samples should produce a valid minimal WAV header."""
        header = create_wav_header(0)
        assert len(header) == 44
        data_size = struct.unpack('<I', header[40:44])[0]
        assert data_size == 0


# --- stream_audio_chunks ---

class TestStreamAudioChunks:
    def _collect(self, audio, **kwargs):
        """Collect all chunks from the async generator."""
        async def _gather():
            chunks = []
            async for chunk in stream_audio_chunks(audio, **kwargs):
                chunks.append(chunk)
            return chunks
        return asyncio.run(_gather())

    def test_total_bytes_match_pcm(self, sample_audio):
        """Total yielded bytes should equal num_samples * 2."""
        chunks = self._collect(sample_audio)
        total = sum(len(c) for c in chunks)
        assert total == len(sample_audio) * 2

    def test_chunk_size(self, sample_audio):
        """All chunks except the last should be CHUNK_SIZE_SAMPLES * 2 bytes."""
        chunks = self._collect(sample_audio)
        expected_size = CHUNK_SIZE_SAMPLES * 2  # 4800
        for chunk in chunks[:-1]:
            assert len(chunk) == expected_size
        # Last chunk can be smaller
        assert len(chunks[-1]) <= expected_size

    def test_wav_header_included(self, sample_audio):
        chunks = self._collect(sample_audio, include_wav_header=True)
        assert chunks[0][:4] == b'RIFF'
        assert len(chunks[0]) == 44

    def test_wav_header_excluded(self, sample_audio):
        chunks = self._collect(sample_audio, include_wav_header=False)
        assert chunks[0][:4] != b'RIFF'

    def test_total_bytes_with_wav_header(self, sample_audio):
        chunks = self._collect(sample_audio, include_wav_header=True)
        total = sum(len(c) for c in chunks)
        assert total == 44 + len(sample_audio) * 2

    def test_empty_audio_with_header(self):
        """Empty audio should yield only the WAV header."""
        empty = np.array([], dtype=np.float32)
        chunks = self._collect(empty, include_wav_header=True)
        assert len(chunks) == 1
        assert chunks[0][:4] == b'RIFF'

    def test_empty_audio_without_header(self):
        """Empty audio with no header should yield nothing."""
        empty = np.array([], dtype=np.float32)
        chunks = self._collect(empty, include_wav_header=False)
        assert len(chunks) == 0

    def test_short_audio(self, short_audio):
        """Audio shorter than one chunk should yield a single chunk."""
        chunks = self._collect(short_audio)
        assert len(chunks) == 1
        assert len(chunks[0]) == len(short_audio) * 2

    def test_pcm_data_integrity(self):
        """Verify the streamed PCM data matches direct conversion."""
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        chunks = self._collect(audio)
        streamed = b''.join(chunks)
        direct = audio_to_pcm_bytes(audio)
        assert streamed == direct


# --- get_audio_duration ---

class TestGetAudioDuration:
    def test_one_second(self, sample_audio):
        assert get_audio_duration(sample_audio) == pytest.approx(1.0)

    def test_empty(self):
        assert get_audio_duration(np.array([], dtype=np.float32)) == 0.0

    def test_custom_sample_rate(self):
        audio = np.zeros(44100, dtype=np.float32)
        assert get_audio_duration(audio, sample_rate=44100) == pytest.approx(1.0)
