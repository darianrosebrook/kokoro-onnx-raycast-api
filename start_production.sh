#!/bin/bash
# Description: Starts the production server using Gunicorn.
# This script is optimized for production deployments, providing robust
# process management and performance tuning. It automatically adjusts the
# number of workers based on the system architecture.

# --- Configuration ---
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"info"}
WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}

# --- Worker Calculation ---
if [[ "$(uname -m)" == "arm64" ]]; then
    WORKERS=1
    echo "⚠️  Apple Silicon detected—running a single Gunicorn worker to ensure CoreML stability."
else
    # Default to the number of CPU cores if `nproc` is available
    if command -v nproc >/dev/null 2>&1; then
        WORKERS=$(nproc)
    else
        WORKERS=2 # Fallback for systems without nproc
    fi
    echo "⚙️  Automatically configuring $WORKERS Gunicorn workers based on CPU cores."
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