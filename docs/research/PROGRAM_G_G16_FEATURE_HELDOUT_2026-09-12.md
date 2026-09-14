# Program G16 — Frozen cross-season feature holdout

Date: 2026-09-12  
Status: complete; no schedule component demonstrated uniform incremental lift

## Purpose

G16 fits each candidate on one complete approved Regular Season, freezes the
scaler and coefficients, and scores the opposite season. The strength-plus-
form control is included so a schedule component must demonstrate transferable
incremental information rather than merely produce an acceptable standalone
score.

## Evidence

Every candidate and the control scored 1,075/1,075 games in both directions.

| Candidate | 2024-25 → 2025-26 | 2025-26 → 2024-25 | Mean | Direction range |
|---|---:|---:|---:|---:|
| Strength + Form control | 0.5954 | 0.6079 | 0.6016 | 0.0125 |
| Strength + Form + B2B | 0.5967 | 0.6052 | 0.6010 | 0.0085 |
| Strength + Form + 4-in-5 | 0.5957 | 0.6079 | 0.6018 | 0.0122 |
| Strength + Form + 5-in-7 | 0.5947 | 0.6081 | 0.6014 | 0.0134 |

Lower log loss is better. None of the three schedule candidates beat the
control in both directions. B2B has the lowest two-direction mean and the
smallest direction range, but its forward result is worse than control. 5-in-7
improves forward loss but worsens reverse loss. These are descriptive
tradeoffs, not a production lift claim.

## Decision

The frozen cross-season data and coverage gates pass. The incremental-lift
gate is held: no schedule component has earned promotion into a predictive
feature family. Keep the components available for descriptive Daily context,
but do not use them to advertise a model advantage.

The next productive move is Program H / availability and rotation evidence,
while keeping G on a narrow monitoring track. A future schedule revisit should
require a new source or a pre-registered hypothesis, not more transforms of the
same fields.

## Verification

```text
focused service tests: 18 passed
G14/G15 component stability and comparison: complete
G16 frozen holdout: complete in both season directions
heldout coverage: 100% for every candidate and control
writes_performed: false
```
