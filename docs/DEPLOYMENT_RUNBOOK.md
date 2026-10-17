# Yuno Ball Deployment Runbook

Status: operational runbook; no repository deployment script is currently validated
Reviewed: 2026-10-16 for local setup, EC2 Ubuntu, `yunoball.xyz`, Nginx, Gunicorn, Redis, PostgreSQL/Neon, and the descriptive Daily/history beta release gate. Production staging remains unverified.

## Supported target architecture

* Ubuntu EC2 instance with IPv4 and, where needed for NBA API access, VPC/subnet/instance IPv6.
* Nginx terminates HTTP/HTTPS and proxies to Gunicorn at `127.0.0.1:8000`.
* `yunoball.service` runs Gunicorn under systemd.
* Redis runs as the local `redis-server` system service and is not public.
* PostgreSQL is configured through environment variables/connection URL; Neon is the intended managed option where used.
* Application path: `/var/www/yunoball`.

## Public beta data and operations gate

The personal-PC PostgreSQL database is a development/source database, not the
public application's durable production host. Before a public release, select
a private managed PostgreSQL instance, take a verified source backup, and
transfer data through a reviewed, bounded migration. Keep the source intact.
Compare schema revision, row counts, game/team pair and key uniqueness checks,
representative historical dates, and the latest validated ingest marker on
source and target. Record any differences and resolve them before switching
the application connection. Do not print connection strings or credentials.

Enable automated off-host backups with a documented retention period and
point-in-time recovery where the chosen service supports it. Restore a backup
into a separate database and prove the application can read the restored
slate and matchup data. Record the latest restorable point, restore duration,
operator, and procedure. Redis remains a private, disposable cache; it is not
a backup or a substitute for PostgreSQL. The 2026-10-16 localhost preview,
before the release-candidate readiness correction, had PostgreSQL `ok`, Redis
`unavailable`, and readiness 503. The candidate contract now treats PostgreSQL
as the readiness dependency: Redis loss is reported as `degraded_ready`
without making durable reads unready. Both healthy and degraded behavior still
require staging proof.

Run ingestion as a controlled scheduled job separate from public requests,
with one active NBA pipeline, durable run records, validated reruns, and a
visible stale/partial state when updates fail. Use
[INGESTION_RUNBOOK.md](INGESTION_RUNBOOK.md) for order, locks, validation, and
recovery. Monitor site errors, dependency readiness, last successful ingest,
source freshness, and daily slate coverage; assign an operator to respond to
failures. A green dependency probe alone does not certify current data.

Stage the exact candidate commit, schema revision, production configuration,
assets, private Redis, database copy, and job schedule before public traffic.
Verify two dates with different real slates, archive navigation, one scheduled
and one final matchup, source/freshness/completeness labels, useful empty and
stale states, production-only route restrictions and redirects, page and API
responses, ingest replay/no-op behavior, and a restore/rollback rehearsal.
Record commit, environment, timestamp, commands, results, and unresolved
risks. Public launch remains gated until these checks pass and the owner
approves the release.

## Controlled personal-PC to managed PostgreSQL move

This is a supervised migration, not an application deployment side effect.
Use three distinct protected connection variables for the application and
reconciliation tool: `YUNOBALL_SOURCE_DATABASE_URL` for the personal-PC source,
`YUNOBALL_TARGET_DATABASE_URL` for the private managed target, and
`RESTORE_TEST_DATABASE_URL` for an empty, isolated restore-test database. For
`pg_dump` and `pg_restore`, configure equivalent named libpq services in a
protected `PGSERVICEFILE` outside the repository (for example
`yunoball-source`, `yunoball-restore-test`, and `yunoball-target`) so credentials
never appear in process arguments or shell history. Do not echo connection
variables, pass credential-bearing URLs on a shared command line, or save them
in the repository. The managed database and Redis must reject public network
access; allow only the staging/application and operator paths.

1. Stop/suspend every source and target ingestion schedule. Record the last
   completed `ingestion_runs` row, application base/candidate SHA, source
   `alembic current`, PostgreSQL major version, and UTC cutoff. Do not mutate or
   delete the source after the move.
2. Create a private backup directory outside the repository and produce a
   custom-format source backup. A representative PowerShell invocation is:

   ```powershell
   $releaseBackup = Join-Path $env:LOCALAPPDATA 'YunoBall\release-backups\<utc-cutoff>'
   New-Item -ItemType Directory -Path $releaseBackup -Force | Out-Null
   $env:PGSERVICEFILE = 'C:\protected\yunoball-pg-services.conf'
   pg_dump --dbname='service=yunoball-source' --format=custom --no-owner --no-acl --file="$releaseBackup\source.dump"
   pg_restore --list "$releaseBackup\source.dump" | Set-Content "$releaseBackup\source.contents.txt"
   Get-FileHash -Algorithm SHA256 "$releaseBackup\source.dump"
   ```

   Record the dump size, SHA-256, start/end time, tool/server versions, exit
   code, and encrypted off-host storage locator. The existing
   `scripts/simple_backup.ps1` writes a database URL into generated batch files
   and is not approved for this release procedure.
3. Restore the backup into the dedicated restore-test database before touching
   the final target. The database must be empty and disposable; `--clean` is
   permitted only when its exact name and isolation have been verified:

   ```powershell
   $env:PGSERVICEFILE = 'C:\protected\yunoball-pg-services.conf'
   pg_restore --dbname='service=yunoball-restore-test' --clean --if-exists --no-owner --no-acl --exit-on-error "$releaseBackup\source.dump"
   $env:DATABASE_URL = $env:RESTORE_TEST_DATABASE_URL
   alembic current
   python scripts/validate_daily_data.py --offline
   ```

   Point a production-configured, non-public application instance at the
   restored database and read two real Daily dates, archive, and a permanent
   matchup. Record restore duration and results. Remove the test database only
   under the managed provider's approved disposable-database procedure.
4. Restore/import into the private managed target, set `DATABASE_URL` to that
   target in the protected staging environment, then apply only reviewed
   forward migrations with `alembic upgrade head`. Never downgrade the source
   to make it match.
5. Reconcile source, restore-test, and target at the same cutoff. Compare
   `alembic current`, schema-only dumps, exact row counts for every `public`
   table, primary/unique constraints, and sequences. At minimum, separately
   record counts and date/season bounds for `game_schedule`, `team_game_stats`,
   `gamelogs`, `player_game_facts`, `ingestion_runs`, and
   `ingestion_task_runs`; verify schedule pair cardinality, orphan checks,
   representative historical dates, latest successful validated ingest, and
   the exact no-op behavior of a bounded replay. Estimates from
   `pg_stat_user_tables` are not row-count evidence.

   Run the repository's credential-safe bounded core reconciliation for at
   least two real dates after the target restore:

   ```powershell
   python scripts/reconcile_release_databases.py --season 2024-25 --season 2025-26 --date 2025-03-03 --date 2025-03-04
   ```

   This command compares the Alembic revision, allowlisted core-table exact
   counts, duplicate groups, reciprocal game/team pairs, selected slate counts,
   and latest validated ingest. It is read-only and omits connection URLs from
   output. It does not replace the required all-table schema/count report.
6. Enable provider-managed automated backups before staging ingestion starts.
   Record retention, PITR window/granularity, encryption, region, operator,
   recovery time objective, and recovery point objective. Perform and time a
   second provider backup/PITR restore into an isolated database. A configured
   backup without a successful restore is not a passed recovery gate.
7. Keep the personal-PC source intact and ingestion disabled until staging,
   reconciliation, rollback, and owner approval are complete. There must never
   be two scheduled writers.

`pg_dump`/`pg_restore` success alone does not prove application compatibility.
The reconciliation artifact must contain commands, exit codes, sanitized
counts/hashes, timestamps, and reviewer approval without credentials or host
details that should remain private.

## Private Redis and readiness contract

Redis is disposable acceleration, not a durable readiness dependency.
Configure `REDIS_URL` with the managed
service's protected endpoint, authentication, TLS scheme/options, and database
selection as supported by the provider. Restrict it to the private network and
application identity; do not bind a Redis port publicly. Start staging with an
empty cache, prove normal page reads repopulate only owned keys, and inspect
TTL/invalidation behavior against [CACHE_CATALOG.md](CACHE_CATALOG.md).

A PostgreSQL-backed application may remain ready while Redis is down. Under the
candidate contract `/health/ready` returns 200 with `status=ready` when both
dependencies are available, 200 with `status=degraded_ready` when PostgreSQL is
available and Redis is unavailable, and 503 when PostgreSQL is unavailable.
Record all three cases in staging. Redis recovery, cache behavior, and the
effect on global rate limiting must be visible and monitored; do not present a
degraded response as a fully healthy one.

## Production ingestion schedule and monitoring

Schedule `daily_ingest.py` outside the web process with the same protected
database/network configuration and one active writer. The database advisory
lock and exit code `3` protect against overlap, but the scheduler still needs a
hard runtime limit, captured output, non-zero exit alerting, and retry policy
that cannot overlap the next run. Do not schedule legacy initial/backfill jobs.

Before enabling the timer, run one supervised staging job, validate it, then
rerun the same bounded validation/replay case and prove that no duplicate grain
or historical deletion occurred. Monitor the durable `ingestion_runs` and
`ingestion_task_runs` records rather than relying only on the host-local JSON
marker. Alert on failed/partial status, failed/skipped validation, exit code 3,
run timeout, missing expected run, source freshness older than
`INGEST_STALE_AFTER_HOURS`, schedule pair/coverage failure, and Daily payloads
that become stale or incomplete. Assign an operator and escalation target.

The existing cron/setup scripts remain historical and are not release-approved
automation. Record the exact scheduler definition actually used in staging,
its timezone, next-run time, environment-file path and permissions, service
identity, timeout, logging destination, alert destination, and disable command.
Only enable production scheduling after the application/database release is
approved, and confirm all personal-PC writers remain disabled.

## Release evidence worksheet

Keep this table in the release record and replace every `PENDING` value with
sanitized evidence. A row passes only in the named staging environment on the
exact candidate; local/offline results belong in notes and do not satisfy it.

| Evidence | Command/check | Result |
| --- | --- | --- |
| Candidate identity | `git rev-parse HEAD`; clean `git status --short`; `npm ci`; `npm run build`; hash `app/static/css/output.css` and required `app/static/dist/*.bundle.js` files (at minimum `swiper.bundle.js`) | LOCAL ONLY: runtime candidate `592a50278fe175c8035ca86c5ff577223cab1217` and local hashes recorded below; exact staging reproduction PENDING |
| Database revision | `alembic current`; `alembic heads`; `alembic check` against managed staging | PENDING; repository head is `i5j6k7l8m9n0` |
| Source backup | `pg_dump`; `pg_restore --list`; SHA-256 and encrypted locator | PENDING |
| Restore rehearsal | `pg_restore --exit-on-error` to isolated DB; application read smoke | PENDING |
| Reconciliation | schema diff and exact all-table counts; `scripts/reconcile_release_databases.py` for bounded core grain/pair/date/ingest checks | PENDING |
| Managed backups | provider policy plus timed isolated PITR/backup restore | PENDING |
| Private Redis | protected `REDIS_URL`; ping; TTL/invalidation inspection | PENDING; localhost Redis was unavailable on 2026-10-16 |
| Healthy/degraded readiness | `/health/ready` healthy; controlled Redis loss remains 200/degraded; PostgreSQL loss returns 503 | PENDING staging; final localhost test-client probe returned 200/degraded with Redis unavailable |
| Daily journey | two distinct real dates; `/daily/archive`; scheduled and final permanent matchup; source/freshness/completeness | PENDING staging |
| Empty/stale journey | no-games date plus controlled old/missing validated-ingest evidence | PENDING staging |
| Route restrictions | production root page; `/home` and legacy redirects; research/design/betting 404 matrix; non-mutating API | PENDING staging |
| Ingestion | supervised job; validator; exact bounded replay/no-op; durable run rows; freshness alert | PENDING |
| Rollback | previous SHA; application rollback; cache action; restore/recovery drill | PENDING |
| Approval | operator, independent reviewer, owner, UTC decision time | PENDING; current decision is NO-GO |

Attach sanitized command output or artifact locations to each row. Record
failures as failures; do not replace them with a fixture, localhost, or offline
result.

### Pull-request verification boundary

`.github/workflows/pr-ci.yml` is the reproducible pull-request gate. Its required
jobs use clean hosted runners, install the locked Python and Node dependencies,
run `python -m compileall -q app`, run the explicitly marked offline/fixture-safe
tests with `pytest -m "not integration"`, and run `npm run build`. A failure in
compilation, tests, dependency installation, or asset build fails the workflow.
The workflow also collects and reports the separate PostgreSQL integration scope;
that collection report is not an integration pass.

PostgreSQL-backed tests are marked `integration` in the test suite and are never
run against a personal-PC database, a protected URL, Redis, or a live NBA
provider by the PR gate. The `PostgreSQL integration gate (manual)` job is only
available through `workflow_dispatch`; it uses an ephemeral PostgreSQL service,
applies the repository migrations, and treats any skipped integration test as a
failure. A successful offline PR gate therefore does not certify database-backed
behavior, staging, ingestion, provider access, or deployment readiness.

### Local candidate evidence — 2026-10-16 (does not satisfy staging)

* Python 3.10.6: `compileall` passed; focused release suite 34 passed; complete
  inert-SQLite suite 457 passed, 15 skipped, 3 PostgreSQL-only failures; the
  exact three tests passed against the personal-PC PostgreSQL database.
* Database: `alembic current` returned `i5j6k7l8m9n0 (head)` and `alembic
  check` returned no new upgrade operations.
* Routes: a production-configured Flask test client against the personal-PC
  database returned 9 games for 2025-03-03, 8 for 2025-03-04, an empty
  2025-07-01 slate, archive and permanent matchup HTTP 200, expected redirects,
  excluded-surface HTTP 404 responses, and readiness HTTP 200
  `degraded_ready` while Redis was unavailable. This is not staging.
* Reconciliation: source-to-itself only passed with both representative dates,
  zero duplicate groups, zero pair failures, and matching Alembic head. No
  managed target was available, so this is a tool regression check only.
* Assets: `npm ci`, `npm run build:css`, and `npm run build:js` passed. Built
  CSS SHA-256 is
  `FE9045DC39127BF00BC4B4F09BA6876645BDB7D9C6FA5D6D1946070795FE7361`;
  built Swiper bundle SHA-256 is
  `59E71068CBB5A3DEBEA99A2A8802E0EA1728B04DDE6736D94D44EE873B6ED5F5`.
  Swiper 12.1.2 removed the prior critical advisory; `npm audit --omit=dev`
  still reports five high and two moderate Tailwind 3 build-chain findings.

## Local development (short)

1. Clone the repo and create `.env` from `.env.example` (never commit secrets).
2. Create/activate the project venv (`venv\Scripts\activate` on Windows) and `pip install -r requirements.txt`.
3. Install locked Node dependencies and build all ignored release assets (`npm ci` / `npm run build`) so the CSS and JavaScript bundles exist.
4. Confirm Redis and PostgreSQL/`DATABASE_URL` connectivity.
5. Run the app with `python run.py` (dev only). Use `--proxy` / `--local` per [PROXY.md](PROXY.md).
6. For daily data work, follow [INGESTION_RUNBOOK.md](INGESTION_RUNBOOK.md).

Minimum local env keys typically include `DATABASE_URL`, `SECRET_KEY`, `API_KEY`, `REDIS_URL`, and optional proxy variables documented in [PROXY.md](PROXY.md). User accounts and JWT authentication are not active in the current analytics application.

### Windows project-interpreter note — 2026-08-25

The repository `venv` is the valid Python 3.10.6 environment and contains the
project dependencies. Bare `python` is not guaranteed to be on PATH. In a
restricted automation shell, launching the venv can also fail at the shell
boundary even though the environment is healthy; that is not a reason to
recreate the venv or switch to the retired `venvSports2` environment.

Use the full project interpreter path from an approved outside-restricted-shell
execution context when running tests or database scripts:

```powershell
C:\Code\sports_analytics\venv\Scripts\python.exe -m pytest -q
C:\Code\sports_analytics\venv\Scripts\python.exe scripts\shadow_program_e_schedule_pressure.py --season 2025-26
```

Do not print `.env` contents or proxy/database credentials while diagnosing
the runtime.

## Pre-deploy checks

1. Confirm the intended branch/commit and record the previous deployed commit for rollback.
2. Verify database backup/snapshot and migration compatibility.
3. Verify required environment variables without printing secrets.
4. Test Python dependencies in a clean virtual environment.
5. Run `npm run build`; confirm the ignored CSS and required JavaScript bundles exist and record their hashes, including `app/static/dist/swiper.bundle.js`.
6. Test direct NBA API connectivity from EC2; confirm IPv6 route if that is the selected path.
7. Confirm Redis and PostgreSQL connectivity.
8. Run route/import smoke tests before restarting production.
9. Verify `/dashboard/*`, `/design/*`, and `/daily/betting` return 404 in
   production; these surfaces are excluded from the descriptive beta.
10. Verify `/health/ready` is bounded by a 10-per-minute in-process per-worker
    limit and the global Redis-backed 60-per-minute limit. Treat it only as a
    PostgreSQL/Redis connectivity check; it does not validate migrations, data
    freshness, ingestion, or page behavior.

## Required environment contract

The reviewed code/scripts reference or imply:

| Variable                                                                    | Purpose                                                              |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `DATABASE_URL` or `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL/Neon connection                                           |
| `FLASK_ENV=production`                                                      | runtime environment marker                                           |
| `FLASK_DEBUG=false`                                                         | never enable debugger publicly                                       |
| `PROXY_ENABLED`                                                             | allow proxy-aware NBA endpoint configuration                         |
| `FORCE_PROXY`                                                               | force proxy path when explicitly required                            |
| `FORCE_LOCAL`                                                               | force direct path for diagnostics                                    |
| `MAX_WORKERS`                                                               | ingestion concurrency; use `1` on EC2 until validated                |
| `INGEST_STALE_AFTER_HOURS`                                                  | optional UI stale threshold for the last validated ingest; default 30 hours |
| `YUNOBALL_CODE_VERSION`                                                     | deployed commit/release recorded on ingestion runs; set when Git metadata is unavailable |
| `SMARTPROXY_*` / proxy credentials used by `api_utils.py`                   | must live in protected environment configuration, not the repository |
| `SPORTSGAMEODDS_API_KEY`                                                    | optional forward odds pilot key; local/protected env only, never log or commit |

Create a root-owned environment file such as `/etc/yunoball/yunoball.env` with mode `600`, then load it through `EnvironmentFile=` in systemd. Do not embed database or proxy secrets in unit files. Full proxy setup: [PROXY.md](PROXY.md).

## Deployment procedure

**Supported release path:** follow this runbook as a manually reviewed procedure only. The repository deployment scripts have not been tested end to end against the current application, database, and target host, so they are not supported release commands. Do not invoke them for a release. Before production use, validate a single deployment path in staging against the exact release candidate, including migration compatibility, service startup, product smoke checks, and rollback. Until that evidence is recorded here, this runbook is the only supported guide and production deployment remains gated.
The current migration chain includes the Phase 2/3/4 analytical and schema
work, followed by an additive external-artifact manifest registry. Application
services expect those tables, so take a database snapshot and apply migrations
before deploying or scheduling the new code:

```bash
alembic current
alembic heads
alembic upgrade head
alembic current
alembic check
```

The current repository migration head is `i5j6k7l8m9n0` (`alembic heads`,
verified 2026-10-14). This identifies the code's graph only; it does not assert
the staging or production database revision. Check `alembic current` against
the target database before applying migrations. The head follows ingestion
tracking, schema-metadata reconciliation, additive player and team/game
snapshot migrations, Phase 4 schema hardening, and later additive research and
availability migrations. Phase 4 canonicalizes four-digit roster
seasons, adds roster/gamelog season checks, adds player and composite schedule
foreign keys to `gamelogs`, and restores the missing primary key on the retained
read-only `player_z_scores` table. The new `external_dataset_imports` table is
empty on creation and the migration does not read, move, or import any external
files. No legacy analytical table is dropped. Take a backup before upgrading
because roster season canonicalization is
intentionally retained if the schema is later downgraded.

`alembic check` is a required pre-deploy gate. The legacy `users` table is
retained by the baseline schema while user/JWT auth is inactive and is
intentionally excluded from autogenerate comparison; it must not be dropped or
recreated by a readiness check. A clean check currently reports `No new upgrade
operations detected.`

The additive Program B migration creates an empty
`availability_report_documents` table for immutable official PDF revision
metadata. It does not fetch a page, download a PDF, create an archive directory,
or parse an availability row. Configure
`YUNOBALL_INJURY_REPORT_ARCHIVE_DIR` to a durable out-of-repository path before
running the collector; deployment alone does not authorize collection.
The follow-on additive migration creates
`availability_report_download_attempts`, initially empty, so failed official
URLs can be retried on the default two-hour cadence. After migration, schedule
the bounded collector every two hours during the agreed publication window;
keep its archive and database environment in a root-owned environment file.
Rollback drops retry history only; it does not delete already archived PDFs or
immutable document rows.

Do not start `daily_ingest.py`,
`daily_fetch.py`, or `daily_calculate.py` on the new code before the migration
succeeds.

Run one current-date
`daily_calculate.py --tasks player_snapshots schedule team_snapshots` smoke
after deployment, then run `scripts/validate_daily_data.py --offline`. Preview a
historical team range only with
`scripts/backfill_team_game_snapshots.py ... --dry-run`; do not run a historical
`--apply` backfill as part of deployment. External dataset registration is also
an explicit operational action, not a deployment step. Do not use
`scripts/register_external_dataset.py --apply` until the durable artifact
locator and licensing metadata have been reviewed.

The external-data migrations also create empty Stat Surge and Kaggle game/market
staging, row-rejection, and market-anomaly tables; extend `game_schedule` with
event type, date precision, structured score, and source lineage; and add
version/run/method fields for Stat Surge identity reconciliation. Migration
does not read any preserved CSV. Existing schedule rows are labeled as legacy
source rows and classified from their NBA game-ID prefix.
Historical staging is a separate bounded operation using
`scripts/import_statsurge_availability.py --dry-run` followed by an explicitly
approved `--apply`; it does not enable routes, caches, canonical availability,
or model features.

Rollback order: deploy the prior application version first so readers no longer
reference v2 tables. The additive tables may remain harmlessly in place. Only
downgrade the migration after confirming no retained snapshot history is needed;
downgrade through the Phase 2/3 migrations drops the v2 tables and therefore
destroys their rows. Downgrading the manifest migration drops
`external_dataset_imports`; export any retained provenance first. It does not
roll back source-row data because this change imports none.
Downgrading `o5p6q7r8s9t0` drops the Stat Surge staging and rejection rows, so
export their manifest/run-linked audit data first if an import has occurred.
The preserved source artifact and manifest remain intact, and the staging data
can be rebuilt idempotently after re-upgrade.
Downgrading `t0u1v2w3x4y5` removes only the Stat Surge identity-resolution audit
columns, but export their run/version/method evidence first. Downgrading
`s9t0u1v2w3x4` removes schedule source/type/score fields; do not do so after
external playoff rows exist unless those provenance-linked rows have been
exported and the application has first been rolled back.
Downgrading through `p6q7r8s9t0u1` and `q7r8s9t0u1v2` drops Kaggle game,
market, and anomaly staging rows. Export their manifest/run-linked audit data
first; no canonical Yuno facts or caches are affected because none consume
these tables yet.
Downgrading `u1v2w3x4y5z6` drops official injury-report document metadata but
does not delete raw files from the configured durable archive. Export document
and ingestion-run metadata before downgrade if collection has occurred; a
later re-upgrade and bounded rerun can re-register preserved byte revisions.

```bash
cd /var/www/yunoball
git fetch origin
git checkout <production-branch>
git pull --ff-only origin <production-branch>

source /home/ubuntu/clean_venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build

python -c "from app import create_app; app=create_app(); print('app import ok')"
redis-cli ping
sudo nginx -t

sudo systemctl daemon-reload
sudo systemctl restart yunoball.service
sudo systemctl reload nginx
```

Then verify:

```bash
sudo systemctl --no-pager --full status yunoball.service
curl -fsS http://127.0.0.1:8000/ >/dev/null
curl -fsS https://yunoball.xyz/ >/dev/null
sudo journalctl -u yunoball.service -n 100 --no-pager
```

Do not run cache warming until the application, database, and current data pass smoke checks.

## Systemd baseline

`wsgi:app` is the Flask WSGI application for Gunicorn. `asgi:app` adapts it
for Uvicorn. Both use the configured environment for network policy; imports
must not force proxy mode. Do not use `run:app` while `run.py` starts a Windows
Redis executable on import.

```ini
[Unit]
Description=Yuno Ball Flask Application
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/yunoball
EnvironmentFile=/etc/yunoball/yunoball.env
ExecStart=/home/ubuntu/clean_venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 --timeout 60 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Worker count is capacity-dependent; the reviewed scripts disagree between one and three. Start conservatively, measure memory/latency, and ensure external NBA calls are not multiplied unexpectedly across workers.

## Nginx and TLS

* Proxy dynamic traffic to `127.0.0.1:8000`.
* Serve the actual Flask static directory. The reviewed configs use `$APP_DIR/static`, while the repository stores assets under `app/static`; verify and correct the alias.
* Preserve `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto`.
* Test HTTP configuration before requesting a certificate.
* Use Certbot only after DNS points to the instance.

Certificate failure check:

```bash
sudo certbot certificates
sudo ls -la /etc/letsencrypt/live/yunoball.xyz/
sudo nginx -t
```

Never leave an Nginx config referencing a nonexistent certificate. Restore a valid HTTP-only server block, reload, then obtain/reinstall the certificate.

## IPv6 and NBA API checks

1. VPC has an IPv6 CIDR.
2. Subnet has an IPv6 CIDR and route `::/0` to an internet gateway.
3. EC2 network interface has an IPv6 address.
4. Security/NACL egress permits HTTPS over IPv6.
5. DNS and TLS work from the host.

```bash
ip -6 addr show
ip -6 route
curl -6 -I https://stats.nba.com/ --max-time 15
```

If direct calls still fail, use the application's proxy-aware endpoint wrapper with secrets in the environment ([PROXY.md](PROXY.md)). Avoid scattered direct `nba_api` constructors because they bypass centralized network policy.

## Logs and health checks

| Area                     | Command/location                                                                         |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| application service      | `journalctl -u yunoball.service -f`                                                      |
| Nginx error/access       | `/var/log/nginx/error.log`, `/var/log/nginx/access.log`, or app-specific configured logs |
| daily ingestion          | `daily_ingest.log`, `/var/log/yunoball-daily-ingest.log`                                 |
| weekly/initial ingestion | `ingest.log`                                                                             |
| Redis                    | `systemctl status redis-server`, `redis-cli INFO`                                        |
| certificate              | `certbot certificates`, `systemctl status certbot.timer`                                 |

Minimum descriptive-beta checks: root page, `/home` redirect to `/daily/`, two
date-specific Daily slates with different games, `/daily/archive`, one permanent matchup,
one non-mutating API response, `/health/ready`, Redis ping, and a bounded DB
query. Confirm research/design/betting routes remain excluded in production.
Player and team destinations are supporting context, not the Daily/history
release acceptance path.

## Rollback

1. Stop new ingestion/warm-up jobs.
2. Check out the recorded previous commit using a fast-forward-safe deployment process or a dedicated release directory/symlink.
3. Restore the previous dependency lock/environment if dependencies changed.
4. Prefer rolling application code back while leaving the additive ingestion-run tables in place. `alembic downgrade h8i9j0k1l2m3` drops those tables and their operational history, so use it only when that data loss is explicitly accepted.
5. Restart `yunoball.service`, test Nginx, and verify local/public health.
6. Invalidate cache versions if payload contracts changed.
7. Record failure cause, affected commit, and data impact.

## Historical, unvalidated deployment scripts

The following scripts are historical examples, not supported deployment tools:

* `scripts/deploy.sh` targets the old `nba-sports-analytics` repository and defaults to the `developProxy` branch.
* `scripts/setup_production.sh` and `scripts/prepare_deployment.sh` disagree on application entrypoint, worker count, proxy settings, and runtime setup; `deploy.sh` has a third configuration.
* The scripts also disagree with the repository and this runbook on paths, Python version, and static asset aliases.
* `run.py` is a development launcher and is unsafe as a production WSGI import while it starts Redis process management on import.

Do not run these scripts to release the current application. The procedure above is the only supported guide until one exact path has passed a staging deployment, smoke checks, and rollback rehearsal, with the tested commit and results recorded here. This classification does not claim that the manual commands above have been tested against production infrastructure.

## Historical analytics rollout

Historical snapshot backfills are separate supervised operations. Use
[`ANALYTICS_ROLLOUT_RUNBOOK.md`](ANALYTICS_ROLLOUT_RUNBOOK.md); application
deployment does not authorize production backfill.
