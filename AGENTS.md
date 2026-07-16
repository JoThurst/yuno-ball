\# Yuno Ball Agent Instructions



\## Mission

Improve Yuno Ball into a trustworthy, differentiated NBA analytics product. Prioritize correctness, maintainability, reproducibility, performance, and clear user-facing data freshness over rapid feature volume.



\## Source of truth

Read these before making material changes:



1\. `YUNOBALL\_ARCHITECTURE.md` — boundaries and current technical debt.

2\. `DATA\_DICTIONARY.md` — implemented tables, grains, and known schema issues.

3\. `INGESTION\_RUNBOOK.md` — ingestion order, idempotency, recovery, and known defects.

4\. `CACHE\_CATALOG.md` — Redis ownership, TTLs, and invalidation.

5\. `ROUTE\_CATALOG.md` — route responsibilities and UX debt.

6\. `MODEL\_FEATURE\_PLAN.md` — leakage-safe modeling contract.

7\. `DEPLOYMENT\_RUNBOOK.md` — production release, local setup baseline, and rollback.

8\. `PROXY.md` — NBA API proxy / direct network path.

9\. `PRODUCT\_STRATEGY.md` — product direction and prioritization.

10\. `DATABASE\_PROFILE.md` — generated sanitized live schema and data-quality snapshot (via `scripts/generate_database_profile.py`).

11\. `SOURCE\_CATALOG.md` — external source, endpoint, grain, cadence, and failure behavior.

12\. `METRIC\_CATALOG.md` — Yuno metric formulas, as-of rules, versions, and prohibited uses.



The repository and live schema remain authoritative for implemented behavior. Do not assume a planning document means a feature exists.



\## Engineering priorities

Work in this order unless a task explicitly requires otherwise:



1\. Data correctness and reproducibility.

2\. Security and destructive-operation controls.

3\. Tests and observability.

4\. Clear boundaries between ingestion, providers, storage, services, routes, and presentation.

5\. Performance and cache correctness.

6\. Product features and visual polish.

7\. Experimental modeling and monetization.



\## Required behavior



\- Make the smallest coherent change that solves the task.

\- Inspect relevant code and documentation before editing.

\- State consequential assumptions in the PR or final summary.

\- Preserve historical data and rerun safety.

\- Use explicit transactions for multi-step writes.

\- Centralize current season, environment, endpoint, and network policy.

\- Keep external NBA calls behind provider/fetch interfaces; avoid new calls directly from routes or models.

\- Treat PostgreSQL as durable and Redis as disposable.

\- Give every cache key an owner, version, TTL, and invalidation trigger.

\- Use named rows, dictionaries, dataclasses, or typed DTOs across service/template boundaries; do not introduce positional tuple contracts.

\- Add `as\_of`, source, completeness, and stale-state metadata to user-facing analytical payloads.

\- For predictions, record immutable model version, feature version, prediction time, training cutoff, and input completeness.

\- Update the relevant canonical document when changing a boundary, table grain, route contract, cache key, ingestion process, model contract, or deployment process.



\## Prohibited shortcuts



\- No unauthenticated public GET route may mutate data.

\- Do not hard-code a season in application or ingestion logic.

\- Do not delete historical roster or game data during a current-season refresh.

\- Do not use current endpoint aggregates to reconstruct historical pregame features.

\- Do not use target-game or postgame information in model features.

\- Do not silently replace missing values with zero when zero has a real basketball meaning.

\- Do not add dynamic SQL identifiers without a strict allowlist.

\- Do not use Redis `KEYS` in production code.

\- Do not commit secrets, proxy credentials, database URLs, production host details that should be environment configuration, or generated datasets.

\- Do not perform broad refactors and feature work in the same change unless required.



\## Verification expectations

Run the narrowest relevant checks plus affected integration checks.



Minimum for Python changes:



```bash

python -m compileall app

pytest -q

```



When no test exists, add one for corrected behavior where practical. For data changes, validate row grain, uniqueness, null rates, paired game rows, and rerun behavior. For routes, verify useful empty/stale states. For cache changes, verify hit, miss, expiration, and invalidation. For ingestion changes, test a bounded team/player/season before a full run.



\## Change summary format

Report:



\- What changed and why.

\- Files and contracts affected.

\- Commands/tests run and their results.

\- Data migration, cache invalidation, deployment, or rollback requirements.

\- Remaining risks or intentionally deferred work.



\## Product standard

A feature is not complete merely because it renders. It should answer a real NBA question faster or more clearly than a generic stats page, explain freshness and uncertainty, degrade safely when sources fail, and create a reusable data or product capability rather than a one-off page.
