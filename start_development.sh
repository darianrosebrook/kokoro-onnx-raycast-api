#!/bin/bash
# Description: Starts the development server with Uvicorn and hot-reloading.
# This script ensures the application runs with optimal settings for a development environment.

# --- Cleanup Check ---
# Check if temp files need cleanup (runs weekly)
CLEANUP_MARKER=".last_cleanup_check"
if [[ ! -f "$CLEANUP_MARKER" ]] || [[ $(find "$CLEANUP_MARKER" -mtime +7 2>/dev/null) ]]; then
    echo " Checking for old temporary files..."
    if python3 scripts/cleanup_temp_files.py --dry-run --force 2>/dev/null | grep -q "Would remove"; then
        echo " Hint: Run 'python3 scripts/cleanup_temp_files.py' to clean up old temp files"
    fi
    touch "$CLEANUP_MARKER"
fi

# --- Configuration ---
HOST=${HOST:-"127.0.0.1"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"info"}
# Automatically enable reload in development, unless explicitly disabled.
# DISABLED by default to reduce memory usage from multiprocessing
UVICORN_RELOAD=${UVICORN_RELOAD:-"0"}
# Set a flag to indicate development mode for the application logic
export KOKORO_DEVELOPMENT_MODE="true"

# Set development performance profile
# Options: minimal, stable, optimized, benchmark
# - minimal: CPU-only, fastest startup, minimal memory usage
# - stable: CoreML EP with conservative settings, good for debugging (default)
# - optimized: Full optimization testing, may use more memory
# - benchmark: Enable all optimizations and benchmarking for performance testing
export KOKORO_DEV_PERFORMANCE_PROFILE="${KOKORO_DEV_PERFORMANCE_PROFILE:-stable}"

# Legacy environment variables (now controlled by profile)
# export KOKORO_DISABLE_DUAL_SESSIONS="true"  # Controlled by profile
# export KOKORO_FORCE_CPU_PROVIDER="true"     # Controlled by profile

# --- Temp Directory Configuration ---
# Set up local temp directories to avoid permission issues on work-provisioned machines
# This must be done before any Python processes start to prevent ONNX Runtime from using system temp
CACHE_DIR="$(pwd)/.cache"
COREML_TEMP_DIR="${CACHE_DIR}/coreml_temp"
ORT_TEMP_DIR="${CACHE_DIR}/ort"

# Create directories if they don't exist
mkdir -p "${COREML_TEMP_DIR}"
mkdir -p "${ORT_TEMP_DIR}"

# Set proper permissions
chmod 755 "${COREML_TEMP_DIR}"
chmod 755 "${ORT_TEMP_DIR}"

# Export environment variables for all child processes
export TMPDIR="${COREML_TEMP_DIR}"
export TMP="${COREML_TEMP_DIR}"
export TEMP="${COREML_TEMP_DIR}"
export COREML_TEMP_DIR="${COREML_TEMP_DIR}"
export ONNXRUNTIME_TEMP_DIR="${COREML_TEMP_DIR}"

# Additional ONNX Runtime temp directory overrides
export ONNXRUNTIME_TEMP="${COREML_TEMP_DIR}"
export ONNXRUNTIME_CACHE_DIR="${COREML_TEMP_DIR}"
export COREML_CACHE_DIR="${COREML_TEMP_DIR}"
export ML_TEMP_DIR="${COREML_TEMP_DIR}"

# Set Python tempfile module environment variables
export PYTHONTEMPDIR="${COREML_TEMP_DIR}"
export PYTHON_TEMP="${COREML_TEMP_DIR}"

echo " Configured temp directories:"
echo "   TMPDIR: ${TMPDIR}"
echo "   COREML_TEMP_DIR: ${COREML_TEMP_DIR}"
echo "   ONNXRUNTIME_TEMP_DIR: ${ONNXRUNTIME_TEMP_DIR}"

# Verify environment variables are set
if [ "$TMPDIR" != "$COREML_TEMP_DIR" ]; then
    echo " ERROR: TMPDIR not set correctly!"
    echo "   Expected: $COREML_TEMP_DIR"
    echo "   Actual: $TMPDIR"
    exit 1
fi

echo "✅ Environment variables verified successfully"
echo ""

# Development mode configuration
export ENVIRONMENT="development"
export KOKORO_DEV_MODE="true"
export DEBUG="true"

# Misaki G2P configuration for development
export KOKORO_MISAKI_ENABLED="${KOKORO_MISAKI_ENABLED:-true}"
export KOKORO_MISAKI_FALLBACK="${KOKORO_MISAKI_FALLBACK:-true}"
export KOKORO_MISAKI_CACHE_SIZE="${KOKORO_MISAKI_CACHE_SIZE:-1000}"
export KOKORO_MISAKI_QUALITY_THRESHOLD="${KOKORO_MISAKI_QUALITY_THRESHOLD:-0.8}"

# Provider configuration for development (use ANE by default for low TTFA)
export KOKORO_COREML_COMPUTE_UNITS="${KOKORO_COREML_COMPUTE_UNITS:-CPUAndNeuralEngine}"

# Model optimization testing configuration (optional)
# Enable model optimization benchmark testing via API endpoint
export KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING="${KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING:-false}"
# Path to optimized model for comparison testing
export KOKORO_OPTIMIZED_MODEL_PATH="${KOKORO_OPTIMIZED_MODEL_PATH:-optimized_models/kokoro-v1.0.int8-graph-opt.onnx}"

# --- Pre-flight Checks ---
# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment '.venv' not found."
    echo "Please run the setup script first: ./setup.sh"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# --- Audio Dependencies Check ---
check_audio_dependencies() {
    echo " Checking audio dependencies..."
    
    local missing_deps=()
    
    # Check for sox
    if ! command -v sox &> /dev/null; then
        missing_deps+=("sox")
    fi
    
    # Check for ffplay (from ffmpeg)
    if ! command -v ffplay &> /dev/null; then
        missing_deps+=("ffmpeg")
    fi
    
    # afplay is built into macOS, but check anyway
    if ! command -v afplay &> /dev/null; then
        echo "  Warning: afplay not found (unusual for macOS)"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo "  Missing audio dependencies: ${missing_deps[*]}"
        
        # Check if we have brew available
        if command -v brew &> /dev/null; then
            echo " Installing missing audio dependencies with Homebrew..."
            for dep in "${missing_deps[@]}"; do
                echo "   Installing $dep..."
                brew install "$dep" || echo " Failed to install $dep"
            done
            echo "✅ Audio dependency installation complete"
        else
            echo " Homebrew not found. Please install the following manually:"
            echo "   brew install ${missing_deps[*]}"
            echo "   Or install Homebrew first: https://brew.sh"
            echo ""
            echo "The system will fall back to afplay if available, but optimal performance requires sox or ffplay."
        fi
    else
        echo "✅ All audio dependencies available"
    fi
    echo ""
}

# Run audio dependency check
check_audio_dependencies

# Check for ORT model and inform user about first-time conversion
if [[ "$(uname -m)" == "arm64" ]] && [ ! -f ".cache/ort/kokoro-v1.0.int8.ort" ]; then
    echo "  First-time ORT conversion may be triggered on startup..."
    echo "This can take ~15s. Subsequent startups will be faster."
fi

# Function to kill process on port
kill_port_process() {
    local port=$1
    local service_name=$2
    if lsof -i :${port} > /dev/null 2>&1; then
        echo "Port ${port} is in use by ${service_name}. Attempting to kill the process..."
        kill -9 $(lsof -t -i:${port}) 2>/dev/null || true
        sleep 2 # Give time for the port to be released
    fi
}

# Audio daemon configuration (for persistent daemon)
AUDIO_DAEMON_PORT=${AUDIO_DAEMON_PORT:-8081}
AUDIO_DAEMON_PATH="raycast/bin/audio-daemon.js"

# Check if Node.js is available for the audio daemon
if ! command -v node &> /dev/null; then
    echo "WARNING: Node.js not found. Audio daemon will not be available."
    echo "Install Node.js to enable audio streaming capabilities."
    AUDIO_DAEMON_DISABLED=true
else
    AUDIO_DAEMON_DISABLED=false
fi

# Check and kill existing processes on both ports
kill_port_process ${PORT} "TTS API"
if [ "$AUDIO_DAEMON_DISABLED" != "true" ]; then
    kill_port_process ${AUDIO_DAEMON_PORT} "Audio Daemon"
fi

# Function to start persistent audio daemon
start_persistent_audio_daemon() {
    if [ "$AUDIO_DAEMON_DISABLED" = "true" ]; then
        echo "  Audio daemon disabled (Node.js not available)"
        return
    fi

    echo " Starting Persistent Audio Daemon on port ${AUDIO_DAEMON_PORT}..."
    echo "   This daemon will stay running for the entire development session."
    echo "   Raycast extension will connect to this daemon instead of spawning its own."
    
    # Start audio daemon in background
    node "$AUDIO_DAEMON_PATH" --port "$AUDIO_DAEMON_PORT" > logs/audio-daemon.log 2>&1 &
    AUDIO_DAEMON_PID=$!
    
    # Wait for startup
    sleep 3
    
    # Check if daemon started successfully
    if kill -0 $AUDIO_DAEMON_PID 2>/dev/null; then
        echo "✅ Audio daemon started successfully (PID: $AUDIO_DAEMON_PID)"
        echo "   Health endpoint: http://localhost:${AUDIO_DAEMON_PORT}/health"
        echo "   WebSocket endpoint: ws://localhost:${AUDIO_DAEMON_PORT}"
        
        # Store PID for cleanup
        echo $AUDIO_DAEMON_PID > .audio-daemon.pid
        
        # Test health endpoint
        if curl -s http://localhost:${AUDIO_DAEMON_PORT}/health >/dev/null 2>&1; then
            echo "✅ Health endpoint responding"
        else
            echo "  Health endpoint not responding yet (may take a moment)"
        fi
    else
        echo " Audio daemon failed to start"
        echo "   Check logs/audio-daemon.log for details"
    fi
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo " Shutting down services..."
    
    # Kill TTS API server
    if [ ! -z "$TTS_PID" ]; then
        echo "   Stopping TTS API server..."
        kill $TTS_PID 2>/dev/null || true
    fi
    
    # Kill audio daemon
    if [ -f ".audio-daemon.pid" ]; then
        DAEMON_PID=$(cat .audio-daemon.pid)
        echo "   Stopping Audio Daemon..."
        kill $DAEMON_PID 2>/dev/null || true
        rm -f .audio-daemon.pid
    fi
    
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGINT SIGTERM

# Create logs directory if it doesn't exist
mkdir -p logs
echo "Starting development server on http://${HOST}:${PORT}"
echo " LOG_LEVEL is set to ${LOG_LEVEL}"
[ "$UVICORN_RELOAD" = "1" ] && echo " Hot-reloading is enabled."
echo ""
echo "ℹ  Development mode features:"
echo "   • API documentation: http://${HOST}:${PORT}/docs"
echo "   • Standard JSON serialization (not ORJSON)"
echo "   • No security headers or compression"
echo "   • Performance profile: ${KOKORO_DEV_PERFORMANCE_PROFILE}"
echo "   • Misaki G2P with fallback enabled: ${KOKORO_MISAKI_ENABLED}"
if [ "$AUDIO_DAEMON_DISABLED" != "true" ]; then
    echo "   • Persistent audio daemon: http://${HOST}:${AUDIO_DAEMON_PORT}/health"
    echo "   • WebSocket endpoint: ws://${HOST}:${AUDIO_DAEMON_PORT}"
fi
echo ""
echo " Performance profiles available:"
echo "   • minimal: CPU-only, fastest startup (KOKORO_DEV_PERFORMANCE_PROFILE=minimal)"
echo "   • stable: CoreML + conservative settings (current: default)"
echo "   • optimized: Full optimization testing"
echo "   • benchmark: All optimizations + benchmarking"
echo ""
if [ "$KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING" = "true" ]; then
    echo " Model optimization testing: ✅ Enabled"
    echo "   Optimized model path: ${KOKORO_OPTIMIZED_MODEL_PATH}"
else
    echo " Model optimization testing: ⚠️  Disabled"
    echo "   Enable with: export KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING=true"
fi
echo ""
echo " For production optimizations, use: ./start_production.sh"

# Start persistent audio daemon first
start_persistent_audio_daemon

# Start TTS API server
echo " Starting TTS API server on http://${HOST}:${PORT}..."

# Use uvicorn directly without exec so we can handle both processes (reload is disabled by default) due to memory usage
if [ "$UVICORN_RELOAD" = "1" ]; then
    uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}"  &
else
    uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" &
fi
TTS_PID=$!

# Wait for TTS server and monitor
wait $TTS_PID 