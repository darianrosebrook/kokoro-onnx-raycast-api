# Kokoro TTS

Local text-to-speech server powered by [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx), with a macOS menu bar app and Raycast extension for quick access.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Raycast Ext    │────▶│  FastAPI Server   │────▶│  kokoro-onnx    │
│  (TypeScript)   │     │  :8080            │     │  ONNX Runtime   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                                              │
        ▼                                              ▼
┌─────────────────┐                           ┌─────────────────┐
│  Audio Daemon   │                           │  Voice Models   │
│  :8081 (WS)     │                           │  models/        │
└─────────────────┘                           └─────────────────┘
        │
        ▼
┌─────────────────┐
│  macOS Menu Bar │
│  (Swift)        │
└─────────────────┘
```

**Components:**

| Component | Location | Purpose |
|-----------|----------|---------|
| FastAPI backend | `api/` | TTS generation via OpenAI-compatible `/v1/audio/speech` endpoint |
| Audio daemon | `raycast/bin/audio-daemon.js` | WebSocket server for streaming audio playback |
| Raycast extension | `raycast/src/` | UI for speaking text/selections |
| macOS menu bar | `KokoroTTS/` | Swift app for server status and controls |
| Launch agents | `launchagents/` | macOS auto-start plists |

## Quick Start

### Prerequisites

- Python 3.11+ with virtual environment
- Node.js 22+
- macOS (for audio daemon and menu bar app)

### Setup

```bash
# Run the full setup (creates venv, installs deps, downloads models)
./setup.sh

# Start development server (auto-detects Cursor/VS Code, safe defaults)
./start_development.sh

# Or production mode
./start_production.sh
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/voices` | GET | List available voices |
| `/status` | GET | Server status with model info |
| `/v1/audio/speech` | POST | Generate speech (OpenAI-compatible) |

### Example

```bash
curl -X POST http://127.0.0.1:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "voice": "af_bella"}' \
  -o output.wav
```

## Development

```bash
# Run tests
python -m pytest tests/unit -v

# Run all quality gates
make caws-gates

# Quick endpoint smoke test
./scripts/quick_test.sh

# Full integration test
python scripts/test_endpoints.py
```

## Models

The default model is `kokoro-v1.0.onnx` in `models/`. Optimized variants (int8, graph-optimized) are in `optimized_models/`. Set `KOKORO_MODEL_FILE` to use a specific model:

```bash
# Use the int8 graph-optimized model (default in production)
KOKORO_MODEL_FILE=kokoro-v1.0.int8-graph-opt.onnx ./start_production.sh
```

## Project Structure

```
api/                  # FastAPI backend (~200 LOC)
  config.py           # Configuration and model paths
  main.py             # Endpoints and request models
  tts.py              # TTS generation with kokoro-onnx
  streaming.py        # Audio streaming with WAV headers
KokoroTTS/            # Swift macOS menu bar app
raycast/              # Raycast extension + audio daemon
  src/                # Extension UI (TypeScript/React)
  bin/audio-daemon.js # WebSocket audio server (Node.js)
tests/                # Test suite
  unit/               # Unit tests
  integration/        # Integration tests
  contract/           # API contract tests
  performance/        # Performance benchmarks
scripts/              # Development utilities
models/               # ONNX model and voice files
optimized_models/     # Quantized/optimized model variants
launchagents/         # macOS LaunchAgent plists
docs/                 # Documentation
  adr/                # Architecture Decision Records
  deployment/         # Deployment guides
  implementation/     # Implementation details
  optimization/       # Performance analysis
contracts/            # OpenAPI specification
```
