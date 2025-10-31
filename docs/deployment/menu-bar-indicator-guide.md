# macOS Menu Bar Status Indicator

**Status:** ✅ Ready  
**Purpose:** Visual status indicator and quick controls in macOS menu bar

---

## Overview

A lightweight menu bar app that provides:
-  **Status Indicator**: Visual indicator showing service health
- 🟢 **Online**: Service running and healthy
- ⚠️ **Warning**: Service running but unhealthy
-  **Stopped**: Service not running

- **Quick Controls**: Start/Stop/Restart service
- **Health Check**: View detailed service status
- **Log Access**: Quick access to service logs
- **Service URL**: Open API documentation

---

## Features

### Visual Status Indicator
- **🟢 Green**: Service online and healthy
- **⚠️ Yellow**: Service running but issues detected
- ** Red**: Service stopped

### Menu Options
- **Status**: Current service status
- **Start Service**: Start the service
- **Stop Service**: Stop the service
- **Restart Service**: Restart the service
- **Health Check**: Detailed health information
- **View Logs**: Open logs in Console.app
- **Open Service URL**: Open API docs in browser
- **Quit**: Quit menu bar app

---

## Installation

### Option 1: Install with Service (Recommended)

```bash
./scripts/install_service.sh
# When prompted, answer 'y' to install menu bar indicator
```

### Option 2: Install Menu Bar Only

```bash
# Install rumps library
python3 -m pip install rumps --user

# Start menu bar app
./scripts/start_menubar.sh
```

### Option 3: Manual Start

```bash
python3 scripts/menubar_status.py
```

---

## Menu Bar Appearance

The menu bar will show:
- ** Kokoro** - Service is online and healthy
- **⚠️ Kokoro** - Service running but unhealthy
- ** Kokoro** - Service stopped

---

## Functionality

### Status Updates
- Updates relevant 5 seconds automatically
- Checks service status via launchctl
- Checks health via HTTP endpoint

### Service Control
- Start/Stop/Restart via menu bar
- Shows notifications for actions
- Updates status immediately

### Health Monitoring
- Checks `/health` endpoint
- Checks `/status` endpoint for details
- Displays provider, model status, request count

### Log Access
- Opens logs in macOS Console.app
- Shows both service.log and service.error.log
- Easy debugging access

---

## Dependencies

### Required
- **rumps**: macOS menu bar library
- **Python 3**: Python 3.7+

### Installation
```bash
python3 -m pip install rumps --user
```

---

## Launch Agent Integration

The menu bar app can be installed as a Launch Agent to start automatically:

```bash
# Menu bar will start with service installation
./scripts/install_service.sh

# Or install menu bar separately
./scripts/install_service_with_menubar.sh
```

---

## Configuration

### Customize Service URL
Edit `scripts/menubar_status.py`:
```python
SERVICE_URL = "http://localhost:8000"  # Change if needed
```

### Customize Update Interval
Edit `scripts/menubar_status.py`:
```python
time.sleep(5)  # Update relevant 5 seconds
```

---

## Troubleshooting

### Menu Bar App Won't Start

1. **Check rumps installation:**
   ```bash
   python3 -c "import rumps; print('✅ rumps installed')"
   ```

2. **Install rumps:**
   ```bash
   python3 -m pip install rumps --user
   ```

3. **Check Python version:**
   ```bash
   python3 --version  # Should be 3.7+
   ```

### Menu Bar App Not Showing

1. **Check if it's running:**
   ```bash
   ps aux | grep menubar_status
   ```

2. **Check menu bar:**
   - Look for " Kokoro" or " Kokoro" in menu bar
   - May be hidden behind other menu bar items

3. **Restart menu bar app:**
   ```bash
   pkill -f menubar_status
   ./scripts/start_menubar.sh
   ```

### Status Not Updating

1. **Check service is running:**
   ```bash
   launchctl list | grep com.kokoro.tts
   ```

2. **Check health endpoint:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Restart menu bar app:**
   - Quit and restart the menu bar app
   - Or restart the Launch Agent

---

## Uninstallation

### Remove Menu Bar Launch Agent

```bash
# Unload menu bar agent
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.menubar.plist

# Remove plist
rm ~/Library/LaunchAgents/com.kokoro.tts.menubar.plist

# Quit running menu bar app
pkill -f menubar_status
```

---

## Benefits

### For Users
- ✅ Visual status at a glance
- ✅ Quick service control
- ✅ Easy log access
- ✅ Health monitoring

### For Developers
- ✅ Service status visibility
- ✅ Quick troubleshooting
- ✅ Easy service management
- ✅ No terminal needed

---

## Screenshots

### Menu Bar Status
```
 Kokoro 
  Status: 🟢 Running | Health: 🟢 Online
  
  Start Service
  Stop Service
  Restart Service
  
  Health Check
  View Logs
  Open Service URL
  
  Quit
```

---

## Next Steps

1. ✅ Menu bar app created
2. ✅ Installation script updated
3. ⏳ Install service: `./scripts/install_service.sh`
4. ⏳ Test menu bar functionality
5. ⏳ Customize as needed

---

*The menu bar app provides a convenient way to monitor and control the Kokoro TTS service!*




