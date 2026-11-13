---
name: yuno-ingestion
description: Change Yuno Ball source adapters, NBA fetch paths, daily ingestion, backfills, or recovery flows while preserving provenance and rerun safety.
---

# Yuno ingestion

Read applicable sections of `docs/INGESTION_RUNBOOK.md`, `docs/SOURCE_CATALOG.md`, and `docs/PROXY.md`. Trace source response through normalization, identity resolution, durable row, task ledger, and consumer. Confirm source grain, timestamp precision, season type, and failure behavior. Distinguish an empty source response from transport/parse failure. Keep network calls in provider/fetch code.

Where the table contract uses it, retain immutable source revisions and select a separate canonical projection. Preserve source hash, retrieval and availability times, parser version, and run lineage. Missing/conflicting data stays explicit. Make related publication transactional and exact replays no-ops; never erase history for a current-season refresh.

Start with a bounded fixture or dry run. Live calls, database apply, scheduled writers, and broad backfills require explicit scope and operational evidence. Respect the shared daily advisory lock and task ledger; initial/backfill jobs must not overlap the daily pipeline. Verify uniqueness, nulls, reciprocal game pairs where applicable, failure recovery, and rerun behavior. Update the ingestion runbook and source catalog for changed source, cadence, or failure behavior.
