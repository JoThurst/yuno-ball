---
name: yuno-data-quality-audit
description: Audit Yuno Ball dataset or analytical payload trustworthiness without changing ingestion or schema. Use for freshness, coverage, grain, missingness, duplicates, pair integrity, and reconciliation questions.
---

# Yuno data quality audit

State the dataset, environment, season/date window, expected grain, and decision the audit supports. Read relevant entries in `docs/DATA_DICTIONARY.md`, `docs/SOURCE_CATALOG.md`, and `docs/METRIC_CATALOG.md`; use `docs/DATABASE_PROFILE.md` only as a dated baseline. Do not turn a local snapshot into a current staging claim.

Work read-only against an explicitly authorized database or exported data. Measure row uniqueness, null/unknown rates, source freshness, coverage by season/date/team, reciprocal team-game pairs, canonical identity joins, and conflicting source revisions as applicable. Separate truly absent data from source failure, pending ingestion, unresolved identity, and intentionally ineligible season types. Keep a numerator, denominator, and exact cutoff with each rate.

Report reproducible queries or commands, observed counts, examples of failures, and the affected consumer. Grade claims as usable, partial, or unverified for the stated purpose; do not silently repair rows during an audit. If a fix is requested, route the implementation through the ingestion or data-contract skill.
