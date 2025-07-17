# Debug Mode Guide

This document explains how to use the debug mode functionality in the Kokoro TTS system to control logging output.

## Overview

The debug mode allows you to control the verbosity of logging output. When debug mode is disabled, only important information, warnings, and errors are displayed. When enabled, additional debug information is shown to help with troubleshooting and development.

## Enabling Debug Mode

There are several ways to enable debug mode:

### 1. Command Line Flag

```bash
# Enable debug mode for the entire application
node your-script.js --debug

# Or use the short form
node your-script.js -d
```

### 2. Environment Variables

```bash
# Set DEBUG environment variable
DEBUG=true node your-script.js

# Or use 1 instead of true
DEBUG=1 node your-script.js

# Use Kokoro-specific debug flag
KOKORO_DEBUG=true node your-script.js
```

### 3. Development Mode

```bash
# Set NODE_ENV to development
NODE_ENV=development node your-script.js
```

## Logger Methods

The enhanced logger provides different methods for different types of output:

### Always Visible (Regardless of Debug Mode)

```typescript
// Important information
logger.consoleInfo("This always shows");

// Warnings
logger.consoleWarn("This always shows");

// Errors
logger.consoleError("This always shows");
```

### Debug Mode Only

```typescript
// Debug information (only shows when debug mode is enabled)
logger.consoleDebug("This only shows in debug mode");

// Structured debug logging
logger.debug("Structured debug message", { context: "data" });
```

## Examples

### Normal Mode Output

```bash
$ node test-debug-mode.js
🔧 Testing Debug Mode Functionality
=====================================
This is important information that always shows
This is a warning that always shows
This is an error that always shows
```

### Debug Mode Output

```bash
$ node test-debug-mode.js --debug
🔧 Testing Debug Mode Functionality
=====================================
This is important information that always shows
[DEBUG] This is debug information that only shows in debug mode
[DEBUG] Debug mode can be enabled with --debug flag or DEBUG=true
This is a warning that always shows
This is an error that always shows
```

## Audio Daemon Debug Output

The audio daemon has been updated to respect debug mode settings. When debug mode is disabled, you won't see:

- Buffer utilization messages
- Audio chunk processing details
- Sox/ffplay spawning information
- Detailed process communication

When debug mode is enabled, you'll see all the detailed information needed for troubleshooting audio issues.

## Best Practices

1. **Use `consoleInfo` for important status updates** that users need to see
2. **Use `consoleWarn` for warnings** that indicate potential issues
3. **Use `consoleError` for errors** that need immediate attention
4. **Use `consoleDebug` for detailed information** that's only needed during development or troubleshooting
5. **Use structured logging** (`logger.debug()`, `logger.info()`, etc.) for programmatic access to log data

## Testing Debug Mode

You can test the debug mode functionality using the provided test script:

```bash
# Test normal mode
node test-debug-mode.js

# Test debug mode
node test-debug-mode.js --debug
DEBUG=true node test-debug-mode.js
```

## Integration with Raycast

When using the Raycast extension, debug mode can be enabled by:

1. Setting environment variables before launching Raycast
2. Using the `--debug` flag when running the extension in development mode
3. Setting `NODE_ENV=development` in your development environment

## Troubleshooting

If debug output is not appearing when expected:

1. Check that debug mode is properly enabled using one of the methods above
2. Verify that the logger is being imported correctly
3. Ensure that `consoleDebug` is being used instead of `console.log` for debug information
4. Check that the `DebugModeManager` is properly initialized

## Migration Guide

To migrate existing code to use the new debug mode:

1. Replace `console.log()` calls with `logger.consoleDebug()` for debug information
2. Replace `console.log()` calls with `logger.consoleInfo()` for important information
3. Replace `console.warn()` calls with `logger.consoleWarn()`
4. Replace `console.error()` calls with `logger.consoleError()`
5. Use structured logging methods (`logger.debug()`, `logger.info()`, etc.) for programmatic access

Example migration:

```typescript
// Before
console.log("Debug info:", data);
console.log("Important info");

// After
logger.consoleDebug("Debug info:", data);
logger.consoleInfo("Important info");
``` 