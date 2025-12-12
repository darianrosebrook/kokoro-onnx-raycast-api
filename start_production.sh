#!/bin/bash
# Description: Starts the production server using Gunicorn.
# This script is optimized for production deployments, providing robust
# process management and performance tuning. It automatically adjusts the
# number of workers based on the system architecture.

# --- Configuration ---
HOST=${HOST:-"127.0.0.1"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"info"}
WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}

# --- Worker Calculation ---
if [[ "$(uname -m)" == "arm64" ]]; then
    WORKERS=1
    echo "  Apple Silicon detected—running a single Gunicorn worker to ensure CoreML stability."
else
    # Default to the number of CPU cores if `nproc` is available
    if command -v nproc >/dev/null 2>&1; then
        WORKERS=$(nproc)
    else
        WORKERS=2 # Fallback for systems without nproc
    fi
    echo "  Automatically configuring $WORKERS Gunicorn workers based on CPU cores."
fi

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

# --- Production Environment Setup ---
# Enable production optimizations
export KOKORO_PRODUCTION=true

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
export ONNXRUNTIME_TEMP="${COREML_TEMP_DIR}"
export ONNXRUNTIME_CACHE_DIR="${COREML_TEMP_DIR}"

echo " Configured temp directories:"
echo "   TMPDIR: ${TMPDIR}"
echo "   COREML_TEMP_DIR: ${COREML_TEMP_DIR}"
echo "   ONNXRUNTIME_TEMP_DIR: ${ONNXRUNTIME_TEMP_DIR}"

# Misaki G2P configuration for production
export KOKORO_MISAKI_ENABLED="${KOKORO_MISAKI_ENABLED:-true}"
export KOKORO_MISAKI_FALLBACK="${KOKORO_MISAKI_FALLBACK:-true}"
export KOKORO_MISAKI_CACHE_SIZE="${KOKORO_MISAKI_CACHE_SIZE:-1000}"
export KOKORO_MISAKI_QUALITY_THRESHOLD="${KOKORO_MISAKI_QUALITY_THRESHOLD:-0.8}"

# Set production defaults if not already configured
export KOKORO_GRAPH_OPT_LEVEL=${KOKORO_GRAPH_OPT_LEVEL:-"BASIC"}
export KOKORO_MEMORY_ARENA_SIZE_MB=${KOKORO_MEMORY_ARENA_SIZE_MB:-"512"}
export KOKORO_DISABLE_MEM_PATTERN=${KOKORO_DISABLE_MEM_PATTERN:-"false"}

# Apple Silicon CoreML optimizations
if [[ "$(uname -m)" == "arm64" ]]; then
    export KOKORO_COREML_MODEL_FORMAT=${KOKORO_COREML_MODEL_FORMAT:-"MLProgram"}
    export KOKORO_COREML_COMPUTE_UNITS=${KOKORO_COREML_COMPUTE_UNITS:-"CPUOnly"}
    export KOKORO_COREML_SPECIALIZATION=${KOKORO_COREML_SPECIALIZATION:-"FastPrediction"}
    # Optimized memory arena for 64GB M1 Max
    export KOKORO_MEMORY_ARENA_SIZE_MB=${KOKORO_MEMORY_ARENA_SIZE_MB:-"3072"}
fi

# Performance profile for optimal chunk timing (50ms chunks)
export KOKORO_DEV_PERFORMANCE_PROFILE=${KOKORO_DEV_PERFORMANCE_PROFILE:-"stable"}

# Model optimization testing configuration (optional)
# Enable model optimization benchmark testing via API endpoint
export KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING="${KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING:-false}"
# Path to optimized model for comparison testing
export KOKORO_OPTIMIZED_MODEL_PATH="${KOKORO_OPTIMIZED_MODEL_PATH:-optimized_models/kokoro-v1.0.int8-graph-opt.onnx}"

echo "Production optimizations enabled:"
echo "   • ORJSON serialization: ✅"
echo "   • GZip compression: ✅"
echo "   • Security headers: ✅"
echo "   • Graph optimization: ${KOKORO_GRAPH_OPT_LEVEL}"
echo "   • Memory arena: ${KOKORO_MEMORY_ARENA_SIZE_MB}MB"
echo "   • Performance profile: ${KOKORO_DEV_PERFORMANCE_PROFILE} (50ms chunks)"
echo "   • Misaki G2P enabled: ${KOKORO_MISAKI_ENABLED}"
[[ "$(uname -m)" == "arm64" ]] && echo "   • CoreML optimization: ✅"
if [ "$KOKORO_ENABLE_MODEL_OPTIMIZATION_TESTING" = "true" ]; then
    echo "   • Model optimization testing: ✅ Enabled"
    echo "   • Optimized model path: ${KOKORO_OPTIMIZED_MODEL_PATH}"
else
    echo "   • Model optimization testing: ⚠️  Disabled"
fi

# --- Audio Daemon Configuration ---
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

# Function to kill processes on a port
kill_port_process() {
    local port=$1
    local service_name=$2
    
    if lsof -i:${port} >/dev/null 2>&1; then
        echo "Port ${port} is in use by ${service_name}. Attempting to kill the process..."
        kill -9 $(lsof -t -i:${port}) 2>/dev/null || true
        sleep 2 # Give time for the port to be released
    fi
}

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
    echo "   This daemon will stay running for the entire production session."
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

# Start persistent audio daemon first
start_persistent_audio_daemon

# --- Server Execution ---
echo "Starting production server on http://${HOST}:${PORT} with ${WORKERS} worker(s)..."

# Use exec to replace the shell process with the gunicorn process
exec gunicorn api.main:app \
    --workers $WORKERS \
    --worker-class "$WORKER_CLASS" \
    --bind "${HOST}:${PORT}" \
    --log-level "${LOG_LEVEL}" \
    --timeout 120 \
    --preload 