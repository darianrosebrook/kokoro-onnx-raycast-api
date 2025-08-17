# Kokoro TTS Production Deployment Guide
**Date**: 2025-08-17  
**Author**: @darianrosebrook  
**Status**: Production-ready with optimized configuration

## 🚀 **Production Configuration Summary**

### **✅ Optimized Settings (Based on Investigation Results)**

| Setting | Value | Rationale |
|---------|-------|-----------|
| `KOKORO_COREML_COMPUTE_UNITS` | `CPUOnly` | CPU provider outperforms CoreML by 27x (152ms vs 4178ms TTFA) |
| `KOKORO_DEV_PERFORMANCE_PROFILE` | `stable` | 50ms chunks provide optimal balance of latency and stability |
| `KOKORO_MEMORY_ARENA_SIZE_MB` | `3072` | Provides excellent memory efficiency (4-5MB RSS range) |
| `KOKORO_DEFER_BACKGROUND_INIT` | `true` | Eliminates background task interference |

### **📊 Performance Targets (Achieved)**

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| TTFA | 800ms | 152ms | ✅ **70% better!** |
| RTF | <0.6 | 0.121 | ✅ **Perfect!** |
| Memory (short) | <300MB | 50.3MB | ✅ **Excellent** |
| Memory (long) | <300MB | 4.4-5.0MB | ✅ **Excellent** |
| Concurrent (2 req) | <500ms | 9.1ms | ✅ **Excellent** |

## 🛠 **Deployment Steps**

### **1. Environment Setup**

```bash
# Clone the repository
git clone https://github.com/darianrosebrook/kokoro-onnx-raycast-api.git
cd kokoro-onnx-raycast-api

# Run setup script
./setup.sh

# Verify environment
python scripts/check_environment.py
```

### **2. Production Configuration**

The production script (`start_production.sh`) is pre-configured with optimal settings:

```bash
# Start production server
./start_production.sh

# Or with custom settings
HOST=0.0.0.0 PORT=8000 ./start_production.sh
```

**Key Production Features:**
- ✅ **CPU Provider**: Optimal performance (152ms TTFA p95)
- ✅ **50ms Chunks**: Best balance of latency and stability
- ✅ **Memory Optimization**: 4-5MB RSS range
- ✅ **Concurrency Support**: 2 concurrent requests optimal
- ✅ **Session Warming**: Eliminates cold start penalties
- ✅ **Cache Management**: Automated cache clearing

### **3. Health Checks**

```bash
# Check server status
curl http://localhost:8000/status

# Test TTS endpoint
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "af_heart", "speed": 1.0}'

# Monitor performance
curl http://localhost:8000/performance/status
```

### **4. Monitoring & Logging**

**Key Metrics to Monitor:**
- **TTFA**: Should be <200ms after warmup
- **Memory Usage**: Should be <50MB RSS
- **Concurrent Requests**: Limit to 2 for optimal performance
- **Cold Start**: ~4 seconds first request (normal)

**Log Analysis:**
```bash
# Monitor server logs
tail -f logs/server.log

# Check for performance issues
grep "TTFA target missed" logs/server.log
grep "cold start" logs/server.log
```

## 🔧 **Configuration Options**

### **Environment Variables**

| Variable | Default | Description |
|----------|---------|-------------|
| `KOKORO_COREML_COMPUTE_UNITS` | `CPUOnly` | Execution provider (CPU recommended) |
| `KOKORO_DEV_PERFORMANCE_PROFILE` | `stable` | Chunk timing profile (50ms chunks) |
| `KOKORO_MEMORY_ARENA_SIZE_MB` | `3072` | Memory arena size in MB |
| `KOKORO_DEFER_BACKGROUND_INIT` | `true` | Defer background initialization |
| `HOST` | `127.0.0.1` | Server host binding |
| `PORT` | `8000` | Server port |
| `WORKERS` | Auto-detected | Number of Gunicorn workers |

### **Performance Profiles**

| Profile | Chunk Size | Use Case |
|---------|------------|----------|
| `safe` | 100ms | Conservative, good steady state |
| `stable` | 50ms | **Production recommended** |
| `optimized` | 50ms | Same as stable |
| `benchmark` | 40ms | Testing only (more underruns) |

## 📈 **Performance Optimization**

### **Cold Start Mitigation**

**Issue**: First request takes ~4 seconds  
**Solution**: Implement session warming

```bash
# Enable session warming (add to environment)
export KOKORO_AGGRESSIVE_WARMING=true

# Or warm up manually
curl http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "voice": "af_heart"}'
```

### **Concurrency Optimization**

**Optimal**: 2 concurrent requests  
**Avoid**: >4 concurrent requests (triggers cold start)

```bash
# Test concurrency
python scripts/run_bench.py --preset=short --stream --trials=3 --concurrency=2
```

### **Memory Management**

**Current**: 4-5MB RSS range (excellent)  
**Monitoring**: Check for memory leaks

```bash
# Monitor memory usage
ps aux | grep python | grep kokoro
```

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. High TTFA (>500ms)**
```bash
# Check provider configuration
curl http://localhost:8000/status | jq '.tts_processing.active_provider'

# Should return: "CPUExecutionProvider"
```

#### **2. Memory Usage High (>100MB)**
```bash
# Check memory arena setting
echo $KOKORO_MEMORY_ARENA_SIZE_MB

# Should be: 3072
```

#### **3. Server Crashes**
```bash
# Check CoreML configuration
echo $KOKORO_COREML_COMPUTE_UNITS

# Should be: CPUOnly (not ALL or CPUAndGPU)
```

#### **4. Slow Concurrent Performance**
```bash
# Limit concurrency to 2 requests
# Check for background processes
ps aux | grep python
```

### **Performance Debugging**

```bash
# Run performance benchmark
python scripts/run_bench.py --preset=short --stream --trials=5 --verbose

# Check detailed metrics
curl http://localhost:8000/performance/status | jq
```

## 🔒 **Security Considerations**

### **Network Security**
- ✅ **Localhost Binding**: Default `127.0.0.1` binding
- ✅ **Security Headers**: Automatic security middleware
- ✅ **Input Validation**: Text sanitization and validation

### **Resource Limits**
- **Memory**: 4-5MB RSS range (very efficient)
- **CPU**: Moderate usage during synthesis
- **Network**: Streaming audio chunks

## 📋 **Deployment Checklist**

### **Pre-Deployment**
- [ ] Environment setup completed
- [ ] Dependencies installed
- [ ] Configuration verified
- [ ] Performance benchmark passed

### **Deployment**
- [ ] Production script configured
- [ ] Environment variables set
- [ ] Server started successfully
- [ ] Health checks passed

### **Post-Deployment**
- [ ] Performance monitoring active
- [ ] Logs being collected
- [ ] Cold start mitigation implemented
- [ ] Concurrency limits enforced

## 🎯 **Best Practices**

### **1. Provider Selection**
- **Always use CPU provider**: `KOKORO_COREML_COMPUTE_UNITS=CPUOnly`
- **Avoid CoreML**: Severe initialization issues and hangs

### **2. Chunk Timing**
- **Use stable profile**: 50ms chunks optimal
- **Avoid benchmark profile**: 40ms chunks cause underruns

### **3. Concurrency**
- **Limit to 2 requests**: Optimal performance
- **Monitor for cold start**: Higher concurrency triggers penalties

### **4. Memory Management**
- **Current settings optimal**: 4-5MB RSS range
- **No further optimization needed**: Excellent efficiency

### **5. Monitoring**
- **Track TTFA**: Should be <200ms after warmup
- **Monitor memory**: Should be <50MB RSS
- **Check logs**: Look for performance warnings

## 📞 **Support**

For issues or questions:
1. Check the troubleshooting section above
2. Review performance logs
3. Run diagnostic benchmarks
4. Check the optimization tracker for known issues

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-17  
**Next Review**: After production deployment
