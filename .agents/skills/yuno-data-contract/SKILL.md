---
name: yuno-data-contract
description: Use ONLY when the task directly modifies PostgreSQL models, table grain, migrations or reconciliation, or audits the quality of existing durable data.
---

# Yuno data contract and quality

## Allowed File Scope
- `app/models/*`, `alembic/versions/<exact migration>.py`, `app/services/*reconcil*`, and the exact writers, readers, and tests affected by the target table.
- Read-only SQL or exported rows for a data-quality audit in the explicitly authorized environment.

## Do Not Read
Do not read full canonical `docs/*.md` catalogs upfront or the generated `docs/DATABASE_PROFILE.md` by default. Use `rg -n` for the relevant `docs/DATA_DICTIONARY.md` section. Open at most the latest one or two migrations when writing a new migration; otherwise open exact migrations only.

## Contract Change
Define row grain, uniqueness, source lineage, as-of/availability time, nullable meaning, season type, and replay behavior before editing. Keep migrations additive where feasible and identify readers/writers that coexist during rollout. Use explicit transactions for related rows, preserve history, and strictly allowlist dynamic SQL identifiers. State rollback and reconciliation implications.

## Read-Only Quality Audit
Specify dataset, environment, season/date window, expected grain, and decision. Measure uniqueness, null/unknown rates, freshness, coverage, reciprocal team-game pairs, identity joins, and conflicting revisions as applicable. Keep numerator, denominator, and cutoff with every rate. Separate absent data from source failure, pending ingestion, unresolved identity, and ineligible season types. Do not repair data during an audit. Report reproducible queries, counts, examples, and consumer impact; grade the claim usable, partial, or unverified.

## Targeted Verification
For schema work, run `python -m compileall app` and `pytest tests/test_schema_metadata.py -q --tb=short`, plus the exact migration or reconciliation test. For a read-only audit, verify queries are read-only and report observed counts and environment instead of running unrelated tests.
