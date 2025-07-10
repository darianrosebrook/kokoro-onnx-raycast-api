#!/bin/bash

# Quick TTS Performance Validation Script
# This script demonstrates the optimization performance improvements

echo "🚀 TTS Performance Validation Test"
echo "=================================="
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Server not running. Please start with: ./start_development.sh"
    exit 1
fi

echo "✅ Server is running and healthy"
echo ""

# Test setup
TEST_TEXT="Testing the optimization performance improvements in our TTS system."
VOICE="af_heart"
SPEED="1.0"

echo "🔬 Running performance tests..."
echo "Text: '$TEST_TEXT'"
echo "Voice: $VOICE"
echo ""

# Test 1: Cold start (first inference)
echo "Test 1: Cold start performance"
echo "------------------------------"
START_TIME=$(date +%s.%N)
curl -s -X POST http://localhost:8000/v1/audio/speech \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$TEST_TEXT\", \"voice\": \"$VOICE\", \"speed\": $SPEED}" \
    -o /tmp/test_cold.wav
END_TIME=$(date +%s.%N)
COLD_TIME=$(echo "$END_TIME - $START_TIME" | bc)
echo "Cold start time: ${COLD_TIME}s"
echo ""

# Test 2: Cached inference (should be much faster)
echo "Test 2: Cached inference performance"
echo "------------------------------------"
START_TIME=$(date +%s.%N)
curl -s -X POST http://localhost:8000/v1/audio/speech \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$TEST_TEXT\", \"voice\": \"$VOICE\", \"speed\": $SPEED}" \
    -o /tmp/test_cached.wav
END_TIME=$(date +%s.%N)
CACHED_TIME=$(echo "$END_TIME - $START_TIME" | bc)
echo "Cached time: ${CACHED_TIME}s"
echo ""

# Calculate improvement
IMPROVEMENT=$(echo "scale=1; ($COLD_TIME - $CACHED_TIME) / $COLD_TIME * 100" | bc)
echo "📊 Performance Analysis"
echo "======================"
echo "Cold start:     ${COLD_TIME}s"
echo "Cached:         ${CACHED_TIME}s"
echo "Improvement:    ${IMPROVEMENT}%"
echo ""

# Get system status
echo "🖥️  System Status"
echo "================"
curl -s http://localhost:8000/status | jq '{
    model_loaded: .model_loaded,
    provider: .performance.provider_used,
    coreml_usage: .performance.coreml_usage_percent,
    avg_inference_time: .performance.average_inference_time,
    total_inferences: .performance.total_inferences,
    apple_silicon: .hardware.is_apple_silicon,
    neural_engine: .hardware.has_neural_engine
}'
echo ""

# Validation summary
echo "✅ Validation Summary"
echo "==================="
if (( $(echo "$IMPROVEMENT > 90" | bc -l) )); then
    echo "✅ EXCELLENT: ${IMPROVEMENT}% improvement - Optimizations working perfectly!"
elif (( $(echo "$IMPROVEMENT > 50" | bc -l) )); then
    echo "✅ GOOD: ${IMPROVEMENT}% improvement - Optimizations working well"
elif (( $(echo "$IMPROVEMENT > 0" | bc -l) )); then
    echo "⚠️  PARTIAL: ${IMPROVEMENT}% improvement - Some optimizations working"
else
    echo "❌ POOR: No improvement detected - Optimizations may not be working"
fi
echo ""

# File cleanup
rm -f /tmp/test_cold.wav /tmp/test_cached.wav

echo "🎉 Performance test complete!"
echo ""
echo "For detailed analysis, see: reports/validation/optimization_validation_report.md" 