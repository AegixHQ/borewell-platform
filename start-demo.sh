#!/usr/bin/env bash
# One-command demo (Mac / Linux). Needs Docker Desktop running, and Node 20+
# for the app step. See START-HERE.md.
#   ./start-demo.sh        start backend, load demo data, open the app
#   ./stop-demo.sh         stop and wipe everything
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "Docker is not installed. Install Docker Desktop first."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Start Docker Desktop and retry."; exit 1; }

echo "1/3 Starting the backend (first run takes a few minutes to build)..."
docker compose up --build -d postgres-platform-spine postgres-quotation postgres-resource-network \
  postgres-payments-data redis platform-spine quotation resource-network payments-data

echo "2/3 Loading demo data..."
docker compose exec -T \
  -e PLATFORM_SPINE_URL=http://localhost:8000 -e QUOTATION_URL=http://quotation:8000 \
  -e RESOURCE_NETWORK_URL=http://resource-network:8000 \
  platform-spine python - < tools/seed-demo/seed_demo.py \
  || echo "Demo data was not loaded. The app still works: create accounts with 'Create account'."

echo "3/3 Starting the app..."
cd apps/borewell-native
if [ ! -f .env ]; then
  cat > .env <<'ENV'
EXPO_PUBLIC_PLATFORM_SPINE_URL=http://localhost:8001
EXPO_PUBLIC_QUOTATION_URL=http://localhost:8002
EXPO_PUBLIC_RESOURCE_NETWORK_URL=http://localhost:8003
EXPO_PUBLIC_PAYMENTS_URL=http://localhost:8004
ENV
fi
if ! command -v node >/dev/null; then
  echo "Backend is running. Install Node.js 20+ from nodejs.org, then run this script again."
  exit 0
fi
[ -d node_modules ] || npm install --no-audit --no-fund
echo "Open the URL it prints (usually http://localhost:8081), press w if asked."
echo "Sign in with customer@example.com / contractor@example.com / owner@example.com, password demo-password-123"
exec npx expo start --web --port 8081
