# Program G12 — Candidate stability review

Date: 2026-09-12  
Status: complete for the stress-test slice; production prediction remains blocked

## Purpose

G12 stress-tests the two candidates admitted by G11 using four chronological
test segments in each approved Regular Season. It checks segment performance,
effective-population coverage, and the sign consistency of standardized
feature coefficients across expanding-history fits.

The review is descriptive. It does not rank candidates, select a production
model, persist forecasts, or change the production hold.

## Contract

`review_feature_family_stability`:

- accepts only the explicitly supplied G11 candidate variants;
- evaluates each chronological block independently using prior history only;
- reports block dates, game counts, coverage, log loss, and Brier score;
- reports coefficient range and sign consistency by feature family;
- marks a candidate `next_gate_ready` only when every segment clears 95%
  coverage and every observed feature direction is sign-consistent;
- performs zero writes.

## Evidence

Both candidates covered 1,025/1,025 test games in each season and completed all
four chronological segments. Strength and form coefficients were positive in
all eight fits for both candidates.

| Candidate | 2024-25 segment log loss | 2025-26 segment log loss | Feature stability | Next gate |
|---|---|---|---|---|
| Strength + Form + Schedule | 0.6613 / 0.6409 / 0.5972 / 0.5802 | 0.7359 / 0.6698 / 0.6017 / 0.5225 | strength/form consistent; schedule flips sign | Hold |
| Strength + Form + Pace Interaction | 0.6714 / 0.6440 / 0.6006 / 0.5813 | 0.7325 / 0.6671 / 0.5971 / 0.5192 | strength/form consistent; schedule and interaction flip sign | Hold |

Cross-season standardized coefficient ranges:

| Candidate | Feature | Coefficient range | Sign status |
|---|---|---:|---|
| Schedule | strength | 0.2187 | consistent positive |
| Schedule | form | 0.4549 | consistent positive |
| Schedule | schedule | 0.1607 | unstable: negative and positive |
| Pace Interaction | strength | 0.2106 | consistent positive |
| Pace Interaction | form | 0.4520 | consistent positive |
| Pace Interaction | schedule | 0.1521 | unstable: negative and positive |
| Pace Interaction | matchup context | 0.2058 | unstable: negative and positive |

## Decision

The data path and chronological scoring procedure pass. The feature-direction
gate does not pass for either candidate, because schedule is not directionally
stable and the interaction variant adds a second unstable feature. The
candidate set remains useful for research, but neither candidate is ready for
production calibration or public prediction output.

The next investigation is concrete: inspect the schedule feature definition and
its interaction with early-season sample size, then rerun the same four-segment
review with a narrower, explicitly signed schedule contract. Keep pace
interaction out of any production claim until its sign stability is resolved.

## Verification

```text
focused service tests: 15 passed
two-season stability runner: complete, 2024-25 and 2025-26, four blocks each
effective coverage: 100% for both candidates in both seasons
writes_performed: false
```
