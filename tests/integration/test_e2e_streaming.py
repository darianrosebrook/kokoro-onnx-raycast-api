"""
End-to-end streaming tests against a live Kokoro TTS server.

These tests require the server to be running on localhost:8080.
Skip with: pytest tests/integration/ -m "not integration"
Run with:  pytest tests/integration/ -v -m integration
"""

import struct

import httpx
import pytest

BASE_URL = "http://localhost:8080"


def server_is_available():
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not server_is_available(),
        reason="TTS server not running on localhost:8080",
    ),
]


class TestLiveHealth:
    def test_health_ok(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True

    def test_voices_available(self):
        r = httpx.get(f"{BASE_URL}/voices", timeout=5)
        assert r.status_code == 200
        voices = r.json()["voices"]
        assert len(voices) > 0


class TestLiveStreaming:
    def test_pcm_stream_complete(self):
        """POST returns complete PCM data with valid headers."""
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": "Hello world", "response_format": "pcm"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/pcm"
        assert len(r.content) > 0
        # PCM: 16-bit samples, so byte count should be even
        assert len(r.content) % 2 == 0

    def test_wav_stream_valid_header(self):
        """WAV response has valid RIFF header and matching data size."""
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": "Hello world", "response_format": "wav"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content[:4] == b"RIFF"
        assert r.content[8:12] == b"WAVE"

        # Verify data_size matches actual PCM payload
        data_size = struct.unpack("<I", r.content[40:44])[0]
        actual_pcm = len(r.content) - 44
        assert data_size == actual_pcm

    def test_timing_headers_present(self):
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": "Test timing"},
            timeout=30,
        )
        assert r.status_code == 200
        assert float(r.headers["x-audio-duration"]) > 0
        assert float(r.headers["x-generation-time"]) > 0
        assert float(r.headers["x-rtf"]) > 0

    def test_consecutive_rapid_requests(self):
        """5 requests sent back-to-back should all succeed."""
        results = []
        for i in range(5):
            r = httpx.post(
                f"{BASE_URL}/v1/audio/speech",
                json={"input": f"Rapid request number {i + 1}"},
                timeout=30,
            )
            results.append(r)

        assert all(r.status_code == 200 for r in results)
        assert all(len(r.content) > 0 for r in results)

    def test_long_text(self):
        """500-word paragraph completes without error."""
        text = " ".join(["The quick brown fox jumps over the lazy dog."] * 55)
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": text},
            timeout=120,
        )
        assert r.status_code == 200
        # Long text should produce substantial audio
        assert len(r.content) > 10000

    def test_empty_text_rejected(self):
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": ""},
            timeout=10,
        )
        assert r.status_code == 422

    def test_whitespace_only_rejected(self):
        r = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json={"input": "   "},
            timeout=10,
        )
        assert r.status_code == 400


class TestLiveConnectionErrors:
    def test_wrong_port_connection_refused(self):
        """Connecting to a wrong port should raise cleanly."""
        with pytest.raises((httpx.ConnectError, httpx.TimeoutException)):
            httpx.post(
                "http://localhost:59999/v1/audio/speech",
                json={"input": "Hello"},
                timeout=2,
            )
