#!/usr/bin/env bash
# Run the whole Borewell stack natively (no Docker/Podman) for a local demo.
#   ./run-local.sh        start 4 backend services + web-app
#   Ctrl+C                stop everything
#
# Uses SQLite files in .demo-data/ instead of Postgres (migrations are the
# same Alembic ones). Redis is optional: events are fire-and-forget and are
# just logged as dropped if Redis isn't running. Start `redis-server` first
# if you want the event path (e.g. payment consumer) live.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
DATA="$ROOT/.demo-data"
VENV="$ROOT/.venv-demo"
mkdir -p "$DATA"

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q fastapi "uvicorn[standard]" sqlalchemy alembic pydantic redis \
  pyjwt bcrypt email-validator httpx prometheus-fastapi-instrumentator

export JWT_SECRET="${JWT_SECRET:-dev-only-secret-change-in-production}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export ALLOWED_ORIGINS="http://localhost:5173,http://localhost:5174,http://localhost:5175"
export JWT_EXPIRY_MINUTES=60
export QUOTATION_SERVICE_URL="http://localhost:8002"
export PLATFORM_SPINE_URL="http://localhost:8001"
export RESOURCE_NETWORK_URL="http://localhost:8003"
# Optional Razorpay test keys: export them before running this script.
export RAZORPAY_KEY_ID="${RAZORPAY_KEY_ID:-}"
export RAZORPAY_KEY_SECRET="${RAZORPAY_KEY_SECRET:-}"
export RAZORPAY_WEBHOOK_SECRET="${RAZORPAY_WEBHOOK_SECRET:-}"

PIDS=()
cleanup() { echo; echo "Stopping..."; kill "${PIDS[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

start_service() {
  local name="$1" port="$2"
  (
    cd "$ROOT/services/$name"
    export DATABASE_URL="sqlite:///$DATA/$name.db"
    alembic upgrade head >"$DATA/$name.migrate.log" 2>&1
    exec uvicorn app.main:app --host 0.0.0.0 --port "$port" >"$DATA/$name.log" 2>&1
  ) &
  PIDS+=($!)
  echo "  $name -> http://localhost:$port"
}

echo "Starting backend services..."
start_service platform-spine 8001
start_service quotation 8002
start_service resource-network 8003
start_service payments-data 8004

echo "Starting web-app..."
if [ ! -d node_modules ]; then npm install >"$DATA/npm-install.log" 2>&1; fi
(
  cd "$ROOT/apps/web-app"
  export VITE_PLATFORM_SPINE_URL=http://localhost:8001
  export VITE_QUOTATION_URL=http://localhost:8002
  export VITE_RESOURCE_NETWORK_URL=http://localhost:8003
  export VITE_PAYMENTS_URL=http://localhost:8004
  exec npm run dev -- --host 0.0.0.0 --port 5173 >"$DATA/web-app.log" 2>&1
) &
PIDS+=($!)

sleep 6
echo
for p in 8001 8002 8003 8004; do
  printf "  :%s healthz -> " "$p"; curl -s -m 3 "localhost:$p/healthz" || echo "NOT UP (see .demo-data/*.log)"; echo
done
echo
echo "App:      http://localhost:5173"
echo "Metrics:  http://localhost:8001/metrics (also 8002/8003/8004)"
echo "Logs:     $DATA/*.log"
echo "Ctrl+C to stop."
wait