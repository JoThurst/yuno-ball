# Yuno Ball Odds Observation Plan

Status: proposed research and implementation specification  
Prepared: 2026-07-15

## Problem

The existing Yuno Ball odds grain retains one row per game and sportsbook and updates it in place. That is useful for a current display but cannot reconstruct:

- opening to closing movement;
- the line available when a prediction was issued;
- market reaction timing;
- multi-book disagreement over time;
- closing-line value;
- morning, injury-window, and pregame comparisons.

The target system must be append-only.

## Data-source candidates

### Candidate A — Free Kaggle historical dataset

Candidate URL supplied for evaluation:

`ehallmar/nba-historical-stats-and-betting-data`

The public page could not be fully inspected through the research environment. Before approval, download its metadata, license, data card, file list, and a sample.

Required questions:

- Which seasons are included?
- Which books or consensus source produced the lines?
- Are lines opening, closing, or both?
- What timezone is used?
- Is vig/price included or only line values?
- Are postponed and rescheduled games handled?
- Are playoffs, play-in, NBA Cup, preseason, and neutral-site games included?
- Are rows one per game or one per team perspective?
- Does the license allow commercial use and derived products?
- Are derived streak, record, and target columns leakage-safe?

Treat it as a candidate backfill, not a canonical source, until these are answered.

### Candidate B — Scottfree historical odds dataset

The current product page describes:

- 24,284 NBA game rows;
- a 146-column schema;
- final scores and scheduled Eastern time;
- closing spread, moneyline, and total;
- opening lines where available;
- team records, streaks, ATS history, and model target variables;
- refresh availability for purchasers.

Current advertised sale price at the time of review: USD 89.

Risks:

- source sportsbook/provenance is not stated on the product page;
- license and redistribution rights are not stated on the product page;
- engineered team records, streaks, ATS fields, and targets may include leakage or unclear as-of semantics;
- the declared natural key uses date, scheduled Eastern time, away team, and home team rather than NBA game ID;
- line prices/vig may be missing or ambiguous;
- “closing” methodology must be defined.

Do not purchase or ingest until a sample data dictionary and license are reviewed.

### Candidate C — Live timestamped provider

Required for forward collection and prediction-time evaluation.

Evaluate:

- coverage by sportsbook;
- moneyline, spread, and total;
- source and retrieval timestamps;
- event-ID stability;
- pregame/live separation;
- opening-line semantics;
- update frequency;
- historical snapshot access;
- cost per season under polling scenarios;
- commercial display and derived-analysis rights;
- raw redistribution restrictions.

## Canonical storage

### `odds_events`

Maps provider event identity to Yuno Ball game identity.

Fields:

- `id`
- `provider`
- `provider_event_id`
- `game_id` nullable until resolved
- `scheduled_tipoff`
- `home_team_id`
- `away_team_id`
- `match_status`
- `created_at`
- `updated_at`

### `odds_observations`

Grain:

`(provider, provider_event_id, sportsbook, market, selection, observed_at, line, price)`

Suggested fields:

- `id`
- `game_id`
- `provider`
- `provider_event_id`
- `sportsbook_id`
- `sportsbook_name`
- `market`
- `selection`
- `line`
- `price`
- `observed_at`
- `provider_updated_at`
- `scheduled_tipoff`
- `is_live`
- `source_run_id`
- `raw_observation_id`
- `created_at`

Start with:

- moneyline;
- spread;
- total.

Player props remain out of scope until player role, minutes, availability, and lineup data are materially stronger.

### `raw_source_observations`

Retain raw provider payloads or immutable file references with:

- source;
- retrieval time;
- content hash;
- schema version;
- storage location;
- source run;
- parse status.

## Polling policy

Start with a cost-controlled schedule:

- prior evening;
- morning;
- official injury-report window;
- every 30 minutes during active game-day hours;
- immediately after a material availability transition when allowed by provider limits;
- 60 minutes before tip;
- 30 minutes before tip;
- 10 minutes before tip;
- final available pregame observation.

Never use live observations in pregame model evaluation.

## Historical dataset import

External CSVs must enter staging tables first.

Import sequence:

1. Store original file and hash.
2. Record provider/version/license.
3. Infer and validate schema.
4. Standardize timezone without discarding original timestamp.
5. Standardize team names.
6. Match to `game_schedule`.
7. Flag ambiguous or unmatched games.
8. Validate scores against canonical final scores.
9. Separate raw market columns from vendor-derived features.
10. Import approved raw observations only.
11. Recompute Yuno features internally.
12. Preserve source-level missingness.

Do not train on vendor-created record, streak, ATS, rolling average, margin, or target columns until their calculation cutoff is independently proven. It is safer to discard them and rebuild from Yuno Ball game history.

## Game matching

Match in descending confidence:

1. Provider NBA game ID.
2. Exact scheduled tipoff plus canonical home/away teams.
3. Game date plus canonical teams with reschedule handling.
4. Manual mapping table.

Never silently match solely on team names and calendar date when multiple competition types or reschedules could collide.

## Market semantics

Document:

- American/decimal odds format;
- whether a spread is from the selected team perspective;
- whether total selection is over/under;
- whether opening and closing are provider-defined;
- whether “closing” is last observed before tip;
- whether postponed-game markets reset;
- whether push rules are represented;
- whether the source is a single book or consensus.

## Quality checks

- observations occur before tip for pregame records;
- prices and lines are in expected ranges;
- home and away spread lines reconcile;
- over and under share a total line;
- event/team identities match schedule;
- no duplicate observation grain;
- no impossible timestamp order;
- no live rows enter pregame views;
- historical final scores match canonical results;
- missing books are not imputed;
- line movement uses comparable book/market/selection observations.

## Licensing gate

A free download or paid purchase does not by itself grant public redistribution or commercial use.

Record:

- license text;
- purchaser rights;
- derived-analysis rights;
- display rights;
- raw redistribution rights;
- model-training rights;
- attribution;
- refresh/subscription conditions;
- termination provisions.

No external odds dataset should be committed to the public repository.

## Acceptance criteria

- append-only observations;
- idempotent polling;
- immutable raw provenance;
- prediction-time lookup;
- opening/current/final pregame semantics;
- no future odds in historical evaluation;
- unmatched games quarantined;
- external derived features excluded by default;
- provider cost observable;
- licensing status recorded;
- current game pages can expose source and as-of timestamp.
