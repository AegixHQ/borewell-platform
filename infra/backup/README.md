# Database Backups

## What this is

`backup.sh` dumps all 4 Postgres databases (`platform_spine`, `quotation`,
`resource_network`, `payments_data`) to gzip-compressed SQL files, using
`pg_dump` run inside each service's own running container via
`docker compose exec` - no separate Postgres client install needed on the
VM beyond Docker, which is already required per
`docs/deployment/PRODUCTION.md`.

**Verified before being added to this repo:** the script's file-naming,
gzip compression/decompression, error handling (a failed `pg_dump` doesn't
leave a corrupt partial file behind), and the retention-pruning logic were
all tested against a mock `docker` command standing in for a real
Postgres connection - every piece of shell logic genuinely exercised, not
assumed correct. What was **not** tested against a real Postgres instance
(no Postgres available in the environment this was built in) is the
`pg_dump` invocation itself - the command syntax is standard and correct
as written, but run it once for real on your actual VM and check the
output before trusting it unattended on a cron schedule.

## One-time setup

```bash
cd borewell-platform   # repo root on the VM, same place you run
                        # docker compose -f docker-compose.prod.yml ...
chmod +x infra/backup/backup.sh
./infra/backup/backup.sh   # run it once manually first - see "Verify a
                            # backup is real" below before trusting it
```

## Automate it with cron

```bash
crontab -e
```

Add (daily at 2 AM server time - adjust to your VM's actual timezone and
low-traffic window):

```cron
0 2 * * * cd /path/to/borewell-platform && ./infra/backup/backup.sh >> /var/log/borewell-backup.log 2>&1
```

Replace `/path/to/borewell-platform` with the real absolute path on your
VM (e.g. `/home/ubuntu/borewell-platform`) - cron does not run with your
shell's working directory, so a relative path here silently fails to
find the script at all.

Check `/var/log/borewell-backup.log` periodically (or wire it into the
monitoring setup - see `infra/monitoring/README.md`) rather than assuming
a cron job that hasn't errored yet is a cron job that's still running at
all; a config typo means the job simply doesn't fire, silently, with no
error to see. Check for actual recent files:

```bash
ls -la backups/ | tail -10
```

## Retention

Defaults to 14 days, deleted automatically by the script itself on every
run (no separate cleanup job needed). Override with:

```bash
BACKUP_RETENTION_DAYS=30 ./infra/backup/backup.sh
```

## Verify a backup is actually real (do this once now, and periodically)

A `pg_dump` that exits `0` is a strong signal, not a guarantee the backup
is restorable. Actually restore one into a throwaway database to be sure:

```bash
# Pick one recent backup file to test:
gunzip -c backups/platform_spine_<timestamp>.sql.gz > /tmp/test_restore.sql

# Spin up a scratch Postgres container, NOT your real one:
docker run --rm -d --name pg-restore-test -e POSTGRES_PASSWORD=test \
  -p 5433:5432 postgres:16-alpine
sleep 3
docker exec -i pg-restore-test createdb -U postgres test_restore
cat /tmp/test_restore.sql | docker exec -i pg-restore-test psql -U postgres -d test_restore
docker exec pg-restore-test psql -U postgres -d test_restore -c "\dt"   # should list real tables
docker stop pg-restore-test   # --rm above means this also deletes it
```

If that produces real tables with real data, the backup is genuinely
good. Worth doing once right after setting this up, and again every few
months - a backup process that's never been test-restored is unverified,
regardless of how long it's been "working."

## Restoring for real (disaster recovery, not a drill)

```bash
gunzip -c backups/platform_spine_<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -T postgres-platform-spine psql --username borewell platform_spine
```

Repeat per service, substituting the container/db name. **This overwrites
whatever's currently in that database** - only run this against a
database you genuinely intend to replace.

## Off-VM storage (the gap this script alone does not close)

A backup living on the same disk as the database it protects does not
protect against losing that disk/VM entirely - only against a bad
migration, a human mistake, or similar. This script does not upload
anywhere by design (keeping it dependency-free and simple to reason
about); add one of these on top once you're ready:

- **Cheapest, lowest-effort:** a nightly `rclone` sync (or plain `scp`) of
  the `backups/` folder to any S3-compatible object storage. Backblaze
  B2, Cloudflare R2, and AWS S3 are the common choices - all charge
  per-GB-stored plus a small egress fee, and at this data scale (a
  handful of daily SQL dumps for a single-contractor pilot) the monthly
  cost is genuinely small. **Check current pricing directly on whichever
  provider's site before committing** - this doc can't respond with a
  reliable live number since Anthropic's own network doesn't have
  general internet access and vendor pricing changes; the "Costs"
  section of the top-level answer this file accompanies has the same
  caveat.
- Add as one more line at the end of `backup.sh`, or a second cron job
  that runs shortly after the backup one.

## Cost of this specific piece

The backup script itself costs nothing beyond what you already pay for
the VM (`pg_dump` and `gzip` are already part of the Postgres image and
any Linux base image respectively - no new software, no new service).
The only new cost is off-VM storage if you add it, and that step is
optional and separable from everything above.
