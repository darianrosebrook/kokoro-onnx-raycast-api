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
-   **Production Mode**: `KOKORO_PRODUCTION` (enables production optimizations)
-   **TTS Parameters**: `MAX_SEGMENT_LENGTH`, `SAMPLE_RATE`
-   **Optimization Flags**: `KOKORO_ORT_OPTIMIZATION`, `KOKORO_BENCHMARK_FREQUENCY`, `KOKORO_DEVELOPMENT_MODE`
-   **Hardware Providers**: `ONNX_PROVIDER`, `COREML_COMPUTE_UNITS`
-   **Resource Management**: `MEMORY_CLEANUP_THRESHOLD` (e.g., `50` to clean up every 50 chunks)
-   **Performance Tuning**: `KOKORO_GRAPH_OPT_LEVEL`, `KOKORO_MEMORY_ARENA_SIZE_MB`, `KOKORO_DISABLE_MEM_PATTERN`
-   **CoreML Optimization**: `KOKORO_COREML_MODEL_FORMAT`, `KOKORO_COREML_COMPUTE_UNITS`, `KOKORO_COREML_SPECIALIZATION`
-   **Security**: `KOKORO_ALLOWED_HOSTS` (comma-separated list for production)

### Apple Silicon Optimization
The API features comprehensive Apple Silicon optimization with exceptional performance results:

- **Neural Engine Acceleration**: Automatically detects and utilizes M1/M2/M3 Neural Engine cores
- **Intelligent Caching**: Thread-safe inference caching with MD5 keys and TTL management
- **Memory Optimization**: Dynamic memory arena sizing based on system specifications
- **Performance Results**: Up to **99.6% faster inference** for cached requests on Apple Silicon

**M1 Max Performance Example**:
- Cold start: ~3.5 seconds
- Cached inference: ~0.014 seconds (99.6% improvement)
- 100% CoreML provider utilization

For a detailed explanation of ORT, its benefits, and manual controls, see the [**ORT Optimization Guide](./docs/ORT_OPTIMIZATION_GUIDE.md)**.

### Benchmarking & Monitoring
The system includes comprehensive tools for performance measurement, validation, and real-time monitoring.

#### **Performance Validation Tools**
```bash
# Quick performance validation (recommended)
./scripts/quick_performance_test.sh

# Comprehensive optimization validation
python scripts/validate_optimization_performance.py

# Compare against previous commit
python scripts/baseline_comparison.py --days-ago 7

# Test specific optimization features
python scripts/validate_optimization_performance.py --test-features
```

#### **Standard Benchmarking**
```bash
# Standard benchmark (tests current configuration)
python scripts/run_benchmark.py

# Comprehensive benchmark (tests multiple production scenarios)
python scripts/run_benchmark.py --comprehensive
```

#### **Real-time Monitoring**
```bash
# Get detailed performance metrics
curl http://localhost:8000/status | jq '.performance'

# Quick system health check
curl http://localhost:8000/health
```

**Performance Reports**: All validation and benchmark reports are automatically saved with timestamps in `reports/validation/` and `reports/benchmarks/` for performance tracking.

For a deep dive into configuring benchmark frequency, managing caches, and interpreting results, see the [**Benchmarking & Monitoring Guide](./docs/benchmarking.md)**.

### Comprehensive Benchmark Suite
The `run_benchmark.py --comprehensive` command runs an extensive test suite that evaluates performance across multiple configurations, providing a clear picture of how different optimization settings affect inference speed.

**Scenarios Tested:**
-   **Development vs. Production Mode**: Compares performance with and without production optimizations.
-   **ONNX Runtime Optimization Levels**: Tests `DISABLED`, `BASIC`, `EXTENDED`, and `ALL` graph optimization levels.
-   **CoreML Compute Units (Apple Silicon only)**: Tests `CPUOnly`, `CPUAndGPU`, and `ALL` to find the optimal hardware utilization strategy.

**Recent Benchmark Insights:**
-   **ORT Level: BASIC** typically provides the best performance balance
-   **CoreML: CPUAndGPU** is optimal for long-form content processing
-   **Production mode** consistently outperforms development mode by ~3%
-   **Diminishing returns** observed with high-level optimizations (ALL levels)

**Workloads Tested:**
-   **Standard Text**: A medium-length paragraph to test typical TTS requests.
-   **Article-Length Text**: A full-length article to evaluate performance on long-form content.

The output is a formatted table that makes it easy to compare results and identify the best-performing configurations for your hardware.

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

#### **Performance Validation**
Validate that the TTS optimizations are working correctly:

```bash
# Quick performance test (recommended)
./scripts/quick_performance_test.sh

# Comprehensive validation
python scripts/validate_optimization_performance.py --quick

# Test with server already running
python scripts/validate_optimization_performance.py --test-features
```

#### **System Testing**
-   **Run Tests**: The `scripts/` directory contains various test and validation scripts.
-   **Enable Debug Logs**: Set `export LOG_LEVEL="DEBUG"` for verbose output.
-   **Validation Reports**: Check `reports/validation/` for detailed performance validation reports.

For a complete walkthrough of the development process, including optimization workflows and debugging tools, see the [**Development Guide](./docs/development.md)**.

## Running in Production

### Quick Production Start
Use the `gunicorn`-based production script for deployment with optimized settings.

```bash
./start_production.sh
```

### Production Optimizations
The production mode automatically enables several performance and security optimizations:

#### **FastAPI Production Features**
- **ORJSON Serialization**: 2-3x faster JSON processing
- **GZip Compression**: Automatic compression for responses >1KB  
- **Security Headers**: XSS protection, content type validation, frame options
- **Documentation Disabled**: API docs disabled for security
- **Performance Middleware**: Request timing and monitoring

#### **ONNX Runtime Optimizations**
- **Graph Optimization**: Maximum optimization level for inference speed
- **Memory Management**: Intelligent arena sizing and pattern optimization
- **Provider Selection**: Hardware-accelerated CoreML with CPU fallback

#### **Production Environment Variables**
```bash
# Enable production mode with all optimizations
export KOKORO_PRODUCTION=true

# ONNX Runtime optimization (BASIC level often performs best)
export KOKORO_GRAPH_OPT_LEVEL=BASIC
export KOKORO_MEMORY_ARENA_SIZE_MB=512
export KOKORO_DISABLE_MEM_PATTERN=false

# CoreML provider tuning (Apple Silicon) - CPUAndGPU often optimal
export KOKORO_COREML_MODEL_FORMAT=MLProgram
export KOKORO_COREML_COMPUTE_UNITS=CPUAndGPU
export KOKORO_COREML_SPECIALIZATION=FastPrediction

# Security (production)
export KOKORO_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
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

### Performance Monitoring
Monitor production performance using the status endpoint:
```bash
curl http://localhost:8000/status | jq '.performance'
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

#### **Performance Validation**
-   **`quick_performance_test.sh`**: Quick performance validation test (recommended for regular checks)
-   **`validate_optimization_performance.py`**: Comprehensive optimization validation suite
-   **`baseline_comparison.py`**: Compare performance against previous commits
-   **`run_benchmark.py`**: Standard benchmarking and performance analysis

#### **System Diagnostics**
-   **`check_environment.py`**: Validates your Python environment, packages, and project setup.
-   **`troubleshoot_coreml.py`**: Runs a full diagnostic on CoreML and hardware acceleration. It detects available compute units (CPU, GPU, Neural Engine), confirms the Neural Engine is used, and provides a clear PASS/FAIL report with actionable suggestions.
    ```bash
    # Run the CoreML probe:
    python scripts/troubleshoot_coreml.py
    ```
-   **`manage_benchmark_cache.py`**: Inspects and manages the benchmark cache.

#### **System Status**
-   **Patch Verification**: Check if the runtime safety patches were applied correctly.
    ```bash
    # Verify patches applied successfully
    curl http://localhost:8000/status | jq '.patch_status'
    
    # Check optimization features status
    curl http://localhost:8000/status | jq '.hardware'
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


