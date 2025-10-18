#!/bin/bash
# Check Kokoro TTS Auto-Start Status
# This script shows the current status of auto-start services
# Author: @darianrosebrook

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${BLUE}Kokoro TTS Auto-Start Status${NC}"
echo "=============================="

# Function to check service status
check_service() {
    local service_name=$1
    local service_type=$2
    local plist_path=$3
    
    echo -e "${CYAN}$service_type Service: $service_name${NC}"
    echo "----------------------------------------"
    
    # Check if plist file exists
    if [ -f "$plist_path" ]; then
        echo -e "Plist file: ${GREEN}✅ Found${NC} ($plist_path)"
    else
        echo -e "Plist file: ${RED}❌ Not found${NC}"
        return
    fi
    
    # Check if service is loaded
    if launchctl list | grep -q "$service_name"; then
        local status=$(launchctl list | grep "$service_name" | awk '{print $1}')
        if [ "$status" = "-" ]; then
            echo -e "Service status: ${GREEN}✅ Loaded and running${NC}"
        else
            echo -e "Service status: ${YELLOW}⚠️  Loaded but not running (PID: $status)${NC}"
        fi
    else
        echo -e "Service status: ${RED}❌ Not loaded${NC}"
    fi
    
    echo ""
}

# Check user-level service
USER_PLIST="$HOME/Library/LaunchAgents/com.kokoro.tts.user.plist"
check_service "com.kokoro.tts.user" "User-level" "$USER_PLIST"

# Check system-level service
SYSTEM_PLIST="/Library/LaunchDaemons/com.kokoro.tts.plist"
check_service "com.kokoro.tts" "System-level" "$SYSTEM_PLIST"

# Check if Kokoro TTS is currently running
echo -e "${CYAN}Current Service Status${NC}"
echo "----------------------"

# Check if the API server is running
if lsof -i:8000 >/dev/null 2>&1; then
    api_pid=$(lsof -t -i:8000)
    echo -e "API Server (port 8000): ${GREEN}✅ Running${NC} (PID: $api_pid)"
else
    echo -e "API Server (port 8000): ${RED}❌ Not running${NC}"
fi

# Check if audio daemon is running
if lsof -i:8081 >/dev/null 2>&1; then
    daemon_pid=$(lsof -t -i:8081)
    echo -e "Audio Daemon (port 8081): ${GREEN}✅ Running${NC} (PID: $daemon_pid)"
else
    echo -e "Audio Daemon (port 8081): ${RED}❌ Not running${NC}"
fi

echo ""

# Show recent logs
echo -e "${CYAN}Recent Auto-Start Logs${NC}"
echo "----------------------"
AUTOSTART_LOG="$PROJECT_ROOT/logs/autostart.log"

if [ -f "$AUTOSTART_LOG" ]; then
    echo "Last 10 lines from autostart.log:"
    tail -10 "$AUTOSTART_LOG" | sed 's/^/  /'
else
    echo -e "${YELLOW}No autostart.log found${NC}"
fi

echo ""

# Show launchd logs
echo -e "${CYAN}Launchd Service Logs${NC}"
echo "---------------------"

# Check user service logs
USER_OUT_LOG="$PROJECT_ROOT/logs/launchd-user.out.log"
USER_ERR_LOG="$PROJECT_ROOT/logs/launchd-user.err.log"

if [ -f "$USER_OUT_LOG" ] || [ -f "$USER_ERR_LOG" ]; then
    echo "User service logs:"
    if [ -f "$USER_OUT_LOG" ]; then
        echo "  Output: $(wc -l < "$USER_OUT_LOG") lines"
        echo "  Last line: $(tail -1 "$USER_OUT_LOG")"
    fi
    if [ -f "$USER_ERR_LOG" ]; then
        echo "  Errors: $(wc -l < "$USER_ERR_LOG") lines"
        if [ -s "$USER_ERR_LOG" ]; then
            echo "  Last error: $(tail -1 "$USER_ERR_LOG")"
        fi
    fi
else
    echo -e "${YELLOW}No user service logs found${NC}"
fi

# Check system service logs
SYSTEM_OUT_LOG="$PROJECT_ROOT/logs/launchd.out.log"
SYSTEM_ERR_LOG="$PROJECT_ROOT/logs/launchd.err.log"

if [ -f "$SYSTEM_OUT_LOG" ] || [ -f "$SYSTEM_ERR_LOG" ]; then
    echo "System service logs:"
    if [ -f "$SYSTEM_OUT_LOG" ]; then
        echo "  Output: $(wc -l < "$SYSTEM_OUT_LOG") lines"
        echo "  Last line: $(tail -1 "$SYSTEM_OUT_LOG")"
    fi
    if [ -f "$SYSTEM_ERR_LOG" ]; then
        echo "  Errors: $(wc -l < "$SYSTEM_ERR_LOG") lines"
        if [ -s "$SYSTEM_ERR_LOG" ]; then
            echo "  Last error: $(tail -1 "$SYSTEM_ERR_LOG")"
        fi
    fi
else
    echo -e "${YELLOW}No system service logs found${NC}"
fi

echo ""
echo -e "${BLUE}Management Commands${NC}"
echo "-------------------"
echo "Enable auto-start:    $SCRIPT_DIR/enable-autostart.sh [user|system]"
echo "Disable auto-start:   $SCRIPT_DIR/disable-autostart.sh [user|system|all]"
echo "Check status:         $SCRIPT_DIR/status-autostart.sh"
echo "View live logs:       tail -f $PROJECT_ROOT/logs/autostart.log"
