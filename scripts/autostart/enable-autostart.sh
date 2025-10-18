#!/bin/bash
# Enable Kokoro TTS Auto-Start
# This script installs the launchd service to start Kokoro TTS automatically
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

echo -e "${BLUE}Kokoro TTS Auto-Start Setup${NC}"
echo "=================================="

# Check if running as root (not recommended for user services)
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Consider using user-level auto-start instead.${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Function to show usage
show_usage() {
    echo "Usage: $0 [user|system]"
    echo ""
    echo "Options:"
    echo "  user    - Install user-level service (recommended, starts when you log in)"
    echo "  system  - Install system-level service (requires sudo, starts at boot)"
    echo ""
    echo "If no option is provided, user-level will be used by default."
}

# Parse arguments
MODE="user"
if [ $# -gt 0 ]; then
    case "$1" in
        "user"|"system")
            MODE="$1"
            ;;
        "-h"|"--help"|"help")
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option '$1'${NC}"
            show_usage
            exit 1
            ;;
    esac
fi

echo -e "${BLUE}Installing $MODE-level auto-start service...${NC}"

# Set up paths based on mode
if [ "$MODE" = "user" ]; then
    PLIST_SOURCE="$SCRIPT_DIR/com.kokoro.tts.user.plist"
    PLIST_NAME="com.kokoro.tts.user"
    LAUNCHD_DIR="$HOME/Library/LaunchAgents"
    SUDO_CMD=""
else
    PLIST_SOURCE="$SCRIPT_DIR/com.kokoro.tts.plist"
    PLIST_NAME="com.kokoro.tts"
    LAUNCHD_DIR="/Library/LaunchDaemons"
    SUDO_CMD="sudo"
fi

# Check if plist file exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo -e "${RED}Error: Plist file not found: $PLIST_SOURCE${NC}"
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
if [ "$MODE" = "user" ]; then
    mkdir -p "$LAUNCHD_DIR"
fi

# Copy plist file to LaunchAgents/LaunchDaemons directory
PLIST_DEST="$LAUNCHD_DIR/$PLIST_NAME.plist"

echo "Copying plist file..."
echo "  From: $PLIST_SOURCE"
echo "  To:   $PLIST_DEST"

$SUDO_CMD cp "$PLIST_SOURCE" "$PLIST_DEST"

# Set proper permissions
if [ "$MODE" = "system" ]; then
    $SUDO_CMD chown root:wheel "$PLIST_DEST"
    $SUDO_CMD chmod 644 "$PLIST_DEST"
else
    chmod 644 "$PLIST_DEST"
fi

# Load the service
echo "Loading service..."
$SUDO_CMD launchctl load "$PLIST_DEST"

# Check if service is loaded
if launchctl list | grep -q "$PLIST_NAME"; then
    echo -e "${GREEN}✅ Auto-start service installed and loaded successfully!${NC}"
    echo ""
    echo "Service details:"
    echo "  Name: $PLIST_NAME"
    echo "  Type: $MODE-level"
    echo "  Status: $(launchctl list | grep "$PLIST_NAME" | awk '{print $1}')"
    echo ""
    echo "The Kokoro TTS service will now start automatically:"
    if [ "$MODE" = "user" ]; then
        echo "  - When you log in to your user account"
    else
        echo "  - When the system boots up"
    fi
    echo "  - And restart automatically if it crashes"
    echo ""
    echo "To check service status: launchctl list | grep $PLIST_NAME"
    echo "To view logs: tail -f $PROJECT_ROOT/logs/autostart.log"
    echo "To disable: $SCRIPT_DIR/disable-autostart.sh $MODE"
else
    echo -e "${RED}❌ Failed to load service. Check the logs for details.${NC}"
    exit 1
fi
