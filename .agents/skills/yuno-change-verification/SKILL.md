---
name: yuno-change-verification
description: Verify a bounded Yuno Ball code change with contract-specific checks and report what the evidence establishes. Use for implementation handoffs or PR review preparation.
---

# Yuno change verification

Map changed files to their owner and relevant tests. Follow the verification cadence in `AGENTS.md`: focused checks during iteration, then compile `app` and run the full pytest suite once for a stable Python patch. Reuse valid results for the same unchanged patch and environment; repeat checks only when edits or unresolved failures justify them. Use the existing `sports-analytics-local-venv` skill when running Python for interpreter and test-database boundaries. Never point tests at an unapproved production-like database. For frontend assets, run the relevant locked Node build and verify its generated outputs. Distinguish offline checks from PostgreSQL-backed integration checks. Documentation-only edits do not require application tests.

Test an adverse case: route empty/stale state, ingestion failure/replay, schema uniqueness/nulls, cache miss/expiry/invalidation, or feature cutoff leakage. Inspect final diff and status to preserve unrelated edits.

For review-only assignments, report actionable findings against the stable patch without editing it. Report commands/results, skipped gates, checkout/commit, changed contracts/docs, and migration/cache/deployment/rollback needs. Summarize counts and relevant failures rather than pasting full logs. Keep local, CI, staging, and live evidence distinct.
