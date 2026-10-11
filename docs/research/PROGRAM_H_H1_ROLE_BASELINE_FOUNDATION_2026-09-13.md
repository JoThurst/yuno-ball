# Program H1 — Role baseline foundation

Date: 2026-09-13  
Status: implementation foundation complete; bounded database apply/replay complete; backtest and forward source gates remain open

## What shipped

H1 now has two versioned durable projections:

- `player_role_history`: a deterministic derived projection of canonical
  player-game facts with actual minutes, parsed decimal minutes, participation,
  starter state, starter position, and source fact/hash/run lineage.
- `pregame_player_role_baselines`: a cutoff-aware descriptive role band with
  prior history counts, starts, 25th percentile / median / 75th percentile
  minutes, confidence, completeness, freshness, and missing-input flags.

The materializer is bounded by `scripts/build_program_h_role_baselines.py` and
creates its own derived ingestion run by default; an existing run ID can be
supplied for replay tests. It skips date-only schedules because a date without
a trustworthy tipoff cannot define a strict pregame cutoff.

The read-only evaluator is `scripts/audit_program_h_role_baseline.py`. It
reports median absolute error and role-band coverage overall and by usable
history depth; it never writes to PostgreSQL. Its historical audit mode uses a
strictly prior game-date proxy because the existing backfilled player facts
have load timestamps rather than source-publication timestamps. That output
is explicitly not production-ready.

## Bounded database gate

The additive migration was applied to the local PostgreSQL database and the
schema is at repository head `i5j6k7l8m9n0`. A bounded 2024-25 Regular Season
materialization then completed under derived ingestion run
`a5d03bbf-828a-4e1a-ba0e-4bac9c3ca627`:

| Check | Result |
| --- | ---: |
| Canonical facts read | 32,515 |
| Role-history rows written | 32,515 |
| Pregame baseline rows written | 216 |
| Role-history natural-key duplicates | 0 |
| Baseline natural-key duplicates | 0 |
| Persisted baseline status | 216 `unknown` / `strict_source` |

The exact materialization was replayed with the same run ID and produced the
same logical counts without duplicate natural keys. The `unknown` result is
correct: these historical facts have 2026 load timestamps rather than source
publication timestamps that can be compared with each game's pregame cutoff.
It does not mean the players had no prior role history; it means the history
cannot be proven available before the target game under the production timing
contract.

The read-only timing audit is `scripts/audit_program_h_source_timing.py`. It
reports timestamp coverage, schedule precision, and the number of exact-tipoff
target team rows with any strictly eligible prior history. This is the source
readiness gate for forward ingestion; it performs no writes.

The first live audit confirms the gate is still closed:

| Season | Facts | Schedule precision | Exact target team rows | Rows with any strict prior history |
| --- | ---: | --- | ---: | ---: |
| 2024-25 | 32,515 | 2,450 date-only / 10 exact | 10 | 0 |
| 2025-26 | 32,179 | 466 date-only / 1,994 exact | 1,994 | 0 |

All facts have a non-null `data_available_at`, but the observed ranges are
2026-08-10 for 2024-25 and 2026-07-30 through 2026-08-04 for 2025-26. Those
timestamps describe the historical backfill, not when each box score became
available after its game, so they cannot support a historical pregame cutoff.
The forward 2026-27 bridge must preserve collection-time timestamps as it
ingests each completed game; no retrospective rewrite is justified.

## Contract decisions

1. A row qualifies only when `game_date < target_game_date` and
   `data_available_at <= feature_as_of`.
2. DNP, missing minutes, and unknown starter status are retained as evidence;
   none is silently changed to zero, bench, or healthy.
3. The output is a role band, not an exact expected-minutes prediction.
4. The baseline is derived from canonical facts only; it does not add a new
   network dependency or replace the existing starter-evidence table.
5. Every baseline records `timing_policy`; the publisher rejects historical
   date-proxy records, keeping them read-only for evaluation.

## Remaining gates

## First backtest — historical timing proxy

The read-only 2024-25 evaluator used a strictly prior game-date proxy because
the backfilled canonical facts were loaded after the games and do not retain
original source-publication times. Results:

| Cohort | Player-games | Median absolute error | Low/high band coverage |
| --- | ---: | ---: | ---: |
| 1–4 usable games | 3,518 | 3.53 minutes | 19.0% |
| 5–9 usable games | 9,128 | 4.22 minutes | 35.1% |
| 10 usable games | 12,971 | 3.70 minutes | 39.3% |
| All evaluated | 25,617 | 3.83 minutes | 35.0% |

The median is promising as a descriptive role anchor, but the current
25th–75th percentile band under-covers actual minutes and the timing proxy is
not production evidence. No predictive or Rotation Shock claim is approved.

Band percentiles are now configurable in the read-only evaluator so wider
candidate intervals can be compared without silently changing the production
contract (`role-baseline-v1` remains 25th–75th percentile until a new version
is approved).

The 15th–85th candidate produced 49.9% coverage on 2024-25 and 51.0% on
2025-26, with median absolute error of 3.83 and 3.87 minutes respectively.
This is the leading candidate for a future `role-baseline-v1.1`, but it still
needs the pre-registered walk-forward gate in
`PROGRAM_H_H1_ROLE_BAND_CALIBRATION_PROTOCOL_2026-09-13.md` and real
source-availability timing.

The complete fixed-candidate historical rehearsal is:

| Season | Band | Evaluated | Coverage | MdAE |
| --- | --- | ---: | ---: | ---: |
| 2024-25 | p25/p75 | 25,617 | 35.0% | 3.83 |
| 2024-25 | p20/p80 | 25,617 | 42.4% | 3.83 |
| 2024-25 | p15/p85 | 25,617 | 49.9% | 3.83 |
| 2024-25 | p10/p90 | 25,617 | 57.6% | 3.83 |
| 2025-26 | p25/p75 | 25,953 | 36.1% | 3.87 |
| 2025-26 | p20/p80 | 25,953 | 43.7% | 3.87 |
| 2025-26 | p15/p85 | 25,953 | 51.0% | 3.87 |
| 2025-26 | p10/p90 | 25,953 | 58.6% | 3.87 |

All eight results use `historical_game_date_proxy` and therefore remain
method-rehearsal evidence only. Wider bands improve coverage monotonically in
this replay, but no band has passed the forward timing or confirmatory gates.

- Run a bounded 2024-25 materialization and verify row grain, null behavior,
  source lineage, and exact rerun counts.
- Recalibrate low/high band widths with a walk-forward evaluation, then
  pre-register error/coverage thresholds before reviewing the next result.
- Obtain trustworthy source-availability timing for forward facts; the current
  historical load timestamps cannot satisfy the strict production cutoff.
- Add official availability joins only after report timestamp and identity
  coverage pass the existing source gates.
- Do not publish Rotation Shock or exact expected-minutes language until those
  checks pass. Preseason is now underway externally, but the current C7 bridge
  remains Regular Season-only; 2026-27 waits on the first eligible completed
  Regular Season game.

## Verification in this change

Focused H1, role-coverage, daily-bridge, starter-bridge, adapter, orchestration,
and schema metadata tests pass with the project runtime (`38 passed`). `compileall` passes for the
application, scripts, and migration. `git diff --check` passes; the remaining
messages are normal Windows line-ending warnings. The live database confirms
Alembic current/head parity at `i5j6k7l8m9n0` and zero duplicate natural keys
in both H1 projections. The hardened 2026-27 daily bridge was rerun on
2026-09-13 and returned `no_op` with zero pending, blocked, or written games;
the completed-game smoke gate remains waiting on the first eligible completed
Regular Season game.
