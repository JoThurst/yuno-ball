# Program E SoS Research Gate — 2026-09-05

Status: research gate complete; rolling prior-opponent Strength of Schedule
remains unapproved for descriptive shadow use, persistence, routes, caches, or
production modeling.

## Scope and source boundary

This gate evaluates two separate descriptive questions:

1. Target-game Opponent Difficulty: how strong the opponent is at the target
   game's exact pregame cutoff.
2. Rolling prior-opponent Strength of Schedule: how strong the team's earlier
   opponents were over season-to-date and recent windows.

The source is the paired `team_game_feature_snapshots` plus complete
`game_environment_snapshots` cohort for the approved Program D seasons. The
legacy `team_daily_metrics.sos_*` fields are excluded because their season
aggregate can represent current endpoint state rather than the historical
cutoff. No rows were written.

## Coverage, pairing, and cutoff

| Season | Selected team rows | Complete team rows | Complete environments | Paired eligible games | Eligible team rows | Excluded complete rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-25 Regular Season | 2,460 | 2,160 | 1,075 | 1,075 | 2,150 | 10 |
| 2025-26 Regular Season | 2,460 | 2,160 | 1,075 | 1,075 | 2,150 | 10 |

The read-only audit found zero missing opponent perspectives, pair cutoff
mismatches, pair calculation-version mismatches, or cutoff failures. All six
candidate fields were non-null on all 2,150 eligible rows in each season:
target-opponent season/recent/delta net rating and team season/recent/delta
SoS. Preseason schedule rows were not included; the C7 and daily canonical
bridges remain Regular Season only.

## Raw-unit formula comparison

Correlations are descriptive retrospective relationships over team rows, not
causal or predictive estimates. The negative sign is directionally expected:
higher opponent-strength context corresponds to a more difficult game for the
team being evaluated.

| Candidate | 2024-25 W/L | 2024-25 margin | 2025-26 W/L | 2025-26 margin |
| --- | ---: | ---: | ---: | ---: |
| Target opponent recent net rating | -0.2533 | -0.2956 | -0.2564 | -0.2979 |
| Target opponent season net rating | -0.2715 | -0.3190 | -0.2888 | -0.3152 |
| Target opponent 60/40 recent-season blend | -0.2728 | -0.3191 | -0.2801 | -0.3182 |
| Team recent SoS | -0.0523 | -0.0628 | -0.0584 | -0.0731 |
| Team season SoS | -0.1458 | -0.1771 | -0.1566 | -0.1782 |
| Team 60/40 recent-season SoS blend | -0.0858 | -0.1035 | -0.0942 | -0.1124 |

Target-opponent season/recent net rating is the stronger game-level context.
Season and recent variants are directionally stable across seasons, but the
60/40 blend does not establish a cross-season improvement. Rolling SoS is
useful explanatory context about schedule history, not a replacement for the
target-opponent input and not a silently mixed composite.

## Pregame-safe scaling

The percentile study used the midrank empirical percentile over strictly
earlier same-season eligible rows and required at least 20 reference values.
The target game and all rows sharing its cutoff were held out until after
evaluation.

| Season | Target rows | Scaled rows | Withheld early-history rows | Target-opponent season raw/percentile order correlation | Team season SoS raw/percentile order correlation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024-25 | 2,150 | 2,130 (99.1%) | 20 | 0.9807 | 0.9534 |
| 2025-26 | 2,150 | 2,112 (98.2%) | 38 | 0.9789 | 0.9069 |

Percentiles stayed near a mean of 50 and preserved raw ordering closely. The
early-history rows were withheld intentionally; no missing reference pool was
converted to zero or a neutral percentile.

## Wording comparison

The read-only prototype rendered three styles from actual eligible rows:

- `raw_plus_percentile`: best for audit/detail because it leads with net-rating
  values and adds the earlier-same-season percentile.
- `percentile_first`: best candidate for a research explanation because the
  relative context is immediately scannable while raw values remain visible.
- `compact`: best for dense matchup cards; it retains raw values, keeps target
  opponent and prior SoS separate, and includes the non-predictive caveat.

All styles use neutral “opponent context” language and state that the result
is not a performance or outcome prediction. Wording is approved for continued
research only, not for a production consumer.

## Deterministic replay and decision

The coverage audit, raw-unit experiment, percentile experiment, and wording
renderings reported `writes_performed: false`. In-process replays of the audit
and percentile experiment returned exact dictionary equality for the same
database state. The pure percentile calculator and metric-service tests also
assert exact replay equality.

Decision: the SoS research gate passes for coverage, pairing, cutoff, raw-unit
comparison, scaling discipline, wording review, and replay safety. Rolling
prior-opponent SoS remains a non-persistent research context. The next action
is an explicit product/analytics approval decision; absent that approval, do
not add SoS fields to routes, caches, model features, or durable tables.
