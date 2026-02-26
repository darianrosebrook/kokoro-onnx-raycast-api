#!/bin/bash
# Quick test script for TTS endpoints and audio daemon

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Kokoro TTS Endpoint Test${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test 1: TTS API Health
echo -e "${BLUE}Test 1: TTS API Health${NC}"
if curl -s http://127.0.0.1:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ TTS API is running${NC}"
    curl -s http://127.0.0.1:8080/health | python3 -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8080/health
else
    echo -e "${RED}✗ TTS API is not running${NC}"
    echo "  Start it with: ./start_development.sh"
fi
echo ""

# Test 2: Audio Daemon HTTP Health
echo -e "${BLUE}Test 2: Audio Daemon HTTP Health${NC}"
if curl -s http://localhost:8081/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Audio daemon HTTP is running${NC}"
    curl -s http://localhost:8081/health
else
    echo -e "${RED}✗ Audio daemon HTTP is not running${NC}"
    echo "  Start it with: ./start_development.sh"
fi
echo ""

# Test 3: Voices Endpoint
echo -e "${BLUE}Test 3: Voices Endpoint${NC}"
if curl -s http://127.0.0.1:8080/voices > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Voices endpoint is accessible${NC}"
    curl -s http://127.0.0.1:8080/voices | python3 -m json.tool 2>/dev/null | head -20 || curl -s http://127.0.0.1:8080/voices
else
    echo -e "${RED}✗ Voices endpoint failed${NC}"
fi
echo ""

# Test 4: TTS Generation (non-streaming)
echo -e "${BLUE}Test 4: TTS Generation (non-streaming)${NC}"
mkdir -p temp/test-audio
TEST_TEXT="Hello, this is a test of the Kokoro TTS system."
if curl -s -X POST http://127.0.0.1:8080/v1/audio/speech \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"${TEST_TEXT}\",\"voice\":\"af_bella\",\"stream\":false}" \
    -o temp/test-audio/test.wav 2>&1; then
    if [ -f temp/test-audio/test.wav ] && [ -s temp/test-audio/test.wav ]; then
        SIZE=$(stat -f%z temp/test-audio/test.wav 2>/dev/null || stat -c%s temp/test-audio/test.wav 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✓ Generated audio: ${SIZE} bytes${NC}"
        echo "  Saved to: temp/test-audio/test.wav"
    else
        echo -e "${RED}✗ Audio generation failed (empty file)${NC}"
    fi
else
    echo -e "${RED}✗ Audio generation request failed${NC}"
fi
echo ""

# Test 5: WebSocket Connection (basic)
echo -e "${BLUE}Test 5: Audio Daemon WebSocket Connection${NC}"
if command -v python3 >/dev/null 2>&1; then
    python3 << 'EOF'
import sys
import json
try:
    import websockets
    import asyncio
    
    async def test_ws():
        try:
            async with websockets.connect("ws://localhost:8081") as ws:
                print("✓ Connected to audio daemon WebSocket")
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(message)
                    if data.get("type") == "status":
                        print(f"  Received status: {data.get('data', {}).get('state', 'unknown')}")
                except asyncio.TimeoutError:
                    print("  (No initial message received)")
                return True
        except Exception as e:
            print(f"✗ WebSocket connection failed: {e}")
            return False
    
    result = asyncio.run(test_ws())
    sys.exit(0 if result else 1)
except ImportError:
    print("⚠ websockets library not installed (pip install websockets)")
    sys.exit(0)
except Exception as e:
    print(f"✗ WebSocket test failed: {e}")
    sys.exit(1)
EOF
else
    echo -e "${YELLOW}⚠ Python3 not available for WebSocket test${NC}"
fi
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Test Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "For full streaming test with audio playback, run:"
echo "  python3 scripts/test_endpoints.py"















