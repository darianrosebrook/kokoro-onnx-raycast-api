# Kokoro-ONNX TTS API

A high-performance, production-ready Text-to-Speech API built on the Kokoro-ONNX neural TTS model, optimized for Apple Silicon and featuring comprehensive performance monitoring, intelligent text processing, and OpenAI-compatible endpoints.

## 🚀 Features

### Core Capabilities
- **High-Quality Neural TTS**: Powered by the Kokoro-ONNX model for natural-sounding speech synthesis
- **Hardware Acceleration**: Optimized for Apple Silicon (M1/M2/M3) with CoreML acceleration
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI's TTS API with `/v1/audio/speech` endpoint
- **Streaming Audio**: Real-time audio streaming with configurable chunk sizes
- **Multi-Voice Support**: 60+ voices across multiple languages with customizable speed settings
- **Intelligent Text Processing**: Advanced text normalization, segmentation, and preprocessing

### Production-Ready Features
- **Comprehensive Validation**: Robust startup validation for dependencies, model files, and environment
- **Production Patches**: Safe, idempotent patches for kokoro-onnx library compatibility
- **Enhanced Error Handling**: Multi-level fallback strategies and graceful error handling
- **Performance Benchmarking**: Automatic provider benchmarking with detailed analysis
- **Real-Time Monitoring**: Comprehensive metrics, statistics, and system health tracking
- **Memory Management**: Automatic cleanup and resource optimization
- **ORT Optimization**: Intelligent Apple Silicon optimization with automatic ORT model conversion
- **Diagnostic Tools**: Comprehensive environment checking and CoreML troubleshooting

### Developer Experience
- **FastAPI Backend**: Modern, high-performance API with automatic OpenAPI documentation
- **Raycast Integration**: Native Raycast extension for quick TTS access
- **Comprehensive Testing**: Automated validation tests and performance benchmarking
- **Development Tools**: Hot reload, debugging support, and performance profiling

## 📁 Project Structure

```
kokoro-onnx/
├── api/                          # FastAPI backend application
│   ├── __init__.py
│   ├── main.py                   # FastAPI application with robust startup validation
│   ├── config.py                 # Configuration models and settings
│   ├── warnings.py               # CoreML warning management
│   ├── model/                    # Model loading and management
│   │   ├── __init__.py
│   │   ├── loader.py             # Hardware detection and model initialization
│   │   └── patch.py              # Production-ready monkey patches with safety guards
│   ├── performance/              # Performance monitoring system
│   │   ├── __init__.py
│   │   ├── stats.py              # Real-time statistics collection
│   │   └── reporting.py          # Benchmark reports and analysis
│   └── tts/                      # TTS processing pipeline
│       ├── __init__.py
│       ├── core.py               # Core TTS functionality
│       └── text_processing.py    # Text normalization and segmentation
├── gunicorn.conf.py              # Gunicorn config for production worker hooks
├── raycast/                      # Raycast extension
│   ├── src/                      # TypeScript source code
│   │   ├── speak-text.tsx        # Text input TTS interface
│   │   ├── speak-selection.tsx   # Selection-based TTS
│   │   ├── types.d.ts            # TypeScript declarations
│   │   ├── types.ts              # TypeScript type definitions
│   │   ├── voices.ts             # Voice configuration (60+ voices)
│   │   └── utils/                # Utility functions
│   │       └── tts-processor.ts  # TTS processing and streaming
│   ├── assets/                   # Extension assets
│   │   └── icon.png              # Raycast extension icon
│   ├── package.json              # Node.js dependencies
│   ├── tsconfig.json             # TypeScript configuration
│   ├── setup.sh                  # Raycast setup script
│   └── test-preprocessing.js     # Testing utilities
├── scripts/                      # Diagnostic and optimization tools
│   ├── check_environment.py      # Environment diagnostic tool
│   ├── troubleshoot_coreml.py    # CoreML troubleshooting tool
│   └── convert_to_ort.py         # ORT conversion and optimization tool
├── README.md                     # This documentation
├── requirements.txt              # Python dependencies
├── run_benchmark.py              # Comprehensive performance benchmarking
├── benchmark_results.md          # Generated performance reports (auto-created) 
├── coreml_config.json            # CoreML configuration file (auto-created)
├── ORT_OPTIMIZATION_GUIDE.md     # Detailed ORT optimization guide
├── start_development.sh          # Development server startup with validation
├── start_production.sh           # Production server startup with Gunicorn
├── kokoro-v1.0.int8.onnx         # ONNX model file (88MB)
├── voices-v1.0.bin               # Voice data file (27MB)
```

## 🚀 Quickstart

Get up and running with a single command. This script will check dependencies, set up the Python environment, download models, and install Raycast dependencies.

```bash
./setup.sh
```

After the setup is complete, follow the instructions to start the API server and the Raycast extension.

## 📦 Installation

If you prefer to install manually, follow the steps below.

### Prerequisites

- **Python 3.8+**: Required for the backend API.
- **Node.js v16+ and npm**: Required for the Raycast extension.
- **Homebrew** (macOS): Recommended for installing `espeak-ng`.
- **wget**: Required for downloading model files.

### 1. Backend API Setup

First, set up the Python environment and install dependencies.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required Python packages
pip install -r requirements.txt
```

### 2. Install eSpeak-ng

The `espeak-ng` library is required for phonemization.

```bash
# macOS (using Homebrew)
brew install espeak-ng

# Other systems (e.g., Debian/Ubuntu)
# sudo apt-get install espeak-ng
```

### 3. Model Files Setup

Download the necessary ONNX model and voice files.

```bash
# Download from GitHub releases into the project root directory
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
```

### 4. Raycast Extension Setup

Finally, install the dependencies for the Raycast extension.

```bash
cd raycast
npm install
```

## ▶️ Running the Application

You need to run the backend API and the Raycast extension in two separate terminal windows.

**1. Start the Backend API:**

In the project root directory, run the development server:

```bash
./start_development.sh
```

**2. Start the Raycast Extension:**

In a new terminal, navigate to the `raycast` directory and start the development server:

```bash
cd raycast
npm run dev
```

## 🚀 Usage

### Development

For development, use the `./start_development.sh` script. It uses `uvicorn` with hot-reloading for a seamless development experience.

```bash
./start_development.sh
```

### Production

For production deployments, use the `./start_production.sh` script, which launches the API using `gunicorn` for robust process management.

```bash
./start_production.sh
```

#### Important Note for Apple Silicon Users

Due to resource contention with the Apple Neural Engine, the production script **automatically forces a single-worker configuration** when running on Apple Silicon (`uname -m` is `arm64`). This is required to ensure the CoreML Execution Provider initializes correctly and hardware acceleration is enabled.

- **Why a single worker?** The CoreML provider cannot handle multiple processes trying to access the Neural Engine simultaneously at startup.
- **Performance**: While limited to a single worker, you get the full performance benefit of hardware acceleration, which is ideal for a low-latency TTS service.
- **Other Platforms**: On non-Apple Silicon systems (e.g., Linux servers), the script will automatically calculate and use an optimal number of workers based on CPU cores.

### API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Comprehensive System Status
```bash
curl http://localhost:8000/status
```

#### Text-to-Speech (OpenAI Compatible)
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test of the TTS system.",
    "voice": "af_heart",
    "speed": 1.0,
    "format": "wav"
  }' \
  --output speech.wav
```

#### Streaming Audio
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Accept: audio/wav" \
  -d '{
    "text": "This is streaming audio generation.",
    "voice": "af_heart",
    "speed": 1.0,
    "format": "wav",
    "stream": true
  }' \
  --no-buffer --output - | mpv -
```

### Raycast Extension

1. **Speak Text**: Use the "Speak Text" command to input text for TTS
2. **Speak Selection**: Use the "Speak Selection" command to convert selected text
3. **Voice Selection**: Configure voice preferences in the extension settings
4. **Speed Control**: Adjust speech speed from 0.25x to 4.0x

## 🏗 Architecture

### Backend Architecture

The backend follows a modular FastAPI architecture optimized for performance and maintainability:

```
┌─────────────────────────────────────────────────────────────
│                     FastAPI Application                           
├─────────────────────────────────────────────────────────────
│  OpenAI-Compatible Endpoints (/v1/audio/speech)                  
│  Health & Status Monitoring (/health, /status)             
│  Comprehensive Startup Validation & Error Handling         
└─────────────────────────────────────────────────────────────
                              │
┌─────────────────────────────────────────────────────────────
│                   TTS Processing Pipeline                   
├─────────────────────────────────────────────────────────────
│  Text Processing → Segmentation → Audio Generation          
│  Normalization → Cleaning → Concurrent Processing          
└─────────────────────────────────────────────────────────────
                              │
┌─────────────────────────────────────────────────────────────
│                  Model & Performance Layer                  
├─────────────────────────────────────────────────────────────
│  Hardware Detection → Provider Selection → Benchmarking    
│  CoreML Acceleration → Memory Management → Statistics       
│  Production Patches → Safety Guards → Error Recovery       
└─────────────────────────────────────────────────────────────
```

### Key Components

#### 1. **Model Loading System** (`api/model/`)
- **Hardware Detection**: Automatic detection of Apple Silicon and Neural Engine
- **Provider Benchmarking**: Intelligent selection between CoreML and CPU execution
- **Resource Management**: Efficient model loading and memory optimization
- **Production Patches**: Safe, idempotent patches for kokoro-onnx compatibility
- **Fallback Strategies**: Graceful handling of hardware limitations

#### 2. **TTS Processing Pipeline** (`api/tts/`)
- **Text Normalization**: Date/time conversion and text preprocessing
- **Intelligent Segmentation**: Sentence-aware text chunking for optimal processing
- **Concurrent Processing**: Parallel audio generation for improved performance
- **Streaming Support**: Real-time audio streaming with configurable chunk sizes

#### 3. **Performance Monitoring** (`api/performance/`)
- **Real-Time Statistics**: Live performance metrics and system health monitoring
- **Benchmark Reports**: Comprehensive performance analysis and optimization recommendations
- **Memory Management**: Automatic cleanup and resource optimization
- **Production Metrics**: Detailed performance tracking for production environments

#### 4. **Startup Validation System**
- **Dependency Validation**: Comprehensive check of all required and optional dependencies
- **Model File Validation**: File presence, accessibility, and basic integrity checks
- **Environment Validation**: Hardware capabilities, ONNX providers, and configuration
- **Patch Status Validation**: Verification of applied patches and error reporting
- **Configuration Validation**: TTS parameter verification and optimization

#### 5. **Error Handling & Resilience**
- **Multi-Level Fallbacks**: Graceful degradation strategies for various failure modes
- **Warning Management**: Intelligent suppression of non-critical CoreML warnings
- **Resource Cleanup**: Automatic memory management and resource optimization
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Production Safety**: Idempotent patches with rollback capabilities

### Frontend Architecture (Raycast Extension)

The Raycast extension provides a native macOS interface for TTS functionality:

```
┌─────────────────────────────────────────────────────────────
│                   Raycast Extension                         
├─────────────────────────────────────────────────────────────
│  Text Input Interface → TTS Processor → Audio Playback     
│  Selection Interface → Voice Selection → Speed Control      
└─────────────────────────────────────────────────────────────
                              │
┌─────────────────────────────────────────────────────────────
│                    API Communication                        
├─────────────────────────────────────────────────────────────
│  HTTP Client → Request Management → Response Processing     
│  Error Handling → Retry Logic → Status Monitoring          
└─────────────────────────────────────────────────────────────
```

## ⚙️ Configuration

### Environment Variables

```bash
# Server Configuration
export HOST="0.0.0.0"
export PORT="8000"
export LOG_LEVEL="INFO"

# TTS Configuration (automatically calculated, override if needed)
export MAX_SEGMENT_LENGTH="200"
export SAMPLE_RATE="24000"
# CHUNK_SIZE_BYTES is calculated automatically (2400 bytes for 50ms chunks)

# Performance Optimization
export ONNX_PROVIDER="CoreMLExecutionProvider"  # or "CPUExecutionProvider"
export KOKORO_BENCHMARK_PROVIDERS="true"        # Enable provider benchmarking
export KOKORO_BENCHMARK_FREQUENCY="weekly"      # Benchmark frequency: daily/weekly/monthly/manually

# Development
export DEVELOPMENT_MODE="true"
export UVICORN_RELOAD="1"                       # Enable hot reload
export PYTHONUNBUFFERED="1"                     # Immediate output
```

### Voice Configuration

The system supports **60+ voices** across multiple languages and regions:

#### English Voices
- **American English** (`af_*`, `am_*`): 11 female, 10 male voices
  - High-quality options: `af_heart`, `af_bella`, `am_michael`, `am_fenrir`
- **British English** (`bf_*`, `bm_*`): 4 female, 4 male voices
  - Notable: `bf_emma`, `bm_fable`, `bm_george`

#### International Languages
- **Japanese** (`jf_*`, `jm_*`): 4 female, 1 male voice
- **Mandarin Chinese** (`zf_*`, `zm_*`): 4 female, 4 male voices  
- **Spanish** (`ef_*`, `em_*`): 1 female, 2 male voices
- **French** (`ff_*`): 1 female voice (`ff_siwis`)
- **Hindi** (`hf_*`, `hm_*`): 2 female, 2 male voices
- **Italian** (`if_*`, `im_*`): 1 female, 1 male voice
- **Brazilian Portuguese** (`pf_*`, `pm_*`): 1 female, 2 male voices

#### Voice Quality Ratings
Voices are rated from A (highest) to F (lowest) quality:
- **Grade A**: `af_heart`, `af_bella` (premium quality)
- **Grade B**: Many voices including `af_nicole`, `am_michael`, `bf_emma`
- **Grade C+**: Good quality options across all languages

Complete voice catalog with quality ratings and characteristics can be found in the [voices.ts](./raycast/src/voices.ts) file.

### Performance Tuning

#### Apple Silicon Optimization
```bash
# Enable CoreML acceleration
export ONNX_PROVIDER="CoreMLExecutionProvider"

# Optimize for Neural Engine
export COREML_COMPUTE_UNITS="CPU_AND_NE"

# Memory optimization
export MEMORY_CLEANUP_THRESHOLD="50"
```

#### CPU Optimization
```bash
# Use CPU provider for non-Apple Silicon
export ONNX_PROVIDER="CPUExecutionProvider"

# CPU thread optimization
export OMP_NUM_THREADS="4"
export ONNX_CPU_THREADS="4"
```

#### Server Startup Optimization

The server startup process has been optimized for faster initialization times. By default, the startup time is reduced from 43+ seconds to ~19 seconds through intelligent caching and development mode optimizations.

**Development Mode (Fastest Startup)**
```bash
# Enable development mode for fastest startup
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true
export KOKORO_FAST_STARTUP=true

# Start development server with optimizations
./start_development.sh
```

**Production Mode (Balanced Performance)**
```bash
# Production mode with benchmarking
export KOKORO_DEVELOPMENT_MODE=false
export KOKORO_SKIP_BENCHMARKING=false

# Start production server
./start_production.sh
```

**Environment Variables for Startup Control**
- `KOKORO_DEVELOPMENT_MODE`: Skip comprehensive benchmarking (default: false)
- `KOKORO_SKIP_BENCHMARKING`: Disable provider benchmarking entirely (default: false)
- `KOKORO_FAST_STARTUP`: Use extended cache duration (7 days vs 24 hours) (default: false)
- `KOKORO_BENCHMARK_PROVIDERS`: Control benchmark execution (default: true)
- `KOKORO_BENCHMARK_FREQUENCY`: Set benchmark cache duration - daily/weekly/monthly/manually (default: daily)

**Startup Progress Monitoring**
```bash
# Monitor startup progress in real-time
curl http://localhost:8000/startup-progress

# Check health during initialization
curl http://localhost:8000/health
```

**Cache Management**
The system uses intelligent caching to avoid re-running expensive operations:
- Provider recommendations are cached based on configured frequency (daily/weekly/monthly/manually)
- Hardware capabilities are cached during runtime
- Cache duration extends automatically in development mode for faster iteration
- Cache is automatically refreshed when used successfully

**Typical Startup Times**
- **Development Mode**: ~5-10 seconds (benchmarking disabled)
- **Production Mode (cached)**: ~15-20 seconds (using cached provider recommendations)
- **Production Mode (fresh)**: ~30-45 seconds (full benchmarking and optimization)

#### Benchmark Frequency Configuration

The system includes configurable benchmark frequency to balance performance optimization with startup speed. Since hardware capabilities don't change frequently, longer cache periods are safe and provide faster startup times.

**Interactive Configuration**
```bash
# Interactive setup with explanations and recommendations
python scripts/configure_benchmark_frequency.py

# Show current configuration
python scripts/configure_benchmark_frequency.py --show-current

# Set frequency non-interactively
python scripts/configure_benchmark_frequency.py --frequency weekly
```

**Frequency Options**
- **Daily** (24 hours): For development or frequently changing systems
- **Weekly** (7 days): ⭐ **Recommended** for most users - balances optimization and convenience
- **Monthly** (30 days): For stable production systems and battery-conscious users  
- **Manual**: Expert mode - only benchmark when explicitly requested

**Environment Variable**
```bash
# Set benchmark frequency (persisted in .env file)
export KOKORO_BENCHMARK_FREQUENCY=weekly

# Add to .env file for persistence
echo "KOKORO_BENCHMARK_FREQUENCY=weekly" >> .env
```

**Cache Management Tools**
```bash
# Show detailed cache status and expiration
python scripts/manage_benchmark_cache.py --status

# Clear cache to force re-benchmark (e.g., after OS updates)
python scripts/manage_benchmark_cache.py --clear

# Force benchmark regardless of cache status
python scripts/manage_benchmark_cache.py --force-benchmark

# Inspect detailed cache contents
python scripts/manage_benchmark_cache.py --inspect
```

**Benefits of Configurable Frequency**
- **Faster Startup**: Longer cache periods mean less frequent 20-30s benchmark delays
- **Battery Friendly**: Reduced power consumption from less frequent benchmarking
- **Hardware Stable**: Since hardware doesn't change often, longer caching is safe
- **User Control**: Choose the right balance for your use case

**Recommendations by Use Case**
- **Developers**: Daily or Weekly (quick iteration, occasional optimization)
- **Most Users**: Weekly (recommended - good balance of speed and optimization)
- **Production**: Monthly (stable systems, minimal startup delays)
- **Experts**: Manual (complete control over when benchmarking occurs)

## 📊 Performance Monitoring

### Benchmark Reports

The system automatically generates comprehensive benchmark reports:

```bash
# Run comprehensive performance benchmark
python run_benchmark.py --verbose

# View current benchmark results
cat benchmark_results.md

# Force regenerate benchmark
curl http://localhost:8000/status
```

### Real-Time Metrics

Monitor system performance in real-time:

```bash
# Get comprehensive system status
curl http://localhost:8000/status | jq '.'

# Get performance statistics
curl http://localhost:8000/status | jq '.performance'

# Monitor inference times
curl http://localhost:8000/status | jq '.performance.average_inference_time'

# Check provider usage
curl http://localhost:8000/status | jq '.performance.provider_used'

# View patch status
curl http://localhost:8000/status | jq '.patch_status'

# Check hardware capabilities
curl http://localhost:8000/status | jq '.hardware'
```

### Key Performance Indicators

- **Inference Time**: Average time per TTS generation
- **Provider Usage**: CoreML vs CPU execution distribution
- **Memory Usage**: Memory consumption and cleanup events
- **Phonemizer Fallbacks**: Text processing fallback rate
- **System Stability**: Error rates and warning counts
- **Patch Status**: Applied patches and any errors
- **Hardware Info**: System capabilities and configuration

## 🔧 Development

### Development Setup

1. **Enable Development Mode**:
   ```bash
   export DEVELOPMENT_MODE="true"
   ./start_development.sh
   ```

2. **Access API Documentation**:
   ```
   http://localhost:8000/docs
   ```

3. **Monitor Performance**:
   ```
   http://localhost:8000/status
   ```

### Testing

```bash
# Validate application startup
python test_application_startup.py --verbose

# Test benchmark features
python test_benchmark_features.py

# Run comprehensive performance benchmark
python run_benchmark.py --warmup-runs 5 --consistency-runs 5
 
```

### Debugging

#### Enable Debug Logging
```bash
export LOG_LEVEL="DEBUG"
./start_development.sh
```

#### Performance Profiling
```bash
# Monitor inference times
curl -s http://localhost:8000/status | jq '.performance.average_inference_time'

# Check memory usage
curl -s http://localhost:8000/status | jq '.performance.memory_cleanup_count'

# Analyze provider performance
curl -s http://localhost:8000/status | jq '.performance.coreml_usage_percent'

# Check patch status
curl -s http://localhost:8000/status | jq '.patch_status'
```

## 🔧 Diagnostic Tools

The system includes comprehensive diagnostic tools to help troubleshoot issues and optimize performance:

### Environment Checker
Check your Python environment, packages, and system compatibility:

```bash
python scripts/check_environment.py
```

**Features:**
- ✅ Virtual environment validation
- ✅ Package version checking
- ✅ ONNX Runtime provider validation
- ✅ System compatibility analysis
- ✅ Project structure verification
- ✅ Automatic recommendations

### CoreML Troubleshooting
Diagnose CoreML and hardware acceleration issues:

```bash
python scripts/troubleshoot_coreml.py
```

**Features:**
- 🔍 Apple Silicon capability analysis
- 🔍 CoreML provider functionality testing
- 🔍 Neural Engine availability check
- 🔍 Model file validation
- 🔍 Performance optimization suggestions
- 📊 Comprehensive diagnostic reports

### ORT Model Converter
Convert ONNX models to optimized ORT format:

```bash
# Convert model
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx

# Convert with specific output
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx -o optimized.ort

# Benchmark comparison
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx --benchmark
```

**Features:**
- 🚀 Automatic Apple Silicon optimization
- 🚀 Performance benchmarking
- 🚀 File size comparison
- 🚀 Validation and testing

### Quick Performance Test
Run a lightweight performance test:

```bash
python scripts/quick_benchmark.py
```

**Features:**
- ⚡ Fast initialization testing (~5 seconds)
- ⚡ Basic inference validation
- ⚡ Provider status checking
- ⚡ Quick health assessment

### Benchmark Frequency Configuration
Configure how often the system benchmarks hardware for optimal provider selection:

```bash
# Interactive configuration with explanations
python scripts/configure_benchmark_frequency.py

# Show current configuration
python scripts/configure_benchmark_frequency.py --show-current

# Set frequency non-interactively
python scripts/configure_benchmark_frequency.py --frequency weekly
```

**Features:**
- ⚙️ Interactive setup with detailed explanations
- ⚙️ Frequency options: daily/weekly/monthly/manual
- ⚙️ Automatic .env file management
- ⚙️ Hardware context and recommendations

### Benchmark Cache Management
Manage benchmark cache for performance optimization:

```bash
# Show detailed cache status and expiration
python scripts/manage_benchmark_cache.py --status

# Clear cache to force re-benchmark
python scripts/manage_benchmark_cache.py --clear

# Force benchmark regardless of cache status
python scripts/manage_benchmark_cache.py --force-benchmark

# Inspect detailed cache contents
python scripts/manage_benchmark_cache.py --inspect
```

**Features:**
- 📊 Cache status monitoring with expiration times
- 🧹 Manual cache clearing and forced benchmarking
- 🔍 Detailed cache inspection and analysis
- ⚡ Expert control over benchmark timing

### Cache Cleanup Utility
Manage cache files and prevent storage bloat:

```bash
# Check cache statistics
python scripts/cleanup_cache.py --stats

# Clean up cache files
python scripts/cleanup_cache.py

# Aggressive cleanup (smaller limits)
python scripts/cleanup_cache.py --aggressive

# API endpoints for cache management
curl http://localhost:8000/cache-status
curl -X POST http://localhost:8000/cache-cleanup
```

**Features:**
- 🧹 Intelligent cleanup policies (age, size, pattern-based)
- 📊 Real-time cache statistics and monitoring
- 🗂️ Preserves important ORT optimized models
- ⚡ Automatic cleanup during server startup
- 🔧 Configurable cleanup thresholds (500MB max, 10 temp dirs)
- 📈 Performance impact monitoring

### Full System Benchmark
Comprehensive performance analysis:

```bash
# Quick benchmark (recommended)
python run_benchmark.py --quick

# Full benchmark (detailed analysis)
python run_benchmark.py
```

**Features:**
- 📊 Provider performance comparison
- 📊 Detailed timing analysis
- 📊 Memory usage tracking
- 📊 Optimization recommendations

## 🛠️ Troubleshooting

### Common Issues and Solutions

#### 1. **Server Startup Takes Too Long**
The system performs comprehensive initialization including model loading and provider benchmarking. This is normal for first-time setup:

```bash
# Check initialization progress
tail -f logs/api_server.log

# Use quick benchmark for faster testing
python scripts/quick_benchmark.py
```

#### 2. **CoreML Provider Not Working**
```bash
# Run CoreML diagnostics
python scripts/troubleshoot_coreml.py

# Check system compatibility
python scripts/check_environment.py
```

#### 3. **ORT Optimization Issues**
```bash
# Manually convert to ORT
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx

# Disable ORT optimization
export KOKORO_ORT_OPTIMIZATION=false
./start_development.sh
```

#### 4. **Permission Issues**
```bash
# Check permissions
ls -la kokoro-v1.0.int8.onnx voices-v1.0.bin

# Recreate cache directory
rm -rf .cache && mkdir -p .cache/ort
```

#### 5. **Port Already in Use**
```bash
# Check what's using port 8000
lsof -i :8000

# Kill existing processes
pkill -f uvicorn

# Use different port
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

### Getting Help

1. **Run full diagnostics**:
   ```bash
   python scripts/check_environment.py
   python scripts/troubleshoot_coreml.py
   ```

2. **Check logs**:
   ```bash
   tail -f logs/api_server.log
   ```

3. **Test basic functionality**:
   ```bash
   python scripts/quick_benchmark.py
   ```

4. **Review system status**:
   ```bash
   curl http://localhost:8000/status
   ```

## 🚀 ORT Optimization

The system includes intelligent ORT (ONNX Runtime) optimization for enhanced Apple Silicon performance:

### Automatic ORT Optimization

**How it works:**
1. **Hardware Detection**: Automatically detects Apple Silicon and Neural Engine
2. **Smart Decision Making**: Determines if ORT optimization will improve performance
3. **On-Demand Conversion**: Creates optimized models automatically on first run
4. **Intelligent Caching**: Caches optimized models for faster subsequent startups

**Configuration:**
```bash
# Enable automatic ORT optimization (default on Apple Silicon)
export KOKORO_ORT_OPTIMIZATION=auto

# Force enable ORT optimization
export KOKORO_ORT_OPTIMIZATION=true

# Disable ORT optimization
export KOKORO_ORT_OPTIMIZATION=false

# Custom ORT cache directory
export KOKORO_ORT_CACHE_DIR=.cache/ort
```

### Benefits of ORT Optimization

#### **Performance Improvements:**
- 🚀 **3-5x faster inference** on Apple Silicon with Neural Engine
- 🚀 **2-3x faster inference** on Apple Silicon without Neural Engine
- 🚀 **Reduced memory usage** through optimized graph structure
- 🚀 **Faster startup times** after initial conversion

#### **Reliability Improvements:**
- 🛡️ **Fewer temporary file issues** - ORT models require less runtime compilation
- 🛡️ **Better CoreML compatibility** - optimized for Apple's ML frameworks
- 🛡️ **Reduced permission issues** - fewer system temp directory dependencies

#### **Developer Experience:**
- 🔧 **Automatic optimization** - no manual intervention required
- 🔧 **Transparent fallback** - graceful degradation if ORT fails
- 🔧 **Comprehensive logging** - detailed optimization information
- 🔧 **Pre-deployment tools** - manual conversion for CI/CD pipelines

### ORT Optimization Logic

The system uses intelligent device-based logic to determine when to use ORT optimization:

```python
# Apple Silicon with Neural Engine
if device.has_neural_engine:
    return "ORT_STRONGLY_RECOMMENDED"  # 3-5x performance boost

# Apple Silicon without Neural Engine  
elif device.is_apple_silicon:
    return "ORT_RECOMMENDED"          # 2-3x performance boost

# Other devices
else:
    return "ORT_OPTIONAL"             # Minimal benefit
```

### ORT File Structure

```
.cache/ort/
├── kokoro-v1.0.int8.ort              # Optimized model file
├── optimization_metadata.json        # Conversion metadata
└── performance_profile.json          # Performance benchmarks
```

### Manual ORT Optimization

For CI/CD pipelines or manual optimization:

```bash
# Convert specific model
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx \
  -o .cache/ort/kokoro-v1.0.int8.ort \
  --verbose

# Validate ORT model
python scripts/convert_to_ort.py \
  --validate .cache/ort/kokoro-v1.0.int8.ort

# Compare performance
python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx \
  --benchmark --compare-original
```

## 🚀 Production Deployment

### Production Setup

1. **Configure Environment**:
   ```bash
   export DEVELOPMENT_MODE="false"
   export LOG_LEVEL="WARNING"
   export ENABLE_PERFORMANCE_MONITORING="true"
   ```

2. **Validate Production Readiness**:
   ```bash
   # Run comprehensive validation
   python scripts/check_environment.py
   
   # Run performance benchmark (completes in ~30 seconds)
   python run_benchmark.py --quick
   
   # Run quick functionality test
   python scripts/quick_benchmark.py
   ```

3. **Start Production Server**:
   ```bash
   chmod +x start_production.sh
   ./start_production.sh
   ```

4. **Monitor Performance**:
   ```bash
   # Check system status
   curl http://localhost:8000/health
   
   # Monitor performance metrics
   curl http://localhost:8000/status
   ```

### Production Considerations

- **Memory Management**: Automatic cleanup prevents memory leaks
- **Error Handling**: Comprehensive fallback strategies ensure reliability
- **Performance Monitoring**: Real-time metrics for production optimization
- **Security**: Proper input validation and sanitization
- **Scalability**: Efficient resource usage for high-volume deployments
- **Startup Validation**: Comprehensive validation prevents runtime failures
- **Patch Safety**: Idempotent patches with rollback capabilities

## 📚 API Reference

### OpenAI-Compatible Endpoints

#### POST `/v1/audio/speech`

Generate speech from text input with optional streaming support.

**Request Body:**
```json
{
  "text": "Text to convert to speech (max 2000 characters)",
  "voice": "af_heart",
  "speed": 1.0,
  "lang": "en-us",
  "format": "wav",
  "stream": false
}
```

**Parameters:**
- `text` (required): Input text for synthesis (1-2000 characters)
- `voice` (optional): Voice ID from available voices (default: "af_heart")
- `speed` (optional): Speech speed multiplier 0.25-4.0 (default: 1.0)
- `lang` (optional): Language code (default: "en-us")
- `format` (optional): Audio format "wav" or "pcm" (default: "pcm")
- `stream` (optional): Enable streaming response (default: false)

**Response:**
- `200 OK`: Audio file (WAV or PCM binary data)
- `400 Bad Request`: Invalid input parameters
- `503 Service Unavailable`: Model not ready

#### GET `/health`

Health check endpoint.

**Response:**
```json
{
  "status": "online"
}
```

#### GET `/status`

Comprehensive system status and performance metrics.

**Response:**
```json
{
  "model_loaded": true,
  "onnx_providers": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
  "performance": {
    "total_inferences": 1234,
    "average_inference_time": 0.123,
    "provider_used": "CoreMLExecutionProvider",
    "coreml_usage_percent": 85.5,
    "phonemizer_fallback_rate": 0.1,
    "memory_cleanup_count": 5
  },
  "patch_status": {
    "applied": true,
    "application_time": 0.001,
    "patch_errors": [],
    "original_functions_stored": 3
  },
  "hardware": {
    "platform": "Darwin arm64",
    "is_apple_silicon": true,
    "has_neural_engine": true,
    "cpu_cores": 10,
    "memory_gb": 64.0
  }
}
```

## 🔒 Security

### Input Validation
- **Text Length Limits**: Configurable maximum text length (2000 characters)
- **Parameter Validation**: Type checking and range validation
- **Sanitization**: Input sanitization to prevent injection attacks

### Rate Limiting
- **Request Throttling**: Configurable rate limiting for API endpoints
- **Resource Protection**: Memory and CPU usage limits
- **Error Handling**: Graceful handling of rate limit violations

### Authentication
- **API Key Support**: Optional API key authentication
- **CORS Configuration**: Configurable CORS settings for web applications
- **SSL/TLS**: HTTPS support for production deployments

## 🤝 Contributing

1. **Fork the Repository**
2. **Create Feature Branch**: `git checkout -b feature/amazing-feature`
3. **Commit Changes**: `git commit -m 'Add amazing feature'`
4. **Push to Branch**: `git push origin feature/amazing-feature`
5. **Open Pull Request**

### Development Guidelines

- **Code Style**: Follow PEP 8 for Python, ESLint for TypeScript
- **Documentation**: Update documentation for new features
- **Testing**: Add tests for new functionality
- **Performance**: Consider performance impact of changes
- **Validation**: Ensure comprehensive validation for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Kokoro-ONNX**: Base TTS model and inference engine
- **FastAPI**: High-performance web framework
- **Raycast**: Extensible launcher platform
- **Apple**: CoreML optimization framework
- **ONNX Runtime**: Cross-platform inference optimization

## 📞 Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/darianrosebrook/kokoro-onnx-raycast-api/issues)
- **Documentation**: Comprehensive guides and API reference
- **Community**: Join discussions and share experiences

---

**Author**: @darianrosebrook  
**Version**: 2.1.0  
**Last Updated**: July 8, 2025


