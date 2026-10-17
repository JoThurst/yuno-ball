# Program G9 — Probability-band subgroup stability

Date: 2026-09-12  
Status: complete for the descriptive subgroup slice; prediction publication remains blocked

## Purpose

Global calibration averages can hide where a model is reliable or fragile.
G9 adds a stable review breakdown across broad probability bands without
changing the chronological fitting procedure or persisting predictions.

## Contract

Every probability report now includes mutually exclusive bands:

- `low_confidence`: predicted home win probability below 0.35;
- `competitive`: probability from 0.35 through below 0.65;
- `high_confidence`: probability at least 0.65.

Each band reports count, share of evaluated games, log loss, Brier score,
Wilson-aware calibration, and thin-bin monitoring. Band coverage sums to 100%
when evaluated rows are present. Empty bands remain explicit with zero count
and null metrics; no missing band is treated as healthy.

## Evidence

Using the established 60/20/20 train/calibration/source-test window:

| Source → held out | Band | Games | Coverage | Held-out log loss | ECE | Thin bins |
|---|---|---:|---:|---:|---:|---:|
| 2024-25 → 2025-26 | Low confidence | 188 | 17.5% | 0.5464 | 0.0335 | 1 |
| 2024-25 → 2025-26 | Competitive | 476 | 44.3% | 0.6755 | 0.0484 | 0 |
| 2024-25 → 2025-26 | High confidence | 411 | 38.2% | 0.5711 | 0.0425 | 1 |
| 2025-26 → 2024-25 | Low confidence | 275 | 25.6% | 0.5866 | 0.0630 | 1 |
| 2025-26 → 2024-25 | Competitive | 402 | 37.4% | 0.6847 | 0.0694 | 0 |
| 2025-26 → 2024-25 | High confidence | 398 | 37.0% | 0.6147 | 0.0866 | 0 |

The competitive band is the largest evaluated subgroup in both directions.
The reverse high-confidence band is materially less calibrated than the
forward high-confidence band, which reinforces the existing production hold.

## Decision

G9 passes the subgroup-reporting contract and produces complete coverage in
both season directions. It does not approve a probability band for product
display, does not create a prediction route, and does not authorize betting
language. The next G slice is to formalize feature-family availability and
subgroup acceptance thresholds on the same effective population.

Verification:

```text
pytest -q tests/test_model_baseline_experiment_service.py: 11 passed
probability-band evaluation on both held-out directions: complete, zero writes
```
