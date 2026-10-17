# Program C6 — Canonical-first player-game consumer migration

Status: completed as a non-destructive compatibility migration

## Read contract

`PlayerGameFactReadService` is the player-game read boundary for migrated
analytics and serving consumers. It selects validated `player_game_facts`
first at the exact player/team/game key and fills only uncovered keys from
legacy `gamelogs`. It exposes named compatibility rows, converts canonical
minutes to the legacy decimal-minute representation, and defaults to played
games so retained DNP evidence does not inflate analytical samples.

The migration covers player snapshots, player details and recent logs,
streaks, heat index, consistency, dashboard reads, and season-context reads.
Direct `GameLogORM` reads now remain only in the compatibility service and the
C5 legacy comparison gate. Fetchers and validators may still maintain or
inspect `gamelogs`; no Program C code deletes, truncates, or rewrites it.

## Database proof

For 2025-26, the merged read returned 28,347 unique player-game keys:
28,112 from legacy fallback and 235 from canonical V3. The legacy table still
contained 28,346 rows, so all old coverage remained available while one
additional validated played canonical row became visible. A leakage-bound
snapshot build for the 2026-03-05 slate consumed 20,092 rows across 542
players and had a maximum source game date of 2026-03-04.

## Removal gate

No legacy table is redundant merely because direct consumers moved behind one
reader. Table retirement requires complete reviewed historical coverage,
consumer and writer inventories, field-level equivalence, rerun/correction
proof, deployment and rollback plans, and completion of the overarching
analytics roadmap. Until then, `gamelogs` and all older tables remain intact.
