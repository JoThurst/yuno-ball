# Program C5 — Player-game correction and reconciliation methodology

Status: implemented as a bounded read-only gate

## Selection and correction contract

Traditional and Advanced V3 source rows are immutable at
`(source_name, source_row_key, parser_version)`. Identical response rows are
no-op replays. A parser-version change or changed source row creates retained
evidence, after which the canonical player/team/game projection selects the
new validated revision transactionally. Legacy `gamelogs` is never updated,
deleted, or used to overwrite the new revision history.

## Required gate

`scripts/validate_player_game_facts.py` accepts an explicit game list and
maximum game count. It fails closed on:

- missing reciprocal schedule rows;
- duplicate traditional or advanced canonical grains;
- Traditional/Advanced player-team identity drift;
- player point totals that do not equal canonical team scores.

It also reports DNP/unknown coverage, parser versions, corrected source rows,
raw revision counts, and field-level overlap with legacy `gamelogs`. Legacy
differences remain evidence to review; they never trigger destructive repair.

## Historical expansion policy

Expansion is explicit-game and bounded to at most 25 games per invocation.
Fetch and reconciliation complete for the whole batch before one publication
transaction starts. Each batch records an ingestion run, per-game response
hash, player/DNP counts, team reconciliation, and exact replay behavior.
Historical seasons proceed in reviewed checkpoints; no full-season scheduler
is enabled by Program C.

## Reviewed evidence

The 2026-07-30 gate passed across 11 explicit games: 22 reciprocal schedule
rows, 291 Traditional facts, 315 Traditional revisions, 291 Advanced facts,
and 291 Advanced revisions. It found zero canonical duplicates, missing
schedule/team rows, Traditional/Advanced identity mismatches, or team-point
mismatches. The revision surplus is the retained 24-row parser-v1 evidence
superseded by parser v2. The overlap with `gamelogs` was 234 rows; 57
Traditional-only rows included 54 DNP rows, two unknown-participation rows,
and one played row. One two-second legacy minutes-format discrepancy remains
non-blocking evidence, not a repair instruction.
