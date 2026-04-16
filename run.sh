#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run.sh — News That Matters · one-command launcher
#
# Usage:  ./run.sh
#
# What it does:
#   1. Validates the venv (not just existence — actually imports FastAPI)
#   2. Recreates + reinstalls if broken / missing
#   3. Kills any stale server already on port 8000
#   4. Starts the FastAPI server in the background
#   5. Opens the prototype in Chrome
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
PORT=8000
LOG="$SCRIPT_DIR/.server.log"

# ── Walmart proxy (required on Eagle WiFi / VPN) ─────────────────────────────
export HTTP_PROXY="http://sysproxy.wal-mart.com:8080"
export HTTPS_PROXY="http://sysproxy.wal-mart.com:8080"
PIP_INDEX="https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple"
PIP_HOST="pypi.ci.artifacts.walmart.com"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "  $*"; }
ok()   { echo "  ✅ $*"; }
warn() { echo "  ⚠️  $*"; }
die()  { echo "  ❌ $*" >&2; exit 1; }

pip_install() {
  "$PIP" install "$@" \
    --index-url "$PIP_INDEX" \
    --trusted-host "$PIP_HOST" \
    --force-reinstall -q
}

# ── Step 1: validate or rebuild venv ─────────────────────────────────────────
echo ""
echo "🐾 News That Matters — starting up"
echo ""

VENV_OK=false
if [[ -f "$PY" ]]; then
  # Test actual import — dist-info-only corrupt installs return exit code 1
  if "$PY" -c "import fastapi, uvicorn, apscheduler" 2>/dev/null; then
    VENV_OK=true
  else
    warn "Venv exists but deps are broken — rebuilding..."
    rm -rf "$VENV"
  fi
fi

if [[ "$VENV_OK" == "false" ]]; then
  log "Creating fresh venv..."
  python3 -m venv "$VENV" || die "python3 -m venv failed — is Python 3.11+ installed?"
  ok "Venv created"

  log "Installing dependencies (this takes ~2 min first time)..."

  # Install in order: lightweight first, heavy ML last.
  # --force-reinstall on every group because this venv has a known issue
  # where pip writes dist-info metadata but NOT the actual module folder
  # (leaving packages silently broken). Force-reinstall guarantees files land.
  pip_install fastapi==0.115.12 "uvicorn[standard]" pydantic pydantic-settings \
              apscheduler httpx python-dotenv anyio starlette annotated-types \
              typing-inspection typing-extensions idna h11
  pip_install feedparser requests lxml google-generativeai google-genai distro
  pip_install scikit-learn numpy scipy
  ok "All dependencies installed"
fi

# ── Step 2: verify all critical imports (catch any remaining corruption) ──────
log "Verifying imports..."
MISSING=$("$PY" -c "
missing=[]
for m in ['fastapi','uvicorn','apscheduler','feedparser','sklearn','numpy','google.generativeai','dotenv','lxml','httpx']:
    try: __import__(m)
    except ImportError: missing.append(m)
print(','.join(missing))
" 2>/dev/null)

if [[ -n "$MISSING" ]]; then
  warn "Corrupt packages detected: $MISSING — force-reinstalling..."
  # Map import names back to pip package names
  PKG_MAP="$MISSING"
  PKG_MAP="${PKG_MAP//sklearn/scikit-learn}"
  PKG_MAP="${PKG_MAP//dotenv/python-dotenv}"
  PKG_MAP="${PKG_MAP//google.generativeai/google-generativeai}"
  PKG_MAP="${PKG_MAP//lxml/lxml}"
  # shellcheck disable=SC2086
  pip_install ${PKG_MAP//,/ }
  ok "Corrupt packages repaired"
fi

ok "All imports verified"

# ── Step 3: kill any existing server on port 8000 ────────────────────────────
if lsof -ti ":$PORT" &>/dev/null; then
  warn "Port $PORT already in use — killing old server..."
  lsof -ti ":$PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# ── Step 4: start the server ──────────────────────────────────────────────────
log "Starting server on http://127.0.0.1:$PORT ..."
cd "$SCRIPT_DIR"
"$VENV/bin/uvicorn" app.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  > "$LOG" 2>&1 &
SERVER_PID=$!
echo "  Server PID: $SERVER_PID"

# ── Step 5: wait for server to be ready ──────────────────────────────────────
log "Waiting for server to be ready..."
for i in {1..20}; do
  if curl -sf "http://127.0.0.1:$PORT/health" &>/dev/null; then
    ok "Server is ready!"
    break
  fi
  sleep 1
  if [[ $i -eq 20 ]]; then
    die "Server didn't start in 20s — check $LOG for errors"
  fi
done

# ── Step 6: open Chrome ───────────────────────────────────────────────────────
log "Opening prototype in Chrome..."
URL="http://127.0.0.1:$PORT/"

if [[ "$(uname)" == "Darwin" ]]; then
  osascript -e "tell application \"Google Chrome\" to open location \"$URL\""
else
  xdg-open "$URL" 2>/dev/null || sensible-browser "$URL" 2>/dev/null || true
fi

echo ""
echo "  ✅ News That Matters is live at $URL"
echo "  📋 Logs: tail -f $LOG"
echo "  🛑 Stop: kill $SERVER_PID"
echo ""
