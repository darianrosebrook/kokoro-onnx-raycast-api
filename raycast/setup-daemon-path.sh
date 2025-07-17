#!/bin/bash

# Setup script for Kokoro TTS Audio Daemon Path Configuration
# This script helps configure the daemon path for the Raycast extension environment

set -e

echo "🔧 Setting up Kokoro TTS Audio Daemon Path Configuration..."

# Get the current project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "📁 Project root: $PROJECT_ROOT"

# Check if daemon script exists
DAEMON_SCRIPT="$PROJECT_ROOT/raycast/bin/audio-daemon.js"
if [ ! -f "$DAEMON_SCRIPT" ]; then
    echo "❌ Error: Audio daemon script not found at $DAEMON_SCRIPT"
    exit 1
fi

echo "✅ Audio daemon script found at: $DAEMON_SCRIPT"

# Set environment variable for Raycast extension
export KOKORO_PROJECT_ROOT="$PROJECT_ROOT"
export KOKORO_AUDIO_DAEMON_PATH="$DAEMON_SCRIPT"

echo "🔧 Environment variables set:"
echo "   KOKORO_PROJECT_ROOT=$KOKORO_PROJECT_ROOT"
echo "   KOKORO_AUDIO_DAEMON_PATH=$KOKORO_AUDIO_DAEMON_PATH"

# Test the daemon script
echo "🧪 Testing daemon script..."
if node "$DAEMON_SCRIPT" --help > /dev/null 2>&1; then
    echo "✅ Daemon script test successful"
else
    echo "⚠️  Daemon script test failed (this might be expected if port is in use)"
fi

echo ""
echo "🎉 Setup complete! The Raycast extension should now be able to find the audio daemon."
echo ""
echo "To make these settings permanent, add the following to your shell profile:"
echo "export KOKORO_PROJECT_ROOT=\"$PROJECT_ROOT\""
echo "export KOKORO_AUDIO_DAEMON_PATH=\"$DAEMON_SCRIPT\""
echo ""
echo "Or run this script before starting Raycast:"
echo "source $PROJECT_ROOT/raycast/setup-daemon-path.sh" 