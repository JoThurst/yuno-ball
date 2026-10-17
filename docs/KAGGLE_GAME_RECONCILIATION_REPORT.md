# Kaggle Game Reconciliation Report

Status: read-only baseline completed; bounded playoff follow-up completed
Generated (UTC): 2026-07-16T16:01:09.761047+00:00

## Technical summary

The exact-ID audit found no identity conflicts. It supported a playoff-only
write boundary: add explicit schedule type, date precision, structured scores,
and provenance, then insert the 838 missing playoff games. That bounded
promotion completed successfully and its exact rerun changed zero domain rows.

## Decision summary

- Source games evaluated: 15,518
- Exact canonical matches: 2,621
- Canonical missing: 12,897
- Canonical incomplete: 0
- Conflicts: 0
- Missing source dates: 363
- Unique player-game date repairs: 363

## Canonical prerequisites

- game_schedule needs explicit season_type before playoff backfill
- canonical rows need source_import_id and source_run_id lineage
- backfill must insert two reciprocal rows per exact NBA game_id
- only final Regular Season/Playoffs rows with known or uniquely repaired dates are eligible

## Status by season type

| Season type | Matched | Missing | Incomplete | Conflict |
|---|---:|---:|---:|---:|
| Playoffs | 161 | 838 | 0 | 0 |
| Regular Season | 2,460 | 12,059 | 0 | 0 |

## Interpretation

Missing Yuno games remain valid staged external evidence. The next write phase must add explicit season-type and source lineage to the canonical schedule contract, then backfill only exact-ID, reciprocal-team, final games with known or uniquely repaired dates.

Playoff absence is a canonical coverage gap, not a reason to discard the staged game or its market observations.

## Bounded playoff follow-up

| Validation measure | Result |
|---|---:|
| Eligible playoff games | 999 |
| Pre-existing exact matches | 161 |
| Promoted missing games | 838 |
| Inserted reciprocal schedule rows | 1,676 |
| Pair, team, score/result, or lineage defects after insert | 0 |
| Exact-rerun domain rows changed | 0 |

The promotion run `e385d229-144d-43ee-a5e4-4948d2859cbf` completed with
`success/passed`; the idempotency run
`2179c3b6-6d32-4f1d-88b2-c75955d067e1` also completed with
`success/passed`. No advisory locks remained after either run.

## Remaining scope and limitation

This result establishes canonical playoff schedule coverage only. It does not
promote market observations, claim opening or closing timing, or resolve the
12,059 still-missing eligible regular-season games. Of the eligible source
games, 363 regular-season games have blank dates; the player-game artifact
provides unanimous repair evidence, but that repair requires its own reviewed
promotion phase.

## Recommended next step

Reconcile staged moneyline, spread, and total rows against the now-complete
eligible playoff schedule set. Keep timing as `unknown` and treat historical
static observations as research evidence until a canonical market-observation
grain and selection semantics are approved.
