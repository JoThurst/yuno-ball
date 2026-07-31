# Program C2 — Traditional V3 bounded pilot

Status: completed and superseded by the reviewed C3-C6 bounded slice.

The adapter is bounded by an explicit game-ID list and `max_games`, uses
`create_api_endpoint` for the shared proxy/header path, and transforms the
Traditional V3 player dataset without modifying `gamelogs`. It rejects
response game/season/season-type identity mismatches, retains a deterministic
hash of the complete response alongside each raw source row, and preserves
zero-minute/DNP rows and unknown starter state. Source row keys, row hashes,
retrieval time, source name, parser version, and run ID are retained in the
revision payload.

`scripts/collect_traditional_player_game_facts.py` requires explicit game IDs,
enforces a maximum of 25 games, and requires `--dry-run` or `--apply`. Apply validates
both reciprocal `game_schedule` rows and their exact date/season/type/team
identity, reconciles player points to the two endpoint team rows, registers
immutable revisions, and only then updates `player_game_facts` in the caller's
transaction. Identical replays are no-ops; a changed source/parser lineage
creates a retained revision and selects it in the canonical projection.

Focused proof: `compileall` passed; 19 focused tests covering the C1 service,
adapter, reconciliation fixture, and schema metadata passed; `alembic check`
reported no new upgrade operations. The fixture proves DNP preservation, null
semantics, unknown starter semantics, deterministic hashing, reciprocal team
totals, and fail-closed mismatch behavior.

Scheduling and unbounded historical expansion remain prohibited. The bounded live run on 2026-07-30
(game `0022500879`) returned HTTP 200 and produced 24 player rows, 0 DNP rows
in this response, reciprocal team points of 123 and 118, and 241 total
points. The retained response hash was
`a0a3ba8855ad5c56012041ce08f6a7cba0eb600993d2633ccfbc1e76766994a4`.

Apply evidence: first apply created 24 revisions and 24 canonical facts; the
exact replay created 0 revisions and left all 24 canonical facts unchanged.
Read-only invariants then showed 24 revisions, 24 facts, 0 duplicate canonical
grains, and 24 revisions with raw provenance. The later parser-v2 correction
classified provider DNP comments without mutating v1 evidence. C3-C6 expanded
the reviewed boundary to 11 games, added Advanced V3, reconciliation, and
canonical-first consumers. `gamelogs` was not mutated by Program C.
