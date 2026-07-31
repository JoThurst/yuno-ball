# Codex Directive — Yuno Ball Analytics Program

Use this directive after the five-phase historical-data foundation has been completed and validated.

## Mission

Implement the Yuno Ball analytics roadmap as a sequence of small, reviewable, durable changes.

Do not treat planning documents as evidence that a feature already exists.

## Required reading

Read:

- `AGENTS.md`;
- canonical architecture, data, ingestion, cache, route, model, deployment, source, and metric documents;
- the current database profile;
- every planning file in this analytics pack;
- historical source evaluations and source-spike plans.

## First deliverable

Inspect the current repository and produce:

1. implementation status matrix;
2. missing prerequisites;
3. proposed next pull request;
4. schema impact;
5. data migration;
6. tests;
7. deployment;
8. rollback;
9. documentation updates;
10. intentionally deferred scope.

Do not begin with a broad rewrite.

## Program order

1. External source manifests and staging.
2. Historical injury and odds staging.
3. Official injury collector.
4. Append-only forward odds collector.
5. Rich traditional player boxes.
6. Advanced player boxes.
7. Leakage-safe team form and schedule features.
8. Metric experiments.
9. Daily Intelligence V1.
10. Baseline game models.
11. Rotation Shock.
12. Timestamped market comparison.
13. Play-by-play, lineups, and shot profiles.
14. Distribution automation.
15. Paid product features only after licensing gates.

## Pull-request boundaries

One source or analytical contract per PR whenever practical.

Do not combine:

- migration and major UI redesign;
- new provider and prediction model;
- historical import and current collector;
- broad refactor and product feature.

## Required implementation standards

- source-specific raw/staging layer;
- canonical stable facts;
- versioned feature snapshots;
- typed service payloads;
- explicit cutoff semantics;
- immutable predictions;
- source and run provenance;
- missing/completeness states;
- reversible Alembic migration;
- idempotent bounded commands;
- job locking;
- contract tests;
- cache versioning;
- canonical doc update.

## External data rules

- raw files not committed to public Git;
- hash and manifest retained;
- license status recorded;
- staging before promotion;
- anomalies quarantined;
- vendor-derived rolling features rejected by default;
- source precision preserved;
- conflicts not silently overwritten.

## Analytics rules

- target game excluded;
- rolling windows shifted;
- no current aggregate in historical pregame rows;
- no historical fall-forward;
- no missing-to-zero;
- formula changes create new versions;
- explanations grounded in metrics.

## Model rules

- chronological splits;
- naive baseline;
- calibration;
- feature-family ablation;
- immutable prediction;
- no market observation after prediction time;
- no betting-value claim before timestamped overlap.

## Final report format

- implemented behavior;
- files changed;
- schema/contracts;
- migrations;
- commands/tests and results;
- source coverage;
- data-quality results;
- cache implications;
- deployment;
- rollback;
- unresolved licensing;
- remaining risks;
- next smallest PR.
