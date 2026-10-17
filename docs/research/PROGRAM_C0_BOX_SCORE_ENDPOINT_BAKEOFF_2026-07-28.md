# Program C0 — Box-Score Endpoint Bake-off

Status: technical source trial complete; production promotion not yet approved  
Evaluated: 2026-07-28  
Canonical sample: game `0022500879`, 2025-26, March 3, 2026

## Purpose

Compare the available traditional and advanced box-score endpoints against the
existing player and team game-fact tables before designing the richer Program C
contract. This was a read-only test. No database rows were written.

## Source requests

Both requests used the repository's shared NBA API headers, proxy manager, and
30-second endpoint timeout:

- `BoxScoreTraditionalV3`
- `BoxScoreAdvancedV3`

Both returned HTTP 200 through the configured proxy. The endpoint response is
game-scoped and returns two team objects with nested player statistics.

## Observed sample results

| Source | Player rows | Rows with minutes | Key coverage |
| --- | ---: | ---: | --- |
| Traditional V3 | 24 | 19 | shooting, rebounds, assists, defense, fouls, points, plus/minus |
| Advanced V3 | 24 | 19 | ratings, usage, true shooting, eFG, pace, possessions, PIE |
| Existing `gamelogs` | 19 | 19 | points, assists, rebounds, steals, blocks, turnovers, minutes |

Traditional V3 exposed 20 player-stat fields in the sample. Advanced V3
exposed 23 advanced player-stat fields. The five zero-minute rows are retained
by the endpoint and represent participation/DNP context that the current thin
`gamelogs` table does not preserve.

Traditional player points summed to 241. Existing player logs also summed to
241, and the two existing team-game rows summed to 241. This is a positive
cross-source consistency result for the sample, not a season-wide approval.

## Cost and failure evidence

- Traditional V3 request latency: approximately 1.5 seconds.
- Advanced V3 request latency: approximately 1.0 second.
- Both requests succeeded through the approved proxy route.
- Direct access is not the production assumption; NBA endpoints remain subject
  to proxy, rate-limit, and upstream availability controls.
- A single-game request is operationally suitable for a bounded pilot. A full
  historical backfill still requires explicit batching, retry, checkpoint, and
  cost limits.

## Decision

Proceed with `BoxScoreTraditionalV3` as the first Program C source candidate.
Use `BoxScoreAdvancedV3` as a separate follow-on source after the traditional
contract is stable.

This decision is technical only. Source licensing, redistribution rights,
historical coverage, and production scheduling still require review before
canonical promotion.

## Next task — C1

Define the traditional player-game fact contract and migration boundary:

1. choose immutable source-revision grain and canonical selected grain;
2. preserve raw payload/hash, source run, parser version, retrieval time, and
   completeness;
3. map traditional fields without silently zero-filling missing values;
4. retain zero-minute/DNP rows and starter/bench evidence where available;
5. add a bounded fixture contract and schema metadata tests;
6. defer historical apply until the contract review passes.
