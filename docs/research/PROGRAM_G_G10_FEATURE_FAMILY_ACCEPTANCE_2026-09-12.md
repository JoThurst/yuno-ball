# Program G10 — Feature-family availability and acceptance review

Date: 2026-09-12  
Status: complete for the descriptive review contract; prediction publication remains blocked

## Purpose

G9 added probability-band reporting. G10 makes the feature-family and subgroup
review gates explicit on the same effective population used by the historical
ablation runner.

## Contract

Each cumulative feature variant now reports:

- effective test games after the chronological warmup;
- scored test games and withheld test games;
- test-population coverage against a 95% review threshold;
- probability-band counts and a 100-game-per-band subgroup review threshold;
- explicit `review_ready` versus `blocked_thin_subgroup` status.

Missing family inputs remain withheld and counted. No value is zero-filled,
and a review-ready variant is not a production approval.

## Evidence

The four variants were evaluated on 1,025 chronological test games per
approved season. All variants scored all 1,025 games in both seasons, giving
100% coverage and zero withheld rows.

| Season | Variant | Coverage | Low / competitive / high games | Subgroup review |
|---|---|---:|---:|---|
| 2024-25 | Strength | 100% | 92 / 528 / 405 | Blocked: low band thin |
| 2024-25 | Strength + form | 100% | 88 / 520 / 417 | Blocked: low band thin |
| 2024-25 | + schedule | 100% | 103 / 502 / 420 | Review-ready |
| 2024-25 | + pace interaction | 100% | 104 / 504 / 417 | Review-ready |
| 2025-26 | Strength | 100% | 191 / 545 / 289 | Review-ready |
| 2025-26 | Strength + form | 100% | 200 / 539 / 286 | Review-ready |
| 2025-26 | + schedule | 100% | 205 / 530 / 290 | Review-ready |
| 2025-26 | + pace interaction | 100% | 211 / 502 / 312 | Review-ready |

## Decision

G10 passes the feature-availability contract and makes subgroup sufficiency
auditable. The 2024-25 simple variants cannot be treated as equally supported
for subgroup review, despite complete inputs. No feature family is promoted to
a production model, and no prediction route or durable forecast table is
created.

The next G slice is to compare feature-family performance and stability only
among variants that meet the explicit review contract, while preserving the
same chronological and held-out gates.

Verification:

```text
pytest -q tests/test_model_baseline_experiment_service.py: 12 passed
compileall app scripts tests: passed
read-only ablations for 2024-25 and 2025-26: complete, zero withheld inputs
```
