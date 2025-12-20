"""
Kokoro TTS API v2 - Configuration

Minimal configuration for the simplified TTS server.
"""

import os
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Model files (kokoro-onnx v1.0)
MODEL_PATH = MODELS_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODELS_DIR / "voices-v1.0.bin"

# Server settings
HOST = os.getenv("TTS_HOST", "0.0.0.0")
PORT = int(os.getenv("TTS_PORT", "8080"))  # Different port to run alongside old server

# Audio settings
SAMPLE_RATE = 24000  # Kokoro outputs 24kHz audio
CHUNK_SIZE_MS = 100  # Stream in 100ms chunks
CHUNK_SIZE_SAMPLES = int(SAMPLE_RATE * CHUNK_SIZE_MS / 1000)  # 2400 samples per chunk

# Default TTS settings
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.5
MAX_SPEED = 2.0

# Warmup settings
WARMUP_TEXT = "System ready."
