#!/bin/bash

# Development startup script for Kokoro TTS API with hot reload and comprehensive validation

echo "🔧 Starting Kokoro TTS API in Development Mode..."

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

# Python application will handle all validation (dependencies, models, etc.)
echo "🐍 Handing off to Python for validation and startup..."

# Set environment variables for development
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export UVICORN_RELOAD=1

# Development mode optimizations for faster startup
export KOKORO_DEVELOPMENT_MODE=true
export KOKORO_SKIP_BENCHMARKING=true
export KOKORO_FAST_STARTUP=true

# Suppress CoreML warnings at the system level
export ORT_LOGGING_LEVEL=3
export ONNXRUNTIME_LOG_SEVERITY_LEVEL=3
export TF_CPP_MIN_LOG_LEVEL=3
export CORE_ML_LOG_LEVEL=3

# Note: ONNX_PROVIDER is NOT set here. The Python application will intelligently
# select the best provider based on hardware benchmarking and caching.

echo "🔧 Starting development server with hot reload..."
echo "📡 Server will be available at: http://localhost:8000"
echo "🎵 Streaming endpoint: http://localhost:8000/v1/audio/speech"
echo "🏥 Health check: http://localhost:8000/health"
echo "📊 Status endpoint: http://localhost:8000/status"
echo "📚 API docs: http://localhost:8000/docs"
echo ""
echo "🔄 Hot reload enabled - changes to files in the 'api' directory will restart the server"
echo "📄 Application logs will be written to: api_server.log"
echo "Press Ctrl+C to stop the server"
echo ""

# Create a local cache directory for CoreML compiled models to avoid permissions issues in /var/folders
mkdir -p .cache

# Start the development server with hot reload
# Set TMPDIR to use the local cache
# Use --log-level info to ensure proper logging output
# Note: Removed grep filtering to allow real-time logs to appear
TMPDIR=$(pwd)/.cache uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir api/ --log-level info 