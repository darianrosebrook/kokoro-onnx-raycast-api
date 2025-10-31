#!/bin/bash
# Startup Time Measurement Script
# Measures startup time from server start to service ready

echo "🚀 Starting startup time measurement..."
START_TIME=$(date +%s.%N)

# Start server in background
cd /Users/drosebrook/Desktop/Projects/kokoro-onnx-raycast-api
source .venv/bin/activate 2>/dev/null

# Start server and capture output
python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000 > logs/startup_test.log 2>&1 &
SERVER_PID=$!

echo "Server started (PID: $SERVER_PID)"
echo "Waiting for service to be ready..."

# Poll health endpoint until ready
MAX_WAIT=60
WAIT_COUNT=0
READY=false

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "online"; then
        END_TIME=$(date +%s.%N)
        STARTUP_TIME=$(echo "$END_TIME - $START_TIME" | bc)
        echo "✅ Service ready!"
        echo "⏱️  Startup time: ${STARTUP_TIME} seconds"
        READY=true
        break
    fi
    sleep 0.5
    WAIT_COUNT=$((WAIT_COUNT + 1))
    echo -n "."
done

if [ "$READY" = false ]; then
    echo "❌ Service did not become ready within ${MAX_WAIT} seconds"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Store PID for cleanup
echo $SERVER_PID > /tmp/kokoro_startup_test.pid

echo ""
echo "📊 Startup time measurement complete"
echo "Server PID: $SERVER_PID"
echo "To stop: kill $SERVER_PID"




