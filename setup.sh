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

# --- 5. Final Instructions ---
print_header "🎉 Setup Complete! 🎉"
echo ""
echo "You're all set! Here's how to run the project:"
echo ""
echo "1. Start the Backend API Server:"
echo "   In your terminal, run:"
echo "   👉 ./start_development.sh"
echo ""
echo "2. Start the Raycast Extension:"
echo "   In a separate terminal, navigate to the 'raycast' directory and run:"
echo "   👉 cd raycast"
echo "   👉 npm run dev"
echo ""
echo "Enjoy using Kokoro TTS!"
echo "========================================================================"
echo "" 