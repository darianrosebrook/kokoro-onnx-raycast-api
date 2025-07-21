#!/bin/bash
# Misaki G2P Environment Setup Script
# This script sets up a Python 3.12 environment for Misaki G2P integration

set -e

echo "🚀 Setting up Misaki G2P environment..."

# Check if conda is available
if command -v conda &> /dev/null; then
    echo "✅ Conda found, using conda environment"
    ENV_MANAGER="conda"
elif command -v pyenv &> /dev/null; then
    echo "✅ Pyenv found, using pyenv environment"
    ENV_MANAGER="pyenv"
else
    echo "⚠️ Neither conda nor pyenv found. Please install one of them:"
    echo "   - Conda: https://docs.conda.io/en/latest/miniconda.html"
    echo "   - Pyenv: https://github.com/pyenv/pyenv"
    exit 1
fi

# Environment name
ENV_NAME="kokoro-misaki"
PYTHON_VERSION="3.12.7"

# Create environment based on available manager
if [ "$ENV_MANAGER" = "conda" ]; then
    echo "📦 Creating conda environment: $ENV_NAME with Python $PYTHON_VERSION"
    
    # Remove existing environment if it exists
    if conda env list | grep -q "^$ENV_NAME "; then
        echo "🔄 Removing existing environment: $ENV_NAME"
        conda env remove -n $ENV_NAME -y
    fi
    
    # Create new environment
    conda create -n $ENV_NAME python=$PYTHON_VERSION -y
    
    # Activate environment
    echo "🔧 Activating environment: $ENV_NAME"
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate $ENV_NAME
    
elif [ "$ENV_MANAGER" = "pyenv" ]; then
    echo "🐍 Creating pyenv environment: $ENV_NAME with Python $PYTHON_VERSION"
    
    # Install Python version if not available
    if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
        echo "📥 Installing Python $PYTHON_VERSION"
        pyenv install $PYTHON_VERSION
    fi
    
    # Create virtual environment
    pyenv virtualenv $PYTHON_VERSION $ENV_NAME
    
    # Activate environment
    echo "🔧 Activating environment: $ENV_NAME"
    pyenv activate $ENV_NAME
fi

# Verify Python version
echo "🔍 Verifying Python version..."
python --version

# Upgrade pip
echo "⬆️ Upgrading pip..."
python -m pip install --upgrade pip

# Install base requirements
echo "📦 Installing base requirements..."
pip install -r requirements.txt

# Install Misaki-specific requirements
echo "📦 Installing Misaki G2P requirements..."
pip install -r requirements-misaki.txt

# Install system dependencies (if on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 Installing system dependencies for macOS..."
    
    # Check if Homebrew is available
    if command -v brew &> /dev/null; then
        echo "📦 Installing phonemizer dependencies via Homebrew..."
        brew install espeak espeak-ng festival flite
    else
        echo "⚠️ Homebrew not found. Please install phonemizer dependencies manually:"
        echo "   brew install espeak espeak-ng festival flite"
    fi
fi

# Set environment variables
echo "🔧 Setting environment variables..."
export KOKORO_MISAKI_ENABLED=true
export KOKORO_MISAKI_FALLBACK=true
export KOKORO_MISAKI_CACHE_SIZE=1000
export KOKORO_MISAKI_QUALITY_THRESHOLD=0.8
export KOKORO_PHONEMIZER_BACKEND=espeak
export KOKORO_PHONEMIZER_LANGUAGE=en-us
export KOKORO_PHONEMIZER_PRESERVE_PUNCTUATION=true
export KOKORO_PHONEMIZER_STRIP_STRESS=false
export KOKORO_PHONEMIZER_QUALITY_MODE=true
export KOKORO_PHONEMIZER_ERROR_TOLERANCE=0.1

# Test Misaki installation
echo "🧪 Testing Misaki G2P installation..."
python -c "
try:
    import misaki
    print('✅ Misaki G2P imported successfully')
    
    # Test basic functionality
    from misaki import en
    g2p = en.G2P(trf=False, british=False)
    phonemes, tokens = g2p('Hello world')
    print(f'✅ Misaki G2P test successful: {phonemes[:20]}...')
    
except ImportError as e:
    print(f'❌ Misaki G2P import failed: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Misaki G2P test failed: {e}')
    exit(1)
"

# Test phonemizer fallback
echo "🧪 Testing phonemizer fallback..."
python -c "
try:
    from phonemizer import phonemize
    text = 'Hello world'
    phonemes = phonemize(text, language='en-us', backend='espeak')
    print(f'✅ Phonemizer fallback test successful: {phonemes[:20]}...')
except Exception as e:
    print(f'❌ Phonemizer fallback test failed: {e}')
    exit(1)
"

echo ""
echo "🎉 Misaki G2P environment setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Activate the environment:"
if [ "$ENV_MANAGER" = "conda" ]; then
    echo "      conda activate $ENV_NAME"
elif [ "$ENV_MANAGER" = "pyenv" ]; then
    echo "      pyenv activate $ENV_NAME"
fi
echo ""
echo "   2. Run the benchmark:"
echo "      python scripts/benchmark_phase1_improvements.py"
echo ""
echo "   3. Test Misaki integration:"
echo "      python scripts/demo_misaki_integration.py"
echo ""
echo "   4. Start the TTS server:"
echo "      python api/main.py"
echo ""
echo "🔧 Environment variables are set for optimal performance."
echo "   You can modify them in your shell profile for persistence." 