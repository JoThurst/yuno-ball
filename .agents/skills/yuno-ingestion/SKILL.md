---
name: yuno-ingestion
description: Use ONLY when the task directly modifies a source adapter, fetch path, ingestion or backfill flow, or evaluates an external provider for possible integration.
---

# Yuno ingestion and source evaluation

## Allowed File Scope
- `app/services/*fetch*`, `app/services/*ingest*`, `app/services/*adapter*`, `app/services/*availability*`, `app/services/*statsurge*`, `app/services/*kaggle*`, `app/services/market_observation_*`, `app/services/sportsgameodds_client.py`, and their exact callers/tests.
- Relevant provider modules, `daily_fetch.py`, and bounded collection scripts when the task targets them.

## Do Not Read
Do not read full canonical `docs/*.md` catalogs upfront. Locate only the applicable section of `docs/INGESTION_RUNBOOK.md`, `docs/SOURCE_CATALOG.md`, or `docs/PROXY.md` with `rg -n` when its contract matters. Do not scan unrelated services, migrations, or tests.

## Source Decision
Start provider feasibility with public documentation, local fixtures, and existing evidence without credentials or live requests. Check source grain, cadence, retrieval and availability timestamps, precision, identity mapping, historical coverage, corrections, schema stability, raw retention, redistribution and model-training rights, and cost. Distinguish empty, unavailable, unsupported, and transport/parse failure. For markets, require complete reciprocal selections and preserve unknown historical timing. Record a bounded sample, request/cost ceiling, and stop condition before any trial.

A source evaluation yields reject, research-only, staging-only, or candidate for explicit integration. It does not authorize a scheduled writer, canonical promotion, public claim, or recurring spend.

## Implementation
Trace response through normalization, identity resolution, durable row, task ledger, and consumer. Preserve source hash, retrieval and availability times, parser version, and run lineage where the contract uses them. Keep missing/conflicting data explicit. Publish related durable rows transactionally; exact replay should be a no-op. Respect the daily advisory lock and avoid overlap with backfills.

## Targeted Verification
For a daily-ingestion change, run `python -m compileall app` and `pytest tests/test_daily_ingest_fail_closed.py -q --tb=short`; add the specific affected adapter/service test. For source evaluation without code changes, report reproducible evidence and gates instead of running pytest. Validate bounded failure recovery, uniqueness, nulls, reciprocal game pairs where applicable, and rerun behavior.
