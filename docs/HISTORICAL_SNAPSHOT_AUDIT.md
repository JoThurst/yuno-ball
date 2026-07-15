# Historical Snapshot and Ingestion Audit

Status: audit, Phase 1, and the additive Phase 2 schema migration completed 2026-07-15; the database is at `k1l2m3n4o5p6` with no Alembic drift. A local 2025-26 Phase 2 backfill has been run, but cutoffs after 2026-03-03 must be republished after bounded schedule-result reconciliation because their original schedule results were null. Phases 3-5 remain unapproved for production execution.

This document records the code-and-schema audit requested in the historical analytics architecture directive. The repository and the sanitized live profile in `DATABASE_PROFILE.md` are the evidence base. Planning documents are not treated as proof that a feature exists.

## Confirmed starting point

- Repository: `C:\Code\sports_analytics`
- Branch: `sqlalchemy_migration`
- Audited commit: `a2a9c1114cd2841baea449238e25311f82a84603`
- Alembic graph: one head, `h8i9j0k1l2m3`; the generated database profile reports the live database at that revision on 2026-07-15.
- Worktree: already dirty before this work. Existing edits and untracked documentation are user-owned and must not be discarded.
- Production backfill: not authorized and not run.

## Findings by durable grain

| Table or domain | Current grain | Current write behavior | History lost or unsafe | Current consumers | Proposed durable grain | Migration approach |
|---|---|---|---|---|---|---|
| `gamelogs` | player, game, team, season | upsert corrects the current source row | Prior corrected values are not versioned; no explicit source availability time | player calculations, player pages | retain source fact grain; add a separate append-only raw/source-observation layer if correction history is required | no destructive rewrite; add observation table later |
| `team_game_stats` | game, team | upsert corrects the current box score | Prior corrected values are not versioned; 2023-24 is incomplete | team metrics, matchup calculations | retain source fact grain; optional append-only raw observation by source run | repair coverage separately; do not synthesize missing opponent rows |
| `game_schedule` | game, team | upsert schedule/status rows | Schedule changes overwrite prior operational state | slate and schedule factors | current operational row plus optional schedule observations keyed by observed-at/run | preserve current table; add observations only if change history becomes a product need |
| `roster` | team, player, stored season | the fetcher clears an entire team's roster before inserting the current response | All older roster seasons for that team can be deleted; live rows use bare `2025` while other tables use `2025-26` | slate player selection, roster coverage validation | team, player, canonical season, source observation/effective interval when known | first stop cross-season deletes and normalize canonical season; do not invent effective dates |
| `league_dash_team_stats` | team, season, season type | endpoint aggregates are overwritten in place across 772 columns | Historical endpoint state is unavailable and unsafe for historical pregame reconstruction | team metrics, team pages | keep as latest operational aggregate; add either raw observations by observed-at/run or curated metrics by feature cutoff | do not copy all 772 columns into a new curated table blindly |
| `leaguedashplayerstats` | player, season | endpoint aggregate overwritten in place | Historical endpoint state unavailable | player pages and services | latest operational aggregate plus optional raw observations | defer until a concrete historical consumer exists |
| `player_streaks` | legacy player/stat/threshold/season | fetcher contains an all-table delete path | All history can be erased; legacy overlap with enhanced tables | scripts and legacy consumers | retire only after consumers are migrated | no first-phase drop |
| `player_consecutive_streaks` | player, stat, threshold, season, streak kind | whole season deleted, then recalculated from all stored season logs | Only the latest season snapshot survives; failures after delete can leave the table empty | slate, reports | player, stat, threshold, season, season type, feature-as-of, calculation version, streak kind | create v2 append-only snapshot table; validated merge in one transaction |
| `player_stat_windows` | player, stat, threshold, season, window | whole season deleted, then recalculated | Latest snapshot only; missing game dates are silently replaced with today's date | slate, reports | player, stat, threshold, season, season type, window, feature-as-of, calculation version | create v2; missing event dates remain missing and affect completeness |
| `player_heat_index` | player, stat, season, window | whole season deleted, then recalculated | Latest snapshot only | slate, reports | player, stat, season, season type, window, feature-as-of, calculation version | create v2; strict pre-cutoff input filter |
| `player_consistency` | player, season, stat, window | whole season deleted, then recalculated | Latest snapshot only; combined PRA replaces missing component stats with zero | slate, player profile | player, stat, season, season type, window, feature-as-of, calculation version | create v2; explicit component-missing rules and completeness |
| `player_z_scores` | player | overwrite by player; no season/cutoff/version | All earlier values lost; creator has a hard-coded default season and calls the provider directly | legacy analytics | player, stat, season, window, feature-as-of, calculation version | replace with the shared player snapshot contract; do not extend current table in place |
| `team_daily_metrics` | stat date, team, window | upsert same date, otherwise append | `stat_date` looks historical but calculations use all available team games and the current league endpoint; historical rows can contain future knowledge | slate, reports, flags, environment | team, season, season type, window, feature-as-of, calculation version | v2 curated snapshots; inputs must be bounded by cutoff |
| `team_daily_flags` | stat date, team, flag type | upsert same date from team metrics | Inherits metric leakage and lacks version/completeness | slate, reports | team, season, season type, flag type, feature-as-of, calculation version | v2 derived from one pinned metrics snapshot |
| `game_environment_daily` | game, game date | upsert game/date | selects the latest team metric with no `<= game_date/cutoff` condition, so historical games can use future metrics | slate | game, season, feature-as-of, calculation version, metric snapshot references | v2 or additive columns only after team snapshots exist |
| `team_schedule_factors` | game, team | whole season delete/rebuild, although the natural grain is stable | unnecessary failure window; source schedule changes overwrite the same row | slate, reports | game, team, schedule-source version; feature-as-of only if used as a historical publication snapshot | replace season delete with validated natural-key upsert; retain source-derived semantics |
| `game_odds` | game, sportsbook | current bookmaker row overwritten | line movement history lost despite `recorded_at`; only `updated_at` changes | slate/betting page | game, sportsbook, market, observed-at/source run | keep latest table for serving and add append-only observations before historical betting analysis |
| `player_game_status` | game, player | current status overwritten | intraday status changes are lost | slate | game, player, observed-at/source run | keep latest serving row plus append-only observations when needed |

## Confirmed leakage and freshness defects

1. Player streak, window, heat, and consistency services delete the current season before rebuilding it. Their rows have no calculation cutoff or version.
2. Player calculations use every stored game for the season. They cannot reproduce what was known before a historical game.
3. `team_daily_metrics.stat_date` is a label, not an enforced data cutoff. Recent games and current endpoint aggregates are not filtered to `<= stat_date`.
4. `game_environment_service` chooses the newest team metric row without constraining it to the requested game date.
5. `slate_service` chooses the newest team metrics and flags for a season without constraining them to the requested slate date. Historical slate pages can therefore move forward in time.
6. Missing streak/window game dates fall back to `date.today()`, which converts missingness into a false event date.
7. The current season helper uses an October calendar boundary only. It has no validation, season transition operations, schedule-aware offseason policy, or distinction between display and ingestion seasons.
8. Daily orchestration has no durable run record or lock. `daily_calculate.py` does not return a non-zero exit status when calculation tasks fail, and the file marker is not a reliable publication record.
9. Alembic's environment imports only part of the ORM catalog, so `alembic check` cannot be trusted until model registration is complete.

## Live data eligibility for backfill

The 2026-07-15 profile supports a bounded eligibility decision, not a production backfill:

| Input | Profile coverage | Eligibility |
|---|---|---|
| `game_schedule` | 2016-17 through 2025-26; paired rows pass | eligible as the event calendar after checking postponed/cancelled semantics |
| `gamelogs` | 2020-21 through 2025-26 | candidate source for player snapshots from 2020-21 forward |
| `team_game_stats` | partial 2023-24 (241 singleton rows), full-looking 2024-25 and 2025-26 | 2023-24 is ineligible; later seasons require bounded paired-row validation before use |
| `league_dash_team_stats` | 46 rows per season for 2023-24 through 2025-26 | latest-state aggregates only; ineligible for historical pregame reconstruction |
| current player derived tables | only 2025-26 snapshots | ineligible as historical training features |
| roster | current rows stored under bare `2025` | ineligible for historical effective-date reconstruction |

No missing values may be converted to basketball zero during a backfill. A snapshot is publishable only after row-grain, uniqueness, cutoff, paired-game, null-rate, and source-completeness checks pass.

## Delivery phases

### Phase 0 — audit and contract

This document and ADR 0001 define the grain, publication, and correction contract. No production data changes are included.

### Phase 1 — season context and ingestion observability

Implemented in code: canonical season parsing and transition helpers, schedule-aware selection boundaries, durable run/task records, a single-run lock, truthful calculation exit codes, atomic success-marker publication, and structured freshness/completeness metadata. This phase is additive and independently deployable after migration `i9j0k1l2m3n4` is applied.

### Phase 2 — player analytical snapshots

Implemented in code: four typed v2 snapshot tables, one atomic publisher, shared
`feature_as_of <= requested_cutoff` readers pinned to one anchor cutoff, Daily and
text-report compatibility reads, provenance/completeness metadata, and a bounded
backfill command. The canonical cutoff is 10:00 ET on a relevant slate date;
source games must have a local NBA date strictly before the target date. Legacy
tables remain readable and are still written as operational latest-state
projections during the expand/migrate period.

### Phase 3 — team and game analytical snapshots

Create versioned team metrics/flags and game environment snapshots. Do not use current league endpoint aggregates to reconstruct historical dates. Replace the schedule-factor delete/rebuild with a validated merge.

### Phase 4 — roster and source corrections

Stop all-season roster deletion, normalize canonical season values, and design explicit raw observations for corrected boxes, odds, schedule state, and player status where product value justifies them.

### Phase 5 — backfill operations

Prepare dry-run, bounded date/season, resume, and calculation-version commands. Run against a disposable database first. A production backfill requires an explicit approval, backup/restore test, row-count forecast, and rollback plan.

## Prepared backfill command contract

The future command surface should be explicit and resumable:

```text
python scripts/backfill_player_snapshots.py --season 2024-25 --from-date 2024-10-22 --to-date 2024-11-05 --calculation-version player-v2.1 --dry-run
python scripts/backfill_player_snapshots.py --season 2024-25 --from-date 2024-10-22 --to-date 2024-11-05 --calculation-version player-v2.1 --resume-after 2024-10-28 --apply
```

The command is implemented with a required `--dry-run` or `--apply` mode and a
default maximum of 31 scheduled slate dates. It does not infer an unbounded range.
No production backfill has been authorized or run.
