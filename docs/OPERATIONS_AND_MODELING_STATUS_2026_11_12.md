# Local operations and modeling checkpoint — November 12, 2026

This is local evidence, not a production release or a public prediction claim.

## Checkout ownership

| Purpose | Checkout / branch | Rule |
| --- | --- | --- |
| Scheduled collection | Existing `C:\Code\sports_analytics`, `ops/local-ingestion` | Only verified, committed releases; approve the exact SHA locally |
| Preserved experiments | Managed `preserved-player-reader` worktree, `codex/preserved-player-reader` | Original player-reader code, tests, documents, and a copy of the original dirty tracked files were preserved with matching SHA-256 hashes |
| New development | Separate worktree based on the reviewed integration candidate | Never edit the scheduled checkout while developing |

The scheduler paths, existing database, archive, and services were retained.
The controller checks approved branch/SHA, tracked cleanliness, and untracked
application/collector code before database access. Approval and runtime status
live outside Git under the existing operations directory. See
[the ingestion runbook](INGESTION_RUNBOOK.md#personal-pc-scheduling).

The operations branch consolidates the previously running commits, the injury
date/DST/retry fixes, the existing PR test workflow, and the existing unresolved
opening-game failure gate. Remote `main` was 21 commits behind the original
running HEAD at the start of this checkpoint. Consolidating a local candidate
does not mean remote main has been merged or deployed.

## Repository boundary decision

Keep one repository for now. Collection owns source access and durable writes;
web requests read persisted data; modeling uses versioned pregame inputs. Run
and deploy these entry points independently. A separate repository is not needed
to isolate processes, release versions, credentials, or schedules. Reconsider
only when independent ownership or incompatible release requirements justify
the additional versioning and shared-contract maintenance.

## Collection recovery and transport

The November 12 identity-only repair matched 334 player observations and 317
team submission records; a replay wrote zero rows. The normal collection cycle
then passed at 19:11 Eastern with zero unresolved identities and zero unparsed
documents in its report window. The raw reports and source dates were retained.

The scheduled controller explicitly disables proxies for its children. The day's
direct stats run completed 12 fetch tasks and nine calculation tasks. This is
evidence for the PC path, not a cloud transport guarantee. An independent NBA
schedule-completeness check still received HTTP 403. Manual environment defaults
and individual fallback paths must be checked before proxy access ends November
14; no proxy subscription or external polling was purchased by this work.

Local status files are not off-PC alerts. Always-on execution, external alerting,
off-device backup copies, and a restore rehearsal remain separate operating work.

## Modeling reproduction

Existing audit and baseline commands were rerun against `yunoball_local` with
PostgreSQL `default_transaction_read_only=on` and a statement timeout. No model,
prediction, training table, or feature rows were written.

| Season | Eligible complete game inputs | Baseline test games | Naive margin MAE | Naive total MAE | Elo win log loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024-25 | 1,075 | 1,025 | 12.965 points | 15.816 points | 0.6272 |
| 2025-26 | 1,075 | 1,025 | 13.316 points | 16.440 points | 0.6171 |

MAE is average absolute error; lower is better. These are the existing
chronological within-season experiments with a 50-game initial history, not a
new cross-season holdout or proof of profitable market performance. Historical
source-availability proxy assumptions still constrain interpretation.

Current-season audit: 18 complete paired game inputs, 14 with outcomes, no
missing required feature fields, and no reported cutoff violations. Four games
were still pending. The existing all-games outcome gate therefore returned
`blocked_outcome_coverage`; this does not mean those four games should already
have results. Do not lower that gate or fabricate labels to train on them.

Local JSON reports are under ignored/uncommitted `tmp/`:
`audit_program_g_model_inputs_<season>.json` and
`run_program_g_baseline_<season>.json`. They are not committed datasets.

## Next bounded modeling step

1. Reproduce the existing cross-season holdout with fixed model definitions.
2. Define immutable model/feature versions and a private prediction ledger with
   actual creation time, training cutoff, pregame input completeness, and source
   provenance. A nominal 10:00 feature cutoff is not the actual prediction time.
3. Save predictions only before tipoff; late or incomplete runs remain explicit
   skips. Score only after paired final outcomes exist.
4. Keep timestamped market observations separate; absent market data prevents
   market/closing-line claims but need not prevent ordinary forecast scoring.
5. Add richer features only after their incremental held-out value is measured.

Do not enable public prediction publication as a side effect of this checkpoint.
