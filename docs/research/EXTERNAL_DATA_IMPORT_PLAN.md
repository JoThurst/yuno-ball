# Yuno Ball External Data Import Plan

Status: proposed implementation plan  
Prepared: 2026-07-15

## Scope

Import the downloaded historical injury, betting, game, player-game, player, and team datasets without disrupting current or future Yuno-owned pipelines.

## Principle

Full preservation does not require full promotion.

- Preserve all original files and rows.
- Stage source-shaped data.
- Promote only validated facts and observations.
- Retain source precision and uncertainty.
- Future collectors write richer observations into the same canonical domains.

## Import phases

### Phase 1 — Manifest and raw preservation

Create:

- `external_dataset_imports`;
- raw file hashes;
- source URLs;
- dataset versions;
- licenses;
- row counts;
- transformation versions;
- import-run linkage.

Do not commit large raw CSVs to public Git.

### Phase 2 — Source-specific staging

Create staging tables for each file.

Staging tables preserve:

- original column names;
- original values;
- source row number;
- parse errors;
- source file ID.

### Phase 3 — Profiling and quarantine

Create:

- `external_row_rejections`
- `external_identity_conflicts`
- `external_market_anomalies`

Reason codes include:

- malformed price;
- impossible line;
- ambiguous game;
- unresolved team;
- unresolved player;
- missing date;
- incomplete season;
- unsupported event type;
- after-cutoff availability.

### Phase 4 — Identity reconciliation

Games:

1. NBA game ID
2. scheduled tip and teams
3. date and teams with reschedule logic
4. manual mapping

Players:

1. NBA player ID
2. exact normalized name within team/date context
3. alias table
4. unresolved

Teams:

- historical franchise mapping separate from current 30-team list.

### Phase 5 — Canonical promotion

Promote:

- historical odds observations with unknown timing precision;
- historical availability checkpoints;
- selected historical game facts;
- selected historical player-game facts.

Do not promote vendor-derived rolling features.

### Phase 6 — Reconciliation

Compare overlapping facts with Yuno:

- score;
- result;
- team identity;
- player totals;
- game date;
- season;
- home/away.

Conflicts remain queryable.

## Recommended initial scope

- Odds and supporting game/player data: 2006-07 through 2017-18.
- Injury checkpoints: all 2021-22 through 2023-24.
- Exclude incomplete 2018-19 fragment.
- Defer pre-2006 box-score import.

## Future compatibility

Historical odds:

- `observed_at = NULL`;
- `timing_precision = unknown`;
- `snapshot_type = historical_static`.

Future odds:

- exact `observed_at`;
- provider update time;
- pregame/live state;
- immutable revisions.

Historical injury:

- daily checkpoint;
- exact report revision unknown.

Future injury:

- exact official report time;
- raw PDF document;
- status transitions.

Shared canonical tables must preserve these differences.

## Verification

- source row counts;
- file hashes;
- rerun idempotency;
- natural-key duplicates;
- game/team/player mapping;
- quarantine counts;
- promoted counts;
- overlap conflicts;
- season coverage;
- post-import database profile.

## Rollback

- staging imports removable by import ID;
- promoted rows linked to source import;
- no deletion of existing Yuno facts;
- source precedence reversible;
- cache unaffected until public consumers are enabled.
