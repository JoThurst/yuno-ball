# Yuno Ball Master Analytics Roadmap

Status: see [canonical project status](../PROJECT_STATUS.md); C7 historical player-fact foundation complete; Program D foundation complete for approved seasons; Program G research gates complete; H1 foundation implemented; no rotation metric or prediction is approved for production
Reviewed: 2026-10-11
Scope: analytics, source expansion, Daily Intelligence, modeling, distribution, and monetization after the five-phase historical-data foundation is complete

## Purpose

This roadmap defines the order in which Yuno Ball should convert its repaired ingestion and historical snapshot foundation into a differentiated NBA analytics product.

It deliberately separates durable source collection, curated analytical data, experimental metrics, production metrics, descriptive Daily Intelligence, predictive models, market comparison, media distribution, and monetization.

The repository, current database schema, and implemented tests remain authoritative. This document describes proposed work unless a repository change explicitly implements it.

## Integration checkpoint — 2026-10-11

Daily presentation and historical matchup context received a readability and
coverage update. Final games expose available canonical traditional rows with
partial/missing game-level coverage and provenance; the V1 compact leader
field remains for existing API consumers. Scheduled games remain pregame-only.

Deployment entrypoints now agree with their runtime protocols (`wsgi:app` for
Gunicorn and `asgi:app` for Uvicorn), and imports respect configured proxy
policy. H1 source-timing audits now fail closed when a fact's own game lacks
exact tipoff evidence. This improves the audit gate but does not establish
original source-publication timing, so H1 remains blocked on forward evidence.

Program G gained a held-out monitoring helper that requires full, same-size
populations and reports production approval as false. Program E SoS examples
now have a research-only contract. SportsGameOdds fixture checks require
finite spread/total lines and reciprocal spread signs; no live request or
durable ingestion was performed. None of these changes promotes a prediction,
SoS field, rotation claim, or market edge into the public product.

Focused integration verification passed: 46 tests, including a service-level
partial box-score and V1 compatibility test, plus compilation of the
application and changed scripts. The full suite returned 432 passed, 15
skipped, and 2 database-dependent failures under inert localhost settings;
the full database-backed gate remains unverified here. See
[`PROJECT_STATUS.md`](../PROJECT_STATUS.md) for exact failing tests and limits.

## Current analytics checkpoint — 2026-10-10

The ingestion foundation has crossed the Program C7 gate for six reviewed
Regular Season backfills from 2020-21 through 2025-26. The canonical
Traditional and Advanced V3 fact projections are key-matched and complete for
28,859/31,321/31,542/32,385/32,515/32,179 player-game rows respectively; the
2020-21 season correctly uses its shortened 1,080-game scope and the other five
seasons use 1,230 games. The regenerated database profile is the current source
of truth, at Alembic head `i5j6k7l8m9n0`, with legacy `gamelogs` retained.

The paired team-game foundation covers 2,160 rows for 2020-21 and 2,460 rows
for each later reviewed season. Duplicate candidate-key checks are zero and
all 7,230 stored team-game IDs have exactly two reciprocal rows. These counts
establish a durable historical fact foundation; they do not automatically mean
that every season has Program D feature snapshots.

Program D is complete for the approved 2024-25 and 2025-26 feature seasons.
The approved 2024-25 rollout covers all 1,230 scheduled games with 2,460
paired team features and 1,230 game environments; the local 2025-26 snapshot
foundation has the same team/environment coverage. The four player snapshot
families are populated wherever a pregame history exists; the first
opening-night cutoff intentionally remains missing rather than inventing
preseason history. Every applied slice passed offline validation, cutoff
checks, exact team/player replay, and natural-key duplicate audits; the
opening-night team repair passed its own exact replay.
Program D feature snapshots remain intentionally scoped to the approved
2024-25 and 2025-26 seasons. The latest profiled completed event is a 2025-26
playoff game (`0042500405`) with schedule rows but no team stats or player logs,
which is an operational freshness gap outside the completed Regular Season C7
scope. The 2026-27 local onboarding now contains 1,200 identified Regular
Season games (2,400 schedule rows) and 582 roster rows across all 30 teams;
seven unresolved NBA Cup/TBD placeholders remain excluded until opponents are
identified. Preseason is now underway externally, but this database snapshot
contains zero `Pre Season` schedule rows and zero 2026-27 canonical player
facts. The existing C7 bridge remains intentionally Regular Season-only, so
the next smoke trigger is the first completed eligible Regular Season game.

### Pre-Program E readiness decision — 2026-08-25

The NBA released the complete 2026-27 Regular Season schedule on August 13,
2026 ([official release](https://www.nba.com/news/2026-27-nba-regular-season-schedule)).
The local database now contains the identified 2026-27 schedule and all 30
current rosters, so the remaining current-season onboarding work is proof and
refresh discipline rather than initial loading. It is not a blocker for metric
research on the approved 2024-25 and 2025-26 datasets.

The following items are now explicitly separated:

- **Schedule onboarding:** initial load is complete for identified games;
  rerun the coverage inventory after each refresh and retain the explicit
  exclusion of unresolved NBA Cup/TBD games.
- **Roster onboarding:** the initial 2026-27 refresh succeeded for all 30
  teams; future refreshes must reconcile current membership without removing
  prior seasons. The historical 2024-25 roster warning remains a compatibility
  follow-up, not a reason to invalidate the completed snapshots.
- **`plus_minus` integrity:** the schema/source contract is repaired as a
  nullable derived value from exact reciprocal team points. Pair-incomplete
  rows remain NULL; no default-zero reconstruction is allowed. The ORM write
  paths and the `h4i5j6k7l8` migration apply the same contract.
- **Daily C7 bridge:** the bounded, C5-gated `daily_fetch.player_facts` task is
  implemented and passed a pre-season no-op proof. A completed-game smoke proof
  with exact replay is still required before production current-season
  Traditional/Advanced V3 facts are expected. The bridge does not block
  Program E research.
- **2024-25 team-value integrity:** the initial audit found `oreb`, `dreb`, and
  `wl` null in all 2,460 2024-25 `team_game_stats` rows. The bounded
  TeamGameLog repair and snapshot rebuild completed on 2026-08-25: all six
  source result/rebound fields are populated, self-opponent identities are
  zero, and the rebuilt team/environment snapshots pass coverage checks.

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

Status (2026-09-03): C0-C7 are complete for the reviewed 2020-21 through
2025-26 Regular Season coverage gates. Traditional and Advanced V3 revisions
and canonical projections are live for all six seasons; correction/replay and
cross-source reconciliation gates pass. Direct player analytics consumers use
a canonical-first reader with `gamelogs` fallback. This does not authorize
table removal. Play-by-play, lineup, shot-profile, tracking, and additional
source expansion remain later Program C work.

C7 coverage inventory is complete for 2025-26: all 1,230 eligible completed
Regular Season games from 2025-10-21 through 2026-04-13 have both Traditional
and Advanced canonical coverage, with zero missing or blocked games. Every
bounded batch was followed by C5 reconciliation and a database-only replay
proof. Legacy tables remain intact until the final redundancy and rollback
audit.

The 2024-25, 2023-24, 2022-23, 2021-22, and 2020-21 Regular Season expansions
are complete with zero missing or blocked games in their final inventories.
Every bounded batch used at most 25 games, fetched Traditional before Advanced,
ran C5 reconciliation, and passed a database-only exact replay. The historical
team-game prerequisite is paired for all six reviewed seasons. The next C7
work is the season-launch daily bridge and 2026-27 onboarding, not an automatic
expansion into more tables or feature snapshots.

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

Status (2026-09-03): the `team-v2.1` snapshot foundation is implemented and
locally populated for the approved 2024-25 and 2025-26 feature seasons after
the early-season boundary repair. The 2024-25 repair populated `oreb`, `dreb`,
`wl`, `w`, `l`, and `w_pct` across all 2,460 team rows, corrected five
self-opponent identities, and rebuilt/revalidated dependent snapshots. Player
snapshots remain descriptive historical context, not a full
availability/rotation model. No Program D snapshot publication has been
authorized for 2020-21 through 2023-24.

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

D completion additionally requires:

- 2024-25 team and environment snapshots cover the intended completed-game
  range;
- player snapshot writes remain idempotent and preserve missingness semantics;
- `data_available_at` and `feature_as_of` satisfy the pregame cutoff contract;
- completeness and missing-input flags are queryable by consumer;
- daily ingestion remains independent of supervised historical backfill.

Completion evidence for the approved feature seasons:

- 1,230/1,230 scheduled games have one environment and 2,460/2,460 paired
  team-perspective features in both 2024-25 and 2025-26;
- zero unpaired games, natural-key duplicates, cutoff violations, or advisory
  locks;
- D1-D6 and the opening-night repair each passed a same-range exact replay;
- legacy `gamelogs` and other historical tables remain intact;
- the first opening-night player snapshot is honestly absent because no prior
  game history exists at that cutoff.

## Program E — Yuno metric research

Program E may begin as a research and data-audit phase on the approved C/D
foundation. Initial metric contracts must use an explicit input allowlist and exclude unvalidated
unapproved market observations, and any current
state table that lacks a historical cutoff. Current-season schedule, roster,
and daily C7 onboarding are operational gates for season launch, not
prerequisites for retrospective metric research. Team-based retrospective
experiments may use the complete 2025-26 rows and the repaired 2024-25 rows,
subject to each snapshot's completeness state; player-only experiments may use
both approved seasons.

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

### Program E progress checkpoint — 2026-09-03

The first reusable research framework is now implemented as a pure service:
`MetricContract`, `MetricResult`, and the versioned
`schedule_pressure-v0.1` candidate. It enforces explicit required inputs,
pregame cutoff ordering, visible partial states, quarantine for inconsistent
source fields, deterministic replay, and a bounded 0-100 candidate output.
The calculator is non-persistent and has no production consumer. The first
Program E gate was the read-only
`scripts/audit_program_e_schedule_pressure.py` retrospective over paired
complete 2025-26 team/game rows. The sensitivity/outcome comparison,
paired-game evaluation, and cross-season validation have now completed for
this candidate; production approval remains open.

The Schedule Pressure bounded-cohort coverage gate passed on 2026-08-25 for
1,075 exactly paired games / 2,150 team rows. Ten snapshot-only games were
excluded explicitly; no schedule-factor or cutoff consistency failures were
reported. The subsequent descriptive outcome comparison found correlations of
-0.0136 with W/L and -0.0265 with point differential. This is a research
signal, not production metric approval or a win predictor.

At the whole-game level, the 2025-26 mean winner-minus-loser pressure
difference was -0.4314; winners had higher/lower/tied pressure at 30.79% /
30.70% / 38.51%. The repaired 2024-25 replication covered 1,075 paired games
and 2,150 team rows with 100% outcome coverage; correlations were -0.0710 with
W/L and -0.0731 with point differential. Its winner-minus-loser pressure
difference averaged -2.1860, with higher/lower/tied rates of 25.21% / 31.07%
/ 43.72%. Schedule Pressure v0.1 remains a descriptive research candidate,
not a production metric or win predictor.

The Schedule Pressure v0.1 contract and neutral user-language wording are now
locked for read-only shadow evaluation. The wording describes schedule strain
from rest and recent game density, explicitly excludes opponent strength and
travel from v0.1, and remains clear that the result is not a performance or
outcome prediction.

The bounded shadow evaluation has now passed for both approved seasons: 2,150
eligible team rows across 1,075 paired games per season, zero missing schedule
factors, zero replay mismatches, and no writes. Schedule Pressure v0.1 is now
approved for descriptive shadow use only. The next bounded E step is the
separate Opponent Difficulty / Strength of Schedule research audit. The non-persistent
`scripts/shadow_program_e_schedule_pressure.py` runner, with
`scripts/prototype_program_e_schedule_pressure.py` retained for human-readable
examples. The shadow runner calculates every selected row twice, checks exact
replay, and reports status/label coverage without writing metric rows. Do not
add a route, cache, or durable metric table until the language is useful,
missingness is acceptable, and the production approval gate is separately
passed.

Opponent Difficulty / Strength of Schedule begins as two related but distinct
research dimensions: target-game opponent strength from the opponent's exact
pregame snapshot, and rolling prior-opponent strength from the team's
`sos_net_*` snapshot fields. Start with coverage, pairing, cutoff, and
distribution evidence before choosing a 0-100 transformation or composite.
The first read-only audit passed for both approved seasons: all six candidate
fields were 100% populated on 2,150 eligible rows per season, with zero missing
opponent perspectives, pair mismatches, or cutoff failures. The next gate is
formula comparison in raw net-rating units before any 0-100 presentation or
persistent consumer is considered. That comparison found target-opponent
season/recent net rating to be the stronger game-level context, while team SoS
remains a separate historical-schedule explanation; the provisional 60/40
blend is not approved. The raw-unit user-language prototype is now
implemented through `scripts/prototype_program_e_opponent_difficulty.py`. It
presents target-game opponent strength and prior-opponent SoS separately, with
no bands, composite, 0-100 scaling, persistence, or production consumer. The
raw-unit wording has been reviewed and approved for research use. The
pregame-safe scaling study was then completed using only prior reference
distributions; no 0-100 transformation or consumer is approved yet.

The next gate was a read-only pregame-safe scaling study using only prior
reference distributions. It covered 2,150 target rows across 1,075 games in
each approved season. The runner withheld 38 early-history rows in 2025-26 and
20 in the approved 2024-25 cohort until 20 prior reference values existed; all
remaining rows received deterministic empirical percentiles. Percentile means
stayed near 50 in both seasons and raw/percentile outcome relationships were
directionally stable. This supports percentile as a possible explanation layer,
not as a new predictive signal. No 0-100 transformation, threshold, composite,
persistence, or consumer is approved; the next gate is wording comparison and
explicit production approval. The scaled wording prototype now exposes
raw-value-first, percentile-first, and compact matchup styles from actual
pregame rows. The wording and read-only replay are complete; explicit
descriptive-shadow approval remains open. No style or percentile presentation
is approved for a production consumer.

Style Collision Map has now passed its input audit for both approved seasons:
2,150 safe team rows across 1,075 paired games per season. Only the pace
preference interaction is fully supported by the current snapshot grain. Seven
planned edges are blocked because their defensive or possession-level
counterparts are not stored. The read-only pace experiment completed with
1,053 usable 2025-26 games and 1,055 usable 2024-25 games after intentional
early-history withholding. The pace wording prototype and a deterministic
read-only shadow replay of both the Pace and Opponent Difficulty / SoS runners
then completed with no database writes. Pace and target Opponent Difficulty are
approved for descriptive shadow use; prior Strength of Schedule remains a
separate unapproved context. The missing 2024-25 `pf` values are deferred to
the future free-throw-pressure/foul-rate edge and do not block this sequence.

The historical C7 foundation is now complete across six Regular Seasons, so
Program E research has a stable player/team base while the remaining 2026-27
operational work is limited to refresh discipline and a completed-game bridge
smoke proof. Schedule Pressure v0.1, target Opponent
Difficulty, and Pace are approved for descriptive shadow use only. Prior
opponent Strength of Schedule remains a separate research context whose
shadow approval is still open; the provisional blend is not approved. No
Program E metric is approved for production, persisted as a durable metric
table, or exposed as a prediction.

Rotation Shock has now entered its input-audit gate. Traditional and Advanced
player facts are complete and key-matched for both approved seasons, and
official availability observations plus prior actual minutes, usage, and assist
percentage can support a scoped v0.1 research prototype. Starter status is
known with provenance for 390 covered 2024-25 facts, but remains unknown for
uncovered 2024-25 facts and all 2025-26 facts; expected pregame minutes are
not stored, and no lineup/rotation table exists. The full planned metric is
therefore not yet supportable. The two-track work runs the clearly labeled
availability-and-role-disruption proxy while separately validating a starter
source. The proxy replay is now complete for both approved seasons: 777 of
2,433 observed-risk 2025-26 panels and 566 of 1,592 observed-risk 2024-25
panels had complete prior same-team role baselines. The remainder is withheld,
not imputed. A broader V2 trial returned usable `START_POSITION` rows for 39
2024-25 games, with all 390 starter rows matching canonical grain, but returned
zero player rows for two 2025-26 games. The reviewed trial is now persisted in
the additive `player_game_starter_evidence` table as 1,022 immutable source rows
(390 starter rows) across 39 reviewed 2024-25 games; the latest exact apply
replay created zero new rows. A provenance-linked projection then updated 390
canonical facts, and its exact replays also produced zero updates. V2 is
therefore a strong candidate for a bounded 2024-25 evidence backfill—not a
universal source—and remains unsuitable for 2025-26 while V2 returns empty
player sets there.

### Operational concerns checkpoint — 2026-09-05

The schedule/roster onboarding, daily canonical bridge implementation, and
`plus_minus` contract cleanup are complete. The daily bridge has passed its
pre-season no-op proof but still needs one completed-game Traditional →
Advanced → C5 → exact-replay smoke proof after the season begins. The
starter/availability audit remains a bounded research input: only 390 reviewed
2024-25 facts have starter/bench provenance, and no lineup/rotation table is
available. The read-only `scripts/audit_legacy_redundancy.py` inventory now
establishes the first table/grain/consumer baseline; no legacy table is
approved for deletion or replacement until the final migration and rollback
gate.

The current database is at Alembic head `i5j6k7l8m9n0`. Preseason schedule rows
remain separate from the reviewed Regular Season C7/Program D boundary, and
the identified 2026-27 schedule does not authorize a completed-game smoke
proof before a completed game exists. The additive H1 migration is applied and
current/head parity is confirmed; the role-baseline migration and rollback
implications remain bounded to the H1 gate.

The latest SoS research gate passed coverage, pairing, cutoff, raw-unit
comparison, wording, and deterministic replay for both approved seasons.
Rolling prior-opponent SoS remains separate from target-game Opponent
Difficulty and remains research-only: no durable field, route, cache, or
descriptive shadow approval is granted by this checkpoint. See
`docs/research/PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md`.

### Live transport follow-up — 2026-09-12

The live box-score starter adapter now has a regression test for proxy rotation
after a transport failure: the failed endpoint is marked failed, the next
healthy endpoint is attempted, and the successful endpoint is marked healthy.
The existing service-level test continues to cover fallback to Traditional V2
with preserved provenance. This hardens the resolved transport path without
changing the public contract.

## Program F — Daily Intelligence V1

F0 package slice implemented on 2026-09-05: `daily-intelligence-v1` is now a
read-only typed adapter and `/daily/api/v1` endpoint over the cutoff-safe slate
service. It provides deterministic editorial ranking, descriptive insight
families, explicit freshness/completeness, and provenance. It intentionally
does not promote prior rolling SoS, add predictions, or add a durable metric.
See `docs/research/DAILY_INTELLIGENCE_V1_PACKAGE_2026-09-05.md`.

### F1 public launch surface — 2026-09-12

`GET /daily/` now renders the typed Daily Intelligence V1 package as the
public product surface rather than the legacy slate template. The page has a
date navigator, ranked context cards, deterministic readout, freshness/trust
layer, explicit empty/partial states, and light-weight canonical market context
when a complete forward sportsbook pair is available. Market context is
observational only and never becomes an edge or recommendation claim.

The historical launch slice is now wired: `/daily/archive` provides a bounded
Regular Season date index, `/daily/YYYY-MM-DD` is the canonical date page, and
`/matchup/YYYY-MM-DD/AWAY-HOME` is the permanent date-scoped matchup page.
The old `/daily/?date=...` form remains compatible, while canonical links and
navigation use the permanent destinations. Team-season archives, prediction
history, and postgame reviews remain later distribution/model outputs.

The 2026-27 bridge is wired into the existing daily fetch order and now runs
C5 reconciliation in the same batch transaction before commit. The real
2026-27 quiet-day proof returned `no_op`, zero pending games, zero blocked
games, and zero writes. The completed-game smoke proof remains correctly
deferred until a game exists. The bridge now also upserts deterministic H1 role
history only after C5 passes, preserving forward collection timestamps without
making the uncalibrated pregame baseline a Daily dependency.

The narrow odds pilot is bounded at 30 games and 500 observations, preserves
source/proxy timestamps and provenance, requires complete market pairs, and
fails closed when the provider returns no complete observations. The
2026-09-12 dry-run confirmed the current NBA endpoint still redirect-loops;
the public product therefore renders honest missing market coverage.

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

The first G0 implementation is now a read-only model-input audit at
`scripts/audit_program_g_model_inputs.py`. It reports paired team features,
pregame cutoff integrity, feature-family coverage, and final-label coverage
without creating predictions or writing data. A season with no completed-game
facts is explicitly classified as blocked rather than healthy-empty. The next
G step remains a historical baseline experiment after this audit passes for an
approved season.

### G0 audit result — 2026-09-11

The audit passes for both approved historical Regular Seasons: 1,075 eligible
games per season (2,150 team rows), complete required feature coverage, final
outcomes for every eligible game, and zero missing-pregame-timestamp,
post-tipoff, future-source, or forbidden-target violations. It performed no
writes. The 2026-27 Regular Season remains correctly blocked with zero eligible
games until a completed game produces current-season evidence.

### G1 historical naive baseline — in place

The first experiment runner is now available at
`scripts/run_program_g_baseline.py`, backed by the pure read-only helper in
`app/services/model_baseline_experiment_service.py`. It evaluates historical
home-win-rate, home-margin-mean, and trailing-game-total-mean baselines, plus
an online Elo-style home-win baseline, using contiguous chronological blocks
after a configurable warmup. Elo ratings update only after each observed
result. The current slice does not persist predictions, does not publish a
route, and cannot use the current game's outcome to form its prediction. This
establishes the comparison floor for the later regression and calibration work.

### G1 result — 2026-09-11

The runner completed on both approved historical Regular Seasons with a
50-game warmup and three chronological test blocks (1,025 test games per
season). Aggregate floors were:

| Season | Home-win log loss / Brier | Home-margin MAE / RMSE | Game-total MAE / RMSE |
|---|---:|---:|---:|
| 2024-25 | 0.7062 / 0.2560 | 13.0 / 16.3 | 15.8 / 19.9 |
| 2025-26 | 0.6901 / 0.2485 | 13.3 / 16.6 | 16.4 / 20.3 |

These are comparison floors, not production-quality predictions. The Elo
extension is now available in the same runner; its historical comparison and
feature-family ablations are the next G gate. The 2026-27 run remains blocked
with zero input games until completed-game evidence exists.

### G2 Elo baseline — 2026-09-12

The same audit-gated runner now evaluates an online Elo-style home-win
baseline. Ratings start at 1500, use a fixed 65-point home advantage and
K-factor 20, update only after each result, and are never persisted. Against
the naive home-rate floor, aggregate home-win results improved as follows:

| Season | Naive log loss / Brier | Elo log loss / Brier |
|---|---:|---:|
| 2024-25 | 0.7062 / 0.2560 | 0.6272 / 0.2190 |
| 2025-26 | 0.6901 / 0.2485 | 0.6171 / 0.2143 |

This clears the comparison checkpoint for feature experiments, not the
production gate. The next bounded slice is feature-family ablation against
the same chronological windows, followed by probability calibration and
stability checks before any prediction consumer is considered.

### G3 cumulative feature-family ablation — 2026-09-12

The runner now includes a small train-only standardized logistic ablation for
the cumulative sequence strength, strength plus form, plus schedule, and plus
the supported pace interaction. Missing inputs are withheld and counted; no
feature is silently zero-filled. All four variants scored all 1,025 test games
in each approved season.

| Season | Strength | + Form | + Schedule | + Pace interaction |
|---|---:|---:|---:|---:|
| 2024-25 log loss | 0.6284 | 0.6258 | 0.6223 | 0.6265 |
| 2025-26 log loss | 0.6353 | 0.6381 | 0.6416 | 0.6374 |

The ablation is useful for direction, but it is not yet a model selection
decision: the small family proxy, coefficient stability, calibration, and
season-to-season behavior need review. The next checkpoint is calibration and
stability reporting against the naive and Elo floors.

### G4 calibration and stability check — 2026-09-12

The experiment payload now includes reliability bins, expected calibration
error (ECE), maximum calibration error (MCE), and chronological block ranges.
The results reinforce the production hold: Elo improves loss metrics, but
calibration is not stable across seasons. For the strength-plus-form-plus-
schedule variant, 2024-25 ECE/MCE were 0.0577/0.1716 with a block log-loss
range of 0.0802; 2025-26 ECE/MCE were 0.0684/0.2323 with a range of 0.2064.
The Elo 2025-26 ECE/MCE were 0.0671/0.2216.

Calibration and stability are now explicit artifacts of the read-only runner,
not assumptions behind the headline loss numbers. The next G slice is
calibration repair and cross-season stability analysis; prediction publication
remains blocked.

### G5 train-only calibration repair — 2026-09-12

The runner now fits a Platt-style calibration transform using only the
historical predictions available before each chronological test block, then
reports raw versus repaired results. On 2024-25, calibrated Elo log loss was
0.6318 versus raw 0.6272 and ECE was 0.0577 versus raw 0.0528. On 2025-26,
calibrated Elo improved log loss to 0.6129 from 0.6171 and reduced ECE to
0.0340 from 0.0671. The mixed result is useful evidence, not approval: there
is not yet a dedicated train/calibration/test split, held-out season test, or
minimum-bin confidence rule. Prediction publication remains blocked.

### G6 dedicated split and season-held-out validation — 2026-09-12

The new read-only gate is available at
`scripts/run_program_g_heldout_validation.py`. It splits a source season into
645 train, 215 calibration, and 215 source-test games (60% / 20% / 20% on the
available 1,075-game seasons), fits the Platt transform on the calibration
window only, freezes it, and evaluates both the source-test window and the
entire opposite season. Elo updates remain private and occur only after each
prediction; no forecasts are persisted.

Both directions completed with 1,075 held-out games. The source-test result
improved in each direction, but the opposite-season result was mixed:

| Source → held-out | Test window | Raw log loss / ECE | Calibrated log loss / ECE |
|---|---|---:|---:|
| 2024-25 → 2025-26 | 2024-25 source test (215) | 0.5928 / 0.0707 | 0.5849 / 0.0577 |
| 2024-25 → 2025-26 | 2025-26 held out (1,075) | 0.6148 / 0.0410 | 0.6130 / 0.0421 |
| 2025-26 → 2024-25 | 2025-26 source test (215) | 0.5019 / 0.1117 | 0.4788 / 0.0943 |
| 2025-26 → 2024-25 | 2024-25 held out (1,075) | 0.6259 / 0.0472 | 0.6337 / 0.0741 |

This clears the procedure and reproducibility gate, not the production gate.
The held-out direction is not uniformly improved, so calibrated prediction
publication remains blocked pending broader seasons/windows, minimum-bin or
interval-aware monitoring, and the remaining planned feature contracts.

### G7 uncertainty-aware calibration monitoring — 2026-09-12

Calibration reports now include two-sided 95% Wilson intervals for each
reliability bin, the interval method, and an explicit minimum-bin monitoring
flag at 25 observations. ECE and MCE remain unchanged point estimates; the
new fields make thin bins visible rather than presenting extreme-bin gaps as
stable evidence. The change is read-only, covered by focused tests, and does
not persist forecasts or alter the production hold.

On the 2024-25 → 2025-26 held-out run, the calibrated result improved log loss
from 0.6148 to 0.6130 and MCE from 0.1585 to 0.1053, while ECE moved from
0.0410 to 0.0421. The held-out report still contains thin bins at the tails,
so this clears the uncertainty-reporting gate only. Broader season/window
evidence and the remaining feature contracts are still required before any
prediction consumer is approved.

The reverse 2025-26 → 2024-25 run is symmetric and remains mixed: held-out log
loss moved from 0.6259 raw to 0.6337 calibrated, ECE from 0.0472 to 0.0741,
while MCE improved from 0.1583 to 0.1067. The interval-aware report flags one
thin calibrated tail bin in that direction. This confirms that calibration
repair cannot be promoted from a single favorable season direction.

### G8 chronological window sweep — 2026-09-12

The read-only held-out runner now supports an explicit 50/25/25, 60/20/20,
and 70/15/15 train/calibration/source-test sweep. Each window is fit and
evaluated independently, with the same audit-gated rows, private Elo updates,
frozen calibration transform, Wilson monitoring, and zero writes. The runner
does not select a winning window or publish a forecast.

All three windows completed in both season directions. For 2024-25 → 2025-26,
held-out calibrated log loss improved in the 50/25/25 and 60/20/20 windows
(0.6149 → 0.6128 and 0.6148 → 0.6130) but worsened in 70/15/15 (0.6139 →
0.6154). For 2025-26 → 2024-25, calibration worsened held-out log loss in
all three windows (0.6247 → 0.6305, 0.6259 → 0.6337, and 0.6274 → 0.6427).
Thin calibrated tail bins remained visible in every window. This clears the
cross-window procedure gate and confirms that no stable production calibration
choice is supported yet.

### G9 probability-band subgroup stability — 2026-09-12

Held-out probability reports now include broad, mutually exclusive confidence
bands: low confidence (`p < 0.35`), competitive (`0.35 ≤ p < 0.65`), and high
confidence (`p ≥ 0.65`). Each band reports test count, coverage, log loss,
Brier score, Wilson-aware calibration, and thin-bin monitoring. Bands are
descriptive only; they do not change fitting or select a production model.

On the 60/20/20 held-out window, the 2024-25 → 2025-26 direction covered
188/476/411 games across the three bands, while the reverse direction covered
275/402/398. Competitive games were the largest source of uncertainty in both
directions, and the reverse high-confidence band had worse calibration (ECE
0.0866) than the forward direction (0.0425). This establishes a reusable
subgroup review contract, but not a production acceptance rule.

### G10 feature-family availability and acceptance review — 2026-09-12

Feature-family ablation outputs now expose effective test-population coverage,
an explicit 95% minimum coverage threshold, and subgroup review status using
the 100-game minimum per probability band. These are review gates only: they
do not select a model, impute missing inputs, or authorize prediction
publication.

The approved 2024-25 and 2025-26 ablations each had 1,025/1,025 scored test
games for all four cumulative variants (strength; strength + form; + schedule;
+ pace interaction), so feature coverage was 100% with zero withheld rows.
The 2024-25 strength and strength + form variants remain blocked for subgroup
review because their low-confidence bands contain 92 and 88 games; the two
schedule-inclusive variants clear the 100-game threshold. All four 2025-26
variants clear the subgroup threshold. This establishes the feature-family
availability contract while confirming that subgroup sufficiency is not yet
uniform across seasons.

### G11 review-ready feature comparison — 2026-09-12

The cross-season comparison runner now intersects the explicit coverage and
subgroup gates before comparing ablation performance. It reports per-season
test-game counts, log loss, Brier score, and cross-season log-loss range; it
does not rank or select a production model.

Only the schedule-inclusive variants pass both seasons' gates. Strength + Form
+ Schedule scored log loss 0.6223 in 2024-25 and 0.6416 in 2025-26, a range of
0.0193. Strength + Form + Pace Interaction scored 0.6265 and 0.6374, a range
of 0.0109. The simpler Strength and Strength + Form variants are excluded from
the common candidate set because their 2024-25 low-confidence bands are thin.
These are research candidates only; the held-out calibration evidence remains
mixed and prediction publication stays blocked.

### G12 candidate stability review — 2026-09-12

Added the read-only `review_feature_family_stability` contract and
`scripts/run_program_g_stability_review.py`. G12 stress-tests only the two
variants admitted by G11 across four chronological segments in both approved
Regular Seasons. Both candidates scored 1,025/1,025 test games per season.
Strength and form directions stayed positive, but schedule changed sign across
the season; the matchup interaction also changed sign across seasons. The
coverage gate passes, while the feature-direction gate remains held. The next
research slice is a narrower, explicitly signed schedule definition and a
repeat of this same stability review. No prediction publication or durable
forecast storage is authorized.

### G13 schedule-definition sensitivity sweep — 2026-09-12

Added the read-only `run_schedule_definition_sweep` contract and
`scripts/run_program_g_schedule_sweep.py`. Four explicit home-perspective rest
definitions were tested against both G11 candidates across four chronological
segments in 2024-25 and 2025-26. All retained 100% coverage, but none removed
the schedule sign flip; the pace/matchup candidate also retained an unstable
interaction term. The next research slice must decompose schedule pressure into
auditable back-to-back, 3-in-4, 4-in-6, and rest-asymmetry components instead of
trying more transforms of the same rest difference. Prediction publication
remains blocked.

### G14/G15 schedule component review — 2026-09-12

Decomposed schedule pressure into independently auditable B2B, 3-in-4,
4-in-5, 5-in-7, rest-asymmetry, and combined components. B2B, 4-in-5, and
5-in-7 passed four-block directional stability and cross-season comparison;
3-in-4, rest asymmetry, and the combined version remained held. The stable
components retained 100% coverage but remain research candidates.

### G16 frozen cross-season feature holdout — 2026-09-12

Added a read-only frozen-source-season validation gate with a strength-plus-form
control. B2B, 4-in-5, and 5-in-7 all scored 1,075/1,075 games in both directions,
but none beat the control in both directions. The data and coverage gates pass;
incremental schedule lift does not. Keep schedule components descriptive-only
for now and move the next product-facing effort to Program H availability and
rotation evidence. Prediction publication remains blocked.

### G17 frozen feature-family comparison rerun — 2026-09-13

Reran `scripts/run_program_g_feature_review.py` with the same 50-game warmup,
three chronological blocks, 95% minimum coverage, and subgroup requirements.
Both approved seasons supplied 1,075 eligible games and all four cumulative
feature variants passed coverage. The schedule-inclusive variants passed the
subgroup gate in both seasons; the matchup variant's cross-season log-loss
range was 0.0109. This confirms a stable, reviewable experiment artifact but
does not override the G12/G16 directional and calibration holds, so no
prediction consumer or durable forecast is approved.

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

### H0 availability and rotation input audit — 2026-09-12

The read-only H audit confirms 32,515 canonical player facts and 390 known
starter/bench rows across 39 complete starter-evidence games in 2024-25. The
2025-26 facts contain zero known starter/bench rows and six completed team
slates without pregame availability coverage. Neither season has a durable
lineup/rotation table or expected pregame minutes observation. Availability
uncertainty can remain a provenance-aware Daily context; exact rotation impact,
replacement quality, and expected minutes at risk remain blocked.

### H1 role baseline foundation — 2026-09-13

The first H1 implementation slice now provides two versioned durable
projections: `player_role_history` for actual canonical player-game role
observations, and `pregame_player_role_baselines` for strict-cutoff descriptive
minutes bands. The materializer is bounded, creates or accepts a derived
ingestion-run lineage ID, skips date-only schedules, and upserts deterministically. It
preserves unknown starter status and missing minutes rather than assigning
bench or zero.

H1 is implementation-complete for its foundation but not production-approved.
The first read-only 2024-25 historical-proxy backtest evaluated 25,617
player-games at 3.83 minutes median absolute error, while the current role band
covered 35.0% of actual minutes. The next gate is band calibration with a
walk-forward evaluation plus trustworthy forward source timing. A 15th–85th
candidate reached 49.9% coverage in 2024-25 and 51.0% in 2025-26, but remains
audit-only until a new version is approved. Rotation Shock, replacement quality,
availability joins, and 2026-27 use remain downstream gates.

The additive migration and bounded database replay gate also passed locally:
32,515 role-history rows and 216 baseline rows were persisted for 2024-25, with
zero natural-key duplicates and identical logical counts on exact replay. All
216 persisted baselines are correctly `unknown` under `strict_source`, because
the historical facts lack trustworthy pregame publication timestamps. The next
active gate is forward source-timing readiness, followed by pre-registered
walk-forward calibration; this timing gap must be solved before Daily or
Rotation Shock consumes the baseline as an eligible feature.

The read-only source-timing audit is now available at
`scripts/audit_program_h_source_timing.py`. It measures timestamp coverage and
strictly eligible prior history by season, while separately reporting the
exact-tipoff schedule requirement. This turns the current source-timing issue
into an inspectable ingestion gate for the next forward slate.

The calibration design is now pre-registered in
`docs/research/PROGRAM_H_H1_ROLE_BAND_CALIBRATION_PROTOCOL_2026-09-13.md`.
Candidate bands, chronological cohorts, minimum sample sizes, WIS/coverage/
MdAE thresholds, and anti-peeking rules are locked there; historical proxy
results cannot approve a production version.

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
The raw-unit prototype is now implemented through
`scripts/prototype_program_e_opponent_difficulty.py`. It presents target-game
opponent strength and prior-opponent SoS separately, with no bands, composite,
0-100 scaling, persistence, or production consumer. The next review is the
clarity of those raw-unit explanations.
