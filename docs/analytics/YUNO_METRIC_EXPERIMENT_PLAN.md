# Yuno Ball Metric Experiment Plan

Status: Schedule Pressure v0.1 approved for descriptive shadow use; target Opponent Difficulty approved for descriptive shadow use; SoS research gate complete but shadow approval pending; Pace wording and read-only shadow replay approved for descriptive shadow use; Rotation Shock observed-risk proxy is research-only and unapproved; no metric approved for production
Prepared: 2026-07-15
Reviewed: 2026-09-05

## Purpose

Define how a Yuno metric moves from an idea to an approved product contract.

## Metric lifecycle

1. Product question
2. Hypothesis
3. Required observation grain
4. Source and coverage audit
5. Formula candidates
6. Leakage and timestamp audit
7. Retrospective experiment
8. Stability and sensitivity analysis
9. User-language prototype
10. Shadow production
11. Approval gate
12. Versioned production
13. Ongoing monitoring

## Program E kickoff audit — 2026-08-25

The first audit begins with Yuno Slate Score because it is the proposed
user-facing composite for deciding which games matter. The audit must precede
formula implementation.

Available and eligible inputs:

- 2024-25 and 2025-26 team/game snapshots after the repaired and explicitly
  labeled early-season partial ranges;
- player form, heat, consistency, and window snapshots for 2024-25 and
  2025-26 where pregame history exists;
- schedule factors and pre-cutoff provenance on the versioned snapshots.

Unavailable or currently unsafe inputs:

- validated historical standings-at-cutoff snapshots;
- approved timestamped market observations;
- calibrated availability or prediction uncertainty inputs;
- `team_game_stats.plus_minus` unless the exact reciprocal pair is complete;
  this is now a nullable derived field rather than a provider-sourced value.

Research decision:

- do not publish or persist a Slate Score yet;
- define the component contract and missing-state behavior first;
- use 2025-26 complete team rows for the first team-based retrospective slice;
- use both approved seasons for player-only components;
- use the repaired and rebuilt 2024-25 team layer for comparable replication,
  while preserving its per-snapshot completeness and cutoff states.

The initial team-based cohort is the 2025-26 complete range beginning
2025-11-09: 2,160 complete team rows across 1,085 games and 1,075 complete
game-environment rows. The small difference is itself a validation item; the
first metric experiment must require a paired complete environment rather than
silently dropping the unmatched team rows.

The first validation target is not “did the score look reasonable?” It is
whether every component is available at the declared pregame cutoff, whether
the score remains stable under exact replay, and whether missing inputs are
visible rather than silently imputed.

## Approval requirements

Every metric must specify:

- metric ID;
- version;
- formula;
- grain;
- source fields;
- required history;
- feature cutoff;
- interpretation;
- uncertainty;
- completeness;
- prohibited uses;
- validation range;
- update cadence;
- consumers.

## Experiment 1 — Yuno Slate Score

### Product question

Which games deserve a fan's attention today?

### Candidate components

- team strength;
- projected competitiveness;
- standings leverage;
- recent-form divergence;
- schedule disadvantage;
- availability uncertainty;
- style contrast;
- prediction uncertainty;
- market/model disagreement when available.

### Research design

Compare components against:

- close-game rate;
- lead changes;
- standings consequences;
- user clicks;
- time on matchup page;
- social engagement;
- editor selections.

Do not optimize only for close final scores.

### Output contract

- 0-100 score;
- component values;
- top three reasons;
- missing components;
- version;
- as-of;
- confidence tier.

## Experiment 2 — Form Quality Index

### Product question

Is recent team performance genuine or mostly schedule-driven?

### Candidate calculation

- recency-weighted net rating;
- opponent strength known before each game;
- home/away adjustment;
- rest adjustment;
- expected-versus-actual performance;
- sample-size shrinkage.

### Baselines

- raw last-5 net rating;
- raw last-10 net rating;
- season-to-date net rating.

### Evaluation

- future 5-game performance;
- future 10-game performance;
- stability by season;
- behavior after roster changes;
- sensitivity to window and decay.

## Experiment 3 — Schedule Pressure Index

### Product question

How much schedule stress enters the game?

### Components

- rest days;
- back-to-back;
- 3-in-4;
- 4-in-6;
- road trip length;
- travel distance proxy;
- timezone change;
- overtime in previous game;
- rest differential;
- consecutive road games.

### Output

- pressure score;
- component flags;
- opponent-relative edge;
- missing travel semantics.

Do not imply causal certainty.

### Research implementation contract — schedule-pressure-v0.1

The first Program E implementation is intentionally a pure, non-persistent
research calculator in `app/services/metric_research_service.py`. It consumes
one pregame team/game observation and returns a versioned result with value,
components, completeness, missing inputs, explanation, `feature_as_of`, and
`data_available_at`. It does not read outcomes, write metric tables, or alter
the existing schedule-factor rows.

Candidate formula for retrospective validation:

```text
short_rest_pressure = clamp((2 - days_rest) / 2, 0, 1)
density_pressure = max(
    clamp(games_last_4 / 2, 0, 1),
    clamp(games_last_7 / 4, 0, 1),
)
opponent_rest_disadvantage = clamp(-rest_diff / 2, 0, 1)
score = 100 * (
    0.45 * short_rest_pressure
    + 0.35 * density_pressure
    + 0.20 * opponent_rest_disadvantage
)
```

The weights are a hypothesis, not a causal estimate. `is_b2b`, `is_3_in_4`,
`is_4_in_5`, and `is_5_in_7` are retained as explanation/validation fields;
the calculator does not double-count them on top of the window counts. A
missing required input returns `partial` with no score, a late input returns
`after_cutoff`, and inconsistent source fields return `quarantined`.

This establishes the reusable E framework, not an approved product metric.
The bounded retrospective is implemented by
`scripts/audit_program_e_schedule_pressure.py`, followed by the sensitivity
and outcome-comparison runner
`scripts/experiment_program_e_schedule_pressure.py`. Both emit JSON evidence
and do not write or rebuild any table.

### Schedule Pressure bounded-cohort gate — 2026-08-25

The first read-only run passed the bounded coverage and cutoff gate:

- 2,160 complete team snapshot rows were inspected across 1,085 game IDs;
- 1,075 game IDs had exactly two team perspectives and a complete game
  environment, producing 2,150 eligible team rows;
- 10 snapshot-only, non-paired game IDs were excluded rather than silently
  scored;
- all eligible rows had schedule factors and returned `complete`;
- no rest-differential, flag, or cutoff consistency failures were reported;
- candidate values ranged from 0.0 to 77.5, with a mean of 39.4401.

The explicit selection rule is the latest `feature_as_of` per
`(game_id, team_id)`. No metric rows were persisted. The coverage gate is
passed for this bounded retrospective cohort.

### Schedule Pressure sensitivity and outcome comparison — 2026-08-25

The read-only experiment completed on the same bounded cohort:

- 2,150 scored team rows across 1,075 paired games;
- 100% outcome-label coverage for final W/L and point differential;
- score versus win-indicator correlation: `-0.0136`;
- score versus point-differential correlation: `-0.0265`;
- lowest-pressure quartile win rate: `0.5204`;
- highest-pressure quartile win rate: `0.4953`.

These are descriptive retrospective results, not evidence of causation or
predictive value. The near-zero outcome relationships support keeping this
candidate as an explanatory schedule-stress input rather than treating it as
a win-probability feature.

Weight sensitivity was moderate. Compared with the fixed v0.1 baseline, the
rest-heavy variant retained 97.02% of the top-quartile rows with rank
correlation `0.9807`; the density-heavy variant retained 94.04% with
correlation `0.9205`; the opponent-disadvantage-heavy variant retained 69.46%
with correlation `0.9471`. The weights remain a research hypothesis and are
not ready for a production revision.

The paired-game evaluation accounts for the dependence between the two team
rows from the same game. Across all 1,075 paired games, the mean winner-minus-
loser pressure difference was `-0.4314`; the winner had higher pressure in
`30.79%` of games, lower pressure in `30.70%`, and an exact pressure tie in
`38.51%`. This confirms that the candidate is describing shared game-context
stress rather than separating winners from losers.

A comparable 2024-25 preflight over `2024-11-09` through `2025-04-12` initially
returned zero eligible rows because the source team values were incomplete.
The authoritative repair, snapshot rebuild, and validation have since passed;
the repaired 2024-25 cohort now supports cross-season replication with the
same explicit completeness and cutoff rules.

Repository-history tracing points to a repairable ingestion defect rather than
missing basketball data: the 2024-25 team rows predate commit `14bc7df`, which
added explicit `TeamGameLog` mappings for `OREB`, `DREB`, `WL`, `W`, `L`, and
`W_PCT`. The repair was proven with a bounded dry-run/apply, reciprocal-row
validation, snapshot rebuild, and exact replay before this season entered the
experiment cohort.

The cross-season gate is addressed below. No metric is approved for production
or consumer integration yet.

### Schedule Pressure cross-season replication — 2026-08-25

The repaired 2024-25 cohort passed the same read-only contract over
`2024-11-09` through `2025-04-12`:

- 2,150 scored team rows across 1,075 paired games;
- complete schedule-factor coverage and 100% W/L plus point-differential
  outcome coverage;
- score versus win-indicator correlation: `-0.0710`;
- score versus point-differential correlation: `-0.0731`;
- whole-game mean winner-minus-loser pressure difference: `-2.1860`;
- winner higher/lower/tied pressure rates: `25.21%` / `31.07%` / `43.72%`.

The candidate therefore replicated as a stable descriptive schedule-context
measure across both approved seasons, while remaining unsuitable as a
standalone outcome predictor. The next Program E decision is whether a
user-language prototype or a different metric candidate adds validated value;
Schedule Pressure v0.1 itself remains non-persistent and research-only.

### Schedule Pressure user-language prototype — 2026-08-25

The first language prototype is implemented in
`build_schedule_pressure_prototype` and exercised by the read-only
`scripts/prototype_program_e_schedule_pressure.py` runner. It presents:

- a plain-language pressure label and 0-100 context value;
- the specific schedule drivers, such as 3-in-4 or fewer rest days;
- an explicit unavailable state for missing, post-cutoff, or quarantined input;
- a persistent caveat that the message is descriptive context, not a forecast.

Real 2025-26 examples rendered low, moderate, and high pressure without any
database writes. The review question is now whether these explanations help a
user understand why a game is demanding. This prototype does not authorize a
route, cache, database table, or production consumer.

### Schedule Pressure v0.1 contract lock — 2026-08-25

The neutral, factual wording is locked for the `schedule-pressure-v0.1`
research version:

- low: “Low schedule strain (0/100). No major congestion or rest disadvantage
  detected.”;
- moderate: “Moderate schedule strain (35/100). The team has played 3 games in
  4 days and 5 in 7 days.”;
- elevated: “Elevated schedule strain (62/100). The team is on a back-to-back
  and has one fewer rest day than its opponent.”;
- high: “High schedule strain (78/100). The team has played 3 games in 4 days
  and has 2 fewer rest days than its opponent.”;
- unavailable: “Schedule strain unavailable. Pregame schedule history is
  incomplete.”

The implementation may render the actual score and observed drivers rather
than these illustrative values. It also states that the result describes
pregame schedule context from rest and recent game density, is not a
performance or outcome prediction, and does not include opponent strength or
travel in v0.1. This wording lock is a shadow-evaluation milestone, not
production approval.

The read-only
`scripts/shadow_program_e_schedule_pressure.py` calculation over the approved
current-season cohort is now complete, with exact replay, status counts, score
bounds, missingness, and cutoff evidence recorded below. No route, cache,
durable metric table, or production consumer is authorized until the separate
approval review passes.

### Schedule Pressure read-only shadow evaluation — 2026-08-25

The shadow runner passed on both approved cohorts without database writes:

- 2025-26: 2,150 eligible team rows across 1,075 paired games; 10 selected
  snapshot rows were excluded because they were outside the paired complete-
  environment cohort;
- 2024-25: 2,150 eligible team rows across 1,075 paired games; 8 selected
  snapshot rows were excluded by the same rule;
- both seasons: 100% `complete` result status, zero missing schedule factors,
  zero replay mismatches, and score bounds of `0.0` to `77.5`;
- no metric rows were persisted.

The contract and wording are ready for approval review as a descriptive
schedule-strain context metric. This remains separate from Opponent Difficulty
or Strength of Schedule, which is the next candidate research track.

### Schedule Pressure descriptive shadow approval — 2026-08-25

Approval was recorded in the task handoff for descriptive shadow use only.
The approved scope is pregame schedule strain from rest and recent game
density. It is not a performance or outcome prediction, does not include
opponent strength or travel, and has no route, cache, durable metric table, or
production consumer. The full-suite compatibility failures remain a separate
legacy cleanup item and do not change this metric-specific approval.

## Experiment 4 — Opponent Difficulty / Strength of Schedule

### Research kickoff — 2026-08-25

This track keeps two related but distinct questions separate:

- **Opponent Difficulty:** how strong is the opponent in this target game,
  based on the opponent's own pregame snapshot at the same cutoff?
- **Strength of Schedule:** how strong have the team's prior opponents been,
  summarized over season-to-date and recent windows?

The first audit uses the leakage-safe `team_game_feature_snapshots` fields
`net_rtg_season`, `net_rtg_lastn`, `sos_net_season`, `sos_net_lastn`, and
`sos_net_delta`, paired by exact `(game_id, feature_as_of,
calculation_version)`. The existing legacy `team_daily_metrics` SoS fields are
not eligible for historical metric research because their season endpoint
values can represent current endpoint state rather than the historical cutoff.

No 0-100 formula, user-facing label, persistent output, or production consumer
is approved yet. The next gate is the read-only coverage, pairing, cutoff, and
distribution audit across both approved seasons.

### Opponent Difficulty / SoS coverage audit — 2026-08-25

The read-only
`scripts/audit_program_e_opponent_difficulty.py` audit passed its source-input
gate on both approved cohorts:

- 2025-26: 2,150 eligible team rows across 1,075 paired games; 10 complete
  snapshot rows were excluded outside the paired complete-environment cohort;
- 2024-25: 2,150 eligible team rows across 1,075 paired games; 10 complete
  snapshot rows were excluded by the same rule;
- all six candidate fields were 100% non-null on eligible rows:
  target-opponent season/recent/delta net rating and team season/recent/delta
  SoS;
- zero missing opponent perspectives, pair cutoff mismatches, pair version
  mismatches, or cutoff failures were found;
- the audit performed no writes.

The inputs are therefore available and cutoff-safe for retrospective research.
They remain distinct: target-opponent net rating answers how difficult the next
opponent is, while `sos_net_*` summarizes the strength of prior opponents the
team has already faced.

The next formula comparison will evaluate raw opponent recent net rating,
season/recent blended opponent net rating, and rolling recent/season SoS as
separate descriptive inputs. A 0-100 transformation is deferred until a
pregame-safe reference distribution and user-language mapping are validated.

### Opponent Difficulty / SoS formula comparison — 2026-08-25

The read-only
`scripts/experiment_program_e_opponent_difficulty.py` comparison covered 2,150
team rows and 100% outcome labels in each approved season. Correlations below
are descriptive retrospective relationships, not causal estimates:

| Candidate input | 2025-26 W/L | 2025-26 margin | 2024-25 W/L | 2024-25 margin |
| --- | ---: | ---: | ---: | ---: |
| Target opponent recent net rating | -0.2564 | -0.2979 | -0.2533 | -0.2956 |
| Target opponent season net rating | -0.2888 | -0.3152 | -0.2715 | -0.3190 |
| Target opponent 60/40 recent-season blend | -0.2801 | -0.3182 | -0.2728 | -0.3191 |
| Team recent SoS | -0.0584 | -0.0731 | -0.0523 | -0.0628 |
| Team season SoS | -0.1566 | -0.1782 | -0.1458 | -0.1771 |
| Team 60/40 recent-season SoS blend | -0.0942 | -0.1124 | -0.0858 | -0.1035 |

The target-opponent fields are the stronger and more stable game-level
difficulty context. Season opponent strength is slightly more stable than
recent opponent strength, while the 60/40 blend is directionally consistent
but does not demonstrate a clear cross-season improvement. Team SoS remains
valuable for explaining the schedule a team has already faced, but it should
not replace the target-opponent input or be silently mixed into it.

No formula is approved yet. The next bounded E step is a raw-unit,
user-language prototype that presents target-opponent strength and rolling SoS
as separate explanatory fields. A 0-100 score, composite, or persistent
consumer remains out of scope until that language and a pregame-safe scaling
method pass review.

### Opponent Difficulty / SoS raw-unit prototype — 2026-08-25

The non-persistent
`scripts/prototype_program_e_opponent_difficulty.py` runner now renders the
two dimensions separately:

- target opponent pregame net rating, shown for season and recent windows;
- the team's prior-opponent average net rating, shown for season and recent
  windows;
- a plain-language explanation that higher values indicate stronger opponents;
- an explicit caveat that the context is not a performance or outcome
  prediction;
- unavailable output when required strength inputs are missing or arrive after
  the declared cutoff.

This is a language prototype only. It does not assign difficulty bands, choose
weights, create a 0-100 score, or persist rows. The next review is whether
these raw units are understandable enough to keep before any scaling research
or consumer integration. The selected wording direction is balanced and
factual: the opponent's season/recent net ratings are stated first, followed
by the team's previous-opponent averages and the explanation that higher
values indicate stronger opponents.

### Opponent Difficulty / SoS raw-unit wording approval — 2026-08-25

The raw-unit wording was reviewed and approved for continued research use.
Because the rendering is isolated in the metric research service, wording may
evolve without changing the underlying snapshot grain or source contract.
Approval covers the explanatory prototype only; no 0-100 scaling, composite,
persistent output, route, cache, or production consumer is approved.

The next research gate is a pregame-safe scaling study: evaluate a historical
reference distribution built only from information available before each
target game, compare percentile/rank and raw-unit presentations, and test
whether the scale remains stable across both approved seasons.

### Opponent Difficulty / SoS pregame-safe scaling study — 2026-08-25

The read-only runner `scripts/experiment_program_e_opponent_difficulty_scaling.py`
evaluated the approved cohorts using a same-season reference distribution. For
each target game, the reference pool contained only eligible team rows with a
strictly earlier `feature_as_of`; the target game and all other rows sharing
that cutoff were added only after evaluation. A minimum of 20 prior values was
required, and missing or non-finite values were withheld rather than treated
as zero.

Results:

- 2025-26: 2,150 target rows across 1,075 games; 2,112 rows scaled (98.2%);
  38 early-history rows withheld; percentile means stayed near 50 across
  fields.
- 2024-25 approved cohort: 2,150 target rows across 1,075 games; 2,130 rows
  scaled (99.1%); 20 early-history rows withheld; percentile means stayed near
  50 across fields.
- Both seasons had 2,150 safe source rows, zero unsafe cutoff rows, and no
  writes. Raw-to-percentile outcome relationships were directionally stable;
  target-opponent season net rating remained the strongest candidate, while
  team SoS remained a separate context field.

The empirical percentile is useful as a possible communication layer because
it answers “how strong relative to earlier observations?” while preserving the
raw net-rating value for auditability. It does not add predictive signal by
itself, and early-season withholding is an intentional limitation. No
percentile thresholds, production 0-100 field, composite, persistent output,
route, cache, or consumer is approved. The next review is selection of a
wording style and a production approval decision only if the early-season
behavior and cross-season semantics are accepted.

### Opponent Difficulty / SoS scaled wording prototype — 2026-08-25

The non-persistent runner `scripts/prototype_program_e_opponent_difficulty_scaled.py`
renders three selectable styles from actual pregame rows:

- `raw_plus_percentile`: leads with auditable net-rating values and adds
  relative percentile context;
- `percentile_first`: leads with the easier-to-scan relative context and keeps
  raw values in parentheses;
- `compact`: produces a shorter matchup-summary sentence for dense surfaces.

All styles use noun-based matchup phrasing so team-name grammar remains stable,
keep target-opponent strength separate from prior team SoS, identify the
reference population as earlier same-season observations, and preserve the
non-predictive caveat. The prototype was rendered for both approved seasons;
2025-26 produced 2,112 complete wording rows and 2024-25 produced 2,130.
This is a language review artifact only: no style, percentile label, route,
cache, persistent field, or production consumer is approved yet.

### Opponent Difficulty / SoS research gate — 2026-09-05

The current database is at Alembic head `h4i5j6k7l8`. The read-only audit,
raw-unit comparison, pregame-safe percentile study, wording comparison, and
deterministic replay were rerun against the approved 2024-25 and 2025-26
Regular Season cohorts. Each season provided 1,075 paired games / 2,150
eligible team rows with all six candidate fields populated and zero pair or
cutoff failures. The current audit excluded 10 complete snapshot rows per
season outside the paired complete-environment cohort.

The raw comparison again showed target-opponent season/recent net rating as
the stronger game-level context, while rolling prior-opponent SoS remained a
separate schedule-history explanation. The 60/40 blend is not approved. With
a minimum reference size of 20, percentile scaling withheld 20 early-history
rows in 2024-25 and 38 in 2025-26; the remaining rows preserved raw ordering
closely. `raw_plus_percentile`, `percentile_first`, and `compact` wording all
retain raw values, earlier-same-season reference context, and the explicit
non-predictive caveat.

The SoS research gate passes, but rolling prior-opponent SoS remains
unapproved for descriptive shadow use, persistence, routes, caches, or model
features. Evidence and detailed results are recorded in
`docs/research/PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md`.

## Experiment 5 — Style Collision Map

### Product question

Where do team tendencies interact most strongly?

### Candidate edges

- rim frequency versus rim allowance;
- three-point rate versus three-point allowance;
- offensive rebound versus defensive rebound;
- turnover creation versus ball security;
- free-throw pressure versus foul rate;
- transition frequency versus transition defense;
- assisted scoring versus opponent creation denial;
- pace preference interaction.

### Output

For each edge:

- home value;
- away/opponent value;
- league percentile;
- expected direction;
- strength;
- confidence;
- deterministic explanation.

### Style Collision Map input coverage audit — 2026-08-31

The read-only audit `scripts/audit_program_e_style_collision.py` checked the
approved 2025-26 cohort and the approved 2024-25 cohort. Each had 2,150 safe
team rows across 1,075 paired games. Five existing recent-window fields—pace,
three-point scoring share, offensive rebound rate, turnover rate, and
free-throw rate—were fully populated, but most planned edges require a
defensive or possession-level counterpart that is not present in the current
snapshot grain.

The audit found one fully supported edge and seven blocked edges:

- Supported: `pace_preference_interaction`, using both teams' `pace_lastn`.
- Blocked: rim frequency/allowance, three-point rate/allowance, offensive
  rebound/defensive rebound, turnover creation/ball security, free-throw
  pressure/foul rate, transition frequency/defense, and assisted scoring/
  creation denial.

Blocked inputs remain explicitly unavailable; no unrelated field is used as a
substitute and no missing value is filled with zero.

### Style Collision Map pace experiment — 2026-08-31

The read-only experiment `scripts/experiment_program_e_style_collision.py`
evaluated the supported pace edge against a same-season reference of strictly
earlier paired-game cutoffs. The output contains home pace, away pace, average
combined pace, absolute pace contrast, and the combined-pace percentile. The
2025-26 cohort produced 1,053 complete games and 22 early-history games
withheld; the 2024-25 cohort produced 1,055 complete games and 20 withheld.
The average contrast was 3.1 possessions in 2025-26 and 3.0 in 2024-25.

This supports a descriptive pace-interaction prototype, not a predictive
metric. Higher combined pace means a faster environment; higher contrast means
the teams have more different recent pace preferences. No edge strength band,
outcome claim, production consumer, persistent field, route, or cache is
approved. The wording prototype and read-only replay are now complete; the next
gate is explicit descriptive-shadow approval for this supported edge.

### Style Collision Map pace wording prototype — 2026-08-31

The service now exposes three read-only wording styles through
`build_style_collision_pace_prototype`: raw-plus-percentile for audit/detail,
percentile-first for a user-facing explanation, and compact for a dense matchup
card. For a matchup with recent pace values of 102.0 and 98.0, the wording
describes a 100.0 combined pace, a 4.0 possession gap, and approximately the
53rd percentile of earlier same-season paired observations.

The wording preserves partial and quarantined states instead of rendering an
incomplete result as a normal metric. The revised wording uses “recent pace
context” and “pace profiles” rather than presenting “pace interaction” as a
user-facing label. Percentile-first remains the leading candidate for review,
while raw-plus-percentile remains the preferred audit form. These are still
research renderings: no production consumer, persistent field, route, cache,
strength band, or outcome claim is approved.

### Opponent Difficulty / SoS and Pace read-only shadow replay — 2026-08-31

The existing read-only research runners were executed twice against each
approved season to verify deterministic replay before any shadow approval:

- Opponent Difficulty / SoS: 2,150 safe team rows and 1,075 paired games in
  each season; 2,112 scaled rows and 38 early-history rows withheld in
  2025-26; 2,130 scaled rows and 20 withheld in 2024-25.
- Pace interaction: 2,150 safe team rows and 1,075 paired games in each
  season; 1,053 complete games and 22 early-history games withheld in
  2025-26; 1,055 complete games and 20 withheld in 2024-25.
- All four replays matched exactly and every run reported
  `writes_performed: false`.

This is a validation shadow, not user-facing production. It confirms that the
current calculations can run repeatedly against the approved historical
cohorts while preserving intentional early-history withholding. Pace and
target Opponent Difficulty are approved for descriptive shadow use; prior
Strength of Schedule remains separate and unapproved. Rotation Shock is now
the active research track.

The missing 2024-25 `pf` values are not a blocker for these tracks. They only
block a future foul-rate/free-throw-pressure edge and should be repaired before
that edge is evaluated, without delaying the current sequence.

## Experiment 6 — Rotation Shock

### Rotation Shock input coverage audit — 2026-08-31

The read-only audit `scripts/audit_program_e_rotation_shock.py` confirms that
the player fact foundation is sufficient to begin a scoped research prototype,
but not to claim the full planned Rotation Shock output. In both approved
seasons, Traditional and Advanced facts are complete and key-matched; usage
percentage, assist percentage, and actual minutes are populated. Official
availability observations are also present with game/player/team identity and
report timing. When joined to the canonical Regular Season schedule, pregame
availability evidence exists for 1,227 of 1,230 games in 2025-26 and 952 of
1,230 games in 2024-25. The 2025-26 source is mostly minute-level; the
2024-25 source is hour-level and therefore remains checkpoint-quality evidence
rather than exact event timing. These counts measure the presence of pregame
report evidence, not a complete available-player census.

The audit found three material gaps:

- `starter_status` is `unknown` for every 2025-26 canonical player-game fact
  and for uncovered 2024-25 facts; 370 covered 2024-25 facts now carry an
  explicit V2 starter-evidence link and position;
- expected pregame minutes are not stored as a source observation;
- no lineup or rotation table is present, so lineup continuity cannot yet be
  measured directly.

Rotation Shock therefore begins with a v0.1 availability-and-role-disruption
research scope using official pregame status, prior actual minutes, usage, and
assist percentage as explicitly labeled proxies. Starter frequency, expected
minutes, replacement quality, and lineup continuity remain blocked or
unvalidated until their contracts and sources are established. No formula,
metric table, route, cache, or production consumer is approved by this audit.

### Rotation Shock two-track replay and source trial — 2026-08-31

The two-track implementation kept the supportable descriptive proxy moving
while separately testing whether a historical starter source could be promoted.
`app/services/metric_research_service.py` now exposes the pure, versioned
`rotation-shock-v0.1` calculator. `scripts/experiment_program_e_rotation_shock.py`
replays it read-only using the latest explicit pregame Questionable, Doubtful,
or Out status per player, a same-team prior played fact, and a cutoff one
second before scheduled tipoff. It never treats an absent report row as
Available, never reads target-game facts, and never writes a metric table.

The approved-season replay produced these research counts:

- 2025-26: 2,446 team-game panels with pregame observations; 2,433 with an
  observed risk status; 777 scoreable panels with complete prior same-team
  minutes, usage, and assist inputs; 1,656 withheld panels.
- 2024-25: 1,598 team-game panels with pregame observations; 1,592 with an
  observed risk status; 566 scoreable panels; 1,026 withheld panels.

The withheld panels are an intentional safe state, primarily covering players
without a prior same-team played fact or without one of the Advanced role
fields. Scores range from near-zero to the capped 100.0 value, so the next
research gate is not formula execution; it is deciding whether the observed
status cohort and baseline coverage are adequate for descriptive shadow use.
These outputs are conditional on observed risk rows, not a complete injury
census, expected-minutes model, replacement model, starter model, or lineup
model.

The bounded `BoxScoreTraditionalV2` source trial is season-dependent. Thirty-seven
2024-25 games were tested: every game returned player rows and 10 populated
`START_POSITION` values, and all 370 starter rows matched the existing
canonical `(game, player, team)` grain. The covered 2024-25 canonical facts
now carry the linked starter evidence; uncovered 2024-25 facts remain
`unknown`. Two 2025-26 games returned a valid response shape with
`START_POSITION` declared but zero player rows. Some requests initially
returned 403 and succeeded after the shared proxy rotated. This means V2 is a
strong candidate historical source for a bounded 2024-25 trial, but is not
universally validated and cannot be assumed to work for 2025-26. The
trial-only parser, reconciliation script, and separate
`player_game_starter_evidence` table remains separate from the Traditional V3
revision contract. The reviewed 37-game 2024-25 sample is now persisted as
972 immutable evidence rows, including 370 starter rows. The latest 25-game
apply added 662 rows and an exact replay created zero new rows;
`player_game_facts` now has a provenance-linked starter projection for the 370
explicit starter rows; its Traditional V3 fact and revision lineage remain
unchanged. No starter status will be inferred from minutes, report absence, or
an empty V2 response.

The preferred Live BoxScore path is now routed through the proxy-aware CDN
provider used by the bounded collector. A 2026-09-05 two-game dry-run for
2024-25 and 2025-26 still received CDN HTTP 403 responses after three proxy
attempts per game, so it created no starter evidence and does not change the
coverage claim. The collector fails closed with the transport error; starter
status remains unknown unless an explicit source row is returned.

The two-track gate remains open: keep the proxy read-only for research and
continue bounded source validation before adding starter or lineup fields to
the canonical facts. The evidence publication gate and the bounded
provenance-linked projection are complete for the reviewed 2024-25 sample: the
table is additive, provenance-bearing, and exact replays are no-ops. The next
source gate is continued season-spanning coverage and an explicit decision
about whether a research consumer may read the projected starter fields. This
does not authorize a 2025-26 backfill while V2 returns empty player sets there.

### Product question

How much does current availability disrupt expected roles?

### Inputs

- official status;
- expected minutes;
- recent usage;
- starting frequency;
- creation share;
- lineup continuity;
- replacement quality;
- status uncertainty.

### Outputs

- expected minutes unavailable;
- expected usage unavailable;
- creation burden shift;
- role-change count;
- rotation continuity loss;
- replacement uncertainty.

Historical rows without exact report time must be labeled checkpoint quality.

## Experiment 7 — Role Stability

### Product question

How predictable is a player's role entering the game?

### Components

- minutes median and dispersion;
- starting consistency;
- usage dispersion;
- attempt-share dispersion;
- teammate availability;
- games since role change;
- recent substitution pattern.

Do not call production “consistent” when only minutes are stable.

## Experiment 8 — Availability Uncertainty

### Product question

How likely is the available rotation to change before tip?

### Components

- questionable/doubtful players;
- expected minutes attached to uncertain players;
- lateness of latest report;
- team submission status;
- minutes until tip.

No probability should be published until calibrated.

## Experiment 9 — Market Disagreement

### Product question

How much do books disagree at a declared timestamp?

### Inputs

- comparable sportsbook observations;
- same market;
- same selection;
- same pregame window.

### Outputs

- consensus line;
- median price;
- range;
- dispersion;
- missing-book count.

Unknown-time historical odds cannot be used for live disagreement products.

## Experiment record template

Each experiment produces:

- research question;
- dataset versions;
- date range;
- inclusion/exclusion criteria;
- formula candidates;
- baseline;
- evaluation metrics;
- result by season;
- sensitivity;
- failure modes;
- recommended version;
- go/no-go;
- next data requirement.
