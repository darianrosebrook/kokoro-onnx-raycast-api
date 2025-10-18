# Kokoro-ONNX TTS System

**Production-ready Text-to-Speech system with exceptional performance**

[![Performance](https://img.shields.io/badge/TTFA-23--62ms-brightgreen)](docs/performance/CURRENT_BENCHMARKS.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)](docs/deployment/production-guide.md)
[![Optimization](https://img.shields.io/badge/Optimization-97%25%20Better%20Than%20Target-blue)](docs/optimization/kokoro-tts-optimization-blueprint.md)

## 🚀 Performance Highlights

- **TTFA (Time to First Audio)**: **23-62ms** (97% better than 800ms target)
- **Memory Usage**: 50.3MB (83% better than 300MB target)
- **System Stability**: All critical errors resolved, production-ready
- **Real-time Streaming**: Sub-25ms response for typical use cases

## 📊 Quick Start

### 1. Start the Server

```bash
# Clone and setup
git clone https://github.com/darianrosebrook/kokoro-onnx.git
cd kokoro-onnx

# Start production server
python api/main.py
```

### 2. Test Performance

```bash
# Quick TTFA test
curl -X POST "http://127.0.0.1:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "voice": "af_heart", "stream": true}'

# Check system status
curl "http://127.0.0.1:8000/status"
```

### 3. Raycast Integration

The system includes a production-ready Raycast extension for macOS:

```bash
cd raycast
npm install
npm run build
```

## 🎯 Key Features

### **Exceptional Performance**
- **23-62ms TTFA** (97% better than target)
- **Real-time streaming** with sub-25ms response
- **Memory efficient** at 50.3MB usage
- **Concurrent processing** with 9.1ms response

### **Production Ready**
- **All critical errors resolved**
- **Comprehensive monitoring** and health checks
- **Automatic fallback** systems
- **Error resilience** with graceful degradation

### **Advanced Optimization**
- **Memory fragmentation** monitoring and cleanup
- **Pipeline warming** with pattern caching
- **Real-time optimization** with auto-tuning
- **Dynamic memory** management

## 📈 Performance Metrics

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| **TTFA (Short)** | 800ms | 23-62ms | ✅ **97% better** |
| **TTFA (Long)** | 800ms | 168ms | ✅ **79% better** |
| **Memory Usage** | 300MB | 50.3MB | ✅ **83% better** |
| **System Stability** | No errors | All fixed | ✅ **Production ready** |

## 🏗️ Architecture

### **FastAPI Backend**
- **Hardware acceleration** with Apple Silicon optimization
- **Streaming audio pipeline** with real-time delivery
- **Comprehensive monitoring** and performance tracking
- **Production-ready** error handling and fallbacks

### **Raycast Frontend**
- **Native macOS integration** with Raycast
- **Real-time audio streaming** with sox/ffplay
- **Intuitive user interface** with voice selection
- **Production-tested** playback reliability

### **Optimization Framework**
- **Memory management** with fragmentation monitoring
- **Pipeline optimization** with pattern caching
- **Real-time tuning** with automatic optimization
- **Performance monitoring** with comprehensive metrics

## 📚 Documentation

- **[Performance Benchmarks](docs/performance/CURRENT_BENCHMARKS.md)** - Current performance metrics and achievements
- **[Production Guide](docs/deployment/production-guide.md)** - Deployment and configuration
- **[Optimization Blueprint](docs/optimization/kokoro-tts-optimization-blueprint.md)** - Technical optimization details
- **[API Documentation](api/main.py)** - Complete API reference
- **[Raycast Extension](raycast/README.md)** - Frontend integration guide

## 🔧 System Requirements

- **macOS** (Apple Silicon recommended)
- **Python 3.8+**
- **Node.js 16+** (for Raycast extension)
- **64GB RAM** (recommended for optimal performance)

## 🚀 Quick Performance Test

```bash
# Test TTFA performance
time curl -X POST "http://127.0.0.1:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "voice": "af_heart", "stream": true}' \
  -o /tmp/test.wav

# Expected: ~23-62ms TTFA (exceptional performance)
```

## 📊 System Status

```bash
# Check comprehensive system status
curl "http://127.0.0.1:8000/status" | jq '.'

# Check performance metrics
curl "http://127.0.0.1:8000/performance-stats" | jq '.'
```

## 🎉 Recent Achievements

- ✅ **97% better than target TTFA** (23-62ms vs 800ms)
- ✅ **All critical system errors resolved**
- ✅ **Production-ready stability and reliability**
- ✅ **Comprehensive optimization frameworks implemented**
- ✅ **Enhanced monitoring and debugging capabilities**

## 📞 Support

- **Performance Issues**: Check [Performance Benchmarks](docs/performance/CURRENT_BENCHMARKS.md)
- **Deployment**: See [Production Guide](docs/deployment/production-guide.md)
- **Optimization**: Review [Optimization Blueprint](docs/optimization/kokoro-tts-optimization-blueprint.md)
- **API Reference**: See [API Documentation](api/main.py)

---

**The Kokoro-ONNX TTS system delivers exceptional performance with 23-62ms TTFA, far exceeding all targets and providing a production-ready solution for high-performance text-to-speech applications.**
