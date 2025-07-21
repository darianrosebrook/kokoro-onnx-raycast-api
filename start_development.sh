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

# Check if port is in use and kill the process
if lsof -i :${PORT} > /dev/null; then
    echo "Port ${PORT} is in use. Attempting to kill the process..."
    kill -9 $(lsof -t -i:${PORT})
    sleep 2 # Give time for the port to be released
fi

# --- Server Execution ---
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
echo ""
echo "💡 For production optimizations, use: ./start_production.sh"

# Use exec to replace the shell process with the uvicorn process
exec uvicorn api.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" $([ "$UVICORN_RELOAD" = "1" ] && echo "--reload") 