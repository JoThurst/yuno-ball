# Program G8 — Chronological window sweep

Date: 2026-09-12  
Status: complete for the read-only stability slice; prediction publication remains blocked

## Purpose

G7 made calibration uncertainty visible within each reliability bin. G8 tests
whether the calibration conclusion is stable when the source season is split
at different chronological boundaries. The sweep is not a model-selection
mechanism and does not persist predictions.

## Contract

`run_season_heldout_window_sweep` evaluates explicit named windows:

- `50_25_25`: 50% train, 25% calibration, 25% source test;
- `60_20_20`: 60% train, 20% calibration, 20% source test;
- `70_15_15`: 70% train, 15% calibration, 15% source test.

Every window reuses the existing audit-gated held-out evaluator. It retains
the private post-prediction Elo update, frozen calibration transform, Wilson
interval metadata, thin-bin flags, and `writes_performed: false` contract.

## Evidence

All three windows completed in both directions with 1,075 games in each
approved Regular Season.

### 2024-25 source → 2025-26 held out

| Window | Source-test raw → calibrated log loss | Held-out raw → calibrated log loss | Held-out ECE raw → calibrated | Thin bins |
|---|---:|---:|---:|---:|
| 50/25/25 | 0.5950 → 0.5869 | 0.6149 → 0.6128 | 0.0337 → 0.0318 | 2 |
| 60/20/20 | 0.5928 → 0.5849 | 0.6148 → 0.6130 | 0.0410 → 0.0421 | 2 |
| 70/15/15 | 0.5844 → 0.5871 | 0.6139 → 0.6154 | 0.0444 → 0.0424 | 2 |

### 2025-26 source → 2024-25 held out

| Window | Source-test raw → calibrated log loss | Held-out raw → calibrated log loss | Held-out ECE raw → calibrated | Thin bins |
|---|---:|---:|---:|---:|
| 50/25/25 | 0.5082 → 0.5066 | 0.6247 → 0.6305 | 0.0532 → 0.0688 | 1 |
| 60/20/20 | 0.5019 → 0.4788 | 0.6259 → 0.6337 | 0.0472 → 0.0741 | 1 |
| 70/15/15 | 0.4933 → 0.4629 | 0.6274 → 0.6427 | 0.0497 → 0.0643 | 1 |

## Decision

G8 passes the reproducible cross-window evaluation gate. It does not support
choosing a production calibration window: source-test improvements are not
consistently preserved in the opposite season, and thin tail bins remain.
Prediction publication stays blocked.

The next G slice is subgroup stability and explicit feature-family contracts
on the same effective population. Current-season 2026-27 remains blocked
until completed-game evidence exists.

Verification:

```text
pytest -q tests/test_model_baseline_experiment_service.py: 10 passed
run_program_g_window_sweep.py in both directions: complete, zero writes
```
