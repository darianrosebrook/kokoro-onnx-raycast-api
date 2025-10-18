# Kokoro TTS Auto-Start Setup Complete

## ✅ Setup Successful

Your Kokoro TTS service is now configured to start automatically when you log in to your Mac!

## What Was Set Up

### Login Items Method (Active)
- **Status**: ✅ Enabled
- **Method**: macOS Login Items
- **Script**: `scripts/autostart/kokoro-tts-login.sh`
- **Logs**: `logs/login-startup.log`

### Alternative: Launchd Service (Available)
- **Status**: Available but not active
- **Method**: macOS launchd service
- **Scripts**: `scripts/autostart/enable-autostart.sh` / `disable-autostart.sh`

## How It Works

1. **When you log in**: The macOS Login Items system automatically runs the Kokoro TTS startup script
2. **Environment setup**: The script activates your Python virtual environment and sets up all necessary environment variables
3. **Service startup**: Kokoro TTS starts in the background with production optimizations
4. **Automatic restart**: If the service crashes, you can restart it manually or re-login

## Verification

### Check if it's working:
```bash
# Check if services are running
./scripts/autostart/status-autostart.sh

# View startup logs
tail -f logs/login-startup.log
```

### Manual verification:
1. Go to **System Preferences > Users & Groups > Login Items**
2. You should see **"Kokoro TTS"** in the list
3. The service should start automatically when you log in

## Management Commands

### Login Items Method (Current)
```bash
# Remove from Login Items
./scripts/autostart/remove-login-item.sh

# Re-add to Login Items
./scripts/autostart/setup-login-item.sh
```

### Launchd Service Method (Alternative)
```bash
# Enable launchd service
./scripts/autostart/enable-autostart.sh user

# Disable launchd service
./scripts/autostart/disable-autostart.sh user

# Check status
./scripts/autostart/status-autostart.sh
```

## Logs and Monitoring

### Log Files
- **Login startup**: `logs/login-startup.log`
- **Auto-start**: `logs/autostart.log` (if using launchd method)
- **Launchd logs**: `logs/launchd-user.out.log` and `logs/launchd-user.err.log`

### View Live Logs
```bash
# Login item logs
tail -f logs/login-startup.log

# All logs
tail -f logs/*.log
```

## Troubleshooting

### Service Not Starting
1. Check if it's in Login Items: System Preferences > Users & Groups > Login Items
2. Check logs: `tail -f logs/login-startup.log`
3. Verify virtual environment: `ls -la .venv/`
4. Test manual start: `./start_production.sh`

### Port Conflicts
```bash
# Check what's using the ports
lsof -i:8000  # API server
lsof -i:8081  # Audio daemon

# Kill conflicting processes if needed
kill -9 $(lsof -t -i:8000)
kill -9 $(lsof -t -i:8081)
```

### Remove Auto-Start
```bash
# Remove from Login Items
./scripts/autostart/remove-login-item.sh

# Or disable launchd service
./scripts/autostart/disable-autostart.sh user
```

## Benefits

✅ **Automatic startup** - No need to remember to start the service  
✅ **Background operation** - Runs without keeping terminal/IDE open  
✅ **Production ready** - Uses optimized production settings  
✅ **Easy management** - Simple scripts to enable/disable  
✅ **Comprehensive logging** - Full visibility into startup process  
✅ **Crash recovery** - Can restart manually if needed  

## Next Steps

1. **Test the setup**: Log out and log back in to verify auto-start works
2. **Monitor logs**: Check `logs/login-startup.log` for any issues
3. **Verify service**: Ensure Kokoro TTS is accessible at `http://localhost:8000`
4. **Raycast integration**: Your Raycast extension should now work without manual server startup

## Support

If you encounter any issues:
1. Check the logs first: `tail -f logs/login-startup.log`
2. Verify the setup: `./scripts/autostart/status-autostart.sh`
3. Test manual startup: `./start_production.sh`
4. Review the troubleshooting section above

---

**Setup completed on**: $(date)  
**Method**: macOS Login Items  
**Status**: ✅ Active and ready
