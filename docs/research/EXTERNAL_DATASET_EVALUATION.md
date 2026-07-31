# Yuno Ball External Historical Dataset Evaluation

Status: candidate-source evaluation  
Prepared: 2026-07-15

## Candidates

### 1. Kaggle — NBA Historical Stats and Betting Data

Candidate owner/slug:

`ehallmar/nba-historical-stats-and-betting-data`

Current assessment: **unverified candidate**.

The dataset page is accessible, but its full metadata, files, schema, license, provenance, and update history were not available through the research environment. It must not be approved based on its title or free price.

Required acquisition package:

- Kaggle data card;
- license text;
- file list;
- file sizes;
- last updated timestamp;
- schema;
- five representative rows;
- stated source of odds;
- season coverage;
- known limitations.

### 2. Scottfree Analytics — NBA Historical Odds Data

Current product-page claims:

- 24,284 NBA game rows;
- 146 columns;
- standardized team names;
- game dates and scheduled Eastern times;
- final scores;
- closing spread, moneyline, and total;
- opening lines where available;
- team records, streaks, scoring averages, margins, ATS history, and model targets;
- schema documentation;
- refreshes available to purchasers.

Current assessment: **potentially useful paid bridge, pending sample and license**.

The raw opening/closing market columns could accelerate historical model benchmarking. The vendor-derived records, streaks, ATS fields, averages, margins, and target variables should be excluded initially because their calculation cutoffs and leakage characteristics are unknown.

### 3. Stat Surge — NBA injury archive

Published archive claims:

- all injury reports from October 2021 through June 2024;
- regular-season and playoff files for 2021-22, 2022-23, and 2023-24;
- more than 35,000 injury designations;
- source methodology based on official NBA injury-report PDFs.

Current assessment: **strong historical bridge candidate with explicit provenance separation**.

It may fill much of the pre-2025 injury gap while Yuno Ball collects official revisions forward. It still requires license/permission review, schema audit, timestamp verification, and comparison against surviving official PDFs.

## Evaluation rubric

Score every dataset from 0 to 3.

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Source provenance | unknown | vague | documented secondary | official/raw |
| License clarity | absent | ambiguous | limited | explicit intended use |
| Observation grain | unclear | inferred | documented | validated |
| Timestamp semantics | absent | date only | documented | source and availability time |
| Identity quality | free text | normalized names | stable IDs partly | canonical IDs |
| Historical coverage | sparse | partial | broad | broad and measured |
| Missingness documentation | none | weak | documented | measured |
| Leakage safety | unsafe | unknown | reviewable | verified |
| Update/version history | none | overwrite | dated files | immutable versions |
| Reconciliation quality | none | sample | broad checks | official agreement measured |

No dataset enters canonical production tables with a score of zero for provenance, license, grain, or timestamp semantics.

## Required staging workflow

1. Download without altering the original.
2. Compute SHA-256.
3. Record download time and source URL.
4. Store license and data-card snapshots.
5. Import into a source-specific staging schema.
6. Profile columns, types, dates, nulls, duplicates, and keys.
7. Preserve raw team/player names.
8. Create explicit mapping tables.
9. Reconcile outcomes against Yuno schedule and box scores.
10. Quarantine ambiguous rows.
11. Promote only approved raw facts/observations.
12. Recalculate Yuno features internally.

## Odds-specific audit

Inspect:

- opening versus closing definitions;
- sportsbook versus consensus;
- line and price/vig availability;
- timezone;
- postponed/rescheduled games;
- playoffs and play-in;
- duplicate game rows;
- home/away perspective;
- pushes;
- missing markets;
- source corrections;
- whether vendor features include the target game or later games.

Only raw market observations and final outcomes should be considered for initial import.

## Injury-specific audit

Inspect:

- one row per report revision or one row per day;
- report timestamp;
- game ID or matchup text;
- team/player naming;
- statuses;
- reasons;
- not-yet-submitted representation;
- regular season versus playoffs;
- duplicate unchanged reports;
- player status transitions;
- missing dates;
- official PDF URL retention;
- whether available players remain in later reports.

## Licensing and repository policy

- Do not commit purchased datasets to Git.
- Do not commit large downloaded datasets merely because they are free.
- Store external raw files in controlled object storage or a data directory excluded by `.gitignore`.
- Commit schemas, hashes, import manifests, small synthetic fixtures, and documentation.
- Do not expose raw rows publicly until the license permits it.
- Separate internal model-training permission from public redistribution permission.
- Record attribution requirements.

## Purchase decision for Scottfree

Request before purchase:

1. Sample rows and full column dictionary.
2. Source sportsbook/provenance.
3. Definition of opening and closing.
4. Whether prices/vig are included.
5. Season start and end.
6. Playoff/play-in/preseason coverage.
7. Correction policy.
8. License for commercial website use.
9. Permission for model training and derived metrics.
10. Restriction on redistribution/API access.
11. Refresh cost and cadence.

The USD 89 price is low relative to engineering time, but price is not the main decision factor. A dataset with unclear provenance or leakage-prone features can create more work than it saves.

## Recommended decision

- Stat Surge injury archive: proceed to download-and-audit, subject to permission.
- Official NBA PDFs: begin forward source spike as the preferred source.
- Kaggle historical betting data: obtain metadata/sample/license before any recommendation.
- Scottfree odds data: request sample/license; purchase only if raw market provenance and rights are acceptable.
- Live odds provider: still required for forward timestamped observations.
