#!/bin/bash
# Kokoro TTS Login Item Script
# This script starts Kokoro TTS when you log in
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

# Log file for login startup
LOGIN_LOG="$LOG_DIR/login-startup.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOGIN_LOG"
}

log "Starting Kokoro TTS from login item..."

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

# Set up environment variables
export KOKORO_AUTOSTART=true
export KOKORO_PRODUCTION=true
export KOKORO_LOGIN_ITEM=true

# Wait for system to be ready (user session established)
sleep 15

# Check if service is already running
if lsof -i:8000 >/dev/null 2>&1; then
    log "Kokoro TTS is already running on port 8000"
    exit 0
fi

# Start the production server in background
log "Starting Kokoro TTS production server..."
nohup ./start_production.sh >> "$LOGIN_LOG" 2>&1 &

# Get the PID
SERVER_PID=$!
log "Kokoro TTS started with PID: $SERVER_PID"

# Wait a moment and check if it's still running
sleep 5
if kill -0 $SERVER_PID 2>/dev/null; then
    log "Kokoro TTS is running successfully"
else
    log "ERROR: Kokoro TTS failed to start"
    exit 1
fi
