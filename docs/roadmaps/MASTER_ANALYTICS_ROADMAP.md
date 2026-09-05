# Yuno Ball Master Analytics Roadmap

Status: C7 historical player-fact foundation complete for 2020-21 through 2025-26; Program D feature foundation complete for 2024-25 and 2025-26; Program E research and descriptive-shadow work active; no metric approved for production
Reviewed: 2026-09-05
Scope: analytics, source expansion, Daily Intelligence, modeling, distribution, and monetization after the five-phase historical-data foundation is complete

## Purpose

This roadmap defines the order in which Yuno Ball should convert its repaired ingestion and historical snapshot foundation into a differentiated NBA analytics product.

It deliberately separates durable source collection, curated analytical data, experimental metrics, production metrics, descriptive Daily Intelligence, predictive models, market comparison, media distribution, and monetization.

The repository, current database schema, and implemented tests remain authoritative. This document describes proposed work unless a repository change explicitly implements it.

## Current analytics checkpoint — 2026-09-05

The ingestion foundation has crossed the Program C7 gate for six reviewed
Regular Season backfills from 2020-21 through 2025-26. The canonical
Traditional and Advanced V3 fact projections are key-matched and complete for
28,859/31,321/31,542/32,385/32,515/32,179 player-game rows respectively; the
2020-21 season correctly uses its shortened 1,080-game scope and the other five
seasons use 1,230 games. The regenerated database profile is the current source
of truth, at Alembic head `h4i5j6k7l8`, with legacy `gamelogs` retained.

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
identified.

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
known with provenance for 370 covered 2024-25 facts, but remains unknown for
uncovered 2024-25 facts and all 2025-26 facts; expected pregame minutes are
not stored, and no lineup/rotation table exists. The full planned metric is
therefore not yet supportable. The two-track work runs the clearly labeled
availability-and-role-disruption proxy while separately validating a starter
source. The proxy replay is now complete for both approved seasons: 777 of
2,433 observed-risk 2025-26 panels and 566 of 1,592 observed-risk 2024-25
panels had complete prior same-team role baselines. The remainder is withheld,
not imputed. A broader V2 trial returned usable `START_POSITION` rows for 37
2024-25 games, with all 370 starter rows matching canonical grain, but returned
zero player rows for two 2025-26 games. The reviewed trial is now persisted in
the additive `player_game_starter_evidence` table as 972 immutable source rows
(370 starter rows) across 37 reviewed 2024-25 games; the latest exact apply
replay created zero new rows. A provenance-linked projection then updated 370
canonical facts, and its exact replays also produced zero updates. V2 is
therefore a strong candidate for a bounded 2024-25 evidence backfill—not a
universal source—and remains unsuitable for 2025-26 while V2 returns empty
player sets there.

### Operational concerns checkpoint — 2026-09-05

The schedule/roster onboarding, daily canonical bridge implementation, and
`plus_minus` contract cleanup are complete. The daily bridge has passed its
pre-season no-op proof but still needs one completed-game Traditional →
Advanced → C5 → exact-replay smoke proof after the season begins. The
starter/availability audit remains a bounded research input: only 370 reviewed
2024-25 facts have starter/bench provenance, and no lineup/rotation table is
available. The read-only `scripts/audit_legacy_redundancy.py` inventory now
establishes the first table/grain/consumer baseline; no legacy table is
approved for deletion or replacement until the final migration and rollback
gate.

The current database is at Alembic head `h4i5j6k7l8`. Preseason schedule rows
remain separate from the reviewed Regular Season C7/Program D boundary, and
the identified 2026-27 schedule does not authorize a completed-game smoke
proof before a completed game exists. The known `alembic check` drift remains
limited to the intentional removal of the inactive `users` table and indexes;
the migration/rollback implications are a separate audit.

The latest SoS research gate passed coverage, pairing, cutoff, raw-unit
comparison, wording, and deterministic replay for both approved seasons.
Rolling prior-opponent SoS remains separate from target-game Opponent
Difficulty and remains research-only: no durable field, route, cache, or
descriptive shadow approval is granted by this checkpoint. See
`docs/research/PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md`.

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
The raw-unit prototype is now implemented through
`scripts/prototype_program_e_opponent_difficulty.py`. It presents target-game
opponent strength and prior-opponent SoS separately, with no bands, composite,
0-100 scaling, persistence, or production consumer. The next review is the
clarity of those raw-unit explanations.
