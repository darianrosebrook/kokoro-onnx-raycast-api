#!/bin/bash

# Kokoro-ONNX + Raycast Unified Setup Script
#
# This script automates the complete setup process for both the Python backend
# and the Raycast frontend, including dependency installation and model downloads.

# --- Configuration ---
set -e  # Exit immediately if a command exits with a non-zero status.
set -o pipefail # Return value of a pipeline is the value of the last command to exit with a non-zero status

# --- Helper Functions ---
function print_header() {
  echo ""
  echo "========================================================================"
  echo "    $1"
  echo "========================================================================"
}

function print_success() {
  echo "✅ $1"
}

function print_warning() {
  echo "⚠️ $1"
}

function print_error() {
  echo "❌ Error: $1"
  exit 1
}

# --- 1. Dependency Checks ---
print_header "Step 1: Checking System Dependencies"

# Check for Python 3 and Pip
if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null; then
  print_error "Python 3 and Pip are required. Please install them to continue."
fi
print_success "Python 3 and Pip found."

# Check for Node.js and npm
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
  print_error "Node.js and npm are required. Please install them to continue."
fi
print_success "Node.js and npm found."

# Check for wget
if ! command -v wget &> /dev/null; then
  print_error "wget is required for downloading model files. Please install it (e.g., 'brew install wget')."
fi
print_success "wget found."

# --- 2. Backend Setup (Kokoro-ONNX API) ---
print_header "Step 2: Setting up the Python Backend (Kokoro-ONNX API)"

# Create Python virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment in .venv/..."
  python3 -m venv .venv
else
  echo "Virtual environment .venv/ already exists."
fi

# Activate virtual environment
source .venv/bin/activate
print_success "Activated Python virtual environment."

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
pip3 install -r requirements.txt
print_success "Python dependencies installed."

# Run environment diagnostics
echo "Running environment diagnostics..."
if [ -f "scripts/check_environment.py" ]; then
  python scripts/check_environment.py
  if [ $? -eq 0 ]; then
    print_success "Environment diagnostics passed."
  else
    print_warning "Environment diagnostics found some issues - check the output above."
  fi
else
  print_warning "Environment diagnostic script not found - skipping diagnostics."
fi

# Install espeak-ng (platform-dependent)
if [[ "$(uname -s)" == "Darwin" ]]; then
  if ! command -v espeak-ng &> /dev/null; then
    echo "Installing espeak-ng using Homebrew..."
    if ! command -v brew &> /dev/null; then
      print_warning "Homebrew not found. Please install espeak-ng manually."
    else
      brew install espeak-ng
      print_success "espeak-ng installed."
    fi
  else
    print_success "espeak-ng is already installed."
  fi
else
  print_warning "Setup for non-macOS systems may require manual installation of 'espeak-ng'."
fi

# --- 3. Model File Download ---
print_header "Step 3: Downloading Model Files"

MODEL_FILE="kokoro-v1.0.int8.onnx"
VOICES_FILE="voices-v1.0.bin"
MODEL_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

if [ -f "$MODEL_FILE" ]; then
  print_success "Model file '$MODEL_FILE' already exists."
else
  echo "Downloading model file: $MODEL_FILE..."
  wget -O "$MODEL_FILE" "$MODEL_URL"
  print_success "Model file downloaded."
fi

if [ -f "$VOICES_FILE" ]; then
  print_success "Voices file '$VOICES_FILE' already exists."
else
  echo "Downloading voices file: $VOICES_FILE..."
  wget -O "$VOICES_FILE" "$VOICES_URL"
  print_success "Voices file downloaded."
fi

# --- 3b. ORT Optimization Setup ---
print_header "Step 3b: Setting up ORT Optimization for Apple Silicon"

# Check if we're on Apple Silicon
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  echo "🍎 Apple Silicon detected - setting up ORT optimization..."
  
  # Enable ORT optimization by default on Apple Silicon
  export KOKORO_ORT_OPTIMIZATION=auto
  echo "export KOKORO_ORT_OPTIMIZATION=auto" >> .env 2>/dev/null || echo "KOKORO_ORT_OPTIMIZATION=auto" > .env
  
  # Create cache directories
  mkdir -p .cache/ort
  
  print_success "ORT optimization configured for Apple Silicon."
  echo "   • ORT models will be automatically created and cached"
  echo "   • This provides better performance and reduces temp file issues"
  
  # Optional: Pre-convert model for faster startup
  if [ -f "scripts/convert_to_ort.py" ] && [ -f "$MODEL_FILE" ]; then
    echo "🔧 Pre-converting model to ORT format for optimal performance..."
    if python scripts/convert_to_ort.py "$MODEL_FILE" -o ".cache/ort/$(basename "$MODEL_FILE" .onnx).ort" 2>/dev/null; then
      print_success "Model pre-converted to ORT format."
    else
      print_warning "ORT pre-conversion failed - will convert automatically on first run."
    fi
  fi
else
  echo "ℹ️  Non-Apple Silicon system detected - ORT optimization not required."
  echo "   • Standard ONNX models will be used"
  echo "   • CPU execution will be optimized automatically"
fi

# --- 4. Frontend Setup (Raycast Extension) ---
print_header "Step 4: Setting up the Raycast Frontend"

if [ -d "raycast" ]; then
  cd raycast
  echo "Installing Node.js dependencies for Raycast extension..."
  npm install
  print_success "Raycast dependencies installed."
  cd ..
else
  print_warning "Raycast directory not found. Skipping frontend setup."
fi

# --- 5. System Validation ---
print_header "Step 5: Final System Validation"

# Run comprehensive diagnostics
if [ -f "scripts/troubleshoot_coreml.py" ]; then
  echo "🔍 Running comprehensive system diagnostics..."
  if python scripts/troubleshoot_coreml.py > /dev/null 2>&1; then
    print_success "System diagnostics passed - CoreML ready."
  else
    print_warning "System diagnostics found potential issues - see ORT_OPTIMIZATION_GUIDE.md for troubleshooting."
  fi
else
  print_warning "Diagnostic script not found - manual validation recommended."
fi

# --- 6. Benchmark Frequency Configuration ---
print_header "Step 6: Benchmark Frequency Configuration"

echo "🔧 Configuring how often the system should benchmark your hardware..."
echo ""
echo "The TTS system benchmarks your hardware to determine the optimal provider"
echo "(CoreML vs CPU) for best performance. Since hardware doesn't change frequently,"
echo "you can cache these results to speed up startup times."
echo ""

if [ -f "scripts/configure_benchmark_frequency.py" ]; then
  # Check if frequency is already configured
  if [ -f ".env" ] && grep -q "KOKORO_BENCHMARK_FREQUENCY" .env; then
    echo "📋 Benchmark frequency already configured:"
    python scripts/configure_benchmark_frequency.py --show-current
    echo ""
    
    # Ask if user wants to reconfigure
    read -p "Do you want to change the benchmark frequency? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "🔧 Launching interactive configuration..."
      python scripts/configure_benchmark_frequency.py
    else
      print_success "Using existing benchmark frequency configuration."
    fi
  else
    echo "🔧 Launching interactive benchmark frequency configuration..."
    python scripts/configure_benchmark_frequency.py
  fi
  
  # Verify configuration was saved
  if [ -f ".env" ] && grep -q "KOKORO_BENCHMARK_FREQUENCY" .env; then
    print_success "Benchmark frequency configured successfully."
  else
    print_warning "Benchmark frequency not configured - using default (daily)."
  fi
else
  print_warning "Benchmark frequency configuration script not found."
  echo "   • Default frequency (daily) will be used"
  echo "   • You can manually set: export KOKORO_BENCHMARK_FREQUENCY=weekly"
fi

# --- 7. Final Instructions ---
print_header "🎉 Setup Complete! 🎉"
echo ""
echo "✅ Your Kokoro TTS system is ready with the following features:"
echo "   • 🧠 Apple Silicon optimization with CoreML and Neural Engine"
echo "   • 🚀 ORT (ONNX Runtime) acceleration for better performance"
echo "   • 🩺 Comprehensive diagnostic and troubleshooting tools"
echo "   • 📊 Automatic performance monitoring and optimization"
echo "   • ⚡ Configurable benchmark frequency for optimal startup times"
echo ""
echo "🔧 Diagnostic Tools:"
echo "   👉 python scripts/check_environment.py     # Check system setup"
echo "   👉 python scripts/troubleshoot_coreml.py   # Diagnose CoreML issues"
echo "   👉 python scripts/configure_benchmark_frequency.py  # Configure benchmark frequency"
echo ""
echo "📊 Benchmark Management:"
echo "   👉 python scripts/configure_benchmark_frequency.py --show-current  # Show current settings"
echo "   👉 python scripts/configure_benchmark_frequency.py --frequency weekly  # Set frequency"
echo "   👉 rm .cache/coreml_config.json  # Clear cache to force re-benchmark"
echo ""
echo "🚀 Quick Start:"
echo "   👉 ./start_development.sh   # Development server with hot reload"
echo "   👉 ./start_production.sh    # Production server with optimization"
echo ""
echo "🔧 Environment Variables:"
echo "   • KOKORO_BENCHMARK_FREQUENCY: Controls benchmark frequency (daily/weekly/monthly/manually)"
echo "   • KOKORO_DEVELOPMENT_MODE: Skip benchmarking for faster development startup"
echo "   • KOKORO_SKIP_BENCHMARKING: Completely disable automatic benchmarking"
echo "   • ONNX_PROVIDER: Override provider selection (CoreMLExecutionProvider/CPUExecutionProvider)"
echo ""
echo "💡 Pro Tips:"
echo "   • Use 'weekly' benchmark frequency for most users (recommended)"
echo "   • Use 'monthly' frequency for stable production systems"
echo "   • Use 'manually' frequency for expert users who want complete control"
echo "   • Clear the cache after major OS updates to re-benchmark"
echo "   • Monitor startup times - longer cache periods = faster startup"
echo ""
echo "========================================================================"
echo "" 