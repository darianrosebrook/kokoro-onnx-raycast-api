#!/bin/bash
# Simple performance benchmark using curl

echo "🚀 Starting Kokoro TTS Performance Benchmark"
echo "=============================================="

BASE_URL="http://localhost:8000"

# Test server health
echo "🔍 Testing server health..."
curl -s "$BASE_URL/health" | jq '.' || echo "❌ Server health check failed"

echo ""

# Test different text lengths
test_texts=(
    "Hello world!"
    "This is a medium-length sentence for testing TTS performance characteristics."
    "This is a much longer text that will test the system's ability to handle extended content. It includes multiple sentences and should provide a good test of the streaming capabilities and overall performance under more realistic conditions."
    "We identified 7 core capabilities, supported by 35 implementations across our product units. For example, Summarization alone has 10 separate implementations distributed across product units, with some leveraging the Insights Engine capabilities and others developing bespoke solutions. This analysis underscores both the duplication across business units and the opportunity for consolidation."
)

text_names=("Short" "Medium" "Long" "Very Long")

for i in "${!test_texts[@]}"; do
    text="${test_texts[$i]}"
    name="${text_names[$i]}"
    length=${#text}
    
    echo "📏 Testing $name text ($length chars): '$text'"
    echo "----------------------------------------"
    
    # Test TTFA (Time To First Audio)
    echo "🎯 TTFA Test:"
    start_time=$(date +%s.%N)
    
    response=$(curl -s -w "\n%{http_code}\n%{time_total}\n%{time_starttransfer}\n%{size_download}" \
        -X POST "$BASE_URL/audio/speech" \
        -H "Content-Type: application/json" \
        -d "{\"input\": \"$text\", \"voice\": \"af_heart\", \"speed\": 1.25}")
    
    end_time=$(date +%s.%N)
    
    # Parse response
    http_code=$(echo "$response" | tail -n 4 | head -n 1)
    time_total=$(echo "$response" | tail -n 3 | head -n 1)
    time_starttransfer=$(echo "$response" | tail -n 2 | head -n 1)
    size_download=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "200" ]; then
        ttfa_ms=$(echo "$time_starttransfer * 1000" | bc -l)
        total_ms=$(echo "$time_total * 1000" | bc -l)
        
        echo "  ✅ Success"
        echo "  TTFA: ${ttfa_ms}ms"
        echo "  Total: ${total_ms}ms"
        echo "  Size: ${size_download} bytes"
        echo "  Rate: $(echo "scale=2; $size_download / $time_total" | bc -l) bytes/sec"
    else
        echo "  ❌ Failed: HTTP $http_code"
    fi
    
    echo ""
    
    # Test streaming
    echo "🌊 Streaming Test:"
    start_time=$(date +%s.%N)
    
    # Create a temporary file for streaming response
    temp_file=$(mktemp)
    
    curl -s -w "\n%{http_code}\n%{time_total}\n%{time_starttransfer}\n%{size_download}" \
        -X POST "$BASE_URL/audio/speech" \
        -H "Content-Type: application/json" \
        -d "{\"input\": \"$text\", \"voice\": \"af_heart\", \"speed\": 1.25, \"stream\": true}" \
        -o "$temp_file"
    
    end_time=$(date +%s.%N)
    
    # Parse streaming response
    http_code=$(tail -n 4 "$temp_file" | head -n 1)
    time_total=$(tail -n 3 "$temp_file" | head -n 1)
    time_starttransfer=$(tail -n 2 "$temp_file" | head -n 1)
    size_download=$(tail -n 1 "$temp_file")
    
    if [ "$http_code" = "200" ]; then
        ttfa_ms=$(echo "$time_starttransfer * 1000" | bc -l)
        total_ms=$(echo "$time_total * 1000" | bc -l)
        
        echo "  ✅ Success"
        echo "  First chunk: ${ttfa_ms}ms"
        echo "  Total: ${total_ms}ms"
        echo "  Size: ${size_download} bytes"
    else
        echo "  ❌ Failed: HTTP $http_code"
    fi
    
    rm -f "$temp_file"
    echo ""
    echo "=============================================="
    echo ""
done

echo "📊 Benchmark Complete!"
echo "Check the results above for performance trends and optimization opportunities."
