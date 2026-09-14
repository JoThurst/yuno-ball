# Program H1 — Role-band calibration protocol

Protocol status: pre-registered for the next evaluation; no production approval
Registered: 2026-09-13
Owner: Yuno Ball analytics
Scope: `player.pregame_role_baseline` (`role-baseline-v1` and candidate `v1.1` bands)

## Purpose and decision boundary

This protocol advances the H1 calibration gate without changing the current
service, model, or production metric contract. It asks whether a descriptive
pregame minutes band is calibrated enough to become a versioned candidate for
future review. It does not authorize a public prediction, Rotation Shock, a
lineup confirmation, an injury estimate, or exact expected-minutes language.

The current production contract remains `role-baseline-v1`: a 10-game window
with the 25th percentile, median, and 75th percentile of prior played-game
minutes. A candidate can be recommended for a later version review only if it
passes this protocol on untouched chronological evidence and the source-timing
gate is separately open.

## Unit of analysis and target

The scored observation is one player-game at the canonical fact grain:

`(canonical_game_id, canonical_player_id, canonical_team_id)`

The target is actual decimal minutes in the completed game. Include an
observation only when all of the following are true:

1. The canonical fact says `participation_status = played`.
2. Minutes parse successfully from the preserved source value.
3. The game has an exact scheduled tipoff or an explicitly documented,
   reproducible forward cutoff.
4. The player belongs to the same canonical team as the target fact.

DNP rows, missing minutes, unknown starter status, and absent player/team
identity remain evidence for data-quality reporting but are not silently
converted into a zero-minute target or a bench label.

## Feature construction lock

For every target game, construct the baseline exactly as the current H1
service contract specifies:

- Use at most the 10 latest prior role-history rows for the same player/team.
- Use only rows with `game_date < target_game_date`.
- In the production evidence track, require
  `data_available_at <= feature_as_of` and preserve the source run/hash.
- Exclude the target game and every later game, including later corrections
  that were not available by the cutoff.
- Use played-game minutes for the quantiles; keep starts and missing flags as
  separate descriptive fields.
- Keep the median as the point anchor for every candidate band.
- Do not tune window size, minimum history, or feature cutoff after inspecting
  the confirmatory results.

The historical `historical_game_date_proxy` mode may be run only as a
read-only method rehearsal. Its source timing is unknown, it must be labeled
proxy-only in outputs, and it cannot satisfy the production evidence gate.

## Candidate bands

The candidate set is fixed before the next result is inspected:

| Candidate | Lower / upper quantiles | Nominal central coverage | Role |
| --- | ---: | ---: | --- |
| `role-baseline-v1` | p25 / p75 | 50% | Existing comparator |
| `role-baseline-v1.1-p20-p80` | p20 / p80 | 60% | Narrow candidate |
| `role-baseline-v1.1-p15-p85` | p15 / p85 | 70% | Primary candidate |
| `role-baseline-v1.1-p10-p90` | p10 / p90 | 80% | Wide safety candidate |

The version label is a research identifier until a separate implementation and
metric-catalog review approves it. The current persisted `role-baseline-v1`
rows are not rewritten by this evaluation.

## Chronological evaluation design

There are two evidence tracks with different decision rights.

### Track A — historical method rehearsal

Run on 2024-25 and 2025-26 Regular Season facts using the existing
strictly-prior-game-date proxy. Results may validate code, expose distribution
shape, and narrow the candidate set, but they cannot approve production because
the historical `data_available_at` values describe backfill time rather than
source-publication time.

Use chronological game order within each season. Do not randomly split player
games. A target is eligible only after its prior history is available under the
proxy rule. Report each season separately and pooled only as a descriptive
summary.

### Track B — forward source-timed evaluation

Use newly ingested completed games once the 2026-27 bridge has real game data.
The feature cutoff is the recorded pregame publication/cutoff time, and every
history row must carry a source-available timestamp no later than that cutoff.
Evaluate in game-date order, freezing each result at the target cutoff.

The first forward block is a smoke-quality block, not a production approval
block. It must demonstrate timestamp and identity coverage before its metrics
are interpreted. The confirmatory block begins only after the smoke checks pass
and includes the next chronological games without changing the protocol.

## Cohorts and minimum sample sizes

Assign each scored player-game by the number of usable prior played-minute
rows actually used by the baseline, after all timing and cutoff filters:

- `1-4`: early-history / low-information cohort
- `5-9`: partial-history cohort
- `10`: full-window cohort
- `all`: pooled result

For a scored evaluation block to be decision-bearing, require at least 1,000
eligible player-games overall, at least 200 observations in `5-9`, at least 200
in `10`, and at least 100 in `1-4`. If a cohort misses its minimum, report it
as underpowered and do not claim a pass for that cohort. The pooled result may
not hide an underpowered full-window cohort.

Also report, by season and block:

- canonical fact rows read;
- exact-tipoff target team rows;
- eligible targets excluded for missing/late source timing;
- parseable played-minute targets;
- evaluated player-games;
- history depth and completeness shares;
- duplicate natural-key count and orphan identity count.

## Metrics

Compute all metrics overall and for every sufficiently powered cohort.

### Primary calibration metrics

1. **Central coverage**: share of actual minutes within `[low, high]`.
2. **Calibration error**: `coverage - nominal_coverage`; report signed and
   absolute values.
3. **Median absolute error (MdAE)** of the median point anchor, in minutes.
4. **Median interval width**, `high - low`, in minutes.

### Secondary metrics

- Mean absolute error of the median anchor.
- 90th-percentile absolute error.
- Weighted interval score (WIS), using the candidate's nominal central
  coverage and the standard interval penalties for misses.
- Coverage by starter-status-known versus starter-status-unknown rows, without
  treating the latter as bench.
- Coverage by history depth and, when sample size permits, by team and season.

For a candidate with nominal central coverage `c`, use `alpha = 1 - c` and

`WIS = (high - low) + (2 / alpha) * (low - actual) * I(actual < low) + (2 / alpha) * (actual - high) * I(actual > high)`.

Lower WIS is better. WIS is a secondary ranking aid and cannot override a
failed data-timing, sample-size, or cohort-calibration gate.

## Pre-registered decision thresholds

Thresholds below are locked before the next evaluation output is reviewed.

### Data validity gate

The block fails and is descriptive-only if any of these occur:

- source timing is proxy-only or more than 5% of included history rows lack a
  trustworthy pre-cutoff availability timestamp;
- duplicate natural keys or target-game leakage are detected;
- any target game's own fact enters its history window;
- the minimum sample-size requirements are not met;
- parsing or identity exclusions are not reported by count and rate.

### Candidate calibration gate

A candidate passes a powered block only when all conditions hold:

- pooled coverage is within ±10 percentage points of nominal coverage;
- each powered `5-9` and `10` cohort is within ±15 percentage points of its
  nominal coverage;
- no powered cohort differs from another powered cohort by more than 20
  percentage points in coverage;
- pooled MdAE is no more than 4.5 minutes;
- no powered cohort has MdAE above 6.0 minutes;
- median interval width is no more than 30 minutes;
- WIS is no worse than the existing p25/p75 comparator in the same block.

The p15/p85 candidate is the primary candidate because it targets 70% central
coverage. A wider candidate cannot pass merely by inflating the band: it must
also satisfy the width and WIS conditions. If multiple candidates pass, select
the narrowest passing band; if none pass, retain `role-baseline-v1` and record
the calibration failure without changing production behavior.

### Confirmatory consistency gate

No candidate is eligible for a future version review unless it passes both:

1. one development block and one later untouched confirmatory block; and
2. every powered cohort in the confirmatory block.

A candidate that passes pooled metrics but fails the `5-9` or `10` cohort is
not approved. A candidate that passes historical proxy results but lacks
forward source-timed evidence is not approved.

## Review and anti-peeking rules

Before scoring:

1. Record the code version, protocol path, candidate set, source timing mode,
   season/block boundaries, and database profile timestamp.
2. Freeze the target-game list and the eligibility counts.
3. Run all candidates in one read-only evaluation.

After scoring:

1. Do not change thresholds, cohorts, window size, or candidate quantiles.
2. Do not select a band using only the pooled result.
3. Do not use a failed proxy result to justify production timing.
4. Treat a later implementation change as a new protocol registration, with a
   new version and a fresh untouched evaluation block.

## Expected report shape

The evaluation artifact must include:

- protocol hash or registration timestamp;
- exact command and read-only/write status;
- source timing mode and cutoff definition;
- candidate table with nominal coverage, coverage, calibration error, MdAE,
  width, WIS, and sample size;
- the same metrics by cohort and season/block;
- data-validity and leakage checks;
- exclusions and missingness rates;
- a single decision for each candidate: `pass`, `fail`, or `underpowered`;
- explicit production decision: `not approved` unless a later authorized review
  confirms all gates.

## Current prior evidence (not part of the next result)

The H1 foundation report records the already-observed historical proxy results:
2024-25 p25/p75 coverage was 35.0% with 3.83-minute pooled MdAE; p15/p85
coverage was 49.9%. For 2025-26, p15/p85 coverage was 51.0% with 3.87-minute
pooled MdAE. These observations motivated this protocol but are not
confirmatory evidence because their source timing is not trustworthy.

## Explicit non-approval

This registration does not approve any candidate for Daily Intelligence,
public predictions, model training, Rotation Shock, or betting/odds decisions.
The next valid action is a read-only evaluation against forward source-timed
facts after the 2026-27 bridge has completed its first real-game smoke proof.
