#!/usr/bin/env bash
# One command to go live (or redeploy): preflight -> build -> start -> smoke test.
#   make prod-deploy
# Safe to re-run: it only rebuilds what changed.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

command -v docker >/dev/null || { echo "ERROR: docker is not installed." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose v2 is required." >&2; exit 1; }

echo "== 1/4 Preflight =="
python3 tools/go-live/preflight.py --dns

echo; echo "== 2/4 Build and start (first run takes a few minutes) =="
tools/go-live/stack.sh up -d --build --remove-orphans --wait --wait-timeout 300

echo; echo "== 3/4 Smoke test (retrying while the HTTPS certificate is issued) =="
passed=0
for attempt in $(seq 1 12); do
  if python3 tools/go-live/smoke.py --env .env.prod; then passed=1; break; fi
  echo "-- not ready yet (attempt $attempt/12), waiting 15s --"
  sleep 15
done

echo; echo "== 4/4 Done =="
if [ "$passed" != 1 ]; then
  echo "The stack is up but the smoke test still fails. Read the FAIL lines above;" >&2
  echo "'tools/go-live/stack.sh logs --tail 100 gateway' shows certificate problems." >&2
  exit 1
fi
domain="$(grep -E '^PUBLIC_DOMAIN=' .env.prod | cut -d= -f2-)"
echo "Live at https://$domain"
echo "Still to do by hand (see docs/deployment/GO-LIVE.md):"
echo "  - Razorpay webhook: https://$domain/v1/payments/webhook  (payment.captured, payment.failed)"
echo "  - If you set BOOTSTRAP_ADMIN_PASSWORD, delete that line from .env.prod and rerun this."
echo "  - Schedule backups: see infra/backup/README.md"
