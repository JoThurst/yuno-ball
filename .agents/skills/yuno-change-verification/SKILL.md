---
name: yuno-change-verification
description: Verify a bounded Yuno Ball code change with contract-specific checks and report what the evidence establishes. Use for implementation handoffs or PR review preparation.
---

# Yuno change verification

Map changed files to their owner and relevant tests. Follow `AGENTS.md` Python minimum: compile `app` and run pytest. Use the existing `sports-analytics-local-venv` skill for interpreter and test-database boundaries. Start with focused checks, then affected integration checks; never point tests at an unapproved production-like database. For frontend assets, run the relevant locked Node build and verify its generated outputs. Distinguish offline checks from PostgreSQL-backed integration checks.

Test an adverse case: route empty/stale state, ingestion failure/replay, schema uniqueness/nulls, cache miss/expiry/invalidation, or feature cutoff leakage. Inspect final diff and status to preserve unrelated edits.

Report commands/results, skipped gates, checkout/commit, changed contracts/docs, and migration/cache/deployment/rollback needs. Keep local, CI, staging, and live evidence distinct.
