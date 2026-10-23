# Yuno Ball Agent Instructions

## Mission
Improve Yuno Ball into a trustworthy NBA analytics product. Prioritize correctness, reproducibility, maintainability, performance, and visible data freshness over feature volume.

## Context and Scope
- Start with the exact branch, `git status --short`, and the target code. Preserve unrelated work.
- Use `rg -n` to find the relevant symbol. Read about 3–5 source files before the first plan or edit; expand only when a concrete dependency requires it.
- Do not sweep canonical documents or scan `app/`, migrations, tests, or static assets broadly. Open exact files and ranges as needed.
- Select one primary Yuno skill for a task. Its domain is the task's main deliverable; do not stack skills just because adjacent layers are touched.
- Leave adjacent debt outside the coherent change and note consequential findings in the final summary.
- Documentation synchronization is a separate task. Do not read or edit catalogs by default during code implementation; when the user requests a contract or documentation update, inspect only the relevant sections.

## Reference Documents: Locate, Then Read Narrowly
The repository and live schema are authoritative for implemented behavior. A plan or dated profile is not proof of a deployed feature. Use `rg -n` to find the relevant section in `docs/`; read only what governs the task.

| Task boundary | Relevant document |
|---|---|
| Schema grain, model, reconciliation | `docs/DATA_DICTIONARY.md` |
| Architecture or cross-layer ownership | `docs/YUNOBALL_ARCHITECTURE.md` |
| Fetch, ingestion, backfill, recovery | `docs/INGESTION_RUNBOOK.md` or `docs/SOURCE_CATALOG.md` |
| NBA proxy or network policy | `docs/PROXY.md` |
| Redis key, TTL, invalidation | `docs/CACHE_CATALOG.md` |
| Route or presentation contract | `docs/ROUTE_CATALOG.md` |
| Metric, as-of rule, model feature | `docs/METRIC_CATALOG.md` or `docs/MODEL_FEATURE_PLAN.md` |
| Release, local setup, rollback | `docs/DEPLOYMENT_RUNBOOK.md` |
| Product scope or priority | `docs/PRODUCT_STRATEGY.md` |

`docs/DATABASE_PROFILE.md` is a generated, dated snapshot. Open it only when the task needs that snapshot; never present it as live database evidence.

## Service Domain Map
Search within the task's domain before expanding to callers or consumers:
- Game facts and starters: `player_game_fact_*`, `player_game_advanced_fact_service.py`, `player_game_starter_*`, `starter_evidence_fetch_service.py`, and boxscore adapters.
- Availability and lineage: `availability_*`, `official_availability_*`, `statsurge_*`, `injury_service.py`, `player_identity_service.py`.
- Markets and external staging: `market_observation_*`, `sportsgameodds_client.py`, `kaggle_game_*`, `kaggle_market_*`, `external_dataset_manifest_service.py`.
- Metrics and modeling: `metric_research_service.py`, `model_baseline_experiment_service.py`, `model_input_audit_service.py`, `player_role_baseline_service.py`, `plus_minus_derivation_service.py`, `analytics_snapshot_service.py`, `consistency_service.py`, `heat_index_service.py`, `streak_calculation_service.py`.
- Web and caching: `daily_intelligence_service.py`, `slate_service.py`, `dashboard_service.py`, `program_status_service.py`, `research_console_service.py`, `cache_service.py`.

## Engineering Priorities
1. Data correctness and reproducibility.
2. Security and destructive-operation controls.
3. Tests and observability.
4. Clear provider, ingestion, storage, service, route, and presentation boundaries.
5. Performance and cache correctness.
6. Product features and visual polish.
7. Experimental modeling and monetization.

## Required Behavior
- Make the smallest coherent change and state consequential assumptions.
- Preserve historical data and rerun safety. Use explicit transactions for multi-step writes.
- Centralize current season, environment, endpoint, and network policy. Keep NBA calls behind provider/fetch interfaces.
- Treat PostgreSQL as durable and Redis as disposable. Give each cache key an owner, version, TTL, and invalidation trigger.
- Pass named rows, dictionaries, dataclasses, or typed DTOs across service/template boundaries; avoid positional tuples.
- Give user-facing analytical payloads `as_of`, source, completeness, and stale-state metadata.
- Record immutable model and feature versions, prediction time, training cutoff, and input completeness.
- Keep public GET routes read-only. Verify authentication and exposure at the enforcing layer, not from navigation visibility.
- Distinguish local, CI, staging, and live evidence. An audit, fixture, or configured workflow does not prove deployment readiness.
- For staging or release, verify the exact commit, managed PostgreSQL/Redis, backup and separate restore, ingestion replay, freshness, and rollback before claiming readiness.
- Billable infrastructure requires the cloud account, region, spending ceiling, and authorization; public traffic and scheduled ingestion require explicit scope.

## Prohibited Shortcuts
- No hard-coded season in application or ingestion logic; no deletion of historical roster or game data during a current-season refresh.
- No current aggregates as historical pregame features, or target-game and postgame information in model features.
- No silent replacement of meaningful missing values with zero.
- No dynamic SQL identifiers without a strict allowlist, and no Redis `KEYS` in production code.
- No secrets, proxy credentials, database URLs, sensitive host details, or generated datasets in commits.
- No broad refactor mixed with feature work unless the task requires it.

## Verification
Run the narrowest relevant checks and affected integration checks. For Python changes, start with:

```bash
python -m compileall app
pytest tests/<relevant_test_file>.py -q --tb=short
```

Do not run the full suite during iterative edits unless requested or needed for a final PR/merge gate. Add a focused regression test when practical. For data changes check grain, uniqueness, nulls, pairs, and reruns; for routes check empty/stale states; for cache changes check hit, miss, expiry, and invalidation; for ingestion test a bounded team/player/season before a full run. Do not run tests against a production-like database without authorization.

## Change Summary
Report what changed and why, exact files and contracts, commands and results, migration/cache/deployment/rollback needs, and remaining risks. Keep evidence levels explicit.

## Product Standard
A feature should answer a real NBA question clearly, explain freshness and uncertainty, degrade safely when sources fail, and create a reusable capability.
