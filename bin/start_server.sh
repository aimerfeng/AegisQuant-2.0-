#!/bin/bash
# ============================================================================
# Titan-Quant Server Startup Script (Linux/Mac)
# ============================================================================
# This script starts the Titan-Quant backend server (Python daemon).
# The server provides WebSocket communication for the UI client.
#
# Usage:
#   ./start_server.sh [options]
#
# Options:
#   --host HOST     Server host address (default: 127.0.0.1)
#   --port PORT     Server port number (default: 8765)
#   --debug         Enable debug logging
#   --daemon        Run as background daemon
#   --help          Show this help message
# ============================================================================

set -e

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of bin/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Default configuration
HOST="127.0.0.1"
PORT="8765"
DEBUG=""
DAEMON=""
VENV_DIR=".venv"
PID_FILE="logs/server.pid"
LOG_FILE="logs/server.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show help message
show_help() {
    echo ""
    echo "Titan-Quant Server Startup Script"
    echo "=================================="
    echo ""
    echo "Usage: ./start_server.sh [options]"
    echo ""
    echo "Options:"
    echo "  --host HOST     Server host address (default: 127.0.0.1)"
    echo "  --port PORT     Server port number (default: 8765)"
    echo "  --debug         Enable debug logging"
    echo "  --daemon        Run as background daemon"
    echo "  --stop          Stop the running daemon"
    echo "  --status        Check daemon status"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start_server.sh"
    echo "  ./start_server.sh --port 9000"
    echo "  ./start_server.sh --host 0.0.0.0 --port 8765 --debug"
    echo "  ./start_server.sh --daemon"
    echo "  ./start_server.sh --stop"
    echo ""
    exit 0
}

# Stop the daemon
stop_daemon() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            print_info "Stopping Titan-Quant server (PID: $PID)..."
            kill "$PID"
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                print_warn "Server did not stop gracefully, forcing..."
                kill -9 "$PID"
            fi
            rm -f "$PID_FILE"
            print_success "Server stopped."
        else
            print_warn "Server is not running (stale PID file)."
            rm -f "$PID_FILE"
        fi
    else
        print_warn "No PID file found. Server may not be running."
    fi
    exit 0
}

# Check daemon status
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            print_success "Server is running (PID: $PID)"
            exit 0
        else
            print_warn "Server is not running (stale PID file)"
            exit 1
        fi
    else
        print_info "Server is not running"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        --daemon)
            DAEMON="true"
            shift
            ;;
        --stop)
            stop_daemon
            ;;
        --status)
            check_status
            ;;
        --help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            ;;
    esac
done

echo ""
echo "============================================"
echo "  Titan-Quant Server Startup"
echo "============================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH."
        echo "Please install Python 3.10+ from https://www.python.org/downloads/"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
print_info "Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ -f "$VENV_DIR/bin/activate" ]; then
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # Git Bash on Windows
    print_info "Activating virtual environment (Windows)..."
    source "$VENV_DIR/Scripts/activate"
else
    print_warn "Virtual environment not found at $VENV_DIR"
    print_info "Using system Python installation"
fi

# Check if required packages are installed
if ! $PYTHON_CMD -c "import websockets" 2>/dev/null; then
    print_warn "Required packages not installed."
    print_info "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        print_error "Failed to install dependencies."
        exit 1
    fi
fi

# Create necessary directories
mkdir -p logs
mkdir -p database/bars
mkdir -p database/ticks
mkdir -p database/cache
mkdir -p reports

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT"
export TITAN_QUANT_HOST="$HOST"
export TITAN_QUANT_PORT="$PORT"

echo ""
print_info "Starting Titan-Quant Server..."
print_info "Host: $HOST"
print_info "Port: $PORT"
[ -n "$DEBUG" ] && print_info "Debug mode: enabled"
echo ""

if [ -n "$DAEMON" ]; then
    # Run as daemon
    print_info "Starting as background daemon..."
    
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            print_error "Server is already running (PID: $PID)"
            exit 1
        fi
    fi
    
    # Start daemon
    nohup $PYTHON_CMD -m core.server $DEBUG --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        print_success "Server started as daemon (PID: $(cat $PID_FILE))"
        print_info "Log file: $LOG_FILE"
        print_info "To stop: ./start_server.sh --stop"
    else
        print_error "Failed to start server. Check $LOG_FILE for details."
        exit 1
    fi
else
    # Run in foreground
    echo "Press Ctrl+C to stop the server."
    echo "============================================"
    echo ""
    
    $PYTHON_CMD -m core.server $DEBUG --host "$HOST" --port "$PORT"
    
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        print_error "Server exited with error code: $EXIT_CODE"
        exit $EXIT_CODE
    fi
    
    echo ""
    print_info "Server stopped."
fi
