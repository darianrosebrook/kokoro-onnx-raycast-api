#!/bin/bash
# Kokoro TTS API - Production Server
# Simplified startup script using Gunicorn

set -e

# --- Configuration ---
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8080}
LOG_LEVEL=${LOG_LEVEL:-"warning"}
AUDIO_DAEMON_PORT=${AUDIO_DAEMON_PORT:-8081}
WORKERS=${WORKERS:-1}  # Single worker recommended for model consistency

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kokoro TTS API - Production Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# --- Pre-flight Checks ---
if [ ! -d ".venv" ]; then
    echo -e "${RED}ERROR: Virtual environment '.venv' not found.${NC}"
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "models/kokoro-v1.0.onnx" ]; then
    echo -e "${RED}ERROR: Model file not found at models/kokoro-v1.0.onnx${NC}"
    echo "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# --- Set environment variables ---
# Fix espeak-ng data path issue (dynamically detect from Python)
ESPEAK_DATA_PATH=$(python3 -c "import espeakng_loader; print(espeakng_loader.get_data_path())" 2>/dev/null || echo "")
if [ -n "$ESPEAK_DATA_PATH" ]; then
    export ESPEAK_DATA_PATH
fi
# Use optimized model if available
export KOKORO_MODEL_FILE="${KOKORO_MODEL_FILE:-kokoro-v1.0.int8-graph-opt.onnx}"

# --- Check for audio dependencies ---
check_audio_deps() {
    local missing=()
    command -v sox &>/dev/null || missing+=("sox")
    command -v ffplay &>/dev/null || missing+=("ffmpeg")
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${YELLOW}Missing audio tools: ${missing[*]}${NC}"
        if command -v brew &>/dev/null; then
            brew install "${missing[@]}" || true
        fi
    else
        echo -e "${GREEN}✓ Audio dependencies ready${NC}"
    fi
}
check_audio_deps

# --- Kill existing processes ---
kill_port() {
    local port=$1
    local max_attempts=5
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        local pids=$(lsof -ti :$port 2>/dev/null || true)
        
        if [ -z "$pids" ]; then
            # Port is free
            return 0
        fi
        
        if [ $attempt -eq 0 ]; then
            echo "Stopping process(es) on port $port..."
        fi
        
        # Kill all processes using this port
        echo "$pids" | xargs kill -9 2>/dev/null || true
        
        # Wait a bit for processes to die
        sleep 0.5
        
        # Check if port is still in use
        if ! lsof -i :$port &>/dev/null; then
            return 0
        fi
        
        attempt=$((attempt + 1))
    done
    
    # If we get here, port is still in use
    echo -e "${YELLOW}Warning: Port $port may still be in use${NC}"
    return 1
}

# Kill processes on both ports
kill_port $PORT
kill_port $AUDIO_DAEMON_PORT

# Also kill any existing gunicorn, uvicorn or audio-daemon processes
pkill -f "gunicorn.*api.main:app" 2>/dev/null || true
pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "audio-daemon.js" 2>/dev/null || true

# Wait a moment for processes to fully terminate
sleep 1

# --- Start Audio Daemon ---
mkdir -p logs
AUDIO_DAEMON_PATH="raycast/bin/audio-daemon.js"

start_audio_daemon() {
    if ! command -v node &>/dev/null; then
        echo -e "${YELLOW}Node.js not found - audio daemon disabled${NC}"
        return
    fi
    
    echo "Starting audio daemon on port ${AUDIO_DAEMON_PORT}..."
    node "$AUDIO_DAEMON_PATH" --port "$AUDIO_DAEMON_PORT" > logs/audio-daemon.log 2>&1 &
    echo $! > .audio-daemon.pid
    sleep 2
    
    if curl -s http://localhost:${AUDIO_DAEMON_PORT}/health &>/dev/null; then
        echo -e "${GREEN}✓ Audio daemon ready${NC}"
    fi
}

# --- Cleanup handler ---
cleanup() {
    echo ""
    echo "Shutting down..."
    
    # Kill audio daemon if PID file exists
    if [ -f .audio-daemon.pid ]; then
        local pid=$(cat .audio-daemon.pid)
        kill $pid 2>/dev/null || true
        rm -f .audio-daemon.pid
    fi
    
    # Kill any remaining processes on our ports
    kill_port $PORT 2>/dev/null || true
    kill_port $AUDIO_DAEMON_PORT 2>/dev/null || true
    
    # Kill any remaining gunicorn, uvicorn or audio-daemon processes
    pkill -f "gunicorn.*api.main:app" 2>/dev/null || true
    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    pkill -f "audio-daemon.js" 2>/dev/null || true
    
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# --- Start services ---
start_audio_daemon

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Starting Production Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configuration:"
echo "  • Host: ${HOST}:${PORT}"
echo "  • Workers: ${WORKERS}"
echo "  • Log Level: ${LOG_LEVEL}"
echo ""
echo "Endpoints:"
echo "  • Health:  http://${HOST}:${PORT}/health"
echo "  • TTS:     http://${HOST}:${PORT}/v1/audio/speech"
echo ""

# Check if gunicorn is available
if command -v gunicorn &>/dev/null; then
    exec gunicorn api.main:app \
        --workers $WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "${HOST}:${PORT}" \
        --log-level "${LOG_LEVEL}" \
        --timeout 120 \
        --preload
else
    echo -e "${YELLOW}Gunicorn not found, falling back to uvicorn${NC}"
    exec uvicorn api.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}"
fi
