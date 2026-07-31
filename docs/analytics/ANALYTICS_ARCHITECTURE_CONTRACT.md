# Yuno Ball Analytics Architecture Contract

Status: proposed architecture contract  
Prepared: 2026-07-15

## Purpose

Define the technical boundaries for analytics after the historical-data foundation is complete.

## Layer model

### 1. Raw source layer

Contains immutable source artifacts:

- provider JSON;
- official PDFs;
- downloaded CSV files;
- source response metadata;
- hashes;
- retrieval timestamps;
- request parameters;
- parser outcomes.

Raw artifacts must not be rewritten to match application expectations.

### 2. Staging layer

Contains source-shaped relational rows.

Examples:

- `stg_kaggle_moneylines`
- `stg_statsurge_availability`
- `stg_nba_boxscore_traditional_v3`

Responsibilities:

- type coercion;
- source-specific normalization;
- row-level validation;
- anomaly tagging;
- identity candidates;
- no public consumer.

### 3. Canonical fact layer

Stable basketball facts:

- games;
- team-game facts;
- player-game facts;
- rosters;
- schedule;
- market observations;
- availability observations.

Canonical rows retain source and ingestion lineage.

### 4. Feature snapshot layer

Pregame or declared-cutoff observations:

- team form;
- schedule factors;
- player role;
- availability impact;
- matchup interaction;
- model input snapshots.

Feature rows are versioned and immutable by logical revision.

### 5. Metric/product layer

User-facing analytical contracts:

- Slate Score;
- Form Quality;
- Rotation Shock;
- Style Collision;
- Daily matchup payload.

These fields include interpretation, confidence, freshness, and missing-state metadata.

### 6. Prediction layer

Immutable prediction records:

- game;
- model version;
- feature version;
- training cutoff;
- prediction time;
- outputs;
- uncertainty;
- completeness;
- revision relationship.

### 7. Presentation and distribution layer

- routes;
- templates;
- JSON contracts;
- caches;
- social cards;
- scripts;
- newsletter;
- alerts.

Presentation does not recalculate analytics.

## Source precedence

When two sources overlap:

1. Preserve both raw observations.
2. Compare at the natural grain.
3. Apply a documented precedence rule for the canonical current value.
4. Retain a conflict record.
5. Trigger derived-data recalculation when a canonical fact changes.
6. Never silently discard the losing source.

Suggested precedence classes:

- official direct source;
- licensed provider;
- trusted community reconstruction;
- historical aggregate;
- inferred repair.

### Implemented external-pack precedence

The historical external pack uses non-destructive, field-specific precedence:

1. **Schedule and final game facts.** A complete existing official NBA
   schedule/game fact remains authoritative. Kaggle may fill a canonical game
   only when the exact NBA game ID is absent and reciprocal teams, season,
   event type, date, result, and score agree. It never overwrites an existing
   conflicting row; conflicts remain staged and queryable.
2. **Historical market observations.** Kaggle moneyline, spread, and total
   records are append-only observations with `timing_precision = unknown` and
   `snapshot_type = historical_static`. They do not overwrite `game_odds`, do
   not become a canonical current value, and are ineligible for prediction-time,
   opening, closing, or line-movement claims. Future exact-time observations
   coexist at their own source/observation grain and are selected by an
   explicit as-of rule rather than field overwrite.
3. **Historical availability checkpoints.** Stat Surge is a daily methodology-
   level checkpoint, not an exact official report revision. Resolved identities
   do not overwrite current or future official availability. Official NBA PDF
   revisions will take precedence for exact-time status consumers; Stat Surge
   remains historical context with `cutoff_status = unknown` unless stronger
   source evidence is added under a new version.
4. **Player and team game facts.** Official NBA facts win overlap conflicts.
   Registered historical artifacts may fill reviewed gaps only through a
   separate bounded promotion with immutable source/run/row/parser lineage.
5. **Anomalies and unresolved identities.** Quarantined market rows, ambiguous
   identities, and unresolved source rows are never silently promoted. A later
   reviewed alias or correction creates versioned resolution evidence and does
   not rewrite the raw source value.

These rules are reversible because source-shaped staging remains intact and
every promoted row retains the manifest and ingestion lineage needed to remove
or supersede one source without deleting another source's evidence.

Precedence may be field-specific.

## Timestamp contract

Allowed concepts:

- `scheduled_tipoff`
- `actual_tipoff`
- `source_published_at`
- `provider_updated_at`
- `retrieved_at`
- `observed_at`
- `data_available_at`
- `feature_as_of`
- `prediction_at`
- `created_at`

`created_at` is never a substitute for `feature_as_of`.

Unknown precision must be explicit:

- exact;
- minute;
- report checkpoint;
- date only;
- unknown.

## Completeness contract

Use explicit states:

- complete;
- partial;
- stale;
- unavailable;
- source_failed;
- identity_unresolved;
- insufficient_history;
- after_cutoff;
- quarantined.

Do not convert these states to zero-valued statistics.

## Version contract

Persist:

- parser version;
- transformation version;
- metric version;
- feature version;
- model version;
- response payload version;
- cache version.

A formula change must not silently alter history under the same version.

## Correction contract

Source facts may be corrected.

Required behavior:

- source observation retained;
- canonical revision recorded;
- affected snapshots identifiable;
- recalculation creates an explicit revision/version;
- published predictions remain immutable;
- latest views may point to the newest approved revision.

## Query contract

Current query:

- newest complete row with cutoff less than or equal to request cutoff;
- return as-of, freshness, version, and completeness.

Historical query:

- never fall forward;
- return unavailable when no valid row exists;
- never substitute current season aggregate.

## Service boundaries

- providers fetch;
- parsers normalize;
- repositories persist;
- feature builders calculate;
- metric services interpret;
- slate service assembles;
- routes present;
- caches accelerate.

No route should call an NBA endpoint directly.

## Cache contract

Each analytical cache key includes:

- environment;
- product domain;
- payload version;
- season;
- date/cutoff;
- relevant dimensions.

Invalidate only after successful canonical or feature commits.

## Test contract

Every layer requires tests for:

- natural-grain uniqueness;
- idempotent rerun;
- source fixture;
- missing input;
- correction behavior;
- historical cutoff;
- version change;
- failed-source state;
- serialization contract.
