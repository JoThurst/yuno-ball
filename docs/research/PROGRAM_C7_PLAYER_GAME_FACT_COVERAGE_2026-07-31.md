# Program C7 — Player-game fact coverage inventory and bounded expansion

Status (2026-08-11): 2025-26 and 2024-25 Regular Season coverage complete

## Read-only inventory

The inventory command is:

```bash
python scripts/generate_player_game_fact_coverage.py --season 2025-26 --season-type "Regular Season" --max-batch-size 25 --summary
```

It reads `game_schedule`, `team_game_stats`, legacy `gamelogs`,
`player_game_facts`, and `player_game_advanced_facts`. It does not write to the
database. A game is eligible only when its two schedule rows are reciprocal,
share one date, both have a final W/L result, and the matching two team-game
rows exist.

## Verified 2025-26 Regular Season range

The local database currently reports:

| Measure | Result |
| --- | ---: |
| Schedule rows | 2,460 |
| Unique scheduled games | 1,230 |
| Eligible completed games | 1,230 |
| Date range | 2025-10-21 through 2026-04-13 |
| Eligible games with reciprocal team stats | 1,230 |
| Traditional canonical coverage | 1,230 games |
| Advanced canonical coverage | 1,230 games |
| Traditional games pending | 0 |
| Advanced games pending | 0 |
| Bounded batches at 25 games | 0 |
| Blocked games from schedule/team facts | 0 |

The 2025-26 coverage gate is complete. Traditional and Advanced facts are
available at the same player/team/game grain, with source revisions retained
and legacy `gamelogs` preserved.

## Verified 2024-25 Regular Season expansion

The read-only inventory reports the following prerequisites:

| Measure | Result |
| --- | ---: |
| Schedule rows | 2,460 |
| Unique scheduled games | 1,230 |
| Eligible completed games | 1,230 |
| Date range | 2024-10-22 through 2025-04-13 |
| Eligible games with reciprocal team stats | 1,230 |
| Traditional canonical coverage | 1,230 games |
| Advanced canonical coverage | 1,230 games |
| Traditional games pending | 0 |
| Advanced games pending | 0 |
| Bounded batches at 25 games | 0 |
| Blocked games from schedule/team facts | 0 |

The completed season was run through the reusable orchestrator:

```bash
python scripts/collect_player_game_fact_batches_until_complete.py \
  --season 2024-25 --season-type "Regular Season" \
  --max-games 25 --pause-seconds 2 --preflight-dry-run
```

The command applies each pending batch once, runs C5 reconciliation, and
performs a database-only no-op replay. It stops on the first failure and
resumes from the uncovered inventory when rerun. `--preflight-dry-run` is
optional and is not repeated for every batch. Use `--max-batches 10` as an
operator safety cap; omit it when intentionally allowing the season to run to
completion.

The run completed all 50 bounded batches. One batch initially stopped on a
G-League-only/inactive Erik Stevenson DNP roster row (`0022400799`); the retry
preserved the Traditional and Advanced DNP facts and recorded a source-only
player identity with `available_seasons=[]`. The successful retry run recorded
`source_only_dnp_ids=[1641907]`, and its database-only replay produced zero
writes.

## Initial batch evidence

Batch 1 covered 25 games through the configured proxy. The apply run was
`078b15a4-4b36-4b35-8b23-b462ac085050`; it published 708 Traditional and 708
Advanced facts, with 120 DNP rows in each representation. C5 reconciliation
passed with zero missing schedule/team rows, duplicate rows, identity
mismatches, or team-total mismatches.

The exact-manifest replay was
`3e1b3462-f59d-4c9f-95ea-d235cd6b7d4b`. It completed successfully with 708
Traditional facts unchanged, 708 Advanced facts unchanged, zero revisions,
and zero writes. This is the required no-op replay proof.

## External access gate

The first Traditional dry-run selected the first 25 planned IDs. The first 15
endpoint responses returned HTTP 200 and were validated in memory; the request
for `0022500006` then timed out after 120 seconds. Because the collector
validates the complete batch before publication, zero rows were written. A
second narrowed 15-game dry-run then timed out on its first request, confirming
that the current NBA access path was unavailable rather than exposing a
source-data or reconciliation defect.

Those direct-path failures remain historical evidence; the configured proxy
path is now healthy for bounded collection. No `gamelogs` or older table was
modified.

## Historical batch evidence

Batch numbers are recalculated from the current pending inventory for the
requested season. The batch runner persists the exact manifest in the
ingestion run and supports `--replay-run-id` for the no-op proof. Apply
Traditional first, then Advanced, with exact identity parity and C5
reconciliation after each pair. Do not schedule the collectors or begin
Program D feature publication for a season until its eligible games pass the
coverage and reconciliation gate.
