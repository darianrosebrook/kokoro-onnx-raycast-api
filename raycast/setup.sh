#!/bin/bash

# Kokoro TTS Raycast Extension Setup Script

echo " Setting up Kokoro TTS Raycast Extension..."

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found. Make sure you're in the raycast directory."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed. Please install npm first."
    exit 1
fi

# Install dependencies
echo " Installing dependencies..."
npm install

# Check if Raycast CLI is available
if ! command -v ray &> /dev/null; then
    echo "⚠️  Raycast CLI not found. Installing globally..."
    npm install -g @raycast/api
fi

# Check if TTS server is running
echo " Checking TTS server connection..."
if curl -s http://localhost:8000/ > /dev/null; then
    echo "✅ TTS server is running on localhost:8000"
else
    echo "⚠️  TTS server not detected on localhost:8000"
    echo "   Make sure to start the TTS server with: python api.py"
fi

echo ""
echo "Setup complete! Next steps:"
echo ""
echo "1. Make sure the TTS server is running:"
echo "   cd .. && python api.py"
echo ""
echo "2. Start the extension in development mode:"
echo "   npm run dev"
echo ""
echo "3. Or build for production:"
echo "   npm run build"
echo ""
echo " See README.md for detailed usage instructions."
echo ""
echo "�� Happy speaking!" 