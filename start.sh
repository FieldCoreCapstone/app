#!/usr/bin/env bash
# FieldCore — Startup Script
# Usage: ./start.sh [--seed] [--test] [--prod]

set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

PORT="${FIELDCORE_PORT:-5001}"
VENV_DIR="$APP_DIR/venv"

# ── Colors ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[FieldCore]${NC} $1"; }
ok()    { echo -e "${GREEN}[FieldCore]${NC} $1"; }
warn()  { echo -e "${YELLOW}[FieldCore]${NC} $1"; }
fail()  { echo -e "${RED}[FieldCore]${NC} $1"; exit 1; }

# ── Parse flags ───────────────────────────────────────────────────────────
SEED=false
TEST=false
PROD=false

for arg in "$@"; do
    case "$arg" in
        --seed) SEED=true ;;
        --test) TEST=true ;;
        --prod) PROD=true ;;
        --help|-h)
            echo ""
            echo -e "${BOLD}FieldCore Startup Script${NC}"
            echo ""
            echo "Usage: ./start.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --seed    Wipe and seed the database with 60 days of test data"
            echo "  --test    Run the full test suite before starting"
            echo "  --prod    Run in production mode (debug off)"
            echo "  --help    Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./start.sh              # Start in debug mode"
            echo "  ./start.sh --seed       # Seed database then start"
            echo "  ./start.sh --test --seed # Run tests, seed, then start"
            echo ""
            exit 0
            ;;
        *) warn "Unknown flag: $arg (use --help for options)" ;;
    esac
done

# ── Step 1: Python check ─────────────────────────────────────────────────
info "Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    fail "Python not found. Install Python 3.10+ and try again."
fi

PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
info "Found Python $PY_VERSION"

# ── Step 2: Virtual environment ──────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
    ok "Virtual environment created at $VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"
ok "Virtual environment activated"

# ── Step 3: Install dependencies ─────────────────────────────────────────
info "Installing dependencies..."
pip install -q -r requirements.txt
ok "Dependencies installed"

# ── Step 4: Run tests (if --test) ────────────────────────────────────────
if [ "$TEST" = true ]; then
    echo ""
    info "Running test suite..."
    echo -e "${BOLD}────────────────────────────────────────${NC}"
    python -m pytest tests/ -v
    echo -e "${BOLD}────────────────────────────────────────${NC}"
    ok "All tests passed"
    echo ""
fi

# ── Step 5: Seed database (if --seed) ────────────────────────────────────
if [ "$SEED" = true ]; then
    info "Seeding database with 60 days of test data..."
    python -c "from backend.scripts.seed_db import seed_db; seed_db()"
    ok "Database seeded"
fi

# ── Step 6: Initialize database if it doesn't exist ──────────────────────
DB_PATH=$(python -c "from backend.config import DATABASE_PATH; print(DATABASE_PATH)")
if [ ! -f "$DB_PATH" ]; then
    info "No database found. Initializing..."
    python -c "from backend.scripts.init_db import init_db; init_db()"
    ok "Database initialized at $DB_PATH"
    warn "Database is empty. Run ./start.sh --seed to populate with test data."
fi

# ── Step 7: Start the server ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  FieldCore Sensor Dashboard${NC}"
echo -e "${BOLD}════════════════════════════════════════${NC}"
echo ""

if [ "$PROD" = true ]; then
    info "Starting in production mode on port $PORT..."
    echo -e "  Dashboard:  ${BOLD}http://localhost:$PORT${NC}"
    echo -e "  API:        ${BOLD}http://localhost:$PORT/api${NC}"
    echo ""
    FLASK_DEBUG=0 python app.py
else
    info "Starting in debug mode on port $PORT..."
    echo -e "  Dashboard:  ${BOLD}http://localhost:$PORT${NC}"
    echo -e "  API:        ${BOLD}http://localhost:$PORT/api${NC}"
    echo -e "  Seed:       ${BOLD}curl -X POST http://localhost:$PORT/api/seed -H 'Content-Type: application/json' -d '{\"interval_minutes\": 30}'${NC}"
    echo ""
    FLASK_DEBUG=1 python app.py
fi
