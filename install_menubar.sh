#!/bin/bash
# Kokoro TTS Menu Bar App - Installation Script
# Builds and installs the menu bar app and LaunchAgents

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="KokoroTTS"
APP_DIR="$SCRIPT_DIR/KokoroTTS"
BUILD_DIR="$APP_DIR/.build/release"
INSTALL_DIR="/Applications"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/Library/Logs/kokoro"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kokoro TTS Menu Bar App - Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Build the app
echo -e "${YELLOW}Step 1: Building menu bar app...${NC}"
cd "$APP_DIR"
swift build -c release
echo -e "${GREEN}Build complete${NC}"
echo ""

# Step 2: Create app bundle
echo -e "${YELLOW}Step 2: Creating app bundle...${NC}"
APP_BUNDLE="$BUILD_DIR/${APP_NAME}.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy executable
cp "$BUILD_DIR/$APP_NAME" "$MACOS_DIR/"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>KokoroTTS</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.kokoro.tts-menubar</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Kokoro TTS</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.1.0</string>
    <key>CFBundleVersion</key>
    <string>2</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMainStoryboardFile</key>
    <string></string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSUserNotificationsUsageDescription</key>
    <string>Kokoro TTS needs to display notifications about service status.</string>
</dict>
</plist>
PLIST

echo -e "${GREEN}App bundle created${NC}"
echo ""

# Step 3: Install app
echo -e "${YELLOW}Step 3: Installing app to /Applications...${NC}"
rm -rf "$INSTALL_DIR/${APP_NAME}.app"
cp -R "$APP_BUNDLE" "$INSTALL_DIR/"
echo -e "${GREEN}App installed to /Applications/${APP_NAME}.app${NC}"
echo ""

# Step 4: Create logs directory
echo -e "${YELLOW}Step 4: Creating logs directory...${NC}"
mkdir -p "$LOGS_DIR"
echo -e "${GREEN}Logs directory: $LOGS_DIR${NC}"
echo ""

# Step 5: Install LaunchAgents (resolve template placeholders)
echo -e "${YELLOW}Step 5: Installing LaunchAgents...${NC}"
mkdir -p "$LAUNCH_AGENTS_DIR"

# Unload existing agents if present
launchctl unload "$LAUNCH_AGENTS_DIR/com.kokoro.tts-api.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.kokoro.audio-daemon.plist" 2>/dev/null || true

# Detect paths for template substitution
NODE_BIN=$(which node 2>/dev/null || echo "/usr/local/bin/node")
NODE_DIR=$(dirname "$NODE_BIN")
ESPEAK_DATA_PATH=$("$SCRIPT_DIR/.venv/bin/python" -c "import espeakng_loader; print(espeakng_loader.get_data_path())" 2>/dev/null || echo "")

echo "  Project: $SCRIPT_DIR"
echo "  Node:    $NODE_BIN"
echo "  Espeak:  ${ESPEAK_DATA_PATH:-not found}"

# Generate plists from templates with resolved paths
for plist in com.kokoro.tts-api.plist com.kokoro.audio-daemon.plist; do
    sed -e "s|__PROJECT_DIR__|${SCRIPT_DIR}|g" \
        -e "s|__HOME__|${HOME}|g" \
        -e "s|__NODE_BIN__|${NODE_BIN}|g" \
        -e "s|__NODE_DIR__|${NODE_DIR}|g" \
        -e "s|__ESPEAK_DATA_PATH__|${ESPEAK_DATA_PATH}|g" \
        "$SCRIPT_DIR/launchagents/$plist" > "$LAUNCH_AGENTS_DIR/$plist"
done

echo -e "${GREEN}LaunchAgents installed (paths resolved for this machine)${NC}"
echo ""

# Step 6: Load LaunchAgents
echo -e "${YELLOW}Step 6: Loading LaunchAgents...${NC}"
launchctl load "$LAUNCH_AGENTS_DIR/com.kokoro.tts-api.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.kokoro.audio-daemon.plist"
echo -e "${GREEN}LaunchAgents loaded - services will start at login${NC}"
echo ""

# Step 7: Add app to Login Items (optional)
echo -e "${YELLOW}Step 7: Adding app to Login Items...${NC}"
osascript << 'APPLESCRIPT' 2>/dev/null || true
tell application "System Events"
    make login item at end with properties {path:"/Applications/KokoroTTS.app", hidden:false}
end tell
APPLESCRIPT
echo -e "${GREEN}App added to Login Items${NC}"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The following have been installed:"
echo "  - Menu bar app: /Applications/${APP_NAME}.app"
echo "  - LaunchAgents: ~/Library/LaunchAgents/com.kokoro.*.plist"
echo "  - Logs: ~/Library/Logs/kokoro/"
echo ""
echo "To start the menu bar app now, run:"
echo "  open /Applications/${APP_NAME}.app"
echo ""
echo "Services will auto-start at login."
echo ""

# Ask to start now
read -p "Start the menu bar app now? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    open "/Applications/${APP_NAME}.app"
    echo -e "${GREEN}Menu bar app started!${NC}"
fi
