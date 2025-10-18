#!/bin/bash
# Remove Kokoro TTS from Login Items
# This script removes Kokoro TTS from your macOS Login Items
# Author: @darianrosebrook

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Remove Kokoro TTS from Login Items${NC}"
echo "=================================="

# Check if osascript is available
if ! command -v osascript &> /dev/null; then
    echo -e "${RED}Error: osascript not found. This script requires macOS.${NC}"
    exit 1
fi

echo "Removing Kokoro TTS from Login Items..."

# Create an AppleScript to remove the login item
cat > /tmp/remove_login_item.applescript << 'EOF'
tell application "System Events"
    -- Get the current login items
    set loginItems to login items
    
    -- Find and remove Kokoro TTS login item
    set kokoroFound to false
    repeat with loginItem in loginItems
        if name of loginItem contains "Kokoro TTS" then
            delete loginItem
            set kokoroFound to true
            exit repeat
        end if
    end repeat
    
    if kokoroFound then
        display dialog "Kokoro TTS has been removed from your Login Items." buttons {"OK"} default button "OK"
    else
        display dialog "Kokoro TTS was not found in your Login Items." buttons {"OK"} default button "OK"
    end if
end tell
EOF

# Execute the AppleScript
osascript /tmp/remove_login_item.applescript

# Clean up
rm -f /tmp/remove_login_item.applescript

echo -e "${GREEN}✅ Removal complete!${NC}"
echo ""
echo "Kokoro TTS will no longer start automatically when you log in."
echo "You can still start it manually using: ./start_production.sh"
