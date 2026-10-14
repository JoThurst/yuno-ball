# Yuno Ball Post-Foundation Roadmap

Status: superseded historical proposal; use the [Master Analytics Roadmap](MASTER_ANALYTICS_ROADMAP.md) and [canonical project status](../PROJECT_STATUS.md) for current progression. This document is retained for historical context and is not current work authorization.
Prepared: 2026-07-15  
Prerequisite: complete and validate the five-phase historical-data and season-agnostic ingestion initiative.

## Purpose

This document defines what Yuno Ball should investigate and build after the data-foundation work is complete. It does not authorize production ingestion, database migrations, provider purchases, model claims, or broad UI work before the five foundation phases pass their acceptance criteria.

The repository and live schema remain authoritative for implemented behavior. The canonical project documents must be updated when a source, table grain, calculation contract, cache payload, route contract, or deployment process changes.

## Strategic conclusion

Yuno Ball should not compete by storing the largest possible collection of NBA endpoint fields. It should compound durable information that is difficult to reconstruct later and turn that information into clear daily basketball decisions.

The first post-foundation product statement should be:

> Yuno Ball explains which NBA games matter today, why they matter, what information could change the outlook, and how confident the underlying data and models are.

## Workstreams

### Workstream A — Append-only information collection

Begin with information that loses value permanently when it is not collected:

1. Official NBA injury-report revisions.
2. Timestamped sportsbook market observations.
3. Published Yuno Ball predictions and revisions.

These observations must be immutable, timestamped, source-attributed, and linked to an ingestion run.

### Workstream B — Richer game facts

Expand player game data in this order:

1. Complete traditional player box scores.
2. Advanced player box scores.
3. Play-by-play and substitutions.
4. Lineup stints.
5. Shot profiles.
6. Tracking and hustle fields only after coverage and stability testing.

Do not begin player-prop modeling from the existing thin gamelog table.

### Workstream C — Differentiated Yuno metrics

Research and validate:

- Yuno Slate Score
- Form Quality Index
- Schedule Pressure
- Style Collision Map
- Rotation Shock
- Role Stability
- Market Reaction Tracker

Every metric requires a formula, grain, pregame cutoff, version, interpretation, missing-data behavior, and prohibited uses before production use.

### Workstream D — Daily Intelligence V1

Build one typed daily matchup payload that can power:

- the Daily homepage;
- permanent matchup pages;
- social cards;
- short-form scripts;
- newsletter sections;
- alerts;
- a future documented API.

The payload must include freshness, completeness, uncertainty, source cutoffs, and deterministic explanations.

### Workstream E — Baseline modeling

Initial targets:

1. Home-team win probability.
2. Expected home margin.
3. Expected game total.

Use chronological evaluation, shifted features, immutable predictions, calibration, and declared naive baselines. Do not claim betting value until a prediction can be compared with a market observation that existed at the prediction timestamp.

## Proposed sequence

### Milestone 1 — Source trials

Deliver:

- official injury PDF collector spike;
- historical injury-archive audit;
- odds-provider comparison and cost estimate;
- traditional/advanced box-score endpoint bake-off;
- external historical dataset audit.

Exit criteria:

- each source has a declared grain;
- raw provenance is preserved;
- licensing and redistribution status is recorded;
- sample coverage and failure rates are measured;
- no source is approved merely because it is inexpensive or accessible.

### Milestone 2 — Forward collectors

#### Live status as of 2026-07-24

Raw official injury documents and parsed observations are complete for the
archived 2024-25 and 2025-26 windows, with cutoff-aware serving, replay-safe
forward collection, canonical schedule coverage, and exact identity
reconciliation in place. The read-only daily slate adapter now exposes
game-scoped official availability with strict scheduled-tipoff cutoffs and
explicit partial/unknown states. The observations remain excluded from model
features and prediction inputs. The append-only market-observation
header/selection schema and idempotent registration service are now implemented
and migrated locally. No market collector, provider purchase, historical
promotion, public route, or model integration is included in that slice.

Implement:

- immutable injury-report document and observation storage;
- bounded live-provider evaluation followed by append-only moneyline, spread,
  and total collection into `market_observation_headers` and
  `market_observation_selections`;
- ingestion-run linkage;
- duplicate-content detection;
- player/team/game identity resolution;
- monitoring and replay-safe ingestion.

Market collectors should initially operate without changing public pages. The
existing mutable `game_odds` path remains compatibility-only until a reviewed
read adapter and source precedence policy exist.

### Milestone 3 — Rich player game facts

#### Bounded status as of 2026-07-30

C0-C6 are implemented for an 11-game reviewed slice: complete Traditional V3
facts, Advanced V3 facts, immutable correction lineage, a read-only
reconciliation gate, and canonical-first consumer reads. Historical
`gamelogs` remains the fallback and no legacy table is deprecated or deleted.
The milestone remains open for reviewed historical expansion and coverage
reporting before any redundancy decision.

Implement complete traditional player box scores, then advanced player box scores.

Exit criteria:

- numerical minutes;
- shooting attempts and makes;
- starting/participation context where available;
- offensive and defensive rebounds;
- fouls and plus/minus;
- advanced efficiency and usage fields;
- corrected-box-score upserts;
- historical coverage report by season;
- stable game/player/team keys.

### Milestone 4 — Daily Intelligence V1

Implement:

- slate ranking;
- team form from leakage-safe game history;
- schedule pressure;
- initial style-collision explanations;
- availability uncertainty;
- clear stale/partial states;
- permanent date and matchup URLs.

A model is optional for this milestone. The product should already be useful through validated descriptive intelligence.

### Milestone 5 — Baseline models

Implement and retain:

- feature snapshots;
- training cutoffs;
- model versions;
- prediction timestamps;
- prediction revisions;
- confidence or uncertainty;
- input completeness;
- walk-forward evaluation.

### Milestone 6 — Rotation and market context

After sufficient injury, odds, minutes, and role history exists:

- Rotation Shock;
- market movement timelines;
- model-versus-market comparison;
- prediction revision explanations;
- postgame review pages.

Do not imply causation from timing alone. Use wording such as “the spread moved after the status update,” not “the status update caused the move,” unless causal evidence exists.

## Data acquisition policy

External datasets may accelerate historical coverage, but they are not trusted merely because they are free or paid.

Every external dataset must pass:

1. License and commercial-use review.
2. Source-provenance review.
3. Grain and uniqueness review.
4. Timestamp semantics review.
5. Team/player/game identity matching.
6. Leakage audit.
7. Missingness and coverage audit.
8. Reconciliation against Yuno Ball and official source facts.
9. Raw-file hashing and version retention.
10. Import into staging before canonical tables.

Never import vendor-created rolling records, streaks, ATS histories, targets, or engineered features directly into model training without proving their as-of semantics. Prefer raw outcomes and raw market observations, then calculate Yuno features internally.

## Product metrics

Track:

- ingestion freshness;
- source completeness;
- parser failure rate;
- unresolved identity rate;
- Daily page usefulness interactions;
- matchup-page activation;
- returning users;
- email conversion;
- prediction calibration;
- corrected-data revision rate;
- social-to-site conversion.

## Monetization order

Prefer:

1. Original Daily analysis.
2. Email and alert convenience.
3. Premium reports and filters.
4. Sponsorship around recurring Yuno formats.
5. Creator/media exports.
6. Data/API products only after licensing, reliability, support, and rate-limit obligations are explicit.

## Deferred scope

Until the above is stable:

- player props;
- guaranteed-edge language;
- raw NBA data resale;
- full tracking ingestion;
- major UI redesign unrelated to Daily Intelligence;
- unbounded endpoint collection;
- production dependence on a community dataset.
