# Program H0 — Availability and rotation input audit

Date: 2026-09-12  
Status: complete for the evidence audit; rotation-impact publication remains blocked

## Evidence

The read-only audit ran against both approved Regular Seasons:

| Season | Canonical player facts | Known starter/bench rows | Complete starter-evidence games | Pregame reported team slates | Unreported completed team slates |
|---|---:|---:|---:|---:|---:|
| 2024-25 | 32,515 | 390 | 39 | 2,460 | 0 |
| 2025-26 | 32,179 | 0 | 0 | 2,454 | 6 |

2024-25 starter evidence is provenance-backed but limited to 39 games. The
2025-26 canonical player facts have no known starter/bench rows. Neither season
has a durable lineup/rotation table or expected pregame minutes observation.

## Decision

The availability source boundary is healthy enough for explicit status context
and a clearly labeled role-disruption research proxy. It is not sufficient for
exact expected-minutes-at-risk, lineup continuity, replacement quality, or a
production Rotation Shock metric. Missing reports remain unknown; they are not
converted into healthy, available, or zero impact.

Program H remains gated on a validated historical/current starter and rotation
source, plus an explicit pregame minutes baseline. The current Daily product
may continue to show provenance-aware availability uncertainty without making
rotation-impact or prediction claims.

## Verification

```text
scripts/audit_program_e_rotation_shock.py: read-only audits complete for 2024-25 and 2025-26
focused availability/starter/player-fact/model regressions: 30 passed
writes_performed: false
```
