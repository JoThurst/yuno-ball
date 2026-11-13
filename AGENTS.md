# Yuno Ball Agent Instructions

## Mission
Build trustworthy NBA analytics. Prioritize data correctness and reproducibility, security, tests and observability, clear layer boundaries, performance, then product features and experiments.

## Scope and context budget
- Start implementation with branch/HEAD, `git status --short`, and the requested outcome. Preserve unrelated edits. Handoffs are context to verify, not permission to execute every listed task.
- Use `rg` to locate relevant symbols and document sections; read bounded ranges before expanding to concrete dependencies. Do not preload all canonical documents, entire handoffs, generated datasets, or broad logs.
- Load the primary applicable skill; add another only when its distinct requirements matter. Planning, implementation, and review are phases, not mandatory separate agents.
- For localized work, use a short plan and proceed. For ambiguous or cross-layer work, establish boundaries and acceptance criteria before editing.
- Complete the smallest coherent change and required verification. Stop when the requested outcome is satisfied; record adjacent debt without automatically starting refactors, audits, or follow-on features.
- Prefer compact tool results: counts, relevant rows, failing test names, and bounded error excerpts. Save large outputs to files and inspect relevant portions.

## Agents and handoffs
- Use one working agent by default. Delegate only when explicitly requested for the task; earlier delegation requests do not carry into unrelated tasks.
- When requested, delegate independent, bounded assignments with an outcome, owned files, relevant context, acceptance checks, and stopping condition. Avoid recursive delegation and full-history forks when a compact brief suffices.
- Assign one writer per file. Keep dependent steps sequential. The parent integrates results without duplicating delegated implementation or unchanged checks.
- Review a stable patch. Reviewers report actionable findings without editing unless explicitly assigned fixes. Separate planner/reviewer agents or different models are not required for every change; honor explicit requests and release gates.
- Handoffs record branch/HEAD, relevant dirty files, completed work, unresolved findings, commands/results, evidence limitations, and the next bounded step. Link details instead of copying transcripts. Verify dated status before relying on it.

## Source of truth: read relevant sections only
Code and the actual schema govern implemented behavior. Plans and generated profiles do not prove deployment or current live state. Locate the contract needed for the task:

| Task | Reference in `docs/` |
|---|---|
| Cross-layer ownership | `YUNOBALL_ARCHITECTURE.md` |
| Tables, grain, reconciliation | `DATA_DICTIONARY.md` |
| Ingestion, recovery, providers | `INGESTION_RUNBOOK.md`, `SOURCE_CATALOG.md` |
| NBA network or proxy policy | `PROXY.md` |
| Redis keys and invalidation | `CACHE_CATALOG.md` |
| Routes and presentation | `ROUTE_CATALOG.md` |
| Metrics, as-of rules, modeling | `METRIC_CATALOG.md`, `MODEL_FEATURE_PLAN.md` |
| Local setup, deployment, rollback | `DEPLOYMENT_RUNBOOK.md` |
| Product scope and priorities | `PRODUCT_STRATEGY.md` |
| Dated schema/data snapshot, only when needed | `DATABASE_PROFILE.md` |

Update the relevant canonical section in the same change when a boundary, grain, route, cache, ingestion, metric/model, or deployment contract changes. Ordinary internal edits do not require a documentation sweep. Skills naming documents mean relevant sections, not automatic full-document reads.

## Engineering constraints
- Preserve historical data and rerun safety. Use explicit transactions for multi-step writes.
- Centralize season, environment, endpoint, and network policy. Keep external NBA calls behind provider/fetch interfaces, outside routes and models.
- PostgreSQL is durable; Redis is disposable. Each cache key needs an owner, version, TTL, and invalidation trigger.
- Use named rows, dictionaries, dataclasses, or typed DTOs across service/template boundaries, not positional tuple contracts.
- Analytical payloads must expose `as_of`, source, completeness, and stale state. Predictions must record immutable model/feature versions, prediction time, training cutoff, and input completeness.
- No unauthenticated public GET may mutate data. Verify exposure and authentication at the enforcing layer.
- No hard-coded season, historical roster/game deletion during refresh, current aggregates reconstructed as historical pregame features, or target-game/postgame feature leakage.
- Do not silently replace missing data with meaningful zeroes. Allowlist dynamic SQL identifiers. Do not use Redis `KEYS` in production.
- Do not commit secrets, credentials, database URLs, sensitive host details, or generated datasets.
- Preserve existing checkout paths, scheduled jobs, and running local services. Inspect listeners/processes before starting or restarting servers; do not stop unrelated processes or move a scheduled task's checkout.
- Bound live ingestion and data writes to authorized scope. Use approved test databases; never redirect tests to live data to make failures disappear.

## Verification without repeated work
- During iteration, run focused regression tests and affected integration checks. Add tests for corrected behavior where practical.
- For a stable Python patch, run `python -m compileall app` and `pytest -q` once using the verified local environment. Repeat only checks invalidated by subsequent edits or unresolved failures; honor additional CI/release gates.
- Documentation-only changes need diff, link/path, and relevant instruction/skill validation, not the application suite.
- Data changes: check grain, uniqueness, nulls, paired rows, and reruns. Routes: useful empty/stale states. Caches: hit, miss, expiry, invalidation. Ingestion: bounded team/player/season before a full run.
- Use targeted browser inspection for affected UI behavior and screenshots when visual evidence helps. Avoid repeated full-page trees and unrelated browser journeys.
- Report failures and unavailable integration prerequisites honestly. Distinguish local, CI, staging, and live evidence; fixtures and configured workflows do not prove release readiness.

## Tools and final report
- Prefer local search, existing scripts, and direct structured tools over browser interaction when they answer the same question. Add an MCP only when it serves a concrete need; do not install one by default.
- For current library/framework/SDK/API/CLI/cloud documentation, use Context7 when available: resolve the library, then query the specific concept. If unavailable, state that briefly and use official documentation. Generic refactoring, business logic, and code review do not require documentation lookup by default.
- Summarize what changed and why, affected files/contracts, verification results, migration/cache/deployment/rollback needs, and remaining risks. Keep it concise; do not claim measured usage savings without telemetry.
- Product work is complete when it answers a real NBA question clearly, explains freshness and uncertainty, and degrades safely when sources fail.
