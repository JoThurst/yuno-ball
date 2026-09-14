# Program G7 — Uncertainty-aware calibration monitoring

Date: 2026-09-12  
Status: complete for the read-only monitoring slice; prediction publication remains blocked

## Why this slice

The G6 held-out validation established a reproducible train/calibration/test
procedure, but calibration conclusions can be overstated when a reliability
bin has very few games. G7 adds uncertainty metadata without changing the
model, fitting future information, persisting forecasts, or changing the
existing ECE/MCE point estimates.

## Implemented contract

`app.services.model_baseline_experiment_service._calibration` now returns:

- a two-sided 95% Wilson interval for each observed win rate;
- `meets_minimum_bin_count` for a 25-game monitoring threshold;
- `stable_bin_count` and `thin_bin_count` in a monitoring summary;
- the explicit interval method name.

Empty calibration reports also return the monitoring metadata with zero bins.
Invalid minimum thresholds fail closed. A focused regression test covers the
interval behavior and thin-bin classification.

## Evidence

The actual 2024-25 source → 2025-26 held-out run remained complete with 1,075
games in each season and no writes:

| Measure | Raw | Calibrated |
|---|---:|---:|
| Held-out log loss | 0.6148 | 0.6130 |
| Held-out Brier | 0.2125 | 0.2117 |
| Held-out ECE | 0.0410 | 0.0421 |
| Held-out MCE | 0.1585 | 0.1053 |

The calibrated held-out report had 8 bins meeting the 25-game threshold and 2
thin bins. The source-test report had 6 stable bins and 4 thin bins. Tail-bin
gaps must therefore be read with their Wilson intervals and not treated as
stable production evidence.

The reverse 2025-26 → 2024-25 direction also completed with 1,075 held-out
games. Calibration improved held-out MCE from 0.1583 to 0.1067, but worsened
log loss from 0.6259 to 0.6337 and ECE from 0.0472 to 0.0741. It had 9 stable
calibrated bins and 1 thin bin. The mixed directions are direct evidence that
calibration repair is not yet a production decision.

## Gate decision

G7 passes the uncertainty-reporting and reproducibility slice. It does not
approve a prediction route, durable prediction table, market comparison, or
betting language. The next G work should broaden chronological windows and
seasons where audited inputs exist, then define minimum-bin/interval-aware
acceptance rules for a future production review.

Verification:

```text
compileall app tests: passed
pytest -q tests/test_model_baseline_experiment_service.py: 9 passed
run_program_g_heldout_validation.py --source-season 2024-25 --heldout-season 2025-26: complete, writes_performed=false
```
