"""
Tests for api/tts.py — model lifecycle, audio generation, voice fallback, speed clamping.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

import api.tts as tts_module
from api.tts import generate_audio, get_model, get_voices, is_model_ready
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
            # Should succeed (fell back to default)
            assert len(audio) > 0
            # Verify the model was called with the default voice
            _, kwargs = mock_model.create.call_args
            assert kwargs['voice'] == DEFAULT_VOICE

    def test_valid_voice_used(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", voice="af_bella")
            _, kwargs = mock_model.create.call_args
            assert kwargs['voice'] == "af_bella"

    def test_speed_clamped_low(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=0.1)
            _, kwargs = mock_model.create.call_args
            assert kwargs['speed'] == MIN_SPEED

    def test_speed_clamped_high(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=5.0)
            _, kwargs = mock_model.create.call_args
            assert kwargs['speed'] == MAX_SPEED

    def test_speed_within_range_unchanged(self, mock_model):
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            generate_audio("Hello", speed=1.5)
            _, kwargs = mock_model.create.call_args
            assert kwargs['speed'] == 1.5

    def test_model_exception_propagates(self, mock_model):
        mock_model.create.side_effect = RuntimeError("ONNX inference failed")
        with patch.object(tts_module, '_model', mock_model), \
             patch.object(tts_module, '_model_ready', True):
            with pytest.raises(RuntimeError, match="ONNX inference failed"):
                generate_audio("Hello")
