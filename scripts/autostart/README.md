# Kokoro TTS Auto-Start Setup

This directory contains scripts and configuration files to automatically start the Kokoro TTS service when your Mac boots up or when you log in.

## Quick Start

### Method 1: Login Items (Recommended for macOS)
```bash
# Add to Login Items (starts when you log in)
./scripts/autostart/setup-login-item.sh

# Remove from Login Items
./scripts/autostart/remove-login-item.sh
```

### Method 2: Launchd Service
```bash
# Enable Auto-Start (User-level)
./scripts/autostart/enable-autostart.sh user

# Check Status
./scripts/autostart/status-autostart.sh

# Disable Auto-Start
./scripts/autostart/disable-autostart.sh user
```

## Auto-Start Options

### Login Items Method (Recommended for macOS)
- **When it starts**: When you log in to your user account
- **Permissions**: No special permissions required
- **Location**: System Preferences > Users & Groups > Login Items
- **Command**: `./setup-login-item.sh`

**Advantages:**
- No root privileges required
- Works reliably on macOS
- Easy to manage through System Preferences
- No security restrictions
- Can be easily enabled/disabled through GUI

**How it works:**
- Adds a script to your macOS Login Items
- Script runs when you log in
- Starts Kokoro TTS in the background
- Logs activity to `logs/login-startup.log`

### Launchd Service Method
- **When it starts**: When you log in to your user account
- **Permissions**: No sudo required
- **Location**: `~/Library/LaunchAgents/`
- **Command**: `./enable-autostart.sh user`

**Advantages:**
- No root privileges required
- Starts with your user session
- Easier to manage and debug
- Better security

### System-Level Auto-Start
- **When it starts**: When the system boots (before user login)
- **Permissions**: Requires sudo
- **Location**: `/Library/LaunchDaemons/`
- **Command**: `./enable-autostart.sh system`

**Advantages:**
- Starts even if no user is logged in
- Available immediately after boot

**Disadvantages:**
- Requires root privileges
- More complex to manage
- Potential security considerations

## Files Overview

### Core Scripts
- `kokoro-tts-login.sh` - Login item script that starts the service when you log in
- `setup-login-item.sh` - Adds Kokoro TTS to macOS Login Items
- `remove-login-item.sh` - Removes Kokoro TTS from macOS Login Items
- `kokoro-tts-startup.sh` - Launchd wrapper script (alternative method)
- `enable-autostart.sh` - Installs and enables launchd auto-start service
- `disable-autostart.sh` - Removes and disables launchd auto-start service
- `status-autostart.sh` - Shows current status of auto-start services

### Configuration Files
- `com.kokoro.tts.plist` - System-level launchd configuration
- `com.kokoro.tts.user.plist` - User-level launchd configuration

## How It Works

1. **Launchd Service**: macOS uses `launchd` to manage services. The `.plist` files define how and when to start the service.

2. **Wrapper Script**: The `kokoro-tts-startup.sh` script:
   - Sets up the proper environment
   - Activates the Python virtual environment
   - Configures temp directories
   - Waits for system resources to be available
   - Starts the production server

3. **Automatic Restart**: If the service crashes, `launchd` will automatically restart it.

4. **Logging**: All output is logged to `logs/autostart.log` and launchd-specific logs.

## Environment Variables

The auto-start service sets these environment variables:
- `KOKORO_AUTOSTART=true` - Indicates the service was started automatically
- `KOKORO_PRODUCTION=true` - Enables production optimizations
- `KOKORO_USER_SESSION=true` - Set for user-level services
- Proper `PATH` and `HOME` variables for the user

## Logging

### Auto-Start Logs
- **Main log**: `logs/autostart.log` - Contains startup messages and service output
- **User service**: `logs/launchd-user.out.log` and `logs/launchd-user.err.log`
- **System service**: `logs/launchd.out.log` and `logs/launchd.err.log`

### Viewing Logs
```bash
# View main auto-start log
tail -f logs/autostart.log

# View user service logs
tail -f logs/launchd-user.out.log
tail -f logs/launchd-user.err.log

# View system service logs (if using system-level)
tail -f logs/launchd.out.log
tail -f logs/launchd.err.log
```

## Troubleshooting

### Service Not Starting
1. Check if the service is loaded:
   ```bash
   launchctl list | grep kokoro
   ```

2. Check the logs for errors:
   ```bash
   ./scripts/autostart/status-autostart.sh
   ```

3. Verify the virtual environment exists:
   ```bash
   ls -la .venv/
   ```

### Port Conflicts
The startup script automatically checks for port conflicts and waits for ports to become available. If you're having issues:
1. Check what's using the ports:
   ```bash
   lsof -i:8000  # API server
   lsof -i:8081  # Audio daemon
   ```

2. Kill conflicting processes if needed:
   ```bash
   kill -9 $(lsof -t -i:8000)
   kill -9 $(lsof -t -i:8081)
   ```

### Permission Issues
- For user-level services: Ensure the script is executable and you have write access to `~/Library/LaunchAgents/`
- For system-level services: You'll need sudo privileges

### Virtual Environment Issues
Make sure the `.venv` directory exists and contains a properly set up Python environment:
```bash
# Check if virtual environment exists
ls -la .venv/

# If missing, run setup
./setup.sh
```

## Manual Service Management

### Using launchctl directly
```bash
# Load a service
launchctl load ~/Library/LaunchAgents/com.kokoro.tts.user.plist

# Unload a service
launchctl unload ~/Library/LaunchAgents/com.kokoro.tts.user.plist

# List all services
launchctl list | grep kokoro

# Start a service immediately
launchctl start com.kokoro.tts.user

# Stop a service
launchctl stop com.kokoro.tts.user
```

## Security Considerations

### User-Level Service (Recommended)
- Runs with your user privileges
- No root access required
- Safer and easier to manage

### System-Level Service
- Runs with system privileges
- Requires sudo to install
- Consider security implications

## Best Practices

1. **Use user-level auto-start** unless you specifically need system-level
2. **Test the service** after enabling auto-start
3. **Monitor logs** regularly to ensure the service is running properly
4. **Keep the project updated** - the auto-start will use the current version
5. **Use the management scripts** instead of manually editing plist files

## Uninstalling

To completely remove auto-start:
```bash
# Disable all auto-start services
./scripts/autostart/disable-autostart.sh all

# Remove the autostart directory (optional)
rm -rf scripts/autostart/
```

## Support

If you encounter issues:
1. Check the logs first: `./scripts/autostart/status-autostart.sh`
2. Verify your setup: Ensure `.venv` exists and `./start_production.sh` works manually
3. Check system resources: Ensure you have enough disk space and memory
4. Review the troubleshooting section above
