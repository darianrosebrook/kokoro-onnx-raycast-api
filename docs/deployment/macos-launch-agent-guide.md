# macOS Launch Agent Setup Guide

**Status:** ✅ Ready to install  
**Purpose:** Run Kokoro TTS as a background service that starts automatically on login

---

## Overview

This setup creates a macOS Launch Agent that:
- ✅ Starts automatically when you log in
- ✅ Runs in the background
- ✅ Automatically restarts if it crashes
- ✅ Stays available 24/7
- ✅ Uses optimized production settings

---

## Quick Start

### Install Service

```bash
cd /Users/drosebrook/Desktop/Projects/kokoro-onnx-raycast-api
./scripts/install_service.sh
```

### Uninstall Service

```bash
./scripts/uninstall_service.sh
```

---

## What Gets Installed

### 1. Launch Agent Plist
- **Location:** `~/Library/LaunchAgents/com.kokoro.tts.plist`
- **Purpose:** macOS launchd configuration
- **Behavior:** Starts on login, keeps service alive

### 2. Service Runner Script
- **Location:** `scripts/run_service.sh`
- **Purpose:** Wrapper script for the service
- **Features:** Sets up environment, logs output

### 3. Log Files
- **Service Log:** `logs/service.log`
- **Error Log:** `logs/service.error.log`

---

## Service Features

### Automatic Startup
- Starts when you log in
- No manual intervention needed
- Runs in background

### Auto-Restart
- Automatically restarts if service crashes
- 10-second throttle interval (prevents rapid restart loops)
- 30-second graceful shutdown timeout

### Optimized Settings
- **Production Mode:** Enabled
- **Minimal Warmup:** Enabled (fast startup)
- **Background Cleanup:** Enabled
- **Performance Profile:** Optimized

---

## Service Management

### Check Status

```bash
# Check if service is loaded
launchctl list | grep com.kokoro.tts

# View service properties
launchctl list com.kokoro.tts
```

### View Logs

```bash
# View service output
tail -f logs/service.log

# View errors
tail -f logs/service.error.log

# View both
tail -f logs/service.log logs/service.error.log
```

### Manual Control

```bash
# Stop service (until next login)
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.plist

# Start service manually
launchctl load ~/Library/LaunchAgents/com.kokoro.tts.plist

# Restart service
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.plist && \
launchctl load ~/Library/LaunchAgents/com.kokoro.tts.plist
```

### Check Service Health

```bash
# Health check
curl http://localhost:8000/health

# Status check
curl http://localhost:8000/status | python3 -m json.tool
```

---

## Configuration

### Environment Variables

The service uses these optimized settings:

```bash
KOKORO_PRODUCTION=true
KOKORO_MINIMAL_WARMUP=true
KOKORO_ENABLE_COLD_START_WARMUP=false
KOKORO_DEV_PERFORMANCE_PROFILE=optimized
```

### Customize Service

Edit `scripts/run_service.sh` to customize:
- Port number
- Host address
- Environment variables
- Log level

Edit `deploy/com.kokoro.tts.plist` (before installation) to customize:
- Auto-restart behavior
- Throttle intervals
- Working directory
- Environment variables

---

## Service Startup Time

With optimizations enabled:
- **Service Ready:** ~10 seconds after login
- **Background Optimization:** Completes in background
- **First Request:** May be slower (~2s) until background warming completes
- **Subsequent Requests:** Fast (3-4ms TTFA)

---

## Troubleshooting

### Service Won't Start

1. **Check logs:**
   ```bash
   tail -100 logs/service.error.log
   ```

2. **Check virtual environment:**
   ```bash
   test -f .venv/bin/activate && echo "✅ Virtual env exists" || echo "❌ Virtual env missing"
   ```

3. **Check permissions:**
   ```bash
   ls -la scripts/run_service.sh
   chmod +x scripts/run_service.sh
   ```

### Service Keeps Restarting

Check error logs for the cause:
```bash
tail -f logs/service.error.log
```

Common issues:
- Missing dependencies
- Port already in use
- Permission issues
- Model file not found

### Port Already in Use

```bash
# Find process using port 8000
lsof -ti:8000

# Kill it
kill $(lsof -ti:8000)

# Or change port in run_service.sh
```

---

## Security Considerations

### Network Binding
- **Default:** `127.0.0.1` (localhost only)
- **Safe:** Only accessible from your Mac
- **Change:** Edit `scripts/run_service.sh` if needed

### Permissions
- Service runs as your user account
- No root privileges required
- Uses your user's virtual environment

### File Access
- Service has access to your project directory
- Logs stored in project directory
- No system-wide changes

---

## Comparison: Manual vs Service

### Manual Start
- ✅ Full control
- ✅ Easy to debug
- ❌ Must remember to start
- ❌ Stops when terminal closes
- ❌ Doesn't restart on crash

### Launch Agent Service
- ✅ Starts automatically
- ✅ Always available
- ✅ Auto-restarts on crash
- ✅ Runs in background
- ⚠️ Must restart to apply changes
- ⚠️ Less visible debugging

---

## Best Practices

### Development
- Use manual start (`./start_development.sh`) for development
- Service is optimized for production use

### Production
- Use Launch Agent for always-on availability
- Monitor logs regularly
- Set up log rotation if needed

### Updating Service
1. Stop service: `launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.plist`
2. Make changes to code
3. Restart service: `launchctl load ~/Library/LaunchAgents/com.kokoro.tts.plist`

---

## Integration with Raycast

The Raycast extension will automatically connect to the service:
- **Port:** 8000 (default)
- **Health Check:** `http://localhost:8000/health`
- **TTS Endpoint:** `http://localhost:8000/v1/audio/speech`

Since the service is always running, Raycast requests will:
- ✅ Be instant (no startup delay)
- ✅ Use optimized production settings
- ✅ Benefit from background warming

---

## Next Steps

1. ✅ Install service: `./scripts/install_service.sh`
2. ✅ Verify it's running: `curl http://localhost:8000/health`
3. ✅ Test Raycast integration
4. ✅ Monitor logs for first few days
5. ✅ Set up log rotation if needed

---

*The service will start automatically on your next login!*




