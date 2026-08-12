#!/bin/bash
# Start backend, frontend, and embedded Hermes Agent API server
# Usage: ./start.sh
# Stop:  Ctrl+C

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
HERMES_HOME_DIR="$SCRIPT_DIR/.hermes-home"

echo "========================================="
echo "  Storyboard Shot Viewer"
echo "========================================="

# Check venv
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual env not found. Run: python3.11 -m venv .venv && .venv/bin/pip install fastapi uvicorn httpx python-multipart pytest pytest-asyncio hermes-agent"
    exit 1
fi

# Check Blender
if ! command -v blender &>/dev/null; then
    echo "ERROR: Blender not found in PATH"
    exit 1
fi

# Check hermes CLI available in venv
if ! "$SCRIPT_DIR/.venv/bin/hermes" --version &>/dev/null; then
    echo "WARNING: hermes-agent not installed in venv. AI generation will be unavailable."
    echo "         Install with: $VENV_PYTHON -m pip install hermes-agent"
fi

# Cleanup on exit
# Agent gateway is a daemon-ish process: it survives plain SIGTERM (and may
# respawn), so kill the real PID from gateway.pid with SIGKILL as a fallback.
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -f "$HERMES_HOME_DIR/gateway.pid" ]; then
        GATEWAY_PID=$("$VENV_PYTHON" -c "import json;print(json.load(open('$HERMES_HOME_DIR/gateway.pid'))['pid'])" 2>/dev/null)
        if [ -n "$GATEWAY_PID" ]; then
            kill "$GATEWAY_PID" 2>/dev/null
            sleep 2
            kill -9 "$GATEWAY_PID" 2>/dev/null
        fi
    fi
    [ -n "$AGENT_PID" ] && kill -9 "$AGENT_PID" 2>/dev/null
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend (unset PYTHONPATH to avoid Hermes venv leakage)
echo "[1/3] Starting backend on http://localhost:8000 ..."
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

# Start embedded Hermes Agent API server
# - HERMES_HOME isolates config/skills/keys from any user-installed Hermes
# - env -i blocks WEIXIN_*/TERMINAL_CWD etc. leaking from the user's local
#   gateway (launchd) into platform detection, which would otherwise make
#   the agent gateway try to start a weixin platform and fail the policy check
# - --force bypasses the "gateway already running under launchd" guard; that
#   guard protects the same Hermes home, ours is a different home, so it is safe
# - clear any leftover gateway on 8643 first (Ctrl+C can leave a daemon-ish
#   gateway alive that would block this start with "already running")
echo "[2/3] Starting Agent API server on http://localhost:8643 ..."
lsof -ti:8643 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1
cd "$SCRIPT_DIR"
env -i \
  PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/Applications/Blender.app/Contents/MacOS" \
  HOME="$HOME" \
  HERMES_HOME="$HERMES_HOME_DIR" \
  LANG="${LANG:-en_US.UTF-8}" \
  "$SCRIPT_DIR/.venv/bin/hermes" gateway run --force &
AGENT_PID=$!
sleep 4

# Verify agent server started
if kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "Agent API server running (PID $AGENT_PID)"
else
    echo "WARNING: Agent API server failed to start. AI generation will be unavailable."
    AGENT_PID=""
fi

# Start frontend
echo "[3/3] Starting frontend on http://localhost:5173 ..."
cd "$SCRIPT_DIR/frontend"
npx vite --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!
sleep 2

# Verify frontend started
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "ERROR: Frontend failed to start"
    [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null
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
