#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Colors ──────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Check dependencies ──────────────────────────────────────
command -v conda >/dev/null || error "conda not found"
command -v node  >/dev/null || error "node not found (need 18+)"

ENV_NAME="pokieticker"

# ── Conda env setup ─────────────────────────────────────────
if ! conda env list | grep -q "^${ENV_NAME} "; then
    info "Creating conda env $ENV_NAME (Python 3.12) ..."
    conda create -n "$ENV_NAME" python=3.12 -y >/dev/null 2>&1
fi

CONDA_PYTHON="conda run -n ${ENV_NAME} python"
CONDA_PIP="conda run -n ${ENV_NAME} pip"

# Check if deps need install
INSTALLED=$($CONDA_PYTHON -c "import fastapi, akshare" 2>/dev/null && echo yes || echo no)
if [ "$INSTALLED" != "yes" ]; then
    info "Installing Python dependencies in conda env ..."
    $CONDA_PIP install -q -r "$ROOT/requirements.txt"
fi

# ── Unpack data (skip if already done) ──────────────────────
if [ ! -f "$ROOT/pokieticker.db" ]; then
    if [ -f "$ROOT/pokieticker.db.gz" ]; then
        info "Unpacking pokieticker.db.gz ..."
        gunzip -k "$ROOT/pokieticker.db.gz"
    else
        warn "No pokieticker.db found — will create on first startup"
    fi
fi

if [ ! -d "$ROOT/backend/ml/models" ] && [ -f "$ROOT/models.tar.gz" ]; then
    info "Unpacking ML models ..."
    mkdir -p "$ROOT/backend/ml/models"
    tar xzf "$ROOT/models.tar.gz" -C "$ROOT/backend/ml/"
fi

# ── Frontend setup ──────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
    info "Installing frontend dependencies ..."
    cd "$ROOT/frontend" && npm install && cd "$ROOT"
fi

# ── .env check ──────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
    warn "No .env file found. Copy .env.example and fill in your API keys."
    [ -f "$ROOT/.env.example" ] && cp "$ROOT/.env.example" "$ROOT/.env"
fi

# ── Start ────────────────────────────────────────────────────
info "Starting backend on :8000 ..."
conda run -n "$ENV_NAME" uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

info "Starting frontend on :7777 ..."
cd "$ROOT/frontend" && npm run dev &
FRONTEND_PID=$!

info "──────────────────────────────────"
info "  Backend  → http://localhost:8000"
info "  Frontend → http://localhost:7777"
info "  Conda env: $ENV_NAME"
info "──────────────────────────────────"
info "Press Ctrl+C to stop both servers"

cleanup() {
    info "Shutting down ..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null
    info "Done."
}
trap cleanup EXIT INT TERM

wait