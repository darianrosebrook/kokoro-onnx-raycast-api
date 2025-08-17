# Kokoro TTS Dashboard

A comprehensive dashboard for monitoring and testing Kokoro TTS performance with real-time audio streaming visualization.

## Features

### 🎵 Live Audio Streaming
- **Real-time TTS Testing**: Type text and hear it spoken instantly with visual feedback
- **Audio Waveform Visualization**: See the audio stream in real-time with amplitude visualization
- **Performance Metrics**: Track TTFA (Time to First Audio), chunk delivery, and streaming efficiency
- **Multiple Voice Options**: Test different Kokoro voices (AF Heart, AF Sky, AF Bella, etc.)
- **Speed Control**: Adjust speech speed from 0.5x to 2.0x
- **WebSocket Integration**: Direct connection to the audio daemon for low-latency streaming

### 📊 Benchmark Analysis
- **Historical Performance Data**: Analyze past benchmark runs
- **Interactive Charts**: Visualize TTFA, RTF, and memory usage trends
- **Filtering & Search**: Filter by preset, streaming mode, and voice
- **Memory Timeline**: Detailed memory usage analysis per benchmark run

## Architecture

The dashboard connects to the Kokoro TTS system through two main interfaces:

1. **HTTP API** (`http://localhost:8000`): For TTS synthesis requests
2. **WebSocket Connection** (`ws://localhost:8081`): For real-time audio streaming via the audio daemon

### Components

#### Audio Streaming Components
- **`TTSControlPanel`**: Main control interface for testing TTS
- **`AudioClient`**: WebSocket client for daemon communication  
- **`AudioVisualizer`**: Real-time waveform visualization
- **Connection management**: Automatic reconnection and error handling

#### Benchmark Analysis Components
- **`BenchmarkSummary`**: Overview of performance metrics
- **`PerformanceChart`**: Interactive charts for various metrics
- **`MemoryTimeline`**: Detailed memory usage visualization

## Usage

### Starting the Audio Streaming Interface

1. **Start the TTS Server**:
   ```bash
   cd kokoro-onnx
   python -m api.main
   ```

2. **Start the Audio Daemon**:
   ```bash
   cd raycast/bin
   node audio-daemon.js
   ```

3. **Start the Dashboard**:
   ```bash
   cd dashboard
   npm run dev
   ```

4. **Open in Browser**: Navigate to `http://localhost:3000`

### Using Live Audio Streaming

1. Click the **"Live Audio Streaming"** tab
2. Wait for the audio daemon connection (green "Connected" badge)
3. Enter text in the text area
4. Select voice and speed preferences
5. Click **"▶ Speak"** to start streaming
6. Watch the real-time waveform visualization
7. Monitor performance metrics in the side panels

### Key Features

- **Real-time Visualization**: See audio amplitude as it streams
- **Performance Monitoring**: Track TTFA, chunks received, buffer health
- **Connection Status**: Visual indicators for daemon connectivity
- **Playback Controls**: Play, pause, stop, and resume functionality
- **Voice Selection**: Choose from available Kokoro voices
- **Speed Adjustment**: Control speech rate for testing

## Technical Implementation

### Audio Streaming Flow

```
User Input → TTS Server → PCM Chunks → Audio Daemon → Speakers
     ↓                                        ↓
Dashboard ←--- WebSocket Monitoring ←--------┘
```

1. **Text Processing**: User enters text in the dashboard
2. **TTS Request**: Dashboard sends streaming request to TTS server
3. **Chunk Streaming**: Server streams PCM audio chunks
4. **Daemon Processing**: Audio daemon receives chunks via WebSocket
5. **Playback**: Native audio playback (sox/ffplay/afplay)
6. **Visualization**: Real-time waveform updates in dashboard

### Performance Metrics

The dashboard tracks several key metrics:

- **TTFA (Time to First Audio)**: Latency from request to first audio chunk
- **Chunk Delivery Rate**: Number of audio chunks received per second
- **Buffer Utilization**: Audio buffer health and underrun detection
- **Streaming Efficiency**: Ratio of expected vs actual streaming time
- **Connection Health**: WebSocket connection status and stability

### WebSocket Protocol

The dashboard communicates with the audio daemon using these message types:

```typescript
// Control messages
{ type: 'control', data: { action: 'play' | 'pause' | 'stop' | 'end_stream' } }

// Audio data
{ type: 'audio_chunk', data: { chunk: number[] } }

// Status updates
{ type: 'status', timestamp: number, data: AudioStatus }

// Completion events
{ type: 'completed', timestamp: number, data: CompletionData }
```

## Development

### File Structure

```
dashboard/src/
├── components/
│   ├── charts/
│   │   ├── audio-visualizer.tsx     # Real-time waveform visualization
│   │   ├── performance-chart.tsx    # Benchmark performance charts
│   │   └── memory-timeline.tsx      # Memory usage timeline
│   ├── tts-control-panel.tsx        # Main TTS testing interface
│   └── ui/                          # Base UI components
├── lib/
│   ├── audio-client.ts              # WebSocket client for audio daemon
│   ├── benchmark-parser.ts          # Benchmark data processing
│   └── real-data-loader.ts          # Data loading utilities
└── app/
    └── page.tsx                     # Main dashboard page with tabs
```

### Adding New Features

1. **Audio Processing**: Extend `AudioClient` for new daemon functionality
2. **Visualization**: Add new chart types in `components/charts/`
3. **Metrics**: Enhance performance tracking in `TTSControlPanel`
4. **UI Components**: Follow the existing design system in `components/ui/`

### Configuration

The dashboard automatically detects and connects to:
- TTS Server: `http://localhost:8000`
- Audio Daemon: `ws://localhost:8081`

These can be configured in the respective client components.

## Troubleshooting

### Audio Daemon Connection Issues

- **Check daemon is running**: `ps aux | grep audio-daemon`
- **Verify WebSocket port**: Default is 8081
- **Check browser console**: Look for connection errors
- **Restart daemon**: Kill and restart if connection is stuck

### TTS Server Issues

- **Verify server is running**: `curl http://localhost:8000/health`
- **Check logs**: Look for server errors in terminal
- **Model loading**: Ensure ONNX models are properly loaded

### Performance Issues

- **Browser DevTools**: Check for JavaScript errors
- **Network tab**: Monitor WebSocket traffic
- **Memory usage**: Large visualizations may impact performance
- **Audio quality**: Ensure proper audio format support

## Browser Compatibility

- **Chrome/Edge**: Full support including WebSocket audio streaming
- **Firefox**: Full support with WebSocket audio streaming  
- **Safari**: WebSocket support, audio may require user interaction
- **Mobile**: Limited audio daemon connectivity

## Related Documentation

- [Kokoro TTS Optimization Blueprint](../docs/optimization/kokoro-tts-optimization-blueprint.md)
- [Audio Daemon Architecture](../raycast/README.md)
- [Performance Benchmarking](../docs/implementation/)
- [API Documentation](../api/)