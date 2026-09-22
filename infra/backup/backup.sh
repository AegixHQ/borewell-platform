#!/usr/bin/env bash
#
# Backs up all 4 Postgres databases (one per service - see Architecture
# doc section 8: "one database per service") using pg_dump run INSIDE
# each service's own postgres container, via `docker compose exec` - not
# a separate pg_dump install on the host, so this has no dependency
# beyond Docker itself already being on the VM (it already is, per
# docs/deployment/PRODUCTION.md's own prerequisites).
#
# Usage (see infra/backup/README.md for the cron line and restore steps):
#   ./infra/backup/backup.sh
#
# Run this FROM THE REPO ROOT on the VM (same working directory as every
# other `docker compose -f docker-compose.prod.yml ...` command in
# docs/deployment/PRODUCTION.md) - it relies on that relative path to
# find docker-compose.prod.yml and .env.prod.
#
# What this does NOT do (being honest about scope, same discipline as
# the rest of this repo):
#   - Does not upload backups off this VM. A backup that lives on the
#     same disk as the database it backs up does not protect against
#     the VM itself being lost (disk failure, accidental deletion,
#     provider-level incident) - only against a bad migration or a
#     human "oops, dropped the wrong table." See infra/backup/README.md
#     for the (small, deliberately optional) step to also copy backups
#     somewhere else.
#   - Does not verify the backup is restorable. A pg_dump that completes
#     without error is a strong signal, not a guarantee - the README
#     covers a periodic real-restore test, which this script does not
#     do automatically (restoring INTO a real database on every backup
#     run would be a meaningfully bigger, riskier script).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found in $REPO_ROOT - this script must be run" >&2
  echo "from a real deployed checkout, not a fresh clone. See" >&2
  echo "docs/deployment/PRODUCTION.md section 4 to create it first." >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

# service-name:db-name pairs - matches docker-compose.prod.yml's actual
# POSTGRES_DB values exactly (checked against that file, not assumed to
# follow a naming pattern).
SERVICES=(
  "postgres-platform-spine:platform_spine"
  "postgres-quotation:quotation"
  "postgres-resource-network:resource_network"
  "postgres-payments-data:payments_data"
)

FAILED=0

for entry in "${SERVICES[@]}"; do
  container="${entry%%:*}"
  db_name="${entry##*:}"
  out_file="$BACKUP_DIR/${db_name}_${TIMESTAMP}.sql.gz"

  echo "Backing up $db_name (container: $container)..."

  # --username borewell matches every POSTGRES_USER in docker-compose.prod.yml
  # (confirmed identical across all 4 postgres-* service blocks). -F p
  # (plain SQL) rather than a custom-format dump - a restore then only
  # needs `psql`, not a pg_restore compatible with whatever exact
  # Postgres minor version produced the dump; worth the larger file size
  # at this data scale (single-contractor pilot, per Architecture doc
  # section 10 - this is not a decision that needs revisiting until real
  # multi-contractor data volume exists).
  if docker compose -f docker-compose.prod.yml --env-file .env.prod \
      exec -T "$container" \
      pg_dump --username borewell -F p "$db_name" \
      | gzip > "$out_file"; then
    size="$(du -h "$out_file" | cut -f1)"
    echo "  OK: $out_file ($size)"
  else
    echo "  FAILED: $db_name" >&2
    rm -f "$out_file"
    FAILED=1
  fi
done

echo ""
echo "Pruning backups older than ${RETENTION_DAYS} days from $BACKUP_DIR..."
find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -print -delete

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "One or more backups FAILED - see output above. Not treating this" >&2
  echo "as a silent success; check 'docker compose ... logs' for the" >&2
  echo "specific postgres container if the reason isn't obvious from the" >&2
  echo "pg_dump error itself." >&2
  exit 1
fi

echo "All 4 backups completed successfully."
