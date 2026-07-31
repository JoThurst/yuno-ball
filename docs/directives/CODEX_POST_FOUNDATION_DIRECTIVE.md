# Codex Directive — Yuno Ball Post-Foundation Research and Source Trials

Use this directive only after the five-phase historical-data and season-agnostic ingestion initiative has been completed, merged, deployed, and validated.

## Context

Yuno Ball now needs to evaluate and eventually implement:

- official NBA injury-report revision ingestion;
- historical injury bridging;
- append-only odds observations;
- external historical odds datasets;
- richer player traditional and advanced box scores;
- differentiated Daily Intelligence features.

Read before acting:

- `AGENTS.md`
- `YUNOBALL_ARCHITECTURE.md`
- `DATA_DICTIONARY.md`
- `INGESTION_RUNBOOK.md`
- `SOURCE_CATALOG.md`
- `METRIC_CATALOG.md`
- `MODEL_FEATURE_PLAN.md`
- `DATABASE_PROFILE.md`
- `CACHE_CATALOG.md`
- `ROUTE_CATALOG.md`
- `DEPLOYMENT_RUNBOOK.md`
- `POST_FOUNDATION_ROADMAP.md`
- `AVAILABILITY_SOURCE_SPIKE.md`
- `ODDS_OBSERVATION_PLAN.md`
- `PLAYER_BOXSCORE_EXPANSION.md`
- `EXTERNAL_DATASET_EVALUATION.md`

The repository and current live schema are authoritative for implemented behavior.

## Required first action

Do not immediately implement all sources.

Produce an audit and phased plan covering:

1. Current tables and consumers affected.
2. Proposed source/provider boundaries.
3. Proposed raw, staging, and curated tables.
4. Observation grains and uniqueness.
5. Timestamp and pregame-cutoff semantics.
6. Source provenance.
7. License and redistribution status.
8. Backfill eligibility.
9. Migration and rollback.
10. Cache and page-contract implications.
11. Tests and monitoring.
12. Cost estimates for paid data.

## Phase A — Availability spike

Implement only a bounded source spike:

- scrape official injury-page links;
- download a small sample of report PDFs;
- retain raw hashes and timestamps;
- parse normalized observations;
- represent `NOT YET SUBMITTED`;
- map sample games, teams, and players;
- compare repeated revisions;
- audit historical URL retention;
- stage the Stat Surge archive separately.

Do not change public injury pages during the spike.

## Phase B — Odds evaluation

- audit the Kaggle dataset metadata, license, schema, and provenance;
- obtain a Scottfree sample and license before purchase;
- compare at least one live timestamped provider;
- model season-level polling costs;
- design append-only market observations;
- create staging import profiles;
- reject vendor-engineered features by default until leakage is disproven.

Do not claim betting value.

## Phase C — Player box-score endpoint bake-off

Test current V3 box-score endpoint families using named datasets.

Deliver:

- endpoint matrix;
- historical coverage;
- schema fixtures;
- latency/failure rates;
- stable curated traditional schema;
- stable curated advanced schema;
- corrected-box-score behavior;
- bounded backfill plan.

Do not add play-by-play in the same pull request.

## Implementation boundaries

- One source family per reviewable pull request.
- Raw payload/file retention separated from curated tables.
- External data enters staging first.
- PostgreSQL is durable; Redis is disposable.
- Every observation links to an ingestion run.
- All timestamps have explicit timezone semantics.
- No current or future observation may enter a historical pregame feature.
- No hard-coded seasons.
- No broad destructive refresh.
- No positional tuple contracts.
- No silent identity guessing.
- No missing-to-zero substitution.
- No public redistribution without permission.

## Required tests

- idempotent reruns;
- duplicate-content handling;
- source outage;
- parser failure;
- unresolved identity;
- historical cutoff;
- post-tip exclusion;
- corrected source data;
- season rollover;
- staging-to-curated promotion;
- license/provenance manifest presence;
- raw file/payload hash retention.

## Documentation

Update canonical documents only for implemented behavior. Keep proposals clearly labeled.

At completion report:

- what was verified;
- what was implemented;
- what was only staged;
- source coverage;
- parser accuracy;
- unmatched identities;
- provider cost;
- licensing gaps;
- migrations;
- tests;
- deployment and rollback;
- recommended next pull request.
