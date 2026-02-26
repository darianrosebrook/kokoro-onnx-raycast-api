# Fix Extension Host Crashes When Running start_development.sh

## Problem
The extension host crashes unexpectedly when running `./start_development.sh`.

## Root Causes

1. **File Watching Conflicts**: The `--reload` flag on uvicorn uses file watching that conflicts with Cursor's extension file watchers
2. **Process Killing**: The `pkill -f` commands might be too aggressive and kill processes extensions are monitoring
3. **Python Extension Hooks**: Python command execution triggers extension hooks that can cause crashes

## Solutions Applied

### 1. Made Process Killing More Specific
- Changed from broad `pkill -f "uvicorn api.main:app"` to more specific patterns
- Added checks before killing to avoid false positives
- Only targets processes matching exact command patterns

### 2. Added Environment Variables to Suppress Hooks
- `VIRTUAL_ENV_DISABLE_PROMPT=1` - Suppresses venv prompt changes
- `CURSOR_AGENT_MODE=1` - Signals to extensions this is an agent/script context
- `PYTHONUNBUFFERED=1` - Prevents Python buffering issues

### 3. Made File Watching Safer
- Added `--reload-dir` flags to limit watched directories to `api/` and `models/`
- Added option to disable reload entirely with `DISABLE_RELOAD=1`

## Usage

### Normal Development (with reload)
```bash
./start_development.sh
```

### If Extension Host Crashes (disable reload)
```bash
DISABLE_RELOAD=1 ./start_development.sh
```

### Alternative: Manual Restart
If reload causes issues, you can manually restart the server:
1. Run without reload: `DISABLE_RELOAD=1 ./start_development.sh`
2. When you make changes, stop (Ctrl+C) and restart

## Additional Troubleshooting

### If Crashes Persist

1. **Check Extension Host Logs**:
   ```bash
   tail -f ~/Library/Application\ Support/Cursor/logs/*/window*/exthost/exthost.log
   ```

2. **Disable File Watching Extensions Temporarily**:
   - Settings → Extensions → Search for "file watcher" or "reload"
   - Disable any extensions that watch files

3. **Check for Port Conflicts**:
   ```bash
   lsof -i :8080
   lsof -i :8081
   ```

4. **Run in External Terminal**:
   - Open Terminal.app (not Cursor's integrated terminal)
   - Run `./start_development.sh` there
   - This isolates the process from Cursor's extension host

### Verify Fixes

After applying fixes, you should see:
- ✅ No extension host crashes when starting the script
- ✅ Server starts normally
- ✅ File changes still trigger reload (if reload is enabled)
- ✅ Processes are killed cleanly on shutdown

## Technical Details

### Process Killing Improvements
- **Before**: `pkill -f "uvicorn api.main:app"` - Too broad, could match anything
- **After**: Specific pattern matching with `pgrep` checks first

### File Watching
- **Before**: `--reload` watches entire project directory
- **After**: `--reload-dir api --reload-dir models` limits to specific directories
- This reduces conflicts with extension file watchers

### Python Execution
- Added environment variables to signal this is a script context
- Extensions should respect `CURSOR_AGENT_MODE` and avoid heavy hooks



