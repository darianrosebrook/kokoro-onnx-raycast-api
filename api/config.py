"""
Kokoro TTS API v2 - Configuration

Minimal configuration for the simplified TTS server.
Uses kokoro-mlx for Apple Silicon GPU-accelerated inference.
"""

import os

# Server settings
HOST = os.getenv("TTS_HOST", "0.0.0.0")
PORT = int(os.getenv("TTS_PORT", "8080"))

# Audio settings
SAMPLE_RATE = 24000  # Kokoro outputs 24kHz audio
CHUNK_SIZE_MS = 100  # Stream in 100ms chunks
CHUNK_SIZE_SAMPLES = int(SAMPLE_RATE * CHUNK_SIZE_MS / 1000)  # 2400 samples per chunk

# Default TTS settings
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.5
MAX_SPEED = 2.0

# MLX model settings
MODEL_ID = os.getenv("KOKORO_MODEL_ID", "mlx-community/Kokoro-82M-bf16")

# Warmup settings
WARMUP_TEXT = "System ready."
