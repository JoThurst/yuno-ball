---
name: yuno-doc-sync
description: Use ONLY when the task directly modifies or synchronizes canonical documentation at the user's explicit request. Never trigger automatically during code implementation.
---

# Yuno documentation sync

## Allowed File Scope
- The exact user-requested file or section in `docs/DATA_DICTIONARY.md`, `docs/ROUTE_CATALOG.md`, `docs/CACHE_CATALOG.md`, `docs/INGESTION_RUNBOOK.md`, `docs/METRIC_CATALOG.md`, `docs/SOURCE_CATALOG.md`, or another explicitly named canonical document.
- Exact `app/models/*`, `app/services/*`, or `app/routes/*` implementation files needed to verify a claim.

## Do Not Read
Do not read full canonical `docs/*.md` catalogs upfront. Find the requested section with `rg -n`. Do not scan unrelated application code, migrations, tests, or generated profiles.

## Workflow
Confirm the target claim against implemented code, tests, migrations, or an authorized live environment. Keep plans and dated snapshots labeled as such. Edit only the requested documentation boundary and retain source, grain, as-of, failure, and operational caveats that matter. Do not create a code change as a side effect of a documentation sync.

## Targeted Verification
Run `git diff --check` and inspect the exact documentation diff. Use a bounded code or SQL check only when needed to establish a factual claim; do not run `pytest -q` for a Markdown-only edit.
