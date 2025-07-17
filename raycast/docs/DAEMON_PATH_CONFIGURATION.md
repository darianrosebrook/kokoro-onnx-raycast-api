# Audio Daemon Path Configuration

## Overview

The Kokoro TTS Raycast extension uses an audio daemon for high-quality audio playback. This document explains how to configure the daemon path for different environments.

## Problem

When running the Raycast extension, the audio daemon script (`audio-daemon.js`) is located in the project directory, but the extension runs from a different location (`~/.config/raycast/extensions/`). This creates a path resolution issue.

## Solution

The extension now includes robust path resolution with multiple fallback options:

### 1. Configuration Priority

The daemon path is resolved in the following order:

1. **Configuration Parameter** - `config.daemonScriptPath`
2. **Environment Variable** - `KOKORO_AUDIO_DAEMON_PATH`
3. **Project Root Detection** - Automatic detection for Raycast extension environment
4. **Relative Paths** - Fallback to relative path resolution

### 2. Environment Variables

Set these environment variables to configure the daemon path:

```bash
# Set the project root directory
export KOKORO_PROJECT_ROOT="/path/to/kokoro-onnx"

# Set the daemon script path directly
export KOKORO_AUDIO_DAEMON_PATH="/path/to/kokoro-onnx/raycast/bin/audio-daemon.js"
```

### 3. Automatic Setup Script

Use the provided setup script to automatically configure the environment:

```bash
# Run the setup script
source raycast/setup-daemon-path.sh

# Or make it permanent by adding to your shell profile
echo 'source /path/to/kokoro-onnx/raycast/setup-daemon-path.sh' >> ~/.zshrc
```

### 4. Manual Configuration

If you prefer manual configuration, you can specify the daemon path in your TTS configuration:

```typescript
const config: TTSProcessorConfig = {
  // ... other config
  daemonScriptPath: "/path/to/kokoro-onnx/raycast/bin/audio-daemon.js",
};
```

## Path Resolution Logic

The extension automatically detects if it's running in a Raycast extension environment and adjusts the path resolution accordingly:

### Raycast Extension Environment Detection

```typescript
const isRaycastExtension = 
  process.cwd().includes('raycast/extensions') || 
  process.cwd().includes('.config/raycast');
```

### Project Root Detection

When running in a Raycast extension environment, the system looks for the project root in these locations:

1. `/Users/darianrosebrook/Desktop/Projects/kokoro-onnx`
2. `$KOKORO_PROJECT_ROOT` environment variable
3. `$HOME/Desktop/Projects/kokoro-onnx`
4. `$HOME/Projects/kokoro-onnx`

### Fallback Mechanisms

If the daemon script cannot be found, the system will:

1. Try to copy the daemon script to the extension directory
2. Use relative path resolution
3. Provide detailed error logging with all attempted paths

## Troubleshooting

### Error: "Audio daemon script not found in any expected location"

This error occurs when the extension cannot locate the audio daemon script. To resolve:

1. **Check the setup script**: Run `raycast/setup-daemon-path.sh`
2. **Verify environment variables**: Check that `KOKORO_PROJECT_ROOT` is set correctly
3. **Check file permissions**: Ensure the daemon script is executable
4. **Review logs**: Check the extension logs for detailed path resolution information

### Debugging Path Resolution

The extension provides detailed logging for path resolution. Look for log entries with:

- `"Starting daemon script path resolution"`
- `"Found daemon script"`
- `"Daemon script not found"`

### Manual Path Verification

You can manually verify the daemon script location:

```bash
# Check if the script exists
ls -la /path/to/kokoro-onnx/raycast/bin/audio-daemon.js

# Test the script
node /path/to/kokoro-onnx/raycast/bin/audio-daemon.js --help
```

## Best Practices

1. **Use the setup script**: Always use `raycast/setup-daemon-path.sh` for initial configuration
2. **Set environment variables**: Make the configuration permanent by adding to your shell profile
3. **Keep the daemon script updated**: Ensure the daemon script is up to date with the latest version
4. **Monitor logs**: Check extension logs for any path resolution issues

## File Locations

- **Daemon Script**: `raycast/bin/audio-daemon.js`
- **Setup Script**: `raycast/setup-daemon-path.sh`
- **Configuration**: `raycast/src/utils/tts/streaming/audio-playback-daemon.ts`
- **Type Definitions**: `raycast/src/utils/validation/tts-types.ts`

## Version History

- **v2.0.0**: Added robust path resolution with multiple fallback options
- **v2.0.1**: Added automatic project root detection for Raycast extension environment
- **v2.0.2**: Added setup script and environment variable support 