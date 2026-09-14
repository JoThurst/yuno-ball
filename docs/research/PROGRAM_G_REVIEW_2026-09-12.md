# Program G implementation review

Date: 2026-09-12  
Scope: read-only review of the current G0 input audit, G1 naive baselines, G2 Elo baseline, G3 feature ablation, G4 calibration/stability payloads, and G6 held-out validation.  
Constraint: this sidecar made no changes to `app/services` or `scripts`.

## Overall assessment

The chronological evaluation loop is directionally sound: rows are sorted by
`scheduled_tipoff`, the current test outcome is appended only after a
prediction, Elo updates occur after observation, and the experiment payloads
declare `writes_performed: false`. The production gate should remain closed.
The follow-up hardening in this session addressed the two high-risk selection
and gating findings and added a train-only Platt calibration procedure.

## Findings

### High — audit status can be `ready` despite missing required feature values — addressed

Evidence: the audit now calculates missing feature counts and includes missing
required values in the `blocked_missing_required_features` decision. The
runner consumes that status before constructing baseline rows.

Why it matters: a historical run can pass G0 while the constructed game rows
contain null family inputs. The ablation withholds some rows, but the gate does
not clearly distinguish a complete baseline dataset from a partially observed
one. This weakens reproducibility and can make season comparisons use different
effective samples.

Resolution: `required_feature_missing` and
`required_feature_missing_rows` are now returned by the audit, missing required
fields produce `blocked_missing_required_features`, and a regression test
asserts the gate.

### High — the runner does not re-check all audit invariants while building games — addressed

Evidence: `scripts/run_program_g_baseline.py` selects the latest snapshot by
`(game_id, team_id)`, requires an environment row and two outcome rows, and
now independently verifies `feature_as_of < scheduled_tipoff`,
`data_available_at <= feature_as_of`, prior-source-date semantics, forbidden
target fields, and environment-tipoff alignment.

Why it matters: the audit and materialization steps are separate, so a future
refactor could change selection or introduce a different snapshot without the
experiment detecting the violation. The model would then be able to score a
row that the gate did not actually validate.

Resolution: the runner now shares deterministic latest-row selection with the
audit and independently fails closed on timestamp, source-date, forbidden
target-field, and environment-tipoff mismatches.

### Medium — latest-row selection is not robust to missing `feature_as_of` — addressed

Evidence: both `model_input_audit_service.py:68-75` and
`run_program_g_baseline.py:38-45` compare `feature_as_of` values directly.
The audit later counts missing timestamps, but selection happens first.

Why it matters: a null timestamp can raise during sorting/selection or cause
non-deterministic selection depending on ORM ordering, preventing the intended
blocked state from being emitted.

Resolution: non-null timestamps now win deterministically over null revisions,
while missing timestamps remain visible as integrity violations. A regression
test covers a null revision.

### Medium — the ablation is not a complete implementation of the written plan

Evidence: `MODEL_BASELINE_EXPERIMENT_PLAN.md:131-142` specifies cumulative and
leave-one-family-out ablations through availability. The implementation at
`model_baseline_experiment_service.py:419-423` evaluates only four cumulative
variants and uses a pace proxy for matchup context; availability and
leave-one-out tests are absent.

Why it matters: the current results support feature-direction exploration, not
the broader model-selection claim implied by the plan or a production gate.

Smallest next step: rename the artifact explicitly as a partial ablation, then
add the remaining variants only after their feature contracts and missingness
policy are defined. Do not compare variants across different effective test
populations without reporting that limitation.

### Medium — calibration output needs held-out evidence — partially addressed

Evidence: `_calibration` reports ECE/MCE and the runner now adds a dedicated
chronological train/calibration/source-test split plus a frozen Platt repair
around Elo. The standalone held-out runner evaluates the entire opposite
season in both directions. The written plan still calls for isotonic
calibration when sample size supports it and interval-aware monitoring.

Why it matters: ECE/MCE can document miscalibration, but cannot establish that
a repaired probability is calibrated or safe for publication. Ten equal-width
bins can also be sparse, so the values should not be treated as stable gates
without confidence intervals or minimum bin counts.

Remaining step: keep current repaired values research-only; add broader
season/window evidence and minimum-bin or interval-aware monitoring before
changing the production gate. The new procedure uses a 100-game minimum
calibration window and remains no-write.

### Low — metric coverage is narrower than the plan

Evidence: the plan requires ROC AUC and breakdowns by team, month, rest bucket,
missing-input state, availability uncertainty, and early/mature season at
`MODEL_BASELINE_EXPERIMENT_PLAN.md:102-129`. The current payload reports log
loss, Brier, MAE/RMSE, calibration bins, and block ranges only.

Why it matters: aggregate block metrics can hide subgroup failure and do not
yet support the planned operational review.

Smallest next step: add only the breakdowns needed for the next gate, with
sample counts and explicit withheld-row denominators; defer UI exposure.

## Gate recommendation

Keep prediction publication blocked. G1/G2/G3 and the G6 procedure are useful
research evidence, but the current implementation should not be promoted:
held-out calibration improved one direction and regressed the other, broader
planned ablations are not yet contracted, and subgroup monitoring evidence is
still absent.
