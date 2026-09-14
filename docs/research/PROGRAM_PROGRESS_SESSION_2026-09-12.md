# Yuno Ball program progress session — 2026-09-12

Status: historical evidence record. For current cross-program state and next
gates, use [`docs/PROJECT_STATUS.md`](../PROJECT_STATUS.md) and the [master
roadmap](../roadmaps/MASTER_ANALYTICS_ROADMAP.md).

## Review checkpoint

This session started with the prior Daily Intelligence V1 package, the G0
model-input audit, and the G1 naive historical baseline already present in the
working tree. The work below is additive and read-only at the data/model
boundary. No commits, resets, broad cleanup, prediction writes, or production
prediction routes were performed.

## Completed this session

### 1. Design refinement: mockups 1 and 3

- Editorial Magazine now has a `Use dark mode` toggle with a restrained
  charcoal/parchment palette and a reversible `Use light mode` state.
- Cinematic Game Night now has a `Deep night mode` toggle that lowers glow and
  saturation while preserving the neon direction, with a reversible return to
  neon state.
- Both toggles were opened and exercised in the local browser preview.
- Corrected the Daily V1 current/blocked empty-state copy so it no longer calls
  an empty package “healthy”; freshness and source health remain explicit.

Files:

- `docs/research/design_lab_mockups/editorial-magazine.html`
- `docs/research/design_lab_mockups/cinematic-game-night.html`
- `app/templates/design/daily_v1_lab.html`

### 2. Program G2: Elo comparison baseline

Added an audit-gated, read-only online Elo baseline:

- starts teams at 1500;
- uses a fixed 65-point home advantage and K-factor 20;
- updates ratings only after the observed result;
- evaluates the same three chronological blocks as G1;
- blocks missing team identity instead of collapsing teams together;
- never persists predictions.

Files:

- `app/services/model_baseline_experiment_service.py`
- `scripts/run_program_g_baseline.py`
- `tests/test_model_baseline_experiment_service.py`

The runner now calls the G0 audit first. A blocked or integrity-failing season
returns without running model metrics.

### 3. Program G3: cumulative feature-family ablation

Added a small train-only standardized logistic experiment for:

1. strength;
2. strength plus form;
3. strength plus form plus schedule;
4. the preceding families plus the supported pace interaction.

The current snapshot grain supports pace as the style interaction. Broader
mixed-unit style aggregation was intentionally not introduced. Missing family
inputs are withheld and counted rather than zero-filled.

## Evidence captured

The historical runs used a 50-game warmup and three chronological test blocks
with 1,025 test games per approved season.

| Season | Naive home-win log loss / Brier | Elo home-win log loss / Brier |
|---|---:|---:|
| 2024-25 | 0.7062 / 0.2560 | 0.6272 / 0.2190 |
| 2025-26 | 0.6901 / 0.2485 | 0.6171 / 0.2143 |

The Elo baseline improves the comparison floor in both seasons. This is a
research checkpoint, not a production approval: calibration, stability,
feature ablations, immutable prediction storage, monitoring, and user-facing
limitations still remain.

The cumulative ablation scored all 1,025 test games in both seasons. Home-win
log loss by variant:

| Season | Strength | + Form | + Schedule | + Pace interaction |
|---|---:|---:|---:|---:|
| 2024-25 | 0.6284 | 0.6258 | 0.6223 | 0.6265 |
| 2025-26 | 0.6353 | 0.6381 | 0.6416 | 0.6374 |

The ablation is directional evidence only. It does not authorize a selected
production model; the next review is calibration and stability across the
same chronological windows.

### 4. Program G4: calibration and stability reporting

Added reliability-bin output with expected calibration error (ECE), maximum
calibration error (MCE), and explicit chronological block ranges. The check
confirmed that lower loss is not sufficient for model approval: the Elo model
has materially worse 2025-26 calibration than its 2024-25 behavior, and the
schedule ablation is more unstable across blocks.

Key evidence:

- Elo 2025-26: ECE 0.0671, MCE 0.2216, block log-loss range 0.1505.
- Strength + form + schedule, 2024-25: ECE 0.0577, MCE 0.1716, range 0.0802.
- Strength + form + schedule, 2025-26: ECE 0.0684, MCE 0.2323, range 0.2064.

Production prediction publication remains blocked pending calibration repair,
cross-season stability, immutable storage, and monitoring.

### 5. Continuation pass: delegated review and gate hardening

Two low-cost sidecars were delegated on disjoint scopes:

- The live transport sidecar added
  `tests/test_live_boxscore_starter_adapter.py`, covering proxy rotation after
  a failed transport request, endpoint failure/success marking, and proxy
  configuration on both attempts. It passed 6 tests.
- The Program G sidecar produced
  `docs/research/PROGRAM_G_REVIEW_2026-09-12.md`. Its two high-risk findings
  were integrated: required feature completeness is now an explicit audit
  blocker, and the runner independently rechecks cutoff/source/target-field
  invariants plus environment-tipoff alignment. Null timestamp revision
  selection is deterministic and covered by a regression test.

### 6. Program G5: train-only calibration repair

Added a Platt-style calibration transform around Elo. It is fit only from
historical predictions before each test block and never from the test block's
outcomes. Results were mixed:

- 2024-25: calibrated log loss 0.6318 vs raw 0.6272; ECE 0.0577 vs 0.0528.
- 2025-26: calibrated log loss 0.6129 vs raw 0.6171; ECE 0.0340 vs 0.0671.

This is an improvement in procedure, not production approval. A dedicated
train/calibration/test split, held-out season evaluation, and minimum-bin
confidence rule remain open.

### 7. Program G6: dedicated split and season-held-out validation

Added `scripts/run_program_g_heldout_validation.py` and the corresponding
service gate. Each source season is split chronologically into 60% train, 20%
calibration, and 20% source-test; Platt calibration is fit only on the
calibration window and frozen for the source-test and opposite-season tests.
The held-out runner completed in both directions with 1,075 games per season,
645 train games, 215 calibration games, and 215 source-test games. Source-test
calibration improved in both directions. Opposite-season performance was mixed:
2024-25 → 2025-26 improved log loss from 0.6148 to 0.6130 but ECE moved from
0.0410 to 0.0421; 2025-26 → 2024-25 worsened log loss from 0.6259 to 0.6337
and ECE from 0.0472 to 0.0741. This is a completed evaluation procedure, not
production approval.

### 8. Daily V1 wording refinement

The current/blocked design-lab empty state no longer says “The package is
healthy.” It now says that no current game context is available and freshness
and source health remain explicit rather than assumed. A regression assertion
guards the language.

The 2026-27 run returned:

- `blocked_no_completed_game_evidence`;
- zero eligible games;
- zero writes.

That gate remains correct until completed-game evidence exists after the
preseason boundary.

### 9. Daily launch, season bridge, and odds pilot

The public `/daily/` route now renders the typed Daily Intelligence V1
contract rather than the legacy betting template. The launch surface includes
date navigation, ranked context cards, deterministic readouts, freshness and
source evidence, explicit empty/partial states, and a dark public visual
system. `/daily/betting` remains available as a compatibility view while the
new surface becomes the canonical product entry point.

The 2026-27 completed-game bridge is wired through the existing daily
orchestration path. Its publication and C5 reconciliation now share one
database transaction, so a failed reconciliation rolls back the batch instead
of leaving partially published canonical facts. A real quiet-day proof on
2026-09-12 returned `no_op` with zero pending games, zero blocked games, zero
eligible completed games, and zero writes. A completed-game smoke proof is
intentionally deferred until the preseason boundary produces eligible
evidence.

The narrow odds observation pilot is append-only and observation-only. Daily
can display the latest complete market pair by sportsbook and market type with
provider/retrieval timestamps and provenance; it does not calculate an edge,
recommend a wager, or treat missing coverage as a signal. The bounded live
probe on 2026-09-12 encountered the known upstream NBA endpoint redirect loop,
so no observations were persisted and the collector remains fail-closed until
the transport/source path is healthy.

### 10. Historical launch destinations

Completed the historical portion of the Daily launch slice. The public surface
now has a bounded read-only `/daily/archive` index sourced from durable Regular
Season schedule rows, a canonical `/daily/YYYY-MM-DD` date page, and a
canonical `/matchup/YYYY-MM-DD/AWAY-HOME` matchup page. Historical matchup
pages resolve back to the same Daily V1 package, filter date-scoped insights,
and preserve cutoff/freshness/provenance language. The existing query-string
date form remains compatible, but canonical links and navigation now point to
the permanent destinations.

The slice intentionally does not include team-season archives, prediction
history, or postgame reviews; those remain later distribution and modeling
outputs rather than launch blockers.

### 11. Program G7 uncertainty-aware calibration monitoring

Calibration reliability bins now expose two-sided 95% Wilson intervals,
`meets_minimum_bin_count`, and a monitoring summary using a 25-game minimum.
ECE and MCE point estimates are unchanged. The new metadata makes the thin
tail bins visible in both held-out directions rather than treating them as
stable evidence. Focused coverage passed with 9 tests, and both read-only
season directions completed with 1,075 held-out games and zero writes.

The result remains a research gate: 2024-25 → 2025-26 improved held-out log
loss from 0.6148 to 0.6130, while the reverse direction worsened from 0.6259
to 0.6337. Calibration monitoring is stronger, but prediction publication is
still blocked pending broader windows, feature-family review, and immutable
consumer gates.

### 12. Program G8 chronological window sweep

Added `run_season_heldout_window_sweep` and the read-only
`scripts/run_program_g_window_sweep.py` runner. The sweep evaluates 50/25/25,
60/20/20, and 70/15/15 chronological splits with the same frozen calibration,
private Elo, Wilson interval, thin-bin, and zero-write contracts. All windows
completed in both directions. The 2024-25 → 2025-26 held-out result improved
in two windows and worsened in one; the 2025-26 → 2024-25 held-out result
worsened in all three. This clears the cross-window procedure gate but does
not support production calibration selection.

### 13. Program G9 probability-band subgroup stability

Added descriptive probability bands to every G win-probability report:
low-confidence, competitive, and high-confidence. Each band reports coverage,
log loss, Brier score, Wilson-aware calibration, and thin-bin monitoring. The
60/20/20 held-out evidence covered 188/476/411 games in the 2024-25 → 2025-26
direction and 275/402/398 in reverse. The competitive band is the largest;
the reverse high-confidence band has weaker calibration. This clears subgroup
reporting, not prediction publication.

The next bounded slice is explicit feature-family availability and subgroup
acceptance thresholds on the same effective population.

### 15. Program G11 review-ready feature comparison

Added the cross-season `compare_review_ready_feature_variants` contract and
read-only `scripts/run_program_g_feature_review.py` runner. It compares only
variants that clear 95% feature coverage and 100-game probability-band gates in
every supplied season. The common candidate set is Strength + Form + Schedule
and Strength + Form + Pace Interaction. Their cross-season log-loss ranges are
0.0193 and 0.0109 respectively; the simpler variants are excluded because of
thin 2024-25 low-confidence bands. This is research comparison evidence, not
production model selection.

### 14. Program G10 feature-family availability and acceptance review

Feature-family ablations now report effective-population coverage against a 95%
threshold and subgroup review status against a 100-game-per-band threshold.
All four variants scored 1,025/1,025 test games in both approved seasons with
100% coverage and zero withheld inputs. In 2024-25, the strength and
strength+form variants are blocked for thin low-confidence bands (92 and 88
games); schedule-inclusive variants clear the threshold. All 2025-26 variants
are review-ready. This formalizes the review contract without approving a
production feature family.

### 16. Program G12 candidate stability review

G12 ran against the two G11 candidates only, using four chronological segments
per approved season. Both candidates had 100% test coverage in every season.
Strength and form coefficients stayed positive across all fits. Schedule was
not directionally stable; the pace/matchup interaction was also not stable
across seasons. The review therefore passes data availability and chronological
scoring but holds the feature-direction gate. Added the read-only stability
service, focused regression coverage, runner, and decision record. Next is a
narrower signed schedule-feature experiment, followed by the same G12 review.

### 17. Program G13 schedule-definition sensitivity sweep

Ran four explicit home-perspective schedule definitions against both G11
candidates across four chronological blocks in each approved season. Every
run retained 100% test coverage. Raw, clipped, signed, and home-rest-deficit
definitions all left schedule directionally unstable; the pace/matchup variant
also left the interaction unstable. Added the in-memory sweep service, runner,
focused coverage, and decision record. Next is component-level schedule
pressure research: back-to-back, 3-in-4, 4-in-6, and rest asymmetry evaluated
independently before any composite is reconsidered.

### 18. Program G14/G15 schedule component review

Decomposed the existing schedule fields into B2B, 3-in-4, 4-in-5, 5-in-7,
rest-asymmetry, and a combined component variant. B2B, 4-in-5, and 5-in-7
passed four-block directional stability and cross-season comparison. The
remaining components were held for sign instability or poor combined behavior.
All runs retained 100% coverage. Added custom feature-variant support, the
component sweep, runner, tests, and review record.

### 19. Program G16 frozen cross-season feature holdout

Froze each G15 component fit on one approved season and tested the opposite
season, including a strength-plus-form control. B2B, 4-in-5, and 5-in-7 all
scored 1,075/1,075 games in both directions. None beat the control in both
directions: B2B had the best two-direction mean, while 5-in-7 improved only the
forward direction. The data gate passed, but incremental schedule lift did not.
Schedule remains descriptive-only; the next product-facing lane is Program H.

### 20. Program H0 availability and rotation input audit

Ran the read-only rotation/availability audit for both approved seasons. 2024-25
has 32,515 player facts, 390 known starter/bench rows, and 39 complete starter
evidence games. 2025-26 has 32,179 player facts but no known starter/bench rows
and six completed team slates without pregame availability coverage. Neither
season has a durable lineup/rotation table or expected pregame minutes field.
The Daily product can keep showing provenance-aware uncertainty; exact Rotation
Shock remains blocked. Focused availability, starter, player-fact, and model
regressions passed 30 tests.

## Verification

- Focused Daily, historical route, bridge, ingestion, and odds pilot tests:
  final result `48 passed`, including the public route contract, archive and
  matchup destinations, latest-observation projection, transaction rollback,
  complete-pair enforcement, and fail-closed collector tests.
- `python -m compileall -q app`: passed.
- The dedicated held-out runner completed 2024-25 → 2025-26 and 2025-26 →
  2024-25 with `writes_performed: false` in both directions.
- The real 2026-27 quiet-day bridge proof returned `no_op` with zero writes.
- The bounded odds dry-run stopped on the upstream redirect loop; no live
  observation was claimed or published.
- Program G7 calibration monitoring: focused service tests `9 passed`; both
  held-out directions returned `complete` with `writes_performed: false` and
  Wilson interval/thin-bin metadata.
- Program G8 window sweep: focused service tests `10 passed`; all three windows
  completed in both held-out directions with `writes_performed: false`.
- Program G9 subgroup stability: focused service tests `11 passed`; probability
  bands covered all held-out rows in both directions with `writes_performed: false`.
- Program G10 feature-family review: focused service tests `12 passed`; both
  approved seasons had 100% feature coverage and zero withheld inputs.
- Program G12 stability review: focused service tests `15 passed`; both G11
  candidates completed four chronological blocks per approved season with
  100% coverage, while the feature-direction gate held on schedule instability.
- Program G13 schedule sweep: focused service tests `16 passed`; all four
  schedule definitions completed for both candidates with 100% coverage, but
  none cleared feature-direction stability.
- Program G14/G15 schedule components: focused service tests `17 passed`; B2B,
  4-in-5, and 5-in-7 cleared directional stability and comparison gates.
- Program G16 frozen feature holdout: focused service tests `18 passed`; all
  candidates and the control scored 1,075 games in both directions, but no
  schedule component beat the control in both directions.
- Program H0 availability/rotation audit: read-only audits completed for both
  approved seasons; focused availability/starter/player-fact/model regressions
  passed `30 tests`; writes remained false.
- Historical launch route tests cover the archive index, canonical date page,
  matchup rendering, Eastern-date grouping, and invalid matchup slugs.
- Read-only live render proof returned `200` for `/daily/archive`,
  `/daily/2025-04-12`, and `/matchup/2025-04-12/ORL-ATL`; the archive resolved
  162 historical 2024-25 dates and the matchup resolved game `0022401186`.
- Local browser verification of both dark-mode controls: passed.
- `git diff --check`: passed; only existing LF/CRLF normalization warnings were
  reported.

## Next checkpoint

The next launch checkpoint is a real completed-game 2026-27 smoke run after the
preseason boundary, plus a healthy odds transport or approved alternate source
for the observation pilot. In parallel, continue the bounded G monitoring and
ablation contract with explicitly contracted feature families and subgroup
acceptance thresholds on the same effective population. Keep prediction
publication blocked until those checks and immutable-storage consumer gates are
evidenced.

## Working-tree note

The repository was intentionally dirty at session start. Existing Daily V1,
Program E, ingestion, and route changes were preserved. Review the targeted
files above together with the roadmap section in
`docs/roadmaps/MASTER_ANALYTICS_ROADMAP.md`.
