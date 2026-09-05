# Program E Rotation Shock — Historical Starter Source Comparison

Date: 2026-08-31  
Source: `BoxScoreTraditionalV2` through the shared NBA fetch/proxy path  
Mode: read-only source probe; no database writes

## Question

Does the Traditional V2 starter source used for the 2024-25 trial also support
the prior five regular seasons, or did the response contract change over time?

## Sample design

Five season-spanning regular-season games were probed from each season:

- 2020-21: opening, early, mid, late, and final-season samples;
- 2021-22: the same spread;
- 2022-23: the same spread;
- 2023-24: the same spread;
- 2024-25: the same spread.

The sample contains 25 games total. The 2024-25 results complement the larger
37-game evidence sample already persisted in
`player_game_starter_evidence`.

## Results

| Season | Games | Player rows | Starter-position rows | Player dataset found | Response shape | Errors |
|---|---:|---:|---:|---:|---|---:|
| 2020-21 | 5 | 137 | 50 | 5/5 | `result_sets` for all | 0 |
| 2021-22 | 5 | 132 | 50 | 5/5 | `result_sets` for all | 0 |
| 2022-23 | 5 | 135 | 50 | 5/5 | `result_sets` for all | 0 |
| 2023-24 | 5 | 131 | 50 | 5/5 | `result_sets` for all | 0 |
| 2024-25 | 5 | 130 | 50 | 5/5 | `result_sets` for all | 0 |

All 25 responses exposed the same `PlayerStats` contract, including
`PLAYER_ID`, `TEAM_ID`, and `START_POSITION`. Each sampled game had exactly
10 populated `START_POSITION` rows. No historical response-shape or starter-
field break was observed.

## Interpretation

The V2 starter method is supported across the sampled 2020-21 through 2024-25
seasons. This is strong evidence that the method did not change across those
seasons, but it is not a full-season completeness claim. A full historical
backfill still needs bounded batches, source retries, exact schedule identity,
canonical-grain reconciliation where canonical facts exist, and exact replay
proof.

The current database boundary is material:

- 2024-25 has 1,230 canonical games and 32,515 canonical player-game facts;
- 2020-21 has 1,080 scheduled regular-season games, reflecting its shortened
  72-game schedule, but no `player_game_facts` yet;
- 2021-22, 2022-23, and 2023-24 each have 1,230 scheduled regular-season games
  but no `player_game_facts` yet;
- the 2024-25 starter-evidence table currently contains 972 rows across 37
  games, including 370 starter rows, and all 370 explicit starter rows are
  linked to canonical facts;
- the two previously tested 2025-26 V2 games returned valid response shapes
  with `START_POSITION` declared but zero player rows.

## Recommended table boundary

Keep `player_game_starter_evidence` as the immutable source-evidence table and
link canonical starter projections back to its evidence row. The 2024-25
covered sample now uses that pattern: 370 canonical facts have starter status,
position, and evidence links, while their existing Traditional V3 revision
lineage remains truthful.

For 2024-25, the reviewed evidence is sufficient for the bounded
provenance-linked projection used for the 37 covered games, with uncovered
games remaining explicitly unknown. Older seasons should first receive their Program C player-game facts
or an equally validated canonical identity layer before starter evidence is
treated as a canonical player-game attribute.

For 2025-26 and future seasons, V2 cannot be the only operational path. The
current-season ingestion should continue through the stable V3 path while a
separate live starter-source trial identifies an endpoint that returns player
rows for current completed games.

## Reproducibility

The probe was run with:

```text
scripts/probe_program_e_rotation_shock_starter_source.py
```

The probe is read-only and intentionally does not create evidence rows.
