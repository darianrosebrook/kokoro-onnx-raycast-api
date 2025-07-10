#!/bin/bash

# Production deployment script for Kokoro TTS API with maximum performance and comprehensive validation

echo "🚀 Starting Kokoro TTS API in Production Mode..."

# Check if we're in the right directory
if [ ! -f "api/main.py" ]; then
    echo "❌ Error: api/main.py not found. Make sure you're in the kokoro-onnx directory."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found. Please create one with:"
    echo "   python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "🔧 Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python is not available in the virtual environment."
    exit 1
fi

# Note: All dependency and model validation is now handled by the Python application.
# This script's only job is to launch the production server correctly.
echo "🐍 Handing off to Python for validation and startup..."

# Set environment variables for optimization
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Suppress CoreML warnings at the system level
export ORT_LOGGING_LEVEL=3
export ONNXRUNTIME_LOG_SEVERITY_LEVEL=3
export TF_CPP_MIN_LOG_LEVEL=3
export CORE_ML_LOG_LEVEL=3

# The Python application will intelligently select the best provider.
# We do not set ONNX_PROVIDER here to allow the app to benchmark and choose.
echo "⚡ ONNX provider will be auto-selected by the application for best performance."

# Try to use uvloop if available
if python -c "import uvloop" 2>/dev/null; then
    export UVICORN_LOOP="uvloop"
    echo "✅ uvloop enabled for better performance"
else
    echo "⚠️ uvloop not available - using default asyncio event loop."
    echo "💡 For better performance, run: pip install uvloop"
fi

# Determine optimal worker count based on CPU cores
cpu_count=$(python -c "import os; print(os.cpu_count() or 4)" 2>/dev/null || echo "4")

# Check for Apple Silicon to decide on worker count
# CoreML provider fails with multiple workers due to resource contention.
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
    echo "🍏 Apple Silicon detected - forcing a single worker for CoreML compatibility."
    WORKER_COUNT=1
else
    WORKER_COUNT=$((cpu_count / 2)) # Balanced recommendation
    if [ $WORKER_COUNT -lt 2 ]; then
        WORKER_COUNT=2 # Minimum of 2 workers for production
    fi
    if [ $WORKER_COUNT -gt 8 ]; then
        WORKER_COUNT=8 # Cap at 8 workers for stability
    fi
fi

echo "🔧 Starting production server with optimized settings..."
echo "📡 Server will be available at: http://localhost:8000"
echo "🎵 Streaming endpoint: http://localhost:8000/v1/audio/speech"
echo "🏥 Health check: http://localhost:8000/health"
echo "📊 Status endpoint: http://localhost:8000/status"
echo ""
echo "⚙️  Configuration:"
echo "   Workers: $WORKER_COUNT"
echo "   Threads per worker: 4"
echo "   CPU cores detected: $cpu_count"
echo "   ONNX Provider: Auto-selected by application"
echo "   uvloop: $([ -n "$UVICORN_LOOP" ] && echo "Enabled" || echo "Disabled")"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Create a local cache directory for CoreML compiled models to avoid permissions issues in /var/folders
mkdir -p .cache

# Start the production server with gunicorn
# Set TMPDIR to use the local cache
# Filter out CoreML context leak warnings from gunicorn output
TMPDIR=$(pwd)/.cache gunicorn api.main:app \
    --config gunicorn.conf.py \
    --workers $WORKER_COUNT \
    --worker-class uvicorn.workers.UvicornWorker \
    --threads 4 \
    --bind 0.0.0.0:8000 \
    --keep-alive 15 \
    --timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --worker-connections 1000 2>&1 | grep -v "Context leak detected" | grep -v "msgtracer returned -1" 