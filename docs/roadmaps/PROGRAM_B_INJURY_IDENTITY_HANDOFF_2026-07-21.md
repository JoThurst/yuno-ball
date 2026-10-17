# Program B Injury Identity Handoff

Status: schedule coverage repaired; game/team identity gate complete; player alias gate pending  
Date: 2026-07-21  
Branch: `codex/program-b-official-injury-documents`

## Executive summary

The official injury-report acquisition and parsing foundation is healthy. Do
not connect the observations to slate payloads yet. The next dependency is
canonical schedule coverage, followed by deterministic identity resolution.

The current injury archive includes reports for games that are not represented
in `game_schedule`, especially 2025-26 postseason and play-in games. Repairing
injury rows before those canonical games exist would require guessing game IDs,
which is prohibited.

## Verified current state

The completed archive and parser validation showed:

- 2024-25: 2,795 documents, all parsed.
- 2025-26: 8,675 documents, all parsed.
- 11,470 successful document attempts and 1,431 terminal `not_found` attempts.
- 962,866 official availability observations.
- 73,855 team submission-status rows.
- Team resolution: complete.
- Player resolution: 0 currently populated; 938,103 rows have a unique exact
  normalized-name candidate, while 24,763 rows contain 21 names needing
  reviewed aliases or remaining unresolved status.
- Game resolution: 28,347 observations currently have `game_id = NULL`.

The canonical schedule now contains the bounded 2025-26 postseason repair:
6 Play-In games and 84 Playoffs games, represented by 182 reciprocal rows for
2026-04-14 through 2026-06-13. The repair used one explicit-season
`ScheduleLeagueV2` request, inserted only missing exact games, and its exact
rerun inserted zero rows.

## Required continuation order

### 1. Restore canonical schedule coverage — complete for the repaired window

`nba_api.stats.endpoints.ScheduleLeagueV2` is now the primary historical path.
The CDN remains a validated fallback only; a season mismatch or empty payload
fails closed. The bounded repair is implemented by
`scripts/repair_schedule_coverage.py`.

Before applying schedule writes:

- use a dry-run or read-only source inspection;
- require canonical NBA game IDs, reciprocal team rows, dates, home/away
  values, and season type;
- preserve source and ingestion-run lineage;
- validate two schedule rows per game and no conflicting existing rows;
- rerun the exact operation and prove zero additional writes.

### 2. Reconcile injury game identities — complete for the repaired window

The `official-injury-identity-v1` pass resolved 23,035 rows (19,020
observations and 4,015 team submissions) using exact report-date/matchup
schedule matches. A repeat dry run and apply both planned/wrote zero rows.
The migration adds version, run, and JSON detail lineage to both tables.

### 3. Reconcile player identities — next gate

The bounded postseason dry run found 18,830 unique normalized-name matches and
190 ambiguous/unresolved rows. Apply only unique normalized-name matches. Do not fuzzy-match. Review these
remaining source names explicitly before adding aliases:

`Alexander-Walker, Nic`; `Alexander-Walker, Nick`; `Antetokounmpo, Thanasi`;
`Bal, Adama`; `Boston, Brandon`; `Butler III, Jimmy`; `Caldwell-Pope, Kentavi`;
`Carrington, Bub`; `Djurisic, Nikola`; `Gilgeous-Alexander, Sh`;
`Hayes-Davis, Nigel`; `Jemison III, Trey`; `Jones Garcia, David`; `Key, Tyreke`;
`Lovering, Lawson`; `Niederhauser, Yanic Ko`; `Poeltl, Jakob`;
`Prosper, Olivier-Maxen`; `Robinson-Earl, Jeremia`; `Sarr, Alex`; and
`Yang, Hansen`.

### 4. Validate before serving

Re-run both seasons and verify duplicate parse rows, missing lineage, missing
dates, parse failures, unresolved game/player counts, and exact rerun behavior.
Only then connect observations to slate payloads. Missing observations must
remain unknown; they must never be converted to healthy or available.

## 403 interpretation

For the historical injury filename probe, a validated CDN 403/404 response can
mean that the specific filename is not present. That candidate is recorded as
terminal `not_found` so it is not retried forever.

This classification is scoped to that known injury-CDN filename behavior. A
403 from the live season page, schedule CDN, or another endpoint may indicate
blocking or access policy and remains a failure requiring investigation. It
must not be classified as missing data automatically.

## Operational state already in place

The Task Scheduler wrapper now uses the project `venv`, runs with a seven-day
lookback, and is configured to run as soon as possible after a missed start.
Successful URLs are skipped by the durable attempt ledger; transient failures
remain retryable. A gap longer than seven days requires reviewed direct-CDN
backfill.

## Relevant files

- `scripts/collect_official_injury_reports.py`
- `scripts/run_injury_report_collector.ps1`
- `scripts/parse_official_injury_reports.py`
- `scripts/validate_official_injury_observations.py`
- `app/services/availability_observation_service.py`
- `app/services/official_availability_identity_service.py`
- `app/services/schedule_coverage_repair_service.py`
- `scripts/repair_schedule_coverage.py`
- `scripts/reconcile_official_availability_identities.py`
- `alembic/versions/2026_07_21_1100-b8c9d0e1f2g3_add_official_availability_identity_lineage.py`
- `docs/INGESTION_RUNBOOK.md`
- `docs/DATA_DICTIONARY.md`
- `docs/SOURCE_CATALOG.md`
- `docs/roadmaps/MASTER_ANALYTICS_ROADMAP.md`
- `docs/roadmaps/POST_FOUNDATION_ROADMAP.md`

Do not commit raw PDFs, generated datasets, proxy credentials, or local
environment files.
