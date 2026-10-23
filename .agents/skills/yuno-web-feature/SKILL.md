---
name: yuno-web-feature
description: Use ONLY when the task directly modifies a Flask route, service-backed web view, template, user-facing state, or Redis/page-performance behavior.
---

# Yuno web and cache features

## Allowed File Scope
- `app/routes/*`, `app/templates/*`, relevant `app/static/*` assets, `app/services/daily_intelligence_service.py`, `app/services/slate_service.py`, `app/services/dashboard_service.py`, `app/services/program_status_service.py`, `app/services/research_console_service.py`, `app/services/cache_service.py`, and exact callers/tests.
- Cache producers and consumers only for the key or query being changed.

## Do Not Read
Do not read full canonical `docs/*.md` catalogs upfront. Locate only the relevant `docs/ROUTE_CATALOG.md` or `docs/CACHE_CATALOG.md` section with `rg -n` when the route or cache contract matters. Do not scan static assets broadly.

## Route and State
Build analytical payloads in services and pass named fields to templates. Expose source, `as_of`, completeness, and useful empty, stale, partial, or unavailable states. Keep observation, prediction, and postgame result distinct. Daily V1 follows selected day's games to a permanent matchup with archive access. Public GET routes stay read-only; verify actual exposure/authentication at the enforcing layer. Keep external fetches behind provider interfaces. Check keyboard access and semantic landmarks on affected pages.

## Cache and Performance
Measure the same request before and after an optimization; check latency, query/external-call count, hit/miss, payload size, and freshness. Avoid N+1 queries. Each changed Redis key needs an owner, environment, version, dimensions, TTL, and invalidation trigger. PostgreSQL is the source of record; a Redis outage must preserve a correct DB-backed response and explicit degraded state where supported. Do not use Redis `KEYS` in production code.

## Targeted Verification
For Daily routes, run `python -m compileall app` and `pytest tests/test_daily_intelligence_v1.py -q --tb=short`; for other routes select the exact route test. Verify a real date/game and an empty or stale path. For cache changes, verify hit, miss, expiry, invalidation after a source change, and Redis-unavailable behavior; report before/after measurements.
