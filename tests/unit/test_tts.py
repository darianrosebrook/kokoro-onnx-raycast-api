"""
Tests for api/tts.py — model lifecycle, audio generation, voice fallback, speed clamping,
split-and-parallel streaming.
"""

import asyncio

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

import api.tts as tts_module
from api.tts import (
    generate_audio, generate_audio_stream, get_model, get_voices,
    is_model_ready,
)
from api.config import DEFAULT_VOICE, MIN_SPEED, MAX_SPEED


class TestModelLifecycle:
    def test_get_model_uninitialized(self):
        with patch.object(tts_module, '_model', None):
            with pytest.raises(RuntimeError, match="Model not initialized"):
                get_model()

    def test_get_model_initialized(self, mock_model):
        with patch.object(tts_module, '_model', mock_model):
            assert get_model() is mock_model

    def test_is_model_ready_false(self):
        with patch.object(tts_module, '_model_ready', False):
            assert is_model_ready() is False

    def test_is_model_ready_true(self):
        with patch.object(tts_module, '_model_ready', True):
            assert is_model_ready() is True

    def test_get_voices_no_model(self):
        with patch.object(tts_module, '_model', None):
            assert get_voices() == []

    def test_get_voices_with_model(self, mock_model):
        with patch.object(tts_module, '_model', mock_model):
            voices = get_voices()
            assert "af_heart" in voices
            assert len(voices) == 3


class TestGenerateAudio:
    def test_returns_tuple(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            audio, sample_rate, gen_time = generate_audio("Hello")
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32
            assert sample_rate == 24000
            assert isinstance(gen_time, float)
            assert gen_time >= 0

    def test_audio_length_proportional_to_text(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            short_audio, _, _ = generate_audio("Hi")
            long_audio, _, _ = generate_audio("This is a much longer sentence for testing")
            assert len(long_audio) > len(short_audio)

    def test_invalid_voice_falls_back(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            audio, _, _ = generate_audio("Hello", voice="nonexistent_voice")
            assert len(audio) > 0
            # Verify model was called with the default voice
            _, kwargs = mock_model.generate_stream.call_args
            assert kwargs['voice'] == DEFAULT_VOICE

    def test_valid_voice_used(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", voice="af_bella")
            _, kwargs = mock_model.generate_stream.call_args
            assert kwargs['voice'] == "af_bella"

    def test_speed_clamped_low(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=0.1)
            _, kwargs = mock_model.generate_stream.call_args
            assert kwargs['speed'] == MIN_SPEED

    def test_speed_clamped_high(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=5.0)
            _, kwargs = mock_model.generate_stream.call_args
            assert kwargs['speed'] == MAX_SPEED

    def test_speed_within_range_unchanged(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=1.5)
            _, kwargs = mock_model.generate_stream.call_args
            assert kwargs['speed'] == 1.5

    def test_model_exception_propagates(self, mock_model):
        mock_model.generate_stream.side_effect = RuntimeError("MLX inference failed")
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            with pytest.raises(RuntimeError, match="MLX inference failed"):
                generate_audio("Hello")


class TestGenerateAudioStream:
    def _collect_stream(self, mock_model, text, **kwargs):
        """Collect all segments from generate_audio_stream."""
        async def _gather():
            segments = []
            async for audio_seg, sr in generate_audio_stream(text, **kwargs):
                segments.append((audio_seg, sr))
            return segments

        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            return asyncio.run(_gather())

    def test_yields_segments(self, mock_model):
        segments = self._collect_stream(mock_model, "Hello world test text")
        assert len(segments) > 0
        for audio, sr in segments:
            assert isinstance(audio, np.ndarray)
            assert sr == 24000

    def test_total_audio_nonempty(self, mock_model):
        segments = self._collect_stream(mock_model, "Test text for streaming")
        total_samples = sum(len(seg) for seg, _ in segments)
        assert total_samples > 0

    def test_invalid_voice_falls_back(self, mock_model):
        """Should not raise even with invalid voice."""
        segments = self._collect_stream(mock_model, "Hello", voice="nonexistent")
        assert len(segments) > 0

    def test_short_text(self, mock_model):
        """Short text should produce audio."""
        segments = self._collect_stream(mock_model, "Hello world.")
        total = sum(len(s) for s, _ in segments)
        assert total > 0
        assert mock_model.generate_stream.call_count == 1

    def test_long_text(self, mock_model):
        """Long text should produce audio from all segments."""
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence."
        segments = self._collect_stream(mock_model, text)
        total = sum(len(s) for s, _ in segments)
        assert total > 0
        # Full text passed to generate_stream in one call
        assert mock_model.generate_stream.call_count == 1

    def test_paragraph_text(self, mock_model):
        """Paragraph-length text should stream successfully."""
        text = (
            "The ancient library stood at the edge of town, its weathered stone "
            "walls covered in ivy that had been growing for decades. Inside, rows "
            "upon rows of leather-bound books stretched from floor to ceiling, "
            "their spines cracked and faded from years of careful handling."
        )
        segments = self._collect_stream(mock_model, text)
        total_samples = sum(len(seg) for seg, _ in segments)
        assert total_samples > 24000  # at least 1 second

    def test_multi_paragraph(self, mock_model):
        """Multi-paragraph text should produce audio from all paragraphs."""
        text = (
            "The morning sun cast long shadows. Birds sang their dawn chorus.\n\n"
            "Inside the bakery, Mrs. Chen arranged croissants. The first customer arrived."
        )
        segments = self._collect_stream(mock_model, text)
        total = sum(len(s) for s, _ in segments)
        assert total > 0
