#!/bin/bash
# ============================================================
# Secure Translate — Start Script
# Kills existing services, then starts backend + frontend.
# Run this AFTER connecting your VPN (Gemini needs it).
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==========================================================${NC}"
echo -e "${YELLOW}  Secure Translate — Starting servers${NC}"
echo -e "${YELLOW}==========================================================${NC}"

# --- Kill existing services ---
echo ""
echo -e "${YELLOW}[1/3] Killing existing services on ports 8000 and 5173...${NC}"

# Kill uvicorn on port 8000
PID_8000=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PID_8000" ]; then
    echo "  Killing uvicorn (PID: $PID_8000) on port 8000..."
    kill -9 $PID_8000 2>/dev/null || true
    echo -e "  ${GREEN}✓ Backend killed${NC}"
else
    echo "  No process on port 8000"
fi

# Kill vite on port 5173
PID_5173=$(lsof -ti :5173 2>/dev/null || true)
if [ -n "$PID_5173" ]; then
    echo "  Killing vite (PID: $PID_5173) on port 5173..."
    kill -9 $PID_5173 2>/dev/null || true
    echo -e "  ${GREEN}✓ Frontend killed${NC}"
else
    echo "  No process on port 5173"
fi

sleep 1

# --- Start backend ---
echo ""
echo -e "${YELLOW}[2/3] Starting backend (FastAPI on http://localhost:8000)...${NC}"
cd "$BACKEND_DIR"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# --- Start frontend ---
echo ""
echo -e "${YELLOW}[3/3] Starting frontend (Vite on http://localhost:5173)...${NC}"
cd "$FRONTEND_DIR"
pnpm dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# --- Cleanup on exit ---
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo -e "${GREEN}==========================================================${NC}"
echo -e "${GREEN}  Both servers are running!${NC}"
echo -e "${GREEN}  Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}  Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop both.${NC}"
echo -e "${GREEN}==========================================================${NC}"
echo ""

# Wait for either process to exit
wait -n $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
cleanup
