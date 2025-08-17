#!/bin/bash

# Persistent Audio Daemon Startup Script
# Starts the persistent audio daemon as a background service

set -e

# Configuration
DAEMON_SCRIPT="bin/persistent-audio-daemon.js"
DEFAULT_PORT=8081
LOG_FILE="logs/persistent-daemon.log"
PID_FILE="logs/persistent-daemon.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if daemon is already running
check_daemon_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is dead
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# Function to stop existing daemon
stop_daemon() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        print_status "Stopping existing daemon (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 2
        if ps -p "$pid" > /dev/null 2>&1; then
            print_warning "Daemon not responding, force killing..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
        print_status "Daemon stopped"
    fi
}

# Function to start daemon
start_daemon() {
    local port=${1:-$DEFAULT_PORT}
    
    print_status "Starting persistent audio daemon on port $port..."
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Check if daemon script exists
    if [ ! -f "$DAEMON_SCRIPT" ]; then
        print_error "Daemon script not found: $DAEMON_SCRIPT"
        exit 1
    fi
    
    # Start daemon in background
    nohup node "$DAEMON_SCRIPT" --port="$port" > "$LOG_FILE" 2>&1 &
    local daemon_pid=$!
    
    # Save PID
    echo "$daemon_pid" > "$PID_FILE"
    
    print_status "Daemon started with PID: $daemon_pid"
    print_status "Log file: $LOG_FILE"
    print_status "PID file: $PID_FILE"
    
    # Wait a moment and check if daemon is running
    sleep 2
    if ps -p "$daemon_pid" > /dev/null 2>&1; then
        print_status "Daemon is running successfully"
        
        # Test health endpoint
        sleep 1
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            print_status "Health check passed"
        else
            print_warning "Health check failed, but daemon is running"
        fi
    else
        print_error "Failed to start daemon"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to show daemon status
show_status() {
    if check_daemon_running; then
        local pid=$(cat "$PID_FILE")
        print_status "Daemon is running (PID: $pid)"
        
        # Try to get status from daemon
        if curl -s "http://localhost:$DEFAULT_PORT/status" > /dev/null 2>&1; then
            print_status "Daemon is responding to requests"
        else
            print_warning "Daemon is running but not responding to requests"
        fi
    else
        print_status "Daemon is not running"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        print_error "Log file not found: $LOG_FILE"
    fi
}

# Main script logic
case "${1:-start}" in
    start)
        if check_daemon_running; then
            print_warning "Daemon is already running"
            show_status
        else
            start_daemon "$2"
        fi
        ;;
    stop)
        if check_daemon_running; then
            stop_daemon
        else
            print_status "Daemon is not running"
        fi
        ;;
    restart)
        stop_daemon
        sleep 1
        start_daemon "$2"
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    health)
        if curl -s "http://localhost:$DEFAULT_PORT/health" > /dev/null 2>&1; then
            print_status "Daemon is healthy"
            exit 0
        else
            print_error "Daemon is not responding"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|health} [port]"
        echo ""
        echo "Commands:"
        echo "  start [port]   Start the persistent audio daemon (default port: $DEFAULT_PORT)"
        echo "  stop           Stop the daemon"
        echo "  restart [port] Restart the daemon"
        echo "  status         Show daemon status"
        echo "  logs           Show daemon logs (follow mode)"
        echo "  health         Check daemon health"
        echo ""
        echo "Examples:"
        echo "  $0 start           # Start on default port $DEFAULT_PORT"
        echo "  $0 start 8082      # Start on port 8082"
        echo "  $0 restart         # Restart on default port"
        echo "  $0 logs            # Show live logs"
        exit 1
        ;;
esac
