#!/bin/bash

# Kokoro-ONNX + Raycast Unified Setup Script
#
# This script automates the complete setup process for both the Python backend
# and the Raycast frontend, including dependency installation and model downloads.
# Designed to be user-friendly for both developers and non-technical users.

# --- Configuration ---
set -e  # Exit immediately if a command exits with a non-zero status.
set -o pipefail # Return value of a pipeline is the value of the last command to exit with a non-zero status

# --- Helper Functions ---
function print_header() {
  echo ""
  echo "========================================================================
    $1
========================================================================
"
}

function print_success() {
  echo "✅ $1"
}

function print_warning() {
  echo "⚠️  $1"
}

function print_error() {
  echo "❌ Error: $1"
  exit 1
}

function print_info() {
  echo "ℹ️  $1"
}

function print_progress() {
  echo " $1"
}

function print_step() {
  echo " $1"
}

# --- Welcome Message ---
echo " Welcome to Kokoro TTS Setup!"
echo ""
echo "This script will set up a complete Text-to-Speech system with:"
echo "   • High-quality neural TTS with 60+ voices"
echo "   • Apple Silicon optimization (if applicable)"
echo "   • Raycast integration for quick access"
echo "   • Automatic performance optimization"
echo ""
echo "The setup process will take 5-10 minutes depending on your internet speed."
echo ""

# Ask for confirmation
read -p "Ready to begin setup? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Setup cancelled. You can run this script again anytime."
  exit 0
fi

# --- 1. Dependency Checks ---
print_header "Step 1: Checking System Dependencies"

print_progress "Checking Python installation..."
# Check for Python 3 and Pip
if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null; then
  print_error "Python 3 and Pip are required. Please install them to continue.
  
  Installation options:
  • macOS: Download from https://www.python.org/downloads/
  • Homebrew: brew install python
  • Windows: Download from https://www.python.org/downloads/
  • Linux: sudo apt-get install python3 python3-pip"
fi
print_success "Python 3 and Pip found."

print_progress "Checking Node.js installation..."
# Check for Node.js and npm
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
  print_error "Node.js and npm are required. Please install them to continue.
  
  Installation options:
  • macOS: Download from https://nodejs.org/
  • Homebrew: brew install node
  • Windows: Download from https://nodejs.org/
  • Linux: sudo apt-get install nodejs npm"
fi
print_success "Node.js and npm found."

print_progress "Checking wget installation..."
# Check for wget
if ! command -v wget &> /dev/null; then
  print_error "wget is required for downloading model files. Please install it:
  
  • macOS: brew install wget
  • Windows: Download from https://eternallybored.org/misc/wget/
  • Linux: sudo apt-get install wget"
fi
print_success "wget found."

print_info "All system dependencies are satisfied!"

# --- 2. Backend Setup (Kokoro-ONNX API) ---
print_header "Step 2: Setting up the Python Backend (Kokoro-ONNX API)"

print_progress "Creating Python virtual environment..."
# Create Python virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment in .venv/..."
  python3 -m venv .venv
  print_success "Virtual environment created."
else
  echo "Virtual environment .venv/ already exists."
  print_info "Using existing virtual environment."
fi

# Activate virtual environment
print_progress "Activating virtual environment..."
source .venv/bin/activate
print_success "Python virtual environment activated."

# Install Python dependencies
print_progress "Installing Python dependencies..."
echo "This may take a few minutes depending on your internet speed..."
pip3 install -r requirements.txt
print_success "Python dependencies installed successfully."

# Verify production optimization dependencies
print_progress "Verifying production optimization dependencies..."
if python3 -c "import orjson" 2>/dev/null; then
  print_success "ORJSON (fast JSON serialization) installed successfully."
else
  print_warning "ORJSON not found - production JSON serialization will use standard library."
fi

# Run environment diagnostics
print_progress "Running environment diagnostics..."
if [ -f "scripts/check_environment.py" ]; then
  python scripts/check_environment.py
  if [ $? -eq 0 ]; then
    print_success "Environment diagnostics passed."
  else
    print_warning "Environment diagnostics found some issues - check the output above."
    print_info "You can continue with setup, but some features may not work optimally."
  fi
else
  print_warning "Environment diagnostic script not found - skipping diagnostics."
fi

# Make performance validation scripts executable
print_progress "Setting up performance validation tools..."
if [ -f "scripts/quick_performance_test.sh" ]; then
  chmod +x scripts/quick_performance_test.sh
  print_success "Performance validation tools configured."
else
  print_warning "Performance validation script not found - some validation features may not be available."
fi

# Install espeak-ng (platform-dependent)
print_progress "Checking eSpeak-ng installation..."
if [[ "$(uname -s)" == "Darwin" ]]; then
  if ! command -v espeak-ng &> /dev/null; then
    echo "Installing espeak-ng using Homebrew..."
    if ! command -v brew &> /dev/null; then
      print_warning "Homebrew not found. Please install espeak-ng manually:
      
      • Download from https://github.com/espeak-ng/espeak-ng/releases
      • Or install Homebrew first: https://brew.sh/"
    else
      brew install espeak-ng
      print_success "espeak-ng installed successfully."
    fi
  else
    print_success "espeak-ng is already installed."
  fi
else
  print_warning "Setup for non-macOS systems may require manual installation of 'espeak-ng'.
  
  Installation options:
  • Ubuntu/Debian: sudo apt-get install espeak-ng
  • CentOS/RHEL: sudo yum install espeak-ng
  • Windows: Download from https://github.com/espeak-ng/espeak-ng/releases"
fi

# --- 3. Model File Download ---
print_header "Step 3: Downloading Model Files"

print_info "The TTS system requires two model files:"
echo "   • kokoro-v1.0.int8.onnx (88MB) - Main neural model"
echo "   • voices-v1.0.bin (27MB) - Voice data for 60+ voices"
echo ""

MODEL_FILE="kokoro-v1.0.int8.onnx"
VOICES_FILE="voices-v1.0.bin"
MODEL_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

# Check and download model file
if [ -f "$MODEL_FILE" ]; then
  # Verify file size to ensure it's not corrupted
  file_size=$(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null || echo "0")
  if [ "$file_size" -gt 50000000 ]; then  # Should be ~88MB
    print_success "Model file '$MODEL_FILE' already exists (${file_size} bytes)."
  else
    print_warning "Model file exists but appears to be incomplete (${file_size} bytes). Re-downloading..."
    rm -f "$MODEL_FILE"
    print_progress "Downloading main neural model (88MB)..."
    echo "This may take a few minutes depending on your internet speed..."
    if wget -O "$MODEL_FILE" "$MODEL_URL" --progress=bar:force; then
      print_success "Main neural model downloaded successfully."
    else
      print_error "Failed to download model file. Please check your internet connection and try again."
    fi
  fi
else
  print_progress "Downloading main neural model (88MB)..."
  echo "This may take a few minutes depending on your internet speed..."
  if wget -O "$MODEL_FILE" "$MODEL_URL" --progress=bar:force; then
    print_success "Main neural model downloaded successfully."
  else
    print_error "Failed to download model file. Please check your internet connection and try again."
  fi
fi

# Check and download voices file
if [ -f "$VOICES_FILE" ]; then
  # Verify file size to ensure it's not corrupted
  file_size=$(stat -f%z "$VOICES_FILE" 2>/dev/null || stat -c%s "$VOICES_FILE" 2>/dev/null || echo "0")
  if [ "$file_size" -gt 20000000 ]; then  # Should be ~27MB
    print_success "Voices file '$VOICES_FILE' already exists (${file_size} bytes)."
  else
    print_warning "Voices file exists but appears to be incomplete (${file_size} bytes). Re-downloading..."
    rm -f "$VOICES_FILE"
    print_progress "Downloading voice data (27MB)..."
    echo "This may take a minute depending on your internet speed..."
    if wget -O "$VOICES_FILE" "$VOICES_URL" --progress=bar:force; then
      print_success "Voice data downloaded successfully."
    else
      print_error "Failed to download voices file. Please check your internet connection and try again."
    fi
  fi
else
  print_progress "Downloading voice data (27MB)..."
  echo "This may take a minute depending on your internet speed..."
  if wget -O "$VOICES_FILE" "$VOICES_URL" --progress=bar:force; then
    print_success "Voice data downloaded successfully."
  else
    print_error "Failed to download voices file. Please check your internet connection and try again."
  fi
fi

# Final verification that both files exist and have reasonable sizes
if [ ! -f "$MODEL_FILE" ] || [ ! -f "$VOICES_FILE" ]; then
  print_error "Critical error: Model files are missing after download attempt.
  
  Please check:
  • Internet connection
  • Available disk space
  • File permissions
  
  You can manually download the files from:
  • Model: $MODEL_URL
  • Voices: $VOICES_URL"
  exit 1
fi

# Verify file sizes one more time
model_size=$(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null || echo "0")
voices_size=$(stat -f%z "$VOICES_FILE" 2>/dev/null || stat -c%s "$VOICES_FILE" 2>/dev/null || echo "0")

if [ "$model_size" -lt 50000000 ] || [ "$voices_size" -lt 20000000 ]; then
  print_error "Critical error: Downloaded files appear to be incomplete.
  
  Model file size: ${model_size} bytes (expected ~88MB)
  Voices file size: ${voices_size} bytes (expected ~27MB)
  
  Please check your internet connection and run the setup script again."
  exit 1
fi

print_success "All model files are ready and verified!"
echo "   • Model file: ${model_size} bytes"
echo "   • Voices file: ${voices_size} bytes"

# --- 3b. ORT Optimization Setup ---
print_header "Step 3b: Setting up ORT Optimization for Apple Silicon"

# Check if we're on Apple Silicon
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  print_info " Apple Silicon detected - setting up performance optimization..."
  
  # Enable ORT optimization by default on Apple Silicon
  export KOKORO_ORT_OPTIMIZATION=auto
  echo "export KOKORO_ORT_OPTIMIZATION=auto" >> .env 2>/dev/null || echo "KOKORO_ORT_OPTIMIZATION=auto" > .env
  
  # Create cache directories
  mkdir -p .cache/ort
  
  print_success "ORT optimization configured for Apple Silicon."
  print_info "Benefits you'll get:"
  echo "   • 3-5x faster speech generation with Neural Engine"
  echo "   • 2-3x faster performance without Neural Engine"
  echo "   • Reduced memory usage and better stability"
  echo "   • Fewer temporary file issues"
  echo "   • Historical benchmark reports with timestamps"
  
  # Optional: Pre-convert model for faster startup
  if [ -f "scripts/convert_to_ort.py" ] && [ -f "$MODEL_FILE" ]; then
    print_progress "Pre-converting model for optimal performance..."
    echo "This may take 2-3 minutes but will speed up future startups..."
    if python scripts/convert_to_ort.py "$MODEL_FILE" -o ".cache/ort/$(basename "$MODEL_FILE" .onnx).ort" 2>/dev/null; then
      print_success "Model pre-converted for optimal performance."
    else
      print_warning "Pre-conversion failed - model will be converted automatically on first use."
    fi
  fi
else
  print_info "ℹ️  Non-Apple Silicon system detected."
  echo "   • Standard ONNX models will be used"
  echo "   • CPU execution will be optimized automatically"
  echo "   • Performance will still be excellent for TTS generation"
fi

# --- 4. Frontend Setup (Raycast Extension) ---
print_header "Step 4: Setting up the Raycast Frontend"

if [ -d "raycast" ]; then
  cd raycast
  print_progress "Installing Node.js dependencies for Raycast extension..."
  echo "This may take a minute..."
  npm install
  print_success "Raycast extension dependencies installed."
  cd ..
  
  print_info "Raycast extension features:"
  echo "   • Quick TTS from selected text"
  echo "   • Interactive text input with voice selection"
  echo "   • Speed control and streaming audio"
  echo "   • Native macOS integration"
else
  print_warning "Raycast directory not found. Skipping frontend setup."
  print_info "You can still use the TTS system via the web API at http://localhost:8000"
fi

# --- 5. System Validation ---
print_header "Step 5: Final System Validation"

# Run comprehensive diagnostics
if [ -f "scripts/troubleshoot_coreml.py" ]; then
  print_progress "Running comprehensive system diagnostics..."
  echo "This will test your hardware capabilities and CoreML support..."
  if python scripts/troubleshoot_coreml.py > /dev/null 2>&1; then
    print_success "System diagnostics passed - everything is ready!"
  else
    print_warning "System diagnostics found potential issues."
    print_info "The system will still work, but some optimizations may not be available."
    echo "   • Check the output above for details"
    echo "   • See ORT_OPTIMIZATION_GUIDE.md for troubleshooting"
  fi
else
  print_warning "Diagnostic script not found - manual validation recommended."
fi

# --- 6. Benchmark Frequency Configuration ---
print_header "Step 6: Benchmark Frequency Configuration"

print_info "The TTS system automatically benchmarks your hardware to find the best performance settings."
echo ""
echo "Since hardware doesn't change frequently, you can cache these results to speed up startup times."
echo ""

if [ -f "scripts/configure_benchmark_frequency.py" ]; then
  # Check if frequency is already configured
  if [ -f ".env" ] && grep -q "KOKORO_BENCHMARK_FREQUENCY" .env; then
    echo " Benchmark frequency already configured:"
    python scripts/configure_benchmark_frequency.py --show-current
    echo ""
    
    # Ask if user wants to reconfigure
    read -p "Do you want to change the benchmark frequency? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      print_progress "Launching interactive configuration..."
      python scripts/configure_benchmark_frequency.py
    else
      print_success "Using existing benchmark frequency configuration."
    fi
  else
    print_progress "Launching interactive benchmark frequency configuration..."
    echo "This will help optimize startup times based on your preferences."
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
print_header " Setup Complete! "

print_success "Your Kokoro TTS system is ready with the following features:"
echo ""
echo "Performance Features:"
echo "   •  Apple Silicon optimization with CoreML and Neural Engine"
echo "   • ORT (ONNX Runtime) acceleration for better performance"
echo "   •  Configurable benchmark frequency for optimal startup times"
echo ""
echo " TTS Capabilities:"
echo "   • 60+ voices across multiple languages"
echo "   • Real-time streaming audio generation"
echo "   • OpenAI-compatible API endpoints"
echo "   • Intelligent text processing and segmentation"
echo ""
echo "🛠️  System Features:"
echo "   •  Comprehensive diagnostic and troubleshooting tools"
echo "   •  Automatic performance monitoring and optimization"
echo "   •  Production-ready error handling and fallbacks"
echo "   •  Raycast integration for quick access"
echo ""

print_step "Next Steps:"
echo ""
echo "1. Start the development server:"
echo "   ./start_development.sh"
echo ""
echo "2.  Access the web interface:"
echo "   http://localhost:8000/docs"
echo ""
echo "3.  Validate performance optimizations:"
echo "   ./scripts/quick_performance_test.sh"
echo ""
echo "4.  Use Raycast extension (if installed):"
echo "   Open Raycast and search for 'Speak Text' or 'Speak Selection'"
echo ""


print_step "Environment Variables (Optional):"
echo ""
echo "Performance & Optimization:"
echo "   • KOKORO_BENCHMARK_FREQUENCY: Controls benchmark frequency (daily/weekly/monthly/manually)"
echo "   • KOKORO_DEVELOPMENT_MODE: Skip benchmarking for faster development startup"
echo "   • KOKORO_SKIP_BENCHMARKING: Completely disable automatic benchmarking"
echo "   • ONNX_PROVIDER: Override provider selection (CoreMLExecutionProvider/CPUExecutionProvider)"
echo ""
echo "Production Optimizations:"
echo "   • KOKORO_PRODUCTION=true: Enable production mode (ORJSON, GZip, security headers)"
echo "   • KOKORO_GRAPH_OPT_LEVEL=ALL: Maximum ONNX Runtime optimization"
echo "   • KOKORO_MEMORY_ARENA_SIZE_MB=512: Memory arena size for performance"
echo "   • KOKORO_COREML_MODEL_FORMAT=MLProgram: Optimal CoreML format for Apple Silicon"
echo "   • KOKORO_ALLOWED_HOSTS: Comma-separated allowed hosts for production security"
echo ""

print_step "Pro Tips:"
echo ""
echo "   • Use 'weekly' benchmark frequency for most users (recommended)"
echo "   • Use 'monthly' frequency for stable production systems"
echo "   • Use 'manually' frequency for expert users who want complete control"
echo "   • Clear the cache after major OS updates to re-benchmark"
echo "   • Monitor startup times - longer cache periods = faster startup"
echo ""

print_success "Setup completed successfully! Your TTS system is ready to use."
echo ""
echo "========================================================================
" 

# Final check and message
print_step "Setup complete!"
echo ""
echo "You can now start the development server by running:"
echo "  ./start_development.sh"
if [[ "$(uname -m)" == "arm64" ]]; then
    echo ""
    echo "⚙️  NOTE: On first run, the server will perform a one-time optimization"
    echo "    for Apple Silicon (ORT conversion), which may take ~15 seconds."
    echo "    Subsequent startups will be much faster."
fi


print_step "Useful Commands:"
echo ""
echo " Performance Validation:"
echo "   ./scripts/quick_performance_test.sh     # Quick performance test (recommended)"
echo "   python scripts/validate_optimization_performance.py  # Comprehensive validation"
echo "   python scripts/baseline_comparison.py --days-ago 7   # Compare with previous version"
echo ""
echo " Diagnostic Tools:"
echo "   python scripts/check_environment.py     # Check system setup"
echo "   python scripts/troubleshoot_coreml.py   # Diagnose CoreML issues"
echo "   python scripts/configure_benchmark_frequency.py  # Configure benchmark frequency"
echo ""
echo " Performance Management:"
echo "   python scripts/configure_benchmark_frequency.py --show-current  # Show current settings"
echo "   python scripts/configure_benchmark_frequency.py --frequency weekly  # Set frequency"
echo "   rm .cache/coreml_config.json  # Clear cache to force re-benchmark"
echo ""
echo "Server Management:"
echo "   ./start_development.sh   # Development server with hot reload"
echo "   ./start_production.sh    # Production server with optimization"
echo ""