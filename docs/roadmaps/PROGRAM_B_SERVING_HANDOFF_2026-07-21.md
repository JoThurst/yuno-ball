# Program B Serving Boundary Handoff

Status: collection, parsing, schedule coverage, identity reconciliation, read-only serving, and daily slate integration complete  
Date: 2026-07-21  
Branch: `codex/program-b-official-injury-documents`

## Purpose

This handoff records the completed Program B serving slice after the canonical
schedule and official injury identity gates were repaired. Official
availability is now connected to the existing daily slate assembly path without
route-side NBA calls, cache writes, model features, or health inference.

## Verified current state

- `availability_report_documents`: 2024-25 and 2025-26 archive windows are
  collected and parsed.
- `availability_observations`: 962,866 total rows.
- Missing `game_id`: 0.
- Missing `player_id`: 57 rows, all intentionally unresolved:
  - `Key, Tyreke`: 46
  - `Lovering, Lawson`: 11
- Fully identified observations: 962,809.
- Schedule rows with `opponent_team_id = team_id`: 0.
- 2024-25 and 2025-26 regular season, NBA Cup, preseason, play-in, and playoff
  schedule coverage has been repaired and validated where represented by the
  local injury archive.
- The NBA Cup final remains represented as a canonical game even though it is
  not part of the official regular-season standings grain.
- Adama Bal was resolved to official NBA player ID `1642380`; the local
  historical `gamelogs` table does not currently contain rows for that ID.
  No speculative gamelog backfill was added in this pass.

## Serving contract now available

`app/services/official_availability_serving_service.py` defines the read-only
boundary:

- consumers provide rows already filtered to an explicit publication `as_of`
  cutoff;
- payloads include `source`, `as_of`, `completeness`, `unknown_reason`, and
  nullable game/team/player identity fields;
- no observations returns `completeness = unknown`;
- any unresolved identity returns `completeness = partial`;
- complete identity resolution returns `completeness = complete`;
- missing observations are never interpreted as healthy, available, or zero
  injury risk.

The service is connected to the read-only daily slate service. It is not used by
prediction features, slate ranking, or cache writes.

## Implemented slate integration

1. The existing `/daily/` slate service uses Eastern calendar slate selection
   and canonical scheduled game IDs.
2. The read-only adapter selects the latest official report with
   `report_published_at < scheduled_tipoff`, preserves source/completeness and
   freshness metadata, and avoids direct NBA calls from routes.
3. Resolved non-available observations populate player callouts. The 57
   unresolved player rows remain preserved as partial game evidence.
4. Explicit `NOT YET SUBMITTED` team states remain separate from player status;
   empty evidence remains unknown.
5. Both daily templates render compact official availability states.

## Boundaries and deferred work

- Do not perform additional broad identity guessing or fuzzy matching.
- Do not resolve `Tyreke Key` or `Lawson Lovering` without an authoritative NBA
  identity source and evidence that the rows belong to NBA canonical player
  records. They may be preseason/G League edge cases.
- Do not infer a healthy/available state from an absent report or absent player
  row.
- Do not add route mutation, cache writes, slate ranking changes, or model
  feature changes in the first serving-integration slice.
- Do not add raw PDFs, generated datasets, credentials, or local environment
  files to version control.

## Validation evidence

- Focused identity, serving, schedule repair, and slate integration tests:
  `18 passed`.
- `python -m compileall app`: passed.
- Database-backed 2026-03-03 slate build: 10 games, 116 official observations,
  complete payloads, 97 non-available status callouts.
- `git diff --check`: passed.
- Database profile regenerated at `docs/DATABASE_PROFILE.md`.

## Relevant files

- `app/services/official_availability_serving_service.py`
- `app/services/official_availability_identity_service.py`
- `app/services/schedule_coverage_repair_service.py`
- `scripts/reconcile_official_availability_identities.py`
- `docs/DATA_DICTIONARY.md`
- `docs/INGESTION_RUNBOOK.md`
- `docs/SOURCE_CATALOG.md`
- `docs/roadmaps/MASTER_ANALYTICS_ROADMAP.md`
- `docs/roadmaps/POST_FOUNDATION_ROADMAP.md`

No database changes are required for the next read-only adapter unless the
existing slate boundary lacks a safe, explicit cutoff contract. Preserve
unrelated worktree changes.
