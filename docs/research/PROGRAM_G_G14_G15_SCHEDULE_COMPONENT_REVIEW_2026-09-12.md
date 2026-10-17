# Program G14/G15 — Schedule component review

Date: 2026-09-12  
Status: complete; three components survive stability, but remain research-only

## G14 component stability

The existing pregame schedule fields were evaluated independently from the
home perspective. Positive binary edges mean the away team has the burden,
which favors the home team: `away_flag - home_flag`.

| Component | 2024-25 avg segment log loss | 2025-26 avg segment log loss | Direction gate |
|---|---:|---:|---|
| Back-to-back edge | 0.6193 | 0.6312 | Pass |
| 3-in-4 edge | 0.6270 | 0.6329 | Hold: sign flip |
| 4-in-5 edge | 0.6229 | 0.6369 | Pass |
| 5-in-7 edge | 0.6275 | 0.6340 | Pass |
| Rest asymmetry | 0.6199 | 0.6325 | Hold: sign flip |
| All components | 0.6295 | 0.6477 | Hold: several sign flips |

All six definitions retained 100% coverage in both seasons and all four
chronological blocks. The combined version was worse than the individual
components and was not advanced.

## G15 cross-season comparison

The three stable components were compared against the same strength-plus-form
logistic baseline across the full 1,025-game test population in each season.

| Candidate | 2024-25 log loss | 2025-26 log loss | Cross-season range |
|---|---:|---:|---:|
| Strength + Form + B2B | 0.6193 | 0.6311 | 0.0118 |
| Strength + Form + 4-in-5 | 0.6229 | 0.6369 | 0.0140 |
| Strength + Form + 5-in-7 | 0.6274 | 0.6338 | 0.0064 |

These are comparison candidates, not a production selection. The 5-in-7
variant has the smallest cross-season range, while B2B has the best average
loss of the three; neither claim is sufficient without frozen holdout evidence.

## Decision

G14 and G15 pass component coverage, chronological fit, and directional
stability for B2B, 4-in-5, and 5-in-7. The unstable 3-in-4, rest-asymmetry,
and all-component variants remain held. The three survivors advance to G16.
