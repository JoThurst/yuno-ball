# Program G11 — Review-ready feature comparison

Date: 2026-09-12  
Status: complete for the comparison slice; prediction publication remains blocked

## Purpose

G10 established explicit feature coverage and subgroup sufficiency gates. G11
compares performance only after applying those gates in every approved season.
It produces candidates for further research without selecting a model.

## Contract

`compare_review_ready_feature_variants`:

- intersects variant names across all supplied seasons;
- requires at least 95% effective test-population coverage;
- requires all probability bands to meet the 100-game review threshold;
- reports per-season log loss, Brier score, test games, and log-loss range;
- never persists forecasts or changes the production hold.

## Evidence

| Variant | 2024-25 log loss | 2025-26 log loss | Cross-season range | Common candidate |
|---|---:|---:|---:|---|
| Strength | 0.6284 | 0.6353 | 0.0069 | No: thin 2024-25 low band |
| Strength + Form | 0.6258 | 0.6381 | 0.0123 | No: thin 2024-25 low band |
| Strength + Form + Schedule | 0.6223 | 0.6416 | 0.0193 | Yes |
| Strength + Form + Pace Interaction | 0.6265 | 0.6374 | 0.0109 | Yes |

All variants scored 1,025 test games per season with complete feature inputs.
The common candidate set is therefore limited by subgroup sufficiency, not
missing feature rows.

## Decision

G11 passes the gated comparison procedure. The two schedule-inclusive variants
are research candidates for the next stability review. The smaller cross-season
log-loss range of the Pace Interaction variant is descriptive, not a selection
claim; neither candidate has cleared the held-out calibration gate. No
prediction route, durable forecast table, or betting language is authorized.

Verification:

```text
pytest -q tests/test_model_baseline_experiment_service.py: 13 passed
run_program_g_feature_review.py for 2024-25 and 2025-26: complete, zero writes
compileall app scripts tests: passed
```
