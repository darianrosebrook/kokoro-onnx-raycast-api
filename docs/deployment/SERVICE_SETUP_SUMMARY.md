# macOS Launch Agent Installation Summary

**Created:** October 30, 2025  
**Status:** ✅ Ready to install

---

## What Was Created

### 1. Launch Agent Plist Template
- **File:** `deploy/com.kokoro.tts.plist`
- **Purpose:** macOS launchd configuration
- **Features:** Auto-start, auto-restart, background mode

### 2. Service Runner Script
- **File:** `scripts/run_service.sh`
- **Purpose:** Wrapper script with optimized settings
- **Features:** Production mode, minimal warmup, logging

### 3. Installation Script
- **File:** `scripts/install_service.sh`
- **Purpose:** Automated installation
- **Features:** Auto-detects paths, installs plist, loads service

### 4. Uninstallation Script
- **File:** `scripts/uninstall_service.sh`
- **Purpose:** Clean removal
- **Features:** Unloads service, removes plist

### 5. Documentation
- **File:** `docs/deployment/macos-launch-agent-guide.md`
- **Purpose:** Complete setup and management guide

---

## Installation

### Quick Install

```bash
cd /Users/drosebrook/Desktop/Projects/kokoro-onnx-raycast-api
./scripts/install_service.sh
```

### What Happens

1. **Creates Launch Agent plist** in `~/Library/LaunchAgents/`
2. **Loads the service** (starts immediately)
3. **Service starts** in background (~10 seconds to ready)
4. **Starts automatically** on future logins

### Verify Installation

```bash
# Check service status
launchctl list | grep com.kokoro.tts

# Check health
curl http://localhost:8000/health

# View logs
tail -f logs/service.log
```

---

## Service Configuration

### Optimized Settings

The service uses production-optimized settings:
- ✅ Production mode enabled
- ✅ Minimal warmup (fast startup)
- ✅ Background cleanup enabled
- ✅ Optimized performance profile

### Environment Variables

```bash
KOKORO_PRODUCTION=true
KOKORO_MINIMAL_WARMUP=true
KOKORO_ENABLE_COLD_START_WARMUP=false
KOKORO_DEV_PERFORMANCE_PROFILE=optimized
```

---

## Benefits

### For Development
- ✅ Always available for testing
- ✅ No need to remember to start server
- ✅ Consistent performance

### For Production Use
- ✅ Zero startup delay for requests
- ✅ Auto-restart on crash
- ✅ Background optimization
- ✅ Always-on availability

### For Raycast Integration
- ✅ Instant TTS requests
- ✅ No startup overhead
- ✅ Optimal performance
- ✅ Reliable service

---

## Management Commands

### Start Service
```bash
launchctl load ~/Library/LaunchAgents/com.kokoro.tts.plist
```

### Stop Service
```bash
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.plist
```

### Restart Service
```bash
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.plist && \
launchctl load ~/Library/LaunchAgents/com.kokoro.tts.plist
```

### View Logs
```bash
tail -f logs/service.log
tail -f logs/service.error.log
```

---

## Next Steps

1. ✅ Service files created
2. ⏳ Run `./scripts/install_service.sh` to install
3. ⏳ Verify service is running
4. ⏳ Test with Raycast extension
5. ⏳ Monitor logs for first few days

---

*The service will be available immediately after installation and will start automatically on future logins!*




