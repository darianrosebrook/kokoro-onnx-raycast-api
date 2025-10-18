#!/bin/bash
# Setup Kokoro TTS as Login Item
# This script adds Kokoro TTS to your macOS Login Items
# Author: @darianrosebrook

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${BLUE}Kokoro TTS Login Item Setup${NC}"
echo "============================="

# Check if osascript is available
if ! command -v osascript &> /dev/null; then
    echo -e "${RED}Error: osascript not found. This script requires macOS.${NC}"
    exit 1
fi

# Path to the login script
LOGIN_SCRIPT="$SCRIPT_DIR/kokoro-tts-login.sh"

# Check if login script exists
if [ ! -f "$LOGIN_SCRIPT" ]; then
    echo -e "${RED}Error: Login script not found: $LOGIN_SCRIPT${NC}"
    exit 1
fi

echo "Setting up Kokoro TTS as a login item..."
echo "Script path: $LOGIN_SCRIPT"

# Create an AppleScript to add the login item
cat > /tmp/add_login_item.applescript << 'EOF'
tell application "System Events"
    -- Get the current login items
    set loginItems to login items
    
    -- Check if Kokoro TTS is already in login items
    set kokoroExists to false
    repeat with loginItem in loginItems
        if name of loginItem contains "Kokoro TTS" then
            set kokoroExists to true
            exit repeat
        end if
    end repeat
    
    if kokoroExists then
        display dialog "Kokoro TTS is already in your Login Items." buttons {"OK"} default button "OK"
    else
        -- Add the login item
        make login item at end with properties {name:"Kokoro TTS", path:"SCRIPT_PATH", hidden:false}
        display dialog "Kokoro TTS has been added to your Login Items successfully!" buttons {"OK"} default button "OK"
    end if
end tell
EOF

# Replace the placeholder with the actual script path
sed -i '' "s|SCRIPT_PATH|$LOGIN_SCRIPT|g" /tmp/add_login_item.applescript

# Execute the AppleScript
echo "Adding to Login Items..."
osascript /tmp/add_login_item.applescript

# Clean up
rm -f /tmp/add_login_item.applescript

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Kokoro TTS will now start automatically when you log in."
echo ""
echo "To verify:"
echo "1. Go to System Preferences > Users & Groups > Login Items"
echo "2. You should see 'Kokoro TTS' in the list"
echo ""
echo "To remove from Login Items:"
echo "1. Go to System Preferences > Users & Groups > Login Items"
echo "2. Select 'Kokoro TTS' and click the '-' button"
echo ""
echo "Logs will be available at: $PROJECT_ROOT/logs/login-startup.log"
