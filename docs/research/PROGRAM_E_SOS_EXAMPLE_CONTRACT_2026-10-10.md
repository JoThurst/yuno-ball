# Program E SoS research example contract — 2026-10-10

Status: wording and examples approved for research review only. This contract
does not approve a public metric, Daily insight, model feature, durable SoS
record, or cache entry. The quantitative evidence and gate decision remain in
[`PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md`](PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md).

## Question and observation grain

An example describes **one team's pregame view of one scheduled Regular Season
game**. Preserve `(season, season_type, game_id, team_id, window_size,
feature_as_of, calculation_version)` and the paired opponent team ID. The
research comparison is one field at that grain; season-level counts and
correlations are summaries of those observations, not values for an individual
matchup. Keep both team perspectives of a game together in any retrospective
split or example review.

The two questions are separate:

| Question | Input at the target cutoff | Meaning |
| --- | --- | --- |
| Target-game Opponent Difficulty | Opponent perspective's `net_rtg_season` and `net_rtg_lastn` | Strength of the specific opponent before this game |
| Rolling prior-opponent SoS | Target team's `sos_net_season` and `sos_net_lastn` | Average strength of opponents faced **before** this game over the season-to-date and recent windows |

Both are in net-rating units (points per 100 estimated possessions). Higher
values mean stronger opposition. `*_delta` is recent minus season; it is an
audit candidate, not an approved headline score. The 60% recent / 40% season
blend was a sensitivity comparison only. Do not combine target-opponent
strength and prior-opponent SoS into one number.

## Eligible inputs and cutoff

Use the approved Program D `team_game_feature_snapshots` and matching complete
`game_environment_snapshots` for the bounded 2024-25 and 2025-26 Regular
Seasons. Select a complete team snapshot per `(game_id, team_id)` at the
reviewed cutoff. Require exactly two reciprocal team perspectives, a complete
environment, the same `feature_as_of` and `calculation_version` for both teams,
`feature_as_of < scheduled_tipoff`, and `data_available_at <= feature_as_of`.
Missing timing or pair evidence withholds the example. The source history must
contain only prior games; the target game's score, box score, result, and
postgame aggregates cannot enter either input. Legacy `team_daily_metrics.sos_*`
is not a historical pregame source because its season aggregate can reflect
the endpoint's later state.

For percentile examples, compare each raw field with **only strictly earlier
same-season eligible observations of that same field**. Hold out the target
game and every observation sharing its cutoff until all rows at that cutoff
have been evaluated. Use the tie-aware midrank empirical percentile and at
least 20 reference values. An insufficient pool, missing value, or nonfinite
value is withheld; never impute zero or a neutral 50th percentile. A percentile
is relative to the prior reference pool, so the raw net-rating value remains
visible for interpretation and audit.

## Approved research wording

Examples may use the existing `raw_plus_percentile`, `percentile_first`, or
`compact` prototype styles. Label the two concepts distinctly, retain the
raw season and recent values, and say that higher values mean stronger
opposition. `percentile_first` is the preferred research explanation when the
reference pool is sufficient; `raw_plus_percentile` is useful for audit detail,
and `compact` for a dense research card. All three require a plain caveat:
the numbers describe pregame opponent and prior-schedule context, **not** a
prediction of performance, score, or win probability. Do not call a percentile
an absolute difficulty score or infer causality from retrospective correlation.

If any required raw field, pair, timing fact, or percentile is unavailable,
show an explicit withheld/incomplete state with the reason. Do not quietly
render a partial example as complete. No production placement is implied by
the approval of wording.

## Evidence packet for each reviewed example

Record enough to reproduce the exact example from the same source state:

1. Season/type, game and both team IDs, game date, scheduled tipoff, selected
   `window_size`, `feature_as_of`, `calculation_version`, completeness status,
   `data_available_at`, and source run/provenance for both snapshots and the
   environment.
2. The four raw season/recent fields, their source perspective, net-rating
   units, missing-input list, and proof that the reciprocal pair and cutoff
   checks passed. Keep the target-game result separate and use it only in a
   labeled retrospective evaluation.
3. For each displayed percentile: field name, target raw value, reference
   season and cutoff rule, reference count, tie-aware percentile, and withheld
   reason when the 20-value minimum is unmet. Include the rendering style,
   exact text, caveat, and research contract version.
4. The bounded query parameters, row counts and exclusions, read-only/no-write
   declaration, and exact replay output or deterministic fixture proof. Report
   missingness, pair mismatches, cutoff failures, and any drift before citing
   the 2026-09-05 coverage or correlation findings in a new cohort.

The existing read-only audit, formula comparison, scaling experiment, and
wording prototype scripts provide the research path. The 2026-09-05 gate
recorded 2,150 eligible team rows per season, exact same-state replay, and
no writes; those are historical results for that bounded cohort, not a
guarantee for future seasons. A separate product and analytics approval with
fresh evidence is required before persistence, routes, caches, model use, or
default Daily presentation.
