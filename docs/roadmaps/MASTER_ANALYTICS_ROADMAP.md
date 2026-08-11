# Yuno Ball Master Analytics Roadmap

Status: proposed post-foundation roadmap; Program B active  
Prepared: 2026-07-15  
Scope: analytics, source expansion, Daily Intelligence, modeling, distribution, and monetization after the five-phase historical-data foundation is complete

## Purpose

This roadmap defines the order in which Yuno Ball should convert its repaired ingestion and historical snapshot foundation into a differentiated NBA analytics product.

It deliberately separates durable source collection, curated analytical data, experimental metrics, production metrics, descriptive Daily Intelligence, predictive models, market comparison, media distribution, and monetization.

The repository, current database schema, and implemented tests remain authoritative. This document describes proposed work unless a repository change explicitly implements it.

## Product objective

Yuno Ball should answer five questions better than a generic statistics site:

1. Which games and players matter today?
2. What basketball factors create the matchup edge?
3. What information is uncertain or likely to change?
4. What does the model expect, and how reliable is that expectation?
5. What did Yuno Ball previously say, and how well did it perform?

The product should not become an opaque picks feed or an uncurated database browser.

## Prerequisite gate

Do not begin production implementation of this roadmap until the historical-data foundation has passed:

- season-agnostic ingestion;
- durable ingestion-run observability;
- non-destructive player snapshots;
- non-destructive team/game snapshots;
- roster and mutable-source repair;
- bounded historical backfill and operational rollout.

Minimum readiness:

- current season reconciled;
- historical cutoffs queryable;
- calculation versions persisted;
- ingestion failures queryable;
- one synchronized Alembic head;
- leakage, preservation, and idempotency tests passing.

## Program A — Historical source integration

Purpose: incorporate the free historical injury, odds, game, and player-game datasets without contaminating canonical tables.

Deliverables:

- source manifests and hashes;
- source-specific staging tables;
- anomaly quarantine;
- identity mapping;
- licensing status;
- reproducible promotion scripts;
- coverage reports by season and source.

Primary inputs:

- Stat Surge injury checkpoints, 2021-22 through 2023-24;
- Kaggle moneyline, spread, and totals, 2006-07 through 2017-18;
- supporting historical game and player-game files.

Exit gate:

- source semantics documented;
- malformed rows quarantined;
- no direct CSV-to-production import;
- source precedence defined;
- promoted rows retain provenance.

## Program B — Forward observation collectors

### Current implementation checkpoint — 2026-07-24

The official injury document archive, parser, observation grain, cutoff-aware
serving boundary, retry ledger, Task Scheduler catch-up wrapper, identity
reconciliation, and read-only daily slate adapter are implemented and
validated. The daily consumer uses canonical game IDs, strict scheduled-tipoff
publication cutoffs, and explicit complete/partial/unknown states. Unresolved
player rows remain evidence and are not converted into health claims.

The append-only market-observation header/selection contract is now implemented
and migrated locally. It preserves source artifact/run/row lineage, explicit
historical-static versus forward timing semantics, and selection-specific
market pairs without modifying legacy `game_odds`.

Next order: evaluate and select a live timestamped odds source, build a bounded
staging/collector adapter against this contract, and monitor forward injury
and slate completeness. Do not promote historical markets, replace
`game_odds`, or add injury/odds data to model features until separate source,
selection, and leakage validation gates pass.

Purpose: collect information that cannot be perfectly reconstructed later.

Order:

1. Official NBA injury-report PDF revisions.
2. Append-only moneyline, spread, and total observations.
3. Published Yuno Ball prediction revisions.
4. Source corrections and availability transitions.

Exit gate:

- raw observations retained;
- exact or declared timestamp precision;
- idempotent reruns;
- ingestion-run linkage;
- game/team/player identity resolution;
- no current-state overwrite.

## Program C — Rich player and team game facts

Status (2026-08-11): C0-C7 are complete for the approved 2025-26 and 2024-25
Regular Season coverage gates. Traditional and Advanced V3 revisions and
canonical projections are live for both 1,230-game seasons; correction/replay
and cross-source reconciliation gates pass. Direct player analytics consumers
now use a canonical-first reader with `gamelogs` fallback. This does not
authorize table removal. Play-by-play, lineup, shot-profile, tracking, and
additional season expansion remain later Program C work.

C7 coverage inventory is complete for 2025-26: all 1,230 eligible completed
Regular Season games from 2025-10-21 through 2026-04-13 have both Traditional
and Advanced canonical coverage, with zero missing or blocked games. Every
bounded batch was followed by C5 reconciliation and a database-only replay
proof. Legacy tables remain intact until the final redundancy and rollback
audit.

The 2024-25 Regular Season expansion is complete: 1,230 eligible games have
both fact sources, zero missing or blocked games, and every bounded batch has
C5 reconciliation plus a database-only replay proof. 2023-24 is not yet ready:
its team-game prerequisites are not paired and must be repaired before
player-fact collection.

The C7 backfill exposed and now addresses a historical identity gap: current
player/static discovery does not cover every short-term NBA call-up or
G-League-only DNP roster listing. C7 resolves played/unknown rows through
CommonPlayerInfo before publication and preserves DNP-only source identities
without claiming NBA season activity. It uses a separate backfill lock; daily
ingestion does not wait on the historical coverage gate.

Order:

1. Complete traditional player box scores for each approved season.
2. Advanced player box scores for the same approved season and manifest.
3. Team traditional/advanced reconciliation.
4. Play-by-play and substitutions.
5. Lineup stints.
6. Shot profiles.
7. Tracking and hustle data only after coverage testing.

Exit gate:

- numeric minutes;
- shooting volume and efficiency inputs;
- starter/participation context;
- rebounds, fouls, and plus/minus;
- usage and efficiency context;
- corrected boxes update safely;
- bounded historical coverage.

## Program D — Leakage-safe analytical feature layer

Core feature families:

- team strength;
- recent form;
- opponent-adjusted form;
- schedule pressure;
- matchup style;
- availability and rotation;
- role stability;
- season phase and stable priors.

Required metadata:

- feature version;
- feature as-of;
- data available at;
- source run;
- completeness;
- missing-input flags;
- correction/revision lineage.

Exit gate:

- target game excluded;
- rolling calculations shifted;
- time-based tests passing;
- historical features do not change merely because later games were added;
- snapshots are reproducibly rebuildable.

## Program E — Yuno metric research

Initial candidates:

1. Yuno Slate Score
2. Form Quality Index
3. Schedule Pressure Index
4. Style Collision Map
5. Rotation Shock
6. Role Stability
7. Availability Uncertainty
8. Market Disagreement
9. Model Disagreement
10. Postgame Explanation Scorecard

Each metric must move through:

- hypothesis;
- data audit;
- exact contract;
- retrospective experiment;
- stability analysis;
- user-language design;
- shadow production;
- production approval;
- monitoring;
- versioned revision.

No metric is production merely because a query can compute it.

## Program F — Daily Intelligence V1

The Daily payload should contain:

- ranked slate;
- matchup importance;
- team form;
- schedule pressure;
- availability uncertainty;
- style edges;
- role changes;
- players to watch;
- freshness and completeness;
- deterministic explanation;
- prediction only after the model gate passes.

One typed contract should power:

- homepage cards;
- permanent matchup pages;
- daily archives;
- social graphics;
- short-form scripts;
- newsletter sections;
- alerts;
- future API responses.

Exit gate:

- useful without live external calls;
- explicit stale and missing states;
- permanent URLs;
- no unversioned cache payload;
- every explanation traceable to metrics.

## Program G — Baseline game models

Targets:

1. Home-team win probability.
2. Expected home margin.
3. Expected game total.

Model order:

- naive baselines;
- Elo-style baseline;
- logistic and ridge models;
- modest boosted trees;
- calibration;
- uncertainty;
- feature-family ablations.

Production gate:

- walk-forward evaluation;
- naive baseline beaten over multiple chronological blocks;
- reasonable calibration;
- immutable predictions;
- input-completeness reporting;
- no market data obtained after prediction time.

## Program H — Availability and rotation intelligence

Inputs:

- official report revisions;
- historical checkpoint data;
- prior minutes and usage;
- starting and rotation history;
- teammate combinations;
- replacement-player quality.

Outputs:

- expected minutes at risk;
- expected usage at risk;
- role redistribution;
- rotation continuity;
- status uncertainty;
- last material status change;
- confidence and missing inputs.

Do not present exact impact when report timing or rotation data is incomplete.

## Program I — Market comparison

Required overlap:

- immutable prediction;
- timestamped market observation;
- same game and market definition;
- observation existed at prediction time;
- no live-market contamination.

Outputs:

- no-vig market probability;
- model probability;
- expected margin versus spread;
- expected total versus total;
- book disagreement;
- line movement timeline;
- prediction revision timeline.

Do not use “value,” “edge,” or closing-line claims without auditable timestamps.

## Program J — Distribution and permanent content

Outputs:

- daily matchup archive;
- team form pages;
- player role pages;
- prediction history;
- postgame review;
- social cards;
- video scripts;
- newsletter;
- alerts;
- embeddable charts.

The site remains the canonical destination.

## Program K — Monetization

Order:

1. Sponsorable recurring content.
2. Email and alert convenience.
3. Premium reports and deeper filters.
4. Membership and saved-team workflows.
5. Creator/media exports.
6. Data/API products only after licensing and reliability gates.

Do not sell raw source data merely because Yuno Ball can download it.

## Recommended release sequence

### Release 1 — External data staging

- import manifests;
- staging tables;
- injury and odds profiles;
- identity reconciliation;
- quarantine rules;
- no public behavior change.

### Release 2 — Forward collectors

- official PDF documents and parsed availability;
- append-only odds;
- collector monitoring;
- no Daily dependency yet.

### Release 3 — Rich current game facts

- traditional player boxes;
- advanced player boxes;
- corrected source updates;
- role and minutes history.

### Release 4 — Team form and schedule intelligence

- leakage-safe team rolling metrics;
- opponent adjustment;
- schedule pressure;
- Daily payload foundation.

### Release 5 — Daily Intelligence V1

- slate ranking;
- matchup explanation;
- availability uncertainty;
- permanent date/matchup pages;
- distribution contract.

### Release 6 — Baseline predictions

- win, margin, and total;
- immutable prediction history;
- calibration;
- postgame review.

### Release 7 — Rotation Shock and market comparison

- rotation impact;
- prediction revisions;
- timestamped market comparison;
- no-vig calculations;
- line movement.

### Release 8 — Advanced context

- play-by-play;
- lineups;
- shot profiles;
- deeper Style Collision.

## Cross-program non-negotiables

- No hard-coded season.
- No destructive historical refresh.
- No current aggregate used to reconstruct past pregame state.
- No target-game leakage.
- No silent missing-to-zero conversion.
- No unauthenticated mutation route.
- No positional tuple contracts.
- No unversioned analytical or cache payload.
- No raw external dataset committed to public Git.
- No public redistribution without permission.
- No model or market claim without auditable timestamps.
- No metric deployed without an exact contract.

## Analytics maturity levels

### Level 0 — Raw facts

Stored source observations with stable keys and provenance.

### Level 1 — Curated descriptive metrics

Versioned calculations with clear cutoffs and missing states.

### Level 2 — Daily explanations

Deterministic matchup and role explanations generated from curated metrics.

### Level 3 — Predictive baselines

Chronologically evaluated, calibrated, immutable forecasts.

### Level 4 — Market and availability reaction

Timestamp-aligned predictions, injury transitions, and odds observations.

### Level 5 — Productized intelligence

Reliable Daily product, permanent archives, distribution system, paid convenience, and auditable history.

Yuno Ball should not skip maturity levels merely to advertise predictions.
