# Yuno Ball Deployment Runbook

Status: operational baseline with current repository conflicts called out
Reviewed: 2026-07-15 for local setup, EC2 Ubuntu, `yunoball.xyz`, Nginx, Gunicorn, Redis, and PostgreSQL/Neon.

## Supported target architecture

* Ubuntu EC2 instance with IPv4 and, where needed for NBA API access, VPC/subnet/instance IPv6.
* Nginx terminates HTTP/HTTPS and proxies to Gunicorn at `127.0.0.1:8000`.
* `yunoball.service` runs Gunicorn under systemd.
* Redis runs as the local `redis-server` system service and is not public.
* PostgreSQL is configured through environment variables/connection URL; Neon is the intended managed option where used.
* Application path: `/var/www/yunoball`.

## Local development (short)

1. Clone the repo and create `.env` from `.env.example` (never commit secrets).
2. Create/activate the project venv (`venv\Scripts\activate` on Windows) and `pip install -r requirements.txt`.
3. Install Node deps and build CSS (`npm ci` / `npm run build:css`) so `app/static/css/output.css` exists.
4. Confirm Redis and PostgreSQL/`DATABASE_URL` connectivity.
5. Run the app with `python run.py` (dev only). Use `--proxy` / `--local` per [PROXY.md](PROXY.md).
6. For daily data work, follow [INGESTION_RUNBOOK.md](INGESTION_RUNBOOK.md).

Minimum local env keys typically include `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `REDIS_URL`, and optional proxy variables documented in [PROXY.md](PROXY.md).

## Pre-deploy checks

1. Confirm the intended branch/commit and record the previous deployed commit for rollback.
2. Verify database backup/snapshot and migration compatibility.
3. Verify required environment variables without printing secrets.
4. Test Python dependencies in a clean virtual environment.
5. Build Tailwind assets and confirm `app/static/css/output.css` exists.
6. Test direct NBA API connectivity from EC2; confirm IPv6 route if that is the selected path.
7. Confirm Redis and PostgreSQL connectivity.
8. Run route/import smoke tests before restarting production.

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

Create a root-owned environment file such as `/etc/yunoball/yunoball.env` with mode `600`, then load it through `EnvironmentFile=` in systemd. Do not embed database or proxy secrets in unit files. Full proxy setup: [PROXY.md](PROXY.md).

## Deployment procedure

The Phase 2 release adds four player snapshot tables after the ingestion run and schema-reconciliation migrations. Application readers expect those tables, so take a database snapshot and apply migrations before deploying or scheduling the new code:

```bash
alembic current
alembic heads
alembic upgrade head
alembic current
alembic check
```

The expected new head is `k1l2m3n4o5p6`. It follows ingestion tracking and the
schema-metadata reconciliation with additive, empty v2 player snapshot tables;
no legacy analytical table is dropped. Do not start `daily_ingest.py`,
`daily_fetch.py`, or `daily_calculate.py` on the new code before the migration
succeeds.

Run one current-date `daily_calculate.py --tasks player_snapshots` smoke after
deployment, then run `scripts/validate_daily_data.py --offline`. Do not run a
historical `--apply` backfill as part of deployment.

Rollback order: deploy the prior application version first so readers no longer
reference v2 tables. The additive tables may remain harmlessly in place. Only
downgrade the migration after confirming no retained snapshot history is needed;
downgrade drops the four v2 tables and therefore destroys their rows.

```bash
cd /var/www/yunoball
git fetch origin
git checkout <production-branch>
git pull --ff-only origin <production-branch>

source /home/ubuntu/clean_venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build:css

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

Use a WSGI module that creates only the Flask app. Do not use `run:app` while `run.py` starts a Windows Redis executable on import.

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

Minimum post-deploy checks: root page, `/home`, one player, one team, `/dashboard/games`, a matchup, Redis ping, DB query, and one non-mutating API response.

## Rollback

1. Stop new ingestion/warm-up jobs.
2. Check out the recorded previous commit using a fast-forward-safe deployment process or a dedicated release directory/symlink.
3. Restore the previous dependency lock/environment if dependencies changed.
4. Prefer rolling application code back while leaving the additive ingestion-run tables in place. `alembic downgrade h8i9j0k1l2m3` drops those tables and their operational history, so use it only when that data loss is explicitly accepted.
5. Restart `yunoball.service`, test Nginx, and verify local/public health.
6. Invalidate cache versions if payload contracts changed.
7. Record failure cause, affected commit, and data impact.

## Repository deployment drift to resolve

* `scripts/deploy.sh` references the old `nba-sports-analytics` repository and defaults to `developProxy`.
* `scripts/setup_production.sh` uses `wsgi:app`, one worker, and forces proxy; `deploy.sh` uses `run:app`, three workers, and only enables proxy support.
* README and scripts disagree about paths, Python version, repository, and static alias.
* `run.py` is a development launcher and is unsafe as the production WSGI import until Redis process management is removed.

Select and test one release path before the next production deploy; treat the current shell scripts as historical automation, not authoritative executable truth. This runbook is the deployment source of truth.
