# Yuno Ball Availability Source Spike

Status: proposed research specification  
Prepared: 2026-07-15  
Primary source: official NBA injury-report PDFs  
Historical bridge candidate: Stat Surge injury CSV archive

## Decision to investigate

Forward collection of official NBA injury-report revisions appears operationally viable.

The active NBA injury-report page publishes links at 15-minute intervals. Direct documents follow a predictable filename pattern such as:

`Injury-Report_YYYY-MM-DD_HH_MMAM.pdf`

The official reports contain report timestamps, game date/time, matchup, team, player name, current status, reason, and explicit `NOT YET SUBMITTED` states.

Historical discovery is less certain because prior dates are not exposed through a complete navigable archive. Direct CDN URLs may remain available after links disappear from the active page, but retention and filename consistency must be measured rather than assumed.

## Goals

1. Prove reliable forward discovery and ingestion.
2. Measure historical CDN retention by season.
3. Evaluate the Stat Surge archive as a provenance-labeled bridge for October 2021 through June 2024.
4. Define normalized availability observations without losing raw report meaning.
5. Establish player, team, matchup, and game identity resolution.
6. Preserve every meaningful status transition.
7. Produce a migration and operational plan, but do not alter production before approval.

## Source tiers

### Tier 1 — Official NBA PDF

Authoritative source document for the observation.

Store:

- exact source URL;
- report timestamp printed in the PDF;
- retrieval timestamp;
- raw file hash;
- HTTP metadata when available;
- parser version;
- parse outcome;
- original reported player/team text.

### Tier 2 — Community historical archive

The Stat Surge archive states that it was built from official NBA injury-report PDFs and offers:

- all injury reports from October 2021 through June 2024;
- season-specific regular-season and playoff CSV files;
- more than 35,000 injury designations described in the methodology article.

Treat this as a historical bridge and validation source, not as equivalent to a preserved official PDF unless each row includes auditable report provenance.

Required provenance:

- dataset name;
- download URL;
- downloaded timestamp;
- file hash;
- stated source;
- dataset version;
- season;
- row-level source timestamp if supplied;
- license or permission status;
- transformation notes.

Do not silently merge community rows with official observations under one indistinguishable source value.

## Discovery design

### Preferred forward discovery

1. Fetch the official current-season injury page.
2. Extract report links.
3. Normalize URLs.
4. Compare against already stored source URLs and hashes.
5. Download unseen documents.
6. Validate PDF signature and report timestamp.
7. Store raw document metadata.
8. Parse in a separate step.
9. Record failures without losing the raw document.
10. Retry safely.

### Fallback discovery

Construct candidate filenames only when link scraping is unavailable.

A constructed URL returning 404 does not prove that no report existed. Record a discovery outcome:

- `linked_and_downloaded`
- `constructed_and_downloaded`
- `not_found`
- `access_denied`
- `timeout`
- `invalid_document`
- `timestamp_mismatch`
- `not_checked`

### Historical retention sample

Before broad probing, select representative dates from each season:

- regular-season dates;
- playoffs;
- back-to-backs;
- early tipoffs;
- heavy slates;
- light slates;
- dates near season boundaries.

Test canonical checkpoints:

- midnight Eastern;
- morning report window;
- noon;
- 2 p.m. Eastern;
- 90 minutes before first tip;
- 30 minutes before each game;
- final available pregame revision.

Only expand to every 15-minute candidate after retention is demonstrated.

## Proposed tables

### `availability_report_documents`

Grain: one retrieved source document.

Suggested fields:

- `id`
- `source`
- `source_url`
- `report_published_at`
- `retrieved_at`
- `report_date`
- `raw_sha256`
- `normalized_content_sha256`
- `raw_storage_location`
- `http_etag`
- `http_last_modified`
- `page_count`
- `parser_version`
- `parse_status`
- `parse_error_summary`
- `source_run_id`
- `created_at`

Unique constraints should prevent storing the same URL/hash repeatedly while still allowing a changed document at the same logical report time to be retained as a revision.

### `availability_observations`

Grain: one reported player status in one report document for one matchup/team context.

Suggested fields:

- `id`
- `report_document_id`
- `game_id` nullable until resolved
- `game_date`
- `scheduled_tipoff`
- `matchup_text`
- `team_id` nullable until resolved
- `player_id` nullable until resolved
- `reported_team_name`
- `reported_player_name`
- `status`
- `reason_category`
- `reason_detail`
- `raw_reason`
- `competition_type`
- `player_match_status`
- `player_match_confidence`
- `created_at`

Do not discard unresolved names.

### `team_report_submission_status`

Grain: one team/game/report document.

Suggested fields:

- `report_document_id`
- `game_id`
- `team_id`
- `submission_status`
- `raw_text`

This prevents `NOT YET SUBMITTED` from being interpreted as a healthy roster.

## Parsing rules

The parser must handle:

- wrapped injury reasons;
- names containing suffixes, punctuation, and compound surnames;
- blank reason continuation lines;
- `Available`, `Probable`, `Questionable`, `Doubtful`, and `Out`;
- rest and injury-management designations;
- G League assignment and two-way designations;
- concussion protocol;
- not-yet-submitted teams;
- games listed for the following date;
- preseason, Summer League, All-Star, and other nonstandard competition types.

The parser should retain raw text and normalized fields. It must never invent a player ID or reason.

## Transition derivation

Create transitions downstream from immutable observations:

- previous status;
- new status;
- previous report time;
- new report time;
- minutes until tip;
- materiality classification;
- affected expected minutes when role data exists.

Do not overwrite prior states.

## Stat Surge bridge audit

Required checks:

1. Obtain and hash each archive file.
2. Record exact column names and data types.
3. Confirm whether each row represents a report revision, a daily checkpoint, or a deduplicated status.
4. Confirm timezone semantics.
5. Determine whether report URL or report timestamp is retained.
6. Measure duplicate rows.
7. Map teams and players.
8. Compare a sample against official PDFs still available.
9. Identify missing dates and seasons.
10. Confirm reuse and commercial permissions.

Until permission is clear, the archive may be used for internal evaluation only.

## Acceptance criteria

- A report linked on the official page is discovered and stored exactly once.
- A rerun is idempotent.
- Raw documents are retained separately from parsed observations.
- Duplicate-content revisions are detectable.
- `NOT YET SUBMITTED` is represented explicitly.
- Player mapping failures remain queryable.
- Historical source tier is preserved.
- No historical row is fabricated from a later status.
- Current availability queries can select the latest report before a declared cutoff.
- Historical queries never select a report after scheduled tipoff.
- Source and parser versions are visible.
- Legal/reuse status is recorded before public redistribution.

## Initial deliverable

Produce a spike report containing:

- forward discovery success rate;
- historical retention by season;
- Stat Surge archive coverage;
- parser accuracy on a reviewed sample;
- unresolved player/team rate;
- recommended historical start date;
- storage estimate;
- operational polling plan;
- legal and provenance gaps;
- go/no-go recommendation.
