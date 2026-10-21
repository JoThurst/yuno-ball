---
name: yuno-cache-performance
description: Diagnose or improve Yuno Ball Redis caches and page or service latency. Use for cache key, invalidation, Redis failure, query cost, or measured performance work.
---

# Yuno cache and performance

Read `docs/CACHE_CATALOG.md` and trace the active producer and consumer before editing a key. Some legacy warmer keys have no confirmed reader. Establish a reproducible baseline for latency, query or external-call count, cache hit/miss, payload size, and user-visible freshness; optimize the measured bottleneck.

PostgreSQL remains the source of record and Redis remains disposable. A changed key needs owner, environment, version, dimensions including season/cutoff when relevant, TTL, and invalidation trigger. Never mix historical snapshots with latest-state payloads or use production `KEYS`. Cache failure must preserve a correct DB-backed response and explicit degraded state where the route supports it.

Verify hit, miss, expiry, invalidation after a source change, and Redis-unavailable behavior. Measure before and after with the same input and environment, and watch for stale live/final scoreboard data or repeated external calls. Update `docs/CACHE_CATALOG.md` when ownership or policy changes.
