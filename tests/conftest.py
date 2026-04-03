"""
Shared test fixtures for Kokoro TTS API tests.

Provides mock model that mimics kokoro-mlx's KokoroTTS interface,
producing real numpy arrays so streaming/PCM code exercises actual data paths.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import api.tts as tts_module
import api.main as main_module
from api.main import app


# --- Audio fixtures ---

@pytest.fixture
def sample_audio():
    """1-second 440Hz sine wave as float32 (24000 samples at 24kHz)."""
    t = np.arange(24000) / 24000
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def short_audio():
    """Very short audio — 10 samples."""
    return np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1], dtype=np.float32)


# --- Mock model (mimics kokoro-mlx KokoroTTS) ---

MOCK_VOICES = ["af_heart", "bm_fable", "af_bella"]


def _make_audio(text, speed=1.0):
    """Generate a sine wave proportional to text length."""
    duration = max(0.1, len(text) * 0.02)  # ~20ms per character
    n_samples = int(24000 * duration)
    t = np.arange(n_samples) / 24000
    return np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.8


def _make_mock_model():
    """Create a mock KokoroTTS model that produces real numpy audio."""
    model = MagicMock()
    model.list_voices.return_value = MOCK_VOICES

    # generate() — kokoro-mlx returns a TTSResult with .audio and .sample_rate
    def fake_generate(text, voice="af_heart", speed=1.0, **kwargs):
        audio = _make_audio(text, speed)
        result = MagicMock()
        result.audio = audio
        result.sample_rate = 24000
        return result

    model.generate.side_effect = fake_generate

    # generate_stream() — sync generator yielding numpy arrays per segment
    def fake_generate_stream(text, voice="af_heart", speed=1.0, **kwargs):
        audio = _make_audio(text, speed)
        n_samples = len(audio)
        # Yield in up to 3 segments
        num_segments = min(3, max(1, n_samples // 2400))
        segment_size = n_samples // num_segments
        for i in range(num_segments):
            start = i * segment_size
            end = n_samples if i == num_segments - 1 else (i + 1) * segment_size
            yield audio[start:end]

    model.generate_stream.side_effect = fake_generate_stream
    return model


@pytest.fixture
def mock_model():
    """A mock KokoroTTS model that produces real numpy arrays."""
    return _make_mock_model()


# --- Client fixtures ---

@pytest.fixture
def client():
    """TestClient with mock model loaded — for testing endpoints that need a ready model."""
    mock = _make_mock_model()
    with patch.object(main_module, 'initialize_model', return_value=0.01), \
         patch.object(tts_module, '_model', mock), \
         patch.object(tts_module, '_model_ready', True):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def client_no_model():
    """TestClient with no model — for testing 503 responses."""
    with patch.object(main_module, 'initialize_model', return_value=0.01), \
         patch.object(tts_module, '_model', None), \
         patch.object(tts_module, '_model_ready', False):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
