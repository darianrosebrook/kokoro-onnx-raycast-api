# Kokoro TTS Optimization Quick Reference

> **Current Status:** TTFA 2188ms → Target 800ms (2.7x improvement needed)
> **Last Updated:** Dec 2024

## 🚀 Quick Actions (Ready to Deploy)

### **P1: Deploy Quantization (High Impact, Low Risk)**
```bash
# Quantize model with ready scripts
python scripts/quantize_model.py --input kokoro-v1.0.onnx --output kokoro-v1.0.int8.onnx --benchmark --validate

# Expected: 2-4x inference speedup
```

### **P1: Apply Graph Optimizations**
```bash
# Run optimization pipeline
python scripts/optimization_pipeline.py --input models/ --stages graph_optimization,quantization

# Expected: Reduced model ops, faster loading
```

### **P1: Check Provider Selection**
```bash
# Verify CoreML availability
curl http://localhost:8000/status

# Look for: "recommended_provider": should be CoreMLExecutionProvider
# If CPU: investigate why CoreML not selected
```

## 📊 Performance Monitoring

### **Quick TTFA Test**
```bash
# Test current TTFA
curl -X POST "http://localhost:8000/benchmarks/ttfa/quick?text=Hello world"

# Expected response:
# {"ttfa_ms": 2188, "target_met": false, "category": "poor"}
```

### **Full Benchmark**
```bash
# Run comprehensive benchmark
curl -X POST http://localhost:8000/benchmarks/run -H "Content-Type: application/json" -d '{"benchmark_type": "full"}'

# Check results
curl http://localhost:8000/benchmarks/results/report
```

### **Real-time Monitoring**
```bash
# Check system status
curl http://localhost:8000/status

# Check optimization status  
curl http://localhost:8000/benchmarks/optimization/status

# Check session health
curl http://localhost:8000/session-status
```

## 🔧 Configuration Tuning

### **Environment Variables (Ready to Test)**
```bash
# CoreML optimization
export KOKORO_COREML_COMPUTE_UNITS=ALL  # vs CPUAndGPU for long text
export KOKORO_MEMORY_ARENA_SIZE_MB=3072  # tune 2048-4096 on 64GB
export KOKORO_COREML_MODEL_FORMAT=MLProgram

# Performance monitoring
export KOKORO_VERBOSE_LOGS=1  # for debugging
```

### **Known Working Configurations**
```bash
# Current production (working but slow)
KOKORO_COREML_COMPUTE_UNITS=ALL
KOKORO_MEMORY_ARENA_SIZE_MB=2048

# Recommended for testing (may improve TTFA)
KOKORO_COREML_COMPUTE_UNITS=CPUAndGPU  # for long text
KOKORO_MEMORY_ARENA_SIZE_MB=3072       # larger memory arena
```

## 🎯 Performance Targets & Current Status

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| TTFA | 800ms | 2188ms | ❌ 2.7x too slow |
| RTF | <0.6 | ~1.0 | ⚠️ Borderline |
| Underruns | <1/10min | 0 | ✅ Good |
| Memory | Stable | Stable | ✅ Good |

## 🚨 Emergency Recovery

### **If Sessions Block**
```bash
# Reset session state
curl -X POST http://localhost:8000/session-reset

# Verify clean state
curl http://localhost:8000/session-status
```

### **If Performance Degrades**
```bash
# Check for issues
curl http://localhost:8000/status | jq '.["performance_stats"]'

# Look for:
# - High memory usage
# - Provider fallbacks
# - Error rates
```

## 📈 Next Steps by Priority

### **P0: Critical Issues** ✅ **RESOLVED**
- ✅ Session resource leaks fixed
- ✅ Streaming errors resolved
- ✅ Performance monitoring working

### **P1: High Impact (Ready to Deploy)**
1. **Deploy INT8 quantization** (2-4x speedup expected)
2. **Apply ONNX graph optimizations** (reduced ops, faster loading)
3. **Investigate provider selection** (ensure CoreML used optimally)
4. **Session pre-warming** (reduce cold start overhead)

### **P2: Medium Impact (Requires Development)**
1. **Advanced caching strategies** (phoneme cache, segment cache)
2. **Audio pipeline optimization** (reduce 700ms processing overhead)
3. **Predictive processing** (start next segment early)

### **P3: Future Enhancements**
1. **Auto-tuning with ML** (Bayesian parameter optimization)
2. **Custom Metal kernels** (low-level hardware optimization)

## 🔍 Debugging Checklist

**If TTFA > 2500ms:**
- [ ] Check provider selection (should be CoreML)
- [ ] Verify model is cached/warmed
- [ ] Check memory arena size
- [ ] Review session utilization

**If audio has gaps/stutters:**
- [ ] Check streaming buffer configuration
- [ ] Monitor chunk delivery timing
- [ ] Verify daemon health
- [ ] Check network/IPC latency

**If memory grows:**
- [ ] Monitor session cleanup
- [ ] Check CoreML context warnings
- [ ] Verify garbage collection
- [ ] Review cache sizes

## 📚 References

- **Blueprint:** `docs/optimization/optimization-blueprint.md`
- **Tracker:** `docs/optimization/optimization-tracker.md`
- **Implementation:** `docs/implementation/ttfa-*.md`
- **Scripts:** `scripts/quantize_model.py`, `scripts/optimization_pipeline.py`
- **Monitoring:** `api/performance/benchmarks/`
