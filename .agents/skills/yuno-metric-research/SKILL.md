---
name: yuno-metric-research
description: Use ONLY when the task directly modifies or evaluates a Yuno metric, descriptive analysis, pregame feature, model experiment, or research promotion gate.
---

# Yuno metric and model research

## Allowed File Scope
- `app/services/metric_research_service.py`, `app/services/model_baseline_experiment_service.py`, `app/services/model_input_audit_service.py`, `app/services/player_role_baseline_service.py`, `app/services/plus_minus_derivation_service.py`, `app/services/analytics_snapshot_service.py`, `app/services/consistency_service.py`, `app/services/heat_index_service.py`, `app/services/streak_calculation_service.py`, and exact consumers/tests.
- Research fixtures or analysis scripts only when directly relevant to the named metric or model.

## Do Not Read
Do not read full canonical `docs/*.md` catalogs upfront. Locate only the relevant `docs/METRIC_CATALOG.md` or `docs/MODEL_FEATURE_PLAN.md` section with `rg -n`; open a source entry only if availability timing is in question.

## Research Contract
State the NBA question, grain, cutoff, source availability, formula/version, eligible season type, and missing-data meaning. Historical pregame features may use only information available strictly before the target-game cutoff. Exclude target-game and later outcomes; preserve unknown rather than substituting zero. Keep descriptive context separate from predictive claims.

For models, retain immutable feature/model versions and completeness evidence. Report temporal split, baseline, calibration or error, subgroup stability, and failure cases. Research does not authorize public prediction or betting claims, provider polling, or scheduled collection. State the evidence needed for promotion.

## Targeted Verification
For metric service edits, run `python -m compileall app` and `pytest tests/test_metric_research_service.py -q --tb=short`; for model changes use `pytest tests/test_model_input_audit_service.py tests/test_model_baseline_experiment_service.py -q --tb=short`. For research-only work, verify provenance and cutoff logic without an unrelated test run.
