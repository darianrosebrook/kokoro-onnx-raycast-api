# TTS Performance Benchmarking System

This document describes the comprehensive benchmarking system for measuring TTS (Text-to-Speech) performance in the Raycast Kokoro extension, with a focus on streaming performance analysis and detailed timing diagnostics.

## Overview

The benchmarking system provides multiple ways to measure TTS performance:

1. **Raycast Extension Benchmarks** - Integrated into the extension UI
2. **Standalone Benchmark Script** - Command-line tool for development
3. **Comprehensive Metrics** - Detailed performance analysis
4. **Streaming Diagnostics** - Real-time streaming performance analysis
5. **Timing Breakdown** - Phase-by-phase timing analysis

## Features

### Performance Metrics

#### Core Timing Metrics
- **Send Time**: Time to initiate the TTS request
- **Network Latency**: Time to establish connection to TTS server
- **Time to First Byte (TTFB)**: Time until first response byte
- **Processing Time**: Server processing time (TTFB - send time)
- **Time to First Audio Chunk**: Time until first audio data arrives
- **Stream-to-Play Delay**: Time from first chunk to actual audio playback
- **First Audio Play Time**: Total time to first audio output
- **Total Response Time**: Complete request-to-audio processing time
- **Audio Processing Time**: Time to process audio for playback

#### Streaming Performance
- **Chunk Count**: Number of audio chunks received
- **Streaming Efficiency**: How much faster streaming is vs non-streaming
- **Cache Performance**: Cache hit rate and speedup analysis
- **Data Transfer**: Audio file sizes and transfer rates

### Benchmarking Modes

- **Single Request**: Test specific text with current settings
- **Streaming Diagnostics**: Detailed phase-by-phase timing analysis
- **Streaming vs Non-Streaming**: Compare performance modes
- **Full Suite**: Comprehensive test with multiple scenarios
- **Streaming Suite**: Focus on streaming performance scenarios
- **Iterations**: Repeat tests for statistical accuracy
- **Cache Analysis**: Compare cached vs network performance

## Usage

### 1. Raycast Extension Benchmarks

#### Quick Single Test
1. Open the Raycast extension
2. Enter text to test
3. Press `Cmd+Shift+T` to benchmark current text
4. Results appear in toast and console logs

#### Streaming Diagnostics
1. Open the Raycast extension
2. Press `Cmd+Shift+D` to run streaming diagnostics
3. Get detailed timing breakdown with performance insights
4. Check console for phase-by-phase analysis

#### Full Benchmark Suite
1. Open the Raycast extension
2. Press `Cmd+Shift+B` to run full benchmark suite
3. Watch progress in toast notifications
4. Check console for detailed results

#### Streaming-Focused Suite
1. Open the Raycast extension
2. Press `Cmd+Shift+S` to run streaming benchmark suite
3. Focus on streaming performance scenarios
4. Get specialized streaming metrics

### 2. Standalone Benchmark Script

#### Basic Usage
```bash
# Test with default settings
node benchmark-tts.js

# Test specific text
node benchmark-tts.js --text "Hello world"

# Run streaming diagnostics
node benchmark-tts.js --text "Test streaming" --diagnostics

# Run full test suite
node benchmark-tts.js --suite

# Run streaming-focused suite
node benchmark-tts.js --streaming-suite

# Test with custom server
node benchmark-tts.js --server http://localhost:8000 --text "Test"

# Multiple iterations for accuracy
node benchmark-tts.js --text "Test" --iterations 5
```

#### Advanced Options
```bash
# All available options
node benchmark-tts.js \
  --server http://localhost:8000 \
  --text "Custom text to test" \
  --voice af_heart \
  --speed 1.2 \
  --iterations 3 \
  --diagnostics \
  --compare-streaming \
  --streaming-suite
```

#### Command Line Options
- `--server <url>`: TTS server URL (default: http://localhost:8000)
- `--text <text>`: Text to synthesize (default: test phrases)
- `--voice <voice>`: Voice to use (default: af_heart)
- `--speed <speed>`: Speech speed (default: 1.0)
- `--iterations <n>`: Number of iterations (default: 1)
- `--suite`: Run full benchmark suite
- `--streaming-suite`: Run streaming-focused benchmark suite
- `--diagnostics`: Run detailed streaming diagnostics
- `--compare-streaming`: Compare streaming vs non-streaming performance
- `--help, -h`: Show help message

### 3. Console Output Example

#### Basic Benchmark
```
🧪 Test 1: "Hello world"
   Voice: af_heart, Speed: 1.0
   📊 Send time: 2.34ms
   📊 Network latency: 12.45ms
   📊 Time to first byte: 145.67ms
   📊 Processing time: 143.33ms
   📊 Time to first chunk: 156.78ms
   📊 Stream-to-play delay: 23.45ms
   📊 First audio play time: 180.23ms
   📊 Total response time: 205.90ms
   ✅ Success
```

#### Streaming Diagnostics
```
🔍 STREAMING TIMING DIAGNOSIS
Text: "This is a test of streaming performance..."
Voice: af_heart, Speed: 1.0
Server: http://localhost:8000
============================================================

📊 TTS Streaming Metrics:
  Send time: 2.34ms
  Processing time: 143.33ms
  Time to first chunk: 156.78ms

🎵 Starting immediate playback:
  Stream-to-play delay: 23.45ms
  Total time to first audio: 180.23ms

📈 DETAILED TIMING BREAKDOWN:
   Request Send Time:        2.34ms
   Network Latency:          12.45ms
   Server Processing Time:   143.33ms
   Time to First Chunk:      156.78ms
   Stream-to-Play Delay:     23.45ms
   First Audio Play Time:    180.23ms
   Total Response Time:      205.90ms

📊 PERFORMANCE ANALYSIS:
   Chunks Received:          3
   Audio Data Size:          45.23 KB
   Cache Hit:                No

🎯 PERFORMANCE INSIGHTS:
   ✅ Excellent streaming performance - First audio in 180.23ms
============================================================
```

#### Full Report
```
📊 TTS PERFORMANCE BENCHMARK REPORT
============================================================

📈 OVERALL STATISTICS:
   Total Requests: 9
   Successful: 9 (100.0%)
   Cache Hit Rate: 22.2%

⏱️  TIMING PERFORMANCE:
   Average Send Time: 2.15ms
   Average Network Latency: 15.45ms
   Average Time to First Byte: 142.33ms
   Average Processing Time: 140.18ms
   Average Stream-to-Play Delay: 25.67ms
   Average First Audio Play Time: 168.00ms
   Average Total Response Time: 190.78ms

🚀 CACHE PERFORMANCE:
   Cached Response Time: 5.12ms
   Network Response Time: 198.45ms
   Cache Speedup: 38.76x faster
   Time Saved: 193.33ms per cached request

🎧 STREAMING PERFORMANCE:
   Average Chunk Count: 2.8
   Streaming Efficiency: 2.15x faster

📦 DATA TRANSFER:
   Total Data Transferred: 387.45 KB
   Average Response Size: 43.05 KB
```

## Integration with Caching System

The benchmarking system integrates seamlessly with the LRU cache:

1. **Cache Hit Detection**: Automatically detects cache hits vs network requests
2. **Performance Comparison**: Shows speedup from caching
3. **Cache Statistics**: Displays cache efficiency metrics
4. **Cache Warming**: Automatically caches responses for future tests

## Understanding Results

### Key Metrics

#### Excellent Performance
- **Send Time**: < 5ms
- **Network Latency**: < 20ms
- **Processing Time**: < 100ms
- **Stream-to-Play Delay**: < 50ms
- **First Audio Play Time**: < 200ms
- **Cache Hit Rate**: > 50%
- **Cache Speedup**: > 20x

#### Good Performance
- **Send Time**: < 10ms
- **Network Latency**: < 50ms
- **Processing Time**: < 200ms
- **Stream-to-Play Delay**: < 100ms
- **First Audio Play Time**: < 500ms
- **Cache Hit Rate**: > 30%
- **Cache Speedup**: > 10x

#### Acceptable Performance
- **Send Time**: < 20ms
- **Network Latency**: < 100ms
- **Processing Time**: < 500ms
- **Stream-to-Play Delay**: < 200ms
- **First Audio Play Time**: < 1000ms
- **Cache Hit Rate**: > 10%
- **Cache Speedup**: > 5x

#### Poor Performance
- **Send Time**: > 20ms
- **Network Latency**: > 100ms
- **Processing Time**: > 500ms
- **Stream-to-Play Delay**: > 200ms
- **First Audio Play Time**: > 1000ms
- **Cache Hit Rate**: < 10%
- **Cache Speedup**: < 5x

### Performance Expectations

| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|------------|------|
| Send Time | < 5ms | < 10ms | < 20ms | > 20ms |
| Network Latency | < 20ms | < 50ms | < 100ms | > 100ms |
| Processing Time | < 100ms | < 200ms | < 500ms | > 500ms |
| Stream-to-Play Delay | < 50ms | < 100ms | < 200ms | > 200ms |
| First Audio Play Time | < 200ms | < 500ms | < 1000ms | > 1000ms |
| Total Response Time | < 300ms | < 800ms | < 1500ms | > 1500ms |
| Cache Hit Rate | > 50% | > 30% | > 10% | < 10% |
| Cache Speedup | > 20x | > 10x | > 5x | < 5x |

## Troubleshooting

### Common Issues

1. **High Send Time**
   - Check client-side network configuration
   - Verify request preparation isn't blocking
   - Consider optimizing request payload

2. **High Network Latency**
   - Check if TTS server is running locally
   - Verify server URL in preferences
   - Check network connectivity and routing

3. **Slow Processing Time**
   - Check server resources (CPU, GPU, memory)
   - Verify model loading and optimization
   - Consider hardware acceleration settings

4. **High Stream-to-Play Delay**
   - Check audio processing pipeline
   - Verify temporary file system performance
   - Consider afplay alternatives

5. **Poor Streaming Performance**
   - Verify streaming is enabled in preferences
   - Check chunk size and processing efficiency
   - Compare with non-streaming mode

### Debug Mode

Enable detailed logging by checking the console output:
```bash
# In the extension, open Console.app and filter for "TTS"
# Look for streaming metrics and timing breakdowns
# Or check the terminal where you ran the benchmark script
```

## Performance Optimization Guide

Based on benchmark results, optimize:

1. **High Send Time**: Optimize request preparation and payload
2. **High Network Latency**: Use local server or optimize network configuration
3. **Slow Processing Time**: Optimize server processing and hardware acceleration
4. **High Stream-to-Play Delay**: Optimize audio processing pipeline
5. **Poor Streaming Efficiency**: Implement true streaming with immediate playback
6. **Low Cache Hit Rate**: Improve cache key strategy and cache warming

## Best Practices

1. **Consistent Testing**: Use same test phrases for comparison
2. **Multiple Iterations**: Run multiple iterations for statistical accuracy
3. **Cache Warming**: Test both cold and warm cache scenarios
4. **Network Conditions**: Test under different network conditions
5. **Server Load**: Consider server load when interpreting results
6. **Streaming Focus**: Use streaming-specific benchmarks for streaming optimization
7. **Timing Analysis**: Use detailed timing diagnostics to identify bottlenecks

## Conclusion

The enhanced TTS benchmarking system provides comprehensive performance analysis with a focus on streaming performance. The detailed timing breakdown helps identify specific bottlenecks in the TTS pipeline, from request initiation to audio playback. Use the streaming diagnostics to optimize the user experience and ensure excellent performance.

For more information, see the main project documentation or contact the development team. 