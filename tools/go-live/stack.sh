#!/usr/bin/env bash
# docker compose for the production stack, with the right files and env file:
#   tools/go-live/stack.sh ps | logs -f platform-spine | exec ... | down
# HTTPS (the TLS overlay) is on unless BORE_NO_TLS=1 (plain HTTP, testing only).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found - run 'make prod-init' first." >&2
  exit 1
fi
files=(-f docker-compose.prod.yml)
if [ "${BORE_NO_TLS:-0}" != "1" ]; then
  files+=(-f docker-compose.tls.yml)
fi
exec docker compose "${files[@]}" --env-file .env.prod "$@"
