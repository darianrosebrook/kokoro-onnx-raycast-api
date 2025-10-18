#!/bin/bash
# Kokoro TTS Auto-Start Wrapper Script
# This script ensures proper environment setup before starting the production server
# Author: @darianrosebrook

# Set script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Change to project directory
cd "$PROJECT_ROOT" || {
    echo "ERROR: Cannot change to project directory: $PROJECT_ROOT"
    exit 1
}

# Set up logging
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Log file for auto-start
AUTOSTART_LOG="$LOG_DIR/autostart.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$AUTOSTART_LOG"
}

log "Starting Kokoro TTS auto-start process..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    log "ERROR: Virtual environment '.venv' not found in $PROJECT_ROOT"
    log "Please run the setup script first: ./setup.sh"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate || {
    log "ERROR: Failed to activate virtual environment"
    exit 1
}

log "Virtual environment activated successfully"

# Set up environment variables for auto-start
export KOKORO_AUTOSTART=true
export KOKORO_PRODUCTION=true

# Ensure proper PATH for system startup
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

# Set up temp directories (same as production script)
CACHE_DIR="$(pwd)/.cache"
COREML_TEMP_DIR="${CACHE_DIR}/coreml_temp"
ORT_TEMP_DIR="${CACHE_DIR}/ort"

mkdir -p "${COREML_TEMP_DIR}"
mkdir -p "${ORT_TEMP_DIR}"

chmod 755 "${COREML_TEMP_DIR}"
chmod 755 "${ORT_TEMP_DIR}"

export TMPDIR="${COREML_TEMP_DIR}"
export TMP="${COREML_TEMP_DIR}"
export TEMP="${COREML_TEMP_DIR}"
export COREML_TEMP_DIR="${COREML_TEMP_DIR}"
export ONNXRUNTIME_TEMP_DIR="${COREML_TEMP_DIR}"
export ONNXRUNTIME_TEMP="${COREML_TEMP_DIR}"
export ONNXRUNTIME_CACHE_DIR="${COREML_TEMP_DIR}"

log "Environment configured for auto-start"

# Wait a bit for system to fully boot
sleep 10

# Check if ports are available
PORT=${PORT:-8000}
AUDIO_DAEMON_PORT=${AUDIO_DAEMON_PORT:-8081}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -i:${port} >/dev/null 2>&1; then
        return 1  # Port is in use
    fi
    return 0  # Port is free
}

# Wait for ports to be available (in case of system startup conflicts)
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if check_port $PORT && check_port $AUDIO_DAEMON_PORT; then
        log "Ports $PORT and $AUDIO_DAEMON_PORT are available"
        break
    fi
    
    log "Waiting for ports to be available... (attempt $((WAIT_COUNT + 1))/$MAX_WAIT)"
    sleep 5
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
    log "WARNING: Ports may still be in use, proceeding anyway..."
fi

# Start the production server
log "Starting Kokoro TTS production server..."
exec ./start_production.sh >> "$AUTOSTART_LOG" 2>&1
