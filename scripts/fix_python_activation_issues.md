# Fix for Repeated Python Environment Activations

## Problem
Python virtual environments are being activated repeatedly in terminals, even after disabling the Python extension's auto-activation feature.

## Root Causes Identified

1. **Python Extension Settings**: The `ms-python.python` extension was trying to auto-activate environments
2. **Terminal History Restoration**: Cursor's shell integration is restoring previous activation commands from history
3. **Extension Host Crashes**: Related to problematic extensions causing extension host restarts

## Solutions Applied

### 1. Disabled Problematic Extensions
- `ms-python.vscode-python-envs` (TypeError during deactivation)
- `redhat.vscode-xml` (Configuration warnings)

### 2. Disabled Python Auto-Activation
Added to `settings.json`:
```json
{
  "python.terminal.activateEnvInCurrentTerminal": false,
  "python.terminal.activateEnvironment": false,
  "python.createEnvironment.trigger": "off"
}
```

### 3. Killed Running Processes
- Stopped `pet server` processes (Python Environment Tools)

## Additional Steps

### Clear Terminal History
The "History restored" messages suggest Cursor is restoring old activation commands. To prevent this:

1. **Clear Cursor's terminal history**:
   - Open Command Palette (Cmd+Shift+P)
   - Run: "Terminal: Clear"
   - Or manually clear: `rm ~/.cursor/terminal-history/*` (if exists)

2. **Disable shell integration temporarily** (if issues persist):
   - Settings → Terminal → Integrated → Shell Integration: Disabled

### Manual Activation
When you need the virtual environment, manually activate it:
```bash
source venv/bin/activate
```

Or use the project's scripts that handle activation:
```bash
./start_development.sh
./start_production.sh
```

## Verification

After restarting Cursor, you should see:
- ✅ No more automatic `[PYTHON]` environment activations
- ✅ No more "extension host terminated unexpectedly" errors
- ✅ Terminals start cleanly without activation commands

## If Issues Persist

1. Check if `pet server` processes restart: `ps aux | grep "pet server"`
2. Check extension host logs: `~/Library/Application Support/Cursor/logs/*/exthost/exthost.log`
3. Consider disabling the Python extension entirely if not needed for basic editing



