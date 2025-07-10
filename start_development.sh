#!/bin/bash
# Description: Starts the development server with Uvicorn and hot-reloading.
# This script ensures the application runs with optimal settings for a development environment.

# --- Configuration ---
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
# Automatically enable reload in development, unless explicitly disabled.
UVICORN_RELOAD=${UVICORN_RELOAD:-"1"}
# Set a flag to indicate development mode for the application logic
export KOKORO_DEVELOPMENT_MODE="true"

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

# --- Server Execution ---
echo "Starting development server on http://${HOST}:${PORT}"
echo " LOG_LEVEL is set to ${LOG_LEVEL}"
[ "$UVICORN_RELOAD" = "1" ] && echo " Hot-reloading is enabled."

# Use exec to replace the shell process with the uvicorn process
exec uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" $([ "$UVICORN_RELOAD" = "1" ] && echo "--reload") 