# Program C1 — Traditional Player-Game Fact Contract

Status: contract implemented; ingestion pilot not started  
Date: 2026-07-28

## Boundary

C1 adds two empty durable tables:

- `player_game_fact_revisions`: immutable source-row evidence;
- `player_game_facts`: selected canonical player-team-game projection.

No historical rows were imported and no existing `gamelogs` rows were changed.

## Revision grain

The immutable source grain is:

`(source_name, source_row_key, parser_version)`

Each revision retains source and canonical identity fields, raw payload,
source-row SHA-256, ingestion-run linkage, retrieval/data-available timestamps,
participation state, starter state, completeness, and traditional box fields.
Conflicting replay of the same source key fails closed. A changed source row or
parser version creates separate evidence.

## Canonical grain

The selected projection is:

`(canonical_game_id, canonical_player_id, canonical_team_id)`

It points to the selected immutable revision and copies the traditional fields
needed for analytical reads. It requires exact schedule/player/team identity and
is not populated by the C1 migration. Selection rules belong to the ingestion
pilot after source reconciliation and correction behavior are tested.

## Traditional field contract

The contract preserves nullable values rather than converting missing values to
zero. It includes minutes, field goals, three-pointers, free throws, offensive
and defensive rebounds, total rebounds, assists, steals, blocks, turnovers,
personal fouls, points, and plus/minus. `participation_status` preserves
`played`, `did_not_play`, and `unknown`; `starter_status` preserves `starter`,
`bench`, and `unknown`.

## Ingestion method deferred to the next task

The later pilot must fetch one bounded completed slate, register source
revisions transactionally, reconcile player totals to team totals, select the
canonical projection, and produce coverage/replay evidence before any season
backfill. Program C will not depend on the legacy thin `gamelogs` table for the
new fact contract.
