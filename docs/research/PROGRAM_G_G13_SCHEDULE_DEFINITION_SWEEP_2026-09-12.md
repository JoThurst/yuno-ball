# Program G13 — Schedule-definition sensitivity sweep

Date: 2026-09-12  
Status: complete; no schedule definition cleared the stability gate

## Purpose

G12 identified schedule-direction instability. G13 tests a bounded set of
explicit home-perspective rest-edge definitions against the two G11 candidates:

- `rest_edge_raw`: home days-rest minus away days-rest, as the control;
- `rest_edge_clipped_1`: the same edge clipped to `[-1, 1]`;
- `rest_edge_signed`: the same edge reduced to `-1`, `0`, or `1`;
- `home_rest_deficit`: negative home rest edge only, with non-negative values
  reduced to zero.

Every definition is applied in memory and rerun through the same four-block,
expanding-history review in 2024-25 and 2025-26. No predictions or source
rows are persisted.

## Evidence

All eight definition/candidate runs retained 1,025/1,025 scored test games in
each season. None cleared the feature-direction gate.

| Definition | Candidate | Average segment log loss 2024-25 | Average segment log loss 2025-26 | Unstable features | Next gate |
|---|---|---:|---:|---|---|
| Raw rest edge | Strength + Form + Schedule | 0.6199 | 0.6325 | schedule | Hold |
| Clipped rest edge | Strength + Form + Schedule | 0.6184 | 0.6334 | schedule | Hold |
| Signed rest edge | Strength + Form + Schedule | 0.6184 | 0.6334 | schedule | Hold |
| Home rest deficit | Strength + Form + Schedule | 0.6264 | 0.6293 | schedule | Hold |
| Raw rest edge | Strength + Form + Pace Interaction | 0.6243 | 0.6290 | schedule, matchup context | Hold |
| Clipped rest edge | Strength + Form + Pace Interaction | 0.6226 | 0.6299 | schedule, matchup context | Hold |
| Signed rest edge | Strength + Form + Pace Interaction | 0.6226 | 0.6299 | schedule, matchup context | Hold |
| Home rest deficit | Strength + Form + Pace Interaction | 0.6319 | 0.6263 | schedule, matchup context | Hold |

## Decision

The issue is not missing schedule data or a single outlier definition. The
schedule signal itself is weak or context-dependent in this baseline: all
definitions retain coverage, but the fitted schedule direction changes across
chronological blocks. Clipping and signing change scale more than information,
and the deficit-only formulation does not remove the instability.

Keep schedule out of any production prediction claim for now. The next useful
slice is not another transform of the same rest difference; it is a source and
contract review of schedule pressure using separately auditable components:
back-to-back, games in four days, games in six days, and rest asymmetry. Those
components should be evaluated independently before any composite is allowed.

## Verification

```text
focused service tests: 16 passed
two-season schedule sweep: complete across four definitions and four blocks
effective coverage: 100% for both candidates under every definition
writes_performed: false
```
