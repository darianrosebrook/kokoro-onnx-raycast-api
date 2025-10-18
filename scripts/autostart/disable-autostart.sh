#!/bin/bash
# Disable Kokoro TTS Auto-Start
# This script removes the launchd service to stop auto-starting Kokoro TTS
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

echo -e "${BLUE}Kokoro TTS Auto-Start Disable${NC}"
echo "================================="

# Function to show usage
show_usage() {
    echo "Usage: $0 [user|system|all]"
    echo ""
    echo "Options:"
    echo "  user    - Disable user-level service"
    echo "  system  - Disable system-level service"
    echo "  all     - Disable both user and system services"
    echo ""
    echo "If no option is provided, user-level will be disabled by default."
}

# Parse arguments
MODE="user"
if [ $# -gt 0 ]; then
    case "$1" in
        "user"|"system"|"all")
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

# Function to disable a specific service
disable_service() {
    local service_mode=$1
    local plist_name
    local launchd_dir
    local sudo_cmd
    
    if [ "$service_mode" = "user" ]; then
        plist_name="com.kokoro.tts.user"
        launchd_dir="$HOME/Library/LaunchAgents"
        sudo_cmd=""
    else
        plist_name="com.kokoro.tts"
        launchd_dir="/Library/LaunchDaemons"
        sudo_cmd="sudo"
    fi
    
    local plist_path="$launchd_dir/$plist_name.plist"
    
    echo -e "${BLUE}Disabling $service_mode-level service...${NC}"
    
    # Check if service is loaded
    if launchctl list | grep -q "$plist_name"; then
        echo "Unloading service: $plist_name"
        $sudo_cmd launchctl unload "$plist_path" 2>/dev/null || true
    else
        echo "Service $plist_name is not currently loaded"
    fi
    
    # Remove plist file if it exists
    if [ -f "$plist_path" ]; then
        echo "Removing plist file: $plist_path"
        $sudo_cmd rm -f "$plist_path"
        echo -e "${GREEN}✅ $service_mode-level service disabled successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Plist file not found: $plist_path${NC}"
    fi
}

# Disable services based on mode
case "$MODE" in
    "user")
        disable_service "user"
        ;;
    "system")
        disable_service "system"
        ;;
    "all")
        echo "Disabling all auto-start services..."
        disable_service "user"
        echo ""
        disable_service "system"
        ;;
esac

echo ""
echo -e "${GREEN}Auto-start disabled successfully!${NC}"
echo ""
echo "The Kokoro TTS service will no longer start automatically."
echo "You can still start it manually using: ./start_production.sh"
echo ""
echo "To re-enable auto-start: $SCRIPT_DIR/enable-autostart.sh"
