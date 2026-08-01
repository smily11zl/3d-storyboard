#!/bin/bash
# Start both backend and frontend for Storyboard Shot Viewer
# Usage: ./start.sh
# Stop:  Ctrl+C

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

echo "========================================="
echo "  Storyboard Shot Viewer"
echo "========================================="

# Check venv
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual env not found. Run: python3.11 -m venv .venv && .venv/bin/pip install fastapi uvicorn httpx python-multipart pytest pytest-asyncio"
    exit 1
fi

# Check Blender
if ! command -v blender &>/dev/null; then
    echo "ERROR: Blender not found in PATH"
    exit 1
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend (unset PYTHONPATH to avoid Hermes venv leakage)
echo "[1/2] Starting backend on http://localhost:8000 ..."
cd "$SCRIPT_DIR"
unset PYTHONPATH
"$VENV_PYTHON" -m uvicorn backend.main:application --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
sleep 2

# Verify backend started
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend failed to start"
    exit 1
fi

# Start frontend
echo "[2/2] Starting frontend on http://localhost:5173 ..."
cd "$SCRIPT_DIR/frontend"
npx vite --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!
sleep 2

# Verify frontend started
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "ERROR: Frontend failed to start"
    kill "$BACKEND_PID" 2>/dev/null
    exit 1
fi

echo ""
echo "========================================="
echo "  Ready!"
echo "  Open: http://localhost:5173"
echo "  Press Ctrl+C to stop"
echo "========================================="

# Wait for either process to exit
wait
