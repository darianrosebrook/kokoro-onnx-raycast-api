#!/bin/bash
# Kokoro TTS API - Development Server
# Simplified startup script for the minimal API
#
# This script automatically detects Cursor/VS Code and avoids killing processes
# that might interfere with the editor. Safe by default!

set -e

# Auto-detect if running in Cursor/VS Code and disable aggressive operations
# Safe by default - only enable aggressive operations if explicitly requested
IN_CURSOR=false
if [ -n "$CURSOR_AGENT" ] || [ -n "$VSCODE_PID" ] || [ -n "$VSCODE_INJECTION" ]; then
    IN_CURSOR=true
elif ps -p $PPID -o command= 2>/dev/null | grep -qE "(Cursor|Code)"; then
    IN_CURSOR=true
fi

# Safe by default - no process killing unless FORCE_KILL is explicitly set
# In Cursor, also disable Python hooks and reload by default
if [ "$IN_CURSOR" = "true" ]; then
    # Running in Cursor/VS Code - use safe defaults
    FORCE_KILL=${FORCE_KILL:-0}
    SKIP_PYTHON_HOOKS=${SKIP_PYTHON_HOOKS:-1}
    DISABLE_RELOAD=${DISABLE_RELOAD:-1}
    echo -e "${YELLOW}Detected Cursor/VS Code - using safe defaults${NC}"
else
    # Not in Cursor - still safe by default (no killing) but allow reload
    FORCE_KILL=${FORCE_KILL:-0}
    SKIP_PYTHON_HOOKS=${SKIP_PYTHON_HOOKS:-0}
    DISABLE_RELOAD=${DISABLE_RELOAD:-0}
fi

# --- Configuration ---
HOST=${HOST:-"127.0.0.1"}
PORT=${PORT:-8080}
LOG_LEVEL=${LOG_LEVEL:-"info"}
AUDIO_DAEMON_PORT=${AUDIO_DAEMON_PORT:-8081}

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kokoro TTS API - Development Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# --- Pre-flight Checks ---
if [ ! -d ".venv" ]; then
    echo -e "${RED}ERROR: Virtual environment '.venv' not found.${NC}"
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check for model files
if [ ! -f "models/kokoro-v1.0.onnx" ]; then
    echo -e "${RED}ERROR: Model file not found at models/kokoro-v1.0.onnx${NC}"
    echo "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases"
    exit 1
fi

# Activate virtual environment
# Suppress Python extension hooks during activation
export VIRTUAL_ENV_DISABLE_PROMPT=1
# Temporarily disable Python extension detection
export PYTHON_EXTENSION_DISABLED=1
source .venv/bin/activate
unset PYTHON_EXTENSION_DISABLED

# --- Set environment variables ---
# Disable Python extension hooks to prevent extension host crashes
export PYTHONUNBUFFERED=1
export CURSOR_AGENT_MODE=1
export VSCODE_PID=""  # Prevent VS Code/Cursor from hooking into this process
export VSCODE_INJECTION=0  # Disable extension injection

# Fix espeak-ng data path issue (dynamically detect from Python)
# Use a cached value if available to avoid triggering Python extension hooks
if [ "${SKIP_PYTHON_HOOKS:-0}" = "1" ]; then
    # Skip Python execution entirely if requested
    ESPEAK_DATA_PATH=""
    echo -e "${YELLOW}Note: Skipping Python hooks to prevent extension host issues${NC}"
elif [ -f ".espeak_path_cache" ]; then
    ESPEAK_DATA_PATH=$(cat .espeak_path_cache 2>/dev/null || echo "")
else
    # Only run Python command if cache doesn't exist
    # Run in a subshell with minimal environment to reduce hook triggers
    ESPEAK_DATA_PATH=$(env -i PATH="$PATH" HOME="$HOME" python3 -c "import espeakng_loader; print(espeakng_loader.get_data_path())" 2>/dev/null || echo "")
    # Cache the result
    [ -n "$ESPEAK_DATA_PATH" ] && echo "$ESPEAK_DATA_PATH" > .espeak_path_cache 2>/dev/null || true
fi
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
            echo "Installing with Homebrew..."
            brew install "${missing[@]}" || true
        else
            echo "Install with: brew install ${missing[*]}"
        fi
    fi
}
check_audio_deps

# --- Kill existing processes ---
# Skip killing by default (safe mode) unless FORCE_KILL is explicitly set
# This prevents killing processes that Cursor or other tools might be using
if [ "${FORCE_KILL:-0}" = "1" ]; then
    kill_port() {
        local port=$1
        local max_attempts=3
        local attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            local pids=$(lsof -ti :$port 2>/dev/null || true)
            
            if [ -z "$pids" ]; then
                # Port is free
                return 0
            fi
            
            if [ $attempt -eq 0 ]; then
                echo "Checking port $port..."
            fi
            
            # Only kill processes we're 100% sure are ours
            # Check the full command line to be absolutely certain
            local our_pids=""
            for pid in $pids; do
                local cmd=$(ps -p $pid -o command= 2>/dev/null || echo "")
                # Very specific patterns - only our exact processes
                if [[ "$cmd" == *"uvicorn api.main:app"* ]] || \
                   [[ "$cmd" == *"raycast/bin/audio-daemon.js"* ]] || \
                   [[ "$cmd" == *"/kokoro-onnx"*"uvicorn"* ]]; then
                    our_pids="$our_pids $pid"
                fi
            done
            
            if [ -n "$our_pids" ]; then
                if [ $attempt -eq 0 ]; then
                    echo "Stopping our process(es) on port $port..."
                fi
                # Try graceful shutdown first
                for pid in $our_pids; do
                    kill -TERM $pid 2>/dev/null || true
                done
                sleep 0.5
                # Only force kill if still running
                for pid in $our_pids; do
                    if kill -0 $pid 2>/dev/null; then
                        kill -9 $pid 2>/dev/null || true
                    fi
                done
            else
                # Port is in use but not by our processes - warn and skip
                echo -e "${YELLOW}Port $port is in use by another process. Skipping kill (safe mode).${NC}"
                echo -e "${YELLOW}To force kill, set FORCE_KILL=1 or manually free the port.${NC}"
                return 1
            fi
            
            # Wait a bit for processes to die
            sleep 0.3
            
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
    
    # Kill processes on both ports (only if they're ours)
    kill_port $PORT || true
    kill_port $AUDIO_DAEMON_PORT || true
else
    echo -e "${YELLOW}Note: Safe mode enabled - skipping process kill${NC}"
    echo -e "${YELLOW}If you need to kill existing processes, set FORCE_KILL=1${NC}"
fi

# Only kill by pattern if FORCE_KILL is set and ports are still in use
if [ "${FORCE_KILL:-0}" = "1" ]; then
    # Check if ports are still in use after kill_port attempts
    if lsof -ti :$PORT > /dev/null 2>&1; then
        # Port still in use - try one more time with pkill (very specific pattern)
        pkill -f "uvicorn api.main:app --host" 2>/dev/null || true
        sleep 0.2
    fi
    if lsof -ti :$AUDIO_DAEMON_PORT > /dev/null 2>&1; then
        # Audio daemon port still in use
        pkill -f "raycast/bin/audio-daemon.js --port" 2>/dev/null || true
        sleep 0.2
    fi
fi

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
    else
        echo -e "${YELLOW}Audio daemon starting...${NC}"
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
    
    # Kill any remaining uvicorn or audio-daemon processes
    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    pkill -f "audio-daemon.js" 2>/dev/null || true
    
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# --- Start services ---
# Check audio daemon port and find alternative if needed
if lsof -ti :$AUDIO_DAEMON_PORT > /dev/null 2>&1 && [ "${AUTO_FIND_PORT:-1}" != "0" ]; then
    echo -e "${YELLOW}Audio daemon port $AUDIO_DAEMON_PORT is in use, finding alternative...${NC}"
    for alt_port in 8082 8083 8084 8085 8086 8087 8088; do
        if ! lsof -ti :$alt_port > /dev/null 2>&1 && [ "$alt_port" != "$PORT" ]; then
            AUDIO_DAEMON_PORT=$alt_port
            echo -e "${GREEN}Using audio daemon port: $AUDIO_DAEMON_PORT${NC}"
            break
        fi
    done
fi

start_audio_daemon

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Starting TTS API on http://${HOST}:${PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Endpoints:"
echo "  • Health:  http://${HOST}:${PORT}/health"
echo "  • Voices:  http://${HOST}:${PORT}/voices"
echo "  • TTS:     http://${HOST}:${PORT}/v1/audio/speech"
echo "  • Docs:    http://${HOST}:${PORT}/docs"
echo ""
echo "Audio Daemon: ws://localhost:${AUDIO_DAEMON_PORT}"
echo ""

# Check if port is still in use before starting
if lsof -ti :$PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}Port $PORT is in use${NC}"
    
    # Show what's using the port
    echo "Process using port $PORT:"
    lsof -i :$PORT 2>/dev/null | tail -n +2 || echo "  (Unable to determine)"
    echo ""
    
    # Try to find an available port automatically
    if [ "${AUTO_FIND_PORT:-1}" != "0" ]; then
        echo "Attempting to find an available port..."
        for alt_port in 8082 8083 8084 8085 8086; do
            if ! lsof -ti :$alt_port > /dev/null 2>&1; then
                echo -e "${GREEN}Found available port: $alt_port${NC}"
                PORT=$alt_port
                echo "Using port $PORT instead"
                break
            fi
        done
        
        # If we couldn't find an alternative, show options
        if lsof -ti :$PORT > /dev/null 2>&1; then
            echo -e "${RED}Could not find an available port${NC}"
            echo ""
            echo "Options:"
            echo "  1. Free the port manually:"
            echo "     lsof -ti :$PORT | xargs kill"
            echo ""
            echo "  2. Use a specific port:"
            echo "     PORT=8082 ./start_development.sh"
            echo ""
            echo "  3. Force kill (not recommended in Cursor):"
            echo "     FORCE_KILL=1 ./start_development.sh"
            echo ""
            echo "  4. Disable auto port finding:"
            echo "     AUTO_FIND_PORT=0 ./start_development.sh"
            exit 1
        fi
    else
        echo "Auto port finding is disabled."
        echo "To free the port, run:"
        echo "  lsof -ti :$PORT | xargs kill"
        echo "Or use a different port:"
        echo "  PORT=8082 ./start_development.sh"
        exit 1
    fi
fi

# Start with hot-reload in development
# Note: --reload uses file watching which may conflict with Cursor extensions
# If you experience extension host crashes, remove --reload or use --reload-dir to limit watched directories
if [ "${DISABLE_RELOAD:-0}" = "1" ]; then
    echo -e "${YELLOW}Note: Hot reload disabled (safe mode)${NC}"
    uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}"
else
    uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" --reload --reload-dir api --reload-dir models
fi
