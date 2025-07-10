# Kokoro-ONNX TTS API

A high-performance, production-ready Text-to-Speech API built on the Kokoro-ONNX neural TTS model, optimized for Apple Silicon and featuring comprehensive performance monitoring, intelligent text processing, and OpenAI-compatible endpoints.

## Features

### Core Capabilities
- **High-Quality Neural TTS**: Powered by the Kokoro-ONNX model for natural-sounding speech synthesis.
- **Hardware Acceleration**: Optimized for Apple Silicon (M1/M2/M3) with CoreML acceleration.
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI's TTS API with a `/v1/audio/speech` endpoint.
- **Streaming Audio**: Real-time audio streaming with configurable chunk sizes.
- **Multi-Voice Support**: 60+ voices across multiple languages with customizable speed settings.
- **Intelligent Text Processing**: Advanced text normalization, segmentation, and preprocessing (including emoji stripping, zero-width character detection, and code-block-aware segmentation).

### Production-Ready
- **Comprehensive Validation**: Robust startup validation for dependencies, model files, and environment.
- **Performance Benchmarking & Real-Time Monitoring**: Automatic provider benchmarking with detailed analysis and real-time metrics.
- **Memory Management**: Automatic cleanup of CoreML session handles to prevent memory leaks, tunable via the `MEMORY_CLEANUP_THRESHOLD` environment variable.
- **ORT Optimization**: Intelligent Apple Silicon optimization with automatic ORT model conversion.
- **Safety Guards**: Idempotent monkey-patches and fallback mechanisms to ensure stability. For more details, see the [Production Patches Guide](./docs/production-patches.md).

### Developer Experience
- **Modern FastAPI Backend**: High-performance API with automatic OpenAPI documentation.
- **Raycast Integration**: Native Raycast extension for quick TTS access.
- **Hot Reload, Debugging & Profiling**: Seamless development experience with `uvicorn`.

## Project Structure

```
kokoro-onnx/
├── api/                          # FastAPI backend application
│   ├── main.py                   # FastAPI application with robust startup validation
│   └── model/                    # Model loading and optimization
│   └── tts/                      # TTS processing pipeline
│   └── performance/              # Performance monitoring and statistics
│   └── utils/                    # Utility functions 
├── docs/                         # Detailed documentation
│   ├── ORT-optimization-guide.md # In-depth guide to ORT optimization
│   ├── benchmarking.md           # Benchmarking and performance monitoring details
│   ├── development.md            # Development and contribution guide
│   └── production-patches.md     # Guide to stability patches
├── raycast/                      # Raycast extension
│   └── src/                      # Raycast extension source code
├── scripts/                      # Diagnostic and optimization tools 
├── requirements.txt              # Python dependencies
├── setup.sh                      # Automated setup script
├── start_development.sh          # Development server startup
└── start_production.sh           # Production server startup
```

## Installation

### Automated Quickstart
Get up and running with a single command. This script handles all dependencies, model downloads, and environment setup.

```bash
./setup.sh
```
> **Note**: On the first run, you may see a message about ORT conversion. This is a one-time optimization step that makes subsequent startups much faster.

### Manual Installation
If you prefer to install manually, follow these steps:

1.  **Set up Python Environment**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
2.  **Install eSpeak-ng**
    ```bash
    # macOS (Homebrew)
    brew install espeak-ng
    ```
3.  **Download Models**
    ```bash
    wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
    wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
    ```
4.  **Install Raycast Extension Dependencies**
    ```bash
    cd raycast
    npm install
    cd ..
    ```

## ⚙️ Configuration & Optimization

### Environment Variables
Configure the application using environment variables. For a full list of options, see the [Development Guide](./docs/development.md).

-   **Server Settings**: `HOST`, `PORT`, `LOG_LEVEL`
-   **TTS Parameters**: `MAX_SEGMENT_LENGTH`, `SAMPLE_RATE`
-   **Optimization Flags**: `KOKORO_ORT_OPTIMIZATION`, `KOKORO_BENCHMARK_FREQUENCY`, `KOKORO_DEVELOPMENT_MODE`
-   **Hardware Providers**: `ONNX_PROVIDER`, `COREML_COMPUTE_UNITS`
-   **Resource Management**: `MEMORY_CLEANUP_THRESHOLD` (e.g., `50` to clean up every 50 chunks)

### ORT Optimization (Apple Silicon)
The API automatically uses ONNX Runtime (ORT) to accelerate performance on Apple Silicon. This can result in a **3-5x inference speedup**. It is enabled by default on compatible hardware.

For a detailed explanation of ORT, its benefits, and manual controls, see the [**ORT Optimization Guide](./docs/ORT_OPTIMIZATION_GUIDE.md)**.

### Benchmarking & Monitoring
The system includes tools for performance measurement and real-time monitoring.

-   **Run Benchmarks**:
    ```bash
    # Quick performance test
    python scripts/quick_benchmark.py
    # Full, detailed benchmark
    python run_benchmark.py --verbose
    ```
-   **Real-time Metrics**: Access performance data at the `/status` endpoint.
    ```bash
    curl http://localhost:8000/status | jq '.performance'
    ```

For a deep dive into configuring benchmark frequency, managing caches, and interpreting results, see the [**Benchmarking & Monitoring Guide](./docs/benchmarking.md)**.

## 🛠️ Development & Testing

### Setup & Run
1.  **Run the setup script**: `./setup.sh`
2.  **Start the development server**:
    ```bash
    # Starts the API with hot-reloading
    ./start_development.sh
    ```
3.  **Run the Raycast extension**:
    ```bash
    cd raycast
    npm run dev
    ```

### Testing & Debugging
-   **Run Tests**: The `scripts/` directory contains various test and validation scripts.
-   **Enable Debug Logs**: Set `export LOG_LEVEL="DEBUG"` for verbose output.

For a complete walkthrough of the development process, including optimization workflows and debugging tools, see the [**Development Guide](./docs/development.md)**.

## Running in Production

Use the `gunicorn`-based production script for deployment.

```bash
./start_production.sh
```

**Note on Apple Silicon**: The production script includes logic to ensure CoreML stability by running a single worker, as the Neural Engine does not support multiprocessing.
```bash
if [[ "$(uname -m)" == "arm64" ]]; then
  WORKERS=1
  echo "⚠️ Apple Silicon detected—running single-worker to ensure CoreML stability."
else
  WORKERS=$(nproc)
fi
gunicorn -w $WORKERS …
```

## API Reference

Once the server is running, full interactive documentation is available at `http://localhost:8000/docs`.

### Key Endpoints

#### `POST /v1/audio/speech`
Generates audio from text. Supports streaming.

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test of the TTS system.",
    "voice": "af_heart"
  }' \
  --output speech.wav
```

#### `GET /status`
Returns a comprehensive JSON object with system status, hardware info, and real-time performance metrics.

#### `GET /health`
A simple health check endpoint that returns `{"status": "online"}`.

## 🛠️ Troubleshooting & Diagnostics

### Diagnostic Tools
The `scripts/` directory contains powerful diagnostic tools:

-   **`check_environment.py`**: Validates your Python environment, packages, and project setup.
-   **`troubleshoot_coreml.py`**: Runs a full diagnostic on CoreML and hardware acceleration. It detects available compute units (CPU, GPU, Neural Engine), confirms the Neural Engine is used, and provides a clear PASS/FAIL report with actionable suggestions.
    ```bash
    # Run the CoreML probe:
    python scripts/troubleshoot_coreml.py
    ```
-   **`manage_benchmark_cache.py`**: Inspects and manages the benchmark cache.
-   **Patch Verification**: Check if the runtime safety patches were applied correctly.
    ```bash
    # Verify patches applied successfully
    curl http://localhost:8000/status | jq '.patch_status'
    ```

### Common Issues
-   **Slow Startup**: The first run includes a one-time benchmarking process. Subsequent startups will be faster. Use `export KOKORO_SKIP_BENCHMARKING=true` to disable it for development.
-   **CoreML Errors**: Run `python scripts/troubleshoot_coreml.py` to diagnose issues.
-   **Port Conflicts**: Use `lsof -i :8000` to find the conflicting process.

## Contributing

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes (`git commit -m 'Add amazing feature'`).
4.  Push to the branch (`git push origin feature/amazing-feature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License.

## Acknowledgments

- **Kokoro-ONNX**: Base TTS model and inference engine
- **FastAPI**: High-performance web framework
- **Raycast**: Extensible launcher platform
- **Apple**: CoreML optimization framework
- **ONNX Runtime**: Cross-platform inference optimization

## Support

For bugs and feature requests, please open an issue on the [project's GitHub page](https://github.com/darianrosebrook/kokoro-onnx-raycast-api/issues).

---

**Author**: @darianrosebrook


