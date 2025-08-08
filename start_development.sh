#!/bin/bash
# Description: Starts the development server with Uvicorn and hot-reloading.
# This script ensures the application runs with optimal settings for a development environment.

# --- Configuration ---
HOST=${HOST:-"127.0.0.1"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"info"}
# Automatically enable reload in development, unless explicitly disabled.
UVICORN_RELOAD=${UVICORN_RELOAD:-"1"}
# Set a flag to indicate development mode for the application logic
export KOKORO_DEVELOPMENT_MODE="true"

# Misaki G2P configuration for development
export KOKORO_MISAKI_ENABLED="${KOKORO_MISAKI_ENABLED:-true}"
export KOKORO_MISAKI_FALLBACK="${KOKORO_MISAKI_FALLBACK:-true}"
export KOKORO_MISAKI_CACHE_SIZE="${KOKORO_MISAKI_CACHE_SIZE:-1000}"
export KOKORO_MISAKI_QUALITY_THRESHOLD="${KOKORO_MISAKI_QUALITY_THRESHOLD:-0.8}"

# --- Pre-flight Checks ---
# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment '.venv' not found."
    echo "Please run the setup script first: ./setup.sh"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate



# Check for ORT model and inform user about first-time conversion
if [[ "$(uname -m)" == "arm64" ]] && [ ! -f ".cache/ort/kokoro-v1.0.int8.ort" ]; then
    echo "⚙️  First-time ORT conversion may be triggered on startup..."
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
        echo "⚠️  Audio daemon disabled (Node.js not available)"
        return
    fi

    echo "🎵 Starting Persistent Audio Daemon on port ${AUDIO_DAEMON_PORT}..."
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
            echo "⚠️  Health endpoint not responding yet (may take a moment)"
        fi
    else
        echo "❌ Audio daemon failed to start"
        echo "   Check logs/audio-daemon.log for details"
    fi
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    
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
echo "ℹ️  Development mode features:"
echo "   • API documentation: http://${HOST}:${PORT}/docs"
echo "   • Standard JSON serialization (not ORJSON)"
echo "   • No security headers or compression"
echo "   • Fast startup (reduced benchmarking)"
echo "   • Misaki G2P with fallback enabled: ${KOKORO_MISAKI_ENABLED}"
if [ "$AUDIO_DAEMON_DISABLED" != "true" ]; then
    echo "   • Persistent audio daemon: http://${HOST}:${AUDIO_DAEMON_PORT}/health"
    echo "   • WebSocket endpoint: ws://${HOST}:${AUDIO_DAEMON_PORT}"
fi
echo ""
echo "💡 For production optimizations, use: ./start_production.sh"

# Start persistent audio daemon first
start_persistent_audio_daemon

# Start TTS API server
echo "🚀 Starting TTS API server on http://${HOST}:${PORT}..."

# Use uvicorn directly without exec so we can handle both processes
uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" $([ "$UVICORN_RELOAD" = "1" ] && echo "--reload") &
TTS_PID=$!

# Wait for TTS server and monitor
wait $TTS_PID 