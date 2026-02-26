"""
Tests for api/main.py — all HTTP endpoints, validation edge cases, error handling.

Replaces the broken contract/integration tests that referenced the old API.
"""

import struct
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pytest

from api.config import DEFAULT_VOICE


# --- Health endpoint ---

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True

    def test_health_model_not_loaded(self, client_no_model):
        r = client_no_model.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "initializing"
        assert data["model_loaded"] is False


# --- Voices endpoint ---

class TestVoicesEndpoint:
    def test_voices_returns_list(self, client):
        r = client.get("/voices")
        assert r.status_code == 200
        voices = r.json()["voices"]
        assert isinstance(voices, list)
        assert "af_heart" in voices

    def test_voices_model_not_ready(self, client_no_model):
        r = client_no_model.get("/voices")
        assert r.status_code == 503


# --- Status endpoint ---

class TestStatusEndpoint:
    def test_status_model_loaded(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["model_loaded"] is True
        assert data["voices_count"] > 0

    def test_status_model_not_loaded(self, client_no_model):
        r = client_no_model.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["model_loaded"] is False
        assert data["voices_count"] == 0


# --- TTS endpoint: valid requests ---

class TestTTSEndpointValid:
    def test_basic_request(self, client):
        r = client.post("/v1/audio/speech", json={
            "input": "Hello world",
            "voice": "af_heart",
            "speed": 1.0,
        })
        assert r.status_code == 200
        assert len(r.content) > 0
        assert r.headers["content-type"] == "audio/pcm"

    def test_text_field_accepted(self, client):
        """Legacy 'text' field should work as fallback for 'input'."""
        r = client.post("/v1/audio/speech", json={
            "text": "Hello world",
        })
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_both_input_and_text(self, client):
        """When both provided, 'input' takes precedence."""
        r = client.post("/v1/audio/speech", json={
            "input": "Short",
            "text": "This is a much longer text that should not be used",
        })
        assert r.status_code == 200
        # Audio should be short (from "Short")
        assert len(r.content) < 10000

    def test_wav_format(self, client):
        r = client.post("/v1/audio/speech", json={
            "input": "Hello",
            "response_format": "wav",
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content[:4] == b'RIFF'

    def test_pcm_format(self, client):
        r = client.post("/v1/audio/speech", json={
            "input": "Hello",
            "response_format": "pcm",
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/pcm"
        # PCM should NOT start with RIFF
        assert r.content[:4] != b'RIFF'

    def test_response_headers(self, client):
        r = client.post("/v1/audio/speech", json={"input": "Hello"})
        assert "x-audio-duration" in r.headers
        assert "x-generation-time" in r.headers
        assert "x-rtf" in r.headers
        assert float(r.headers["x-audio-duration"]) > 0

    def test_wav_header_data_size_matches_body(self, client):
        """WAV header data_size field should match actual PCM data."""
        r = client.post("/v1/audio/speech", json={
            "input": "Hello world",
            "response_format": "wav",
        })
        header = r.content[:44]
        data_size = struct.unpack('<I', header[40:44])[0]
        actual_pcm = len(r.content) - 44
        assert data_size == actual_pcm

    def test_invalid_voice_falls_back(self, client):
        """Invalid voice should succeed with default voice, not error."""
        r = client.post("/v1/audio/speech", json={
            "input": "Hello",
            "voice": "nonexistent_voice_xyz",
        })
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_compat_endpoint(self, client):
        """/audio/speech should work the same as /v1/audio/speech."""
        r = client.post("/audio/speech", json={"input": "Hello"})
        assert r.status_code == 200

    def test_unicode_text(self, client):
        r = client.post("/v1/audio/speech", json={"input": "Héllo wörld café"})
        assert r.status_code == 200

    def test_single_character(self, client):
        r = client.post("/v1/audio/speech", json={"input": "A"})
        assert r.status_code == 200


# --- TTS endpoint: validation errors ---

class TestTTSEndpointValidation:
    def test_empty_text(self, client):
        """Empty string should be rejected (len < 1 in validator)."""
        r = client.post("/v1/audio/speech", json={"input": ""})
        assert r.status_code == 422

    def test_whitespace_only(self, client):
        """Whitespace-only text passes pydantic but caught by endpoint."""
        r = client.post("/v1/audio/speech", json={"input": "   "})
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_text_too_long(self, client):
        """Text over 10000 chars should be rejected."""
        r = client.post("/v1/audio/speech", json={"input": "x" * 10001})
        assert r.status_code == 422

    def test_text_at_max_length(self, client):
        """Text at exactly 10000 chars should be accepted."""
        r = client.post("/v1/audio/speech", json={"input": "x" * 10000})
        assert r.status_code == 200

    def test_no_text_fields(self, client):
        """Request with neither 'input' nor 'text' should fail."""
        r = client.post("/v1/audio/speech", json={"voice": "af_heart"})
        assert r.status_code == 422

    def test_speed_too_low(self, client):
        """Speed below MIN_SPEED should be rejected by pydantic."""
        r = client.post("/v1/audio/speech", json={"input": "Hello", "speed": 0.1})
        assert r.status_code == 422

    def test_speed_too_high(self, client):
        """Speed above MAX_SPEED should be rejected by pydantic."""
        r = client.post("/v1/audio/speech", json={"input": "Hello", "speed": 5.0})
        assert r.status_code == 422

    def test_speed_at_min(self, client):
        r = client.post("/v1/audio/speech", json={"input": "Hello", "speed": 0.5})
        assert r.status_code == 200

    def test_speed_at_max(self, client):
        r = client.post("/v1/audio/speech", json={"input": "Hello", "speed": 2.0})
        assert r.status_code == 200


# --- TTS endpoint: error conditions ---

class TestTTSEndpointErrors:
    def test_model_not_ready(self, client_no_model):
        r = client_no_model.post("/v1/audio/speech", json={"input": "Hello"})
        assert r.status_code == 503
        assert "not ready" in r.json()["detail"].lower()

    def test_generation_exception(self, client):
        """If model.create() throws, endpoint should return 500."""
        from unittest.mock import patch
        import api.tts as tts_module

        failing_model = tts_module._model
        failing_model.create.side_effect = RuntimeError("ONNX crash")
        r = client.post("/v1/audio/speech", json={"input": "Hello"})
        assert r.status_code == 500
        assert "ONNX crash" in r.json()["detail"]
        # Restore
        from tests.conftest import _make_mock_model
        mock = _make_mock_model()
        failing_model.create.side_effect = mock.create.side_effect


# --- Concurrent requests ---

class TestConcurrentRequests:
    def test_concurrent_requests(self, client):
        """10 simultaneous requests should all succeed."""
        def make_request(i):
            return client.post("/v1/audio/speech", json={
                "input": f"Concurrent request number {i}",
            })

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(make_request, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        statuses = [r.status_code for r in results]
        assert all(s == 200 for s in statuses), f"Got statuses: {statuses}"

    def test_concurrent_mixed_voices(self, client):
        """Concurrent requests with different voices should all succeed."""
        voices = ["af_heart", "bm_fable", "af_bella"]

        def make_request(voice):
            return client.post("/v1/audio/speech", json={
                "input": f"Testing voice {voice}",
                "voice": voice,
            })

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(make_request, v) for v in voices]
            results = [f.result() for f in as_completed(futures)]

        assert all(r.status_code == 200 for r in results)
