# PlayerGameLogs conflict recovery: bounded implementation brief

## Baseline and outcome

Prepared October 27, 2026 for one GPT-5.6 Sol implementation agent. Do not
delegate. This is a plan, not authorization to execute unrelated handoff work.

- Checkout: `C:\Code\sports_analytics`.
- Branch/HEAD: `codex/issue-43-correction-lineage`, `bebbb77`.
- Refreshed origin: HEAD matches its remote branch; 17 commits ahead of
  `origin/main`, zero behind. Local main is not the current implementation base.
- Working tree: 33 modified tracked files and 22 untracked files before this
  plan, spanning ingestion, PC automation, product features, and instructions.
  Recheck status. Preserve all existing edits; do not bulk-stage or reset.
- Scheduled jobs execute this checkout. Do not move it, restart services, or
  change scheduled tasks. A clean worktree at HEAD omits required ingestion edits.

Outcome: tolerate a demonstrably resolvable PlayerGameLogs conflict using
validated canonical box-score evidence, while preserving rejection of unresolved
data and atomic publication. Do not implement general partial-cycle scheduling.

## Reproduced evidence

On October 27 at 14:27 and 14:31 Eastern, the current-season Regular Season
PlayerGameLogs response contained two Devin Booker (1626164) rows for
0022600124, dated October 26: PHX, 33.79 minutes, 2 points; OKC, zero minutes,
1 point. The existing canonical fact was PHX, 33:47, 3 points. Legacy gamelogs
had no row for this player/game. One duplicate was found across 1,182 source
rows and 104 completed schedule pairs; no unexpected-team conflicts were found.
The upstream cause is unknown. Reverify live evidence before applying recovery.

## Implementation sequence

1. Read relevant ingestion skill and bounded runbook/source sections. Inspect
   the existing dirty diff in smart_gamelog_fetcher.py, daily_fetch.py, and
   tests/test_local_ingestion_cycle.py before extending it. Inspect canonical
   fact completeness, revision lineage, team reconciliation, and minutes mapping.
2. Separate duplicate-player/game and unexpected-team diagnostics. Include
   affected keys and bounded conflicting values, without secrets or full responses.
3. Add a pure conflict-resolution step with injected canonical evidence. Prefer
   replacing the affected game's played-player projection as a coherent unit
   over mixing contradictory source rows. Require both scheduled teams, one team
   per played player/game, complete required fields, correct season/type/game,
   trusted revision/source lineage, and applicable team-total reconciliation.
   Convert minutes explicitly using existing contracts. Preserve real zeros and
   missingness; exclude DNP rows under the established legacy contract. Never
   sum duplicate rows or choose one by order. Do not mutate canonical facts.
4. Establish when fallback evidence becomes eligible. The current daily task
   order places gamelogs before player_facts: do not silently reorder tasks or
   assume today's facts have been collected. Reuse independently verified stored
   facts when sufficient; otherwise fail with an actionable reason. Any required
   fresh collection must use the existing bounded provider/publication path and
   shared writer-lock contract, not an ad-hoc network call or nested lock.
5. Validate the complete resolved payload before one transactional legacy upsert.
   Unresolved conflicts must leave that batch unpublished and keep downstream
   calculations blocked. Preserve historical rows and rerun safety.
6. Record recovered game IDs, conflict reasons, canonical revision/source IDs,
   and fallback counts in existing run/task evidence. Report successful fallback
   explicitly; do not call it an unchanged clean source result. Update only the
   affected ingestion/source contract sections.

## Acceptance and verification

- Fixtures reproduce Booker's cross-team duplicate and resolve to one PHX row
  with 3 points using complete canonical game evidence.
- Missing, incomplete, wrong-season/team, ambiguous or unreconciled fallback
  fails before publication. DNP, nulls, zeros, and minutes retain their meaning.
- Healthy source path remains unchanged. Reruns do not duplicate rows; publication
  failure rolls back. Recovery metadata identifies exactly which facts were used.
- Run focused tests during iteration. For the stable Python patch, use
  `C:\Code\sports_analytics\venv\Scripts\python.exe` to run
  `-m compileall app` and `-m pytest -q` once. Report unavailable service/test DB
  prerequisites honestly; never redirect generic tests to the live local DB.
- First produce a read-only one-game recovery preview showing identities,
  mapped fields, completeness and reconciliation evidence. Do not run a full
  manual ingestion or write live data as part of this implementation brief.

Stop after the stable patch, tests, and preview. Report changed files, remaining
risks and the exact bounded operational validation needed. Do not merge, deploy,
repair unrelated product work, redesign retries, or enable partial-success cycles.

## Git packaging

Keep this fix reviewable against the pre-existing dirty baseline. Do not bundle
all current work into a commit. If clean isolation is needed, first prepare an
explicitly scoped ingestion-baseline checkpoint including its dependencies;
do not manufacture a clean worktree that lacks the uncommitted bulk-fetch path.
Commit/push only when separately requested.
