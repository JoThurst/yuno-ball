# Yuno Ball NBA API Proxy

Status: canonical network-path guide for stats.nba.com access
Reviewed: 2026-07-15 against `app/utils/config_utils.py` and `app/utils/fetch/api_utils.py`.

## Why proxy exists

We use [swar/nba_api](https://github.com/swar/nba_api) for `stats.nba.com`. Datacenter / AWS IP ranges are often blocked. The app centralizes proxy selection so routes and models do not construct ad-hoc NBA clients.

Pass nba_api's `STATS_HEADERS` (includes `x-nba-stats-token` / `x-nba-stats-origin`). Custom headers that omit those often hang or time out.

## Environment variables

Never commit credentials. Put them in `.env` locally or `/etc/yunoball/yunoball.env` in production (`mode 600`).

```bash
PROXY_ENABLED=true
FORCE_LOCAL=false
FORCE_PROXY=false

SMARTPROXY_USERNAME=user-your_username
SMARTPROXY_PASSWORD=your_password
SMARTPROXY_HOST=gate.decodo.com
SMARTPROXY_PORTS=7000
SMARTPROXY_SCHEME=http
```

| Variable | Purpose |
| --- | --- |
| `PROXY_ENABLED` | Allow proxy-aware NBA calls when not forced local |
| `FORCE_LOCAL` | Always use direct connection (diagnostics) |
| `FORCE_PROXY` | Always use proxy (even on non-AWS hosts) |
| `SMARTPROXY_*` | Provider host, ports, scheme, and credentials |

Notes:

* Prefer `SMARTPROXY_SCHEME=http`. `https://user:pass@host...` commonly fails with `RemoteDisconnected`.
* Decodo usernames usually start with `user-`. The app warns / may auto-prefix if missing.
* Residential rotating endpoint is commonly port `7000`. Sticky ports only work if your plan exposes them.
* On AWS, scripts often reduce `MAX_WORKERS` to `1`.

Behavior summary:

* Local by default: proxy off unless `--proxy` / `FORCE_PROXY=true`.
* AWS / enabled: proxy on unless `--local` / `FORCE_LOCAL=true`.

## CLI usage

```bash
# Connectivity checks
python scripts/test_proxy.py
python scripts/test_proxy.py --proxy
python scripts/test_proxy.py --local
python scripts/verify_proxy_setup.py   # if present

# App / ingest
python run.py --proxy
python run.py --local
python daily_ingest.py --proxy
python daily_ingest.py --local
python ingest_data.py --proxy
```

Windows helpers may exist as `scripts/test_proxy.bat` / `scripts/test_smartproxy.bat` wrapping the same Python entry points.

## Implementation ownership

| File | Responsibility |
| --- | --- |
| `app/utils/config_utils.py` | Env parsing, AWS detection, proxy URL list |
| `app/utils/fetch/api_utils.py` | `get_api_config()` for endpoint constructors |
| `scripts/test_proxy.py` | End-to-end NBA call via configured path |

Keep new NBA HTTP behind these helpers. Do not scatter raw `nba_api` constructors from routes or models.

## Troubleshooting

1. **Timeouts** — raise timeout in `get_api_config()`; confirm scheme is `http`.
2. **Auth failures** — verify username/password and `user-` prefix; never paste secrets into docs or tickets.
3. **Proxy blocked** — rotate port/provider; try `--local` only from a non-blocked network.
4. **Rate limiting** — adjust shared limiter in config; prefer fewer endpoint fan-outs over higher concurrency.
5. **IPv6 direct path** — see [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) IPv6 checks before relying on proxy as the only EC2 option.
