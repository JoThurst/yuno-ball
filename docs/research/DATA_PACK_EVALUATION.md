# Yuno Ball External Data Pack Evaluation

Status: completed file-level evaluation  
Prepared: 2026-07-16  
Scope: uploaded Kaggle NBA historical files and Stat Surge injury CSV  
Implementation status: no database import or repository change performed

## Executive verdict

The free datasets are worth keeping.

The highest-value files are:

1. `Injury Database - Oct 2021 - June 2024.csv`
2. `nba_betting_money_line.csv`
3. `nba_betting_spread.csv`
4. `nba_betting_totals.csv`
5. `nba_games_all.csv`
6. `nba_players_game_stats.csv`

The identity files are supporting inputs:

- `nba_players_all.csv`
- `nba_teams_all.csv`

The main recommendation is **not** to copy all rows and columns into existing Yuno Ball tables. Import the files into source-specific staging tables, validate licenses and semantics, and promote only stable raw facts or observations.

The datasets solve different problems:

- The injury CSV bridges three historical seasons of pregame availability.
- The betting files provide multi-book historical market snapshots for 12 seasons.
- The game and player-game files provide the game identities and box-score context required to validate those odds.
- The long historical game files can later support historical pages, but Yuno Ball does not need to import every season immediately.

## Uploaded-file manifest

| File | Rows | Approximate coverage | Recommended disposition |
|---|---:|---|---|
| Injury Database | 35,522 | 2021-10-19 through 2024-06-17 | Import to staging; high-value historical bridge |
| Moneyline | 125,286 | 2006-07 through 2017-18 | Import to staging; retain every book/game observation |
| Spread | 131,690 | 2006-07 through 2017-18 | Import to staging; selection-specific lines |
| Totals | 131,386 | 2006-07 through 2017-18 | Import to staging; quarantine outliers |
| Team game rows | 125,624 | 1950-51 through 2018-19 | Use to validate odds and selectively backfill |
| Player identities | 4,885 | careers through 2018 | Mapping support only |
| Player game rows | 1,268,211 | 1950-51 through 2017-18 | Selective historical box-score backfill |
| Team identities | 69 | franchise/team IDs through 2018 | Historical mapping support only |

## 1. Injury database

### Profile

- 35,522 rows
- 628 distinct report dates
- 3,901 distinct date/matchup combinations
- 786 distinct player-name strings
- 30 teams
- Seasons:
  - 2021-22: 11,933 rows
  - 2022-23: 11,100 rows
  - 2023-24: 12,489 rows
- No blank required fields
- No exact duplicate rows
- No duplicate natural keys at:
  `(date, game, team, player)`

Status distribution:

| Status | Rows |
|---|---:|
| Out | 25,839 |
| Questionable | 5,829 |
| Probable | 1,773 |
| Available | 1,418 |
| Doubtful | 663 |

Reason families:

| Reason family | Rows |
|---|---:|
| Injury/Illness | 23,736 |
| G League assignment/two-way | 8,683 |
| Health and Safety | 1,272 |
| Non-medical absence | 951 |
| Other | 539 |
| Unspecified | 217 |
| Rest/load management | 124 |

### What the file actually represents

This is **not** a full revision history.

There is exactly one row per player/team/game/date and no report timestamp. It cannot reconstruct:

- Questionable → Out transitions
- when a status changed;
- late scratches;
- which 15-minute PDF revision supplied the row;
- market movement around an exact update.

The author's methodology says the historical database was produced from official NBA injury-report PDFs and that the scheduled daily dataset used the 2 p.m. report. Source:

`https://statsurge.substack.com/p/creating-an-nba-injury-database`

Therefore, this should be treated as a **daily report checkpoint dataset**, not as an immutable sequence of every official report revision.

Do not invent an exact `published_at` value for individual rows. Store the source time semantics separately, for example:

- `source_checkpoint = 'daily_2pm_report'`
- `published_at = NULL` unless an exact source timestamp is available
- `source_time_confidence = 'methodology_level'`

Early-tip games require special handling. A 2 p.m. checkpoint may occur after an early game started. Those observations must not automatically enter strict pregame modeling.

### Important limitations

- No NBA player ID
- No NBA game ID
- No exact report timestamp
- No report URL or source document hash
- No explicit `NOT YET SUBMITTED` records
- 356 games contain designations from only one of the two teams

A missing team or player must not be interpreted as:

- submitted and healthy;
- available;
- absent from the roster.

### Recommended use

Use it for:

- historical afternoon availability snapshots;
- probable/questionable/doubtful/out labels;
- historical availability burden;
- role-impact research after joining to prior minutes and usage;
- validating official-PDF backfills.

Do not use it for:

- exact intraday status transitions;
- late-news timing;
- causal odds-movement claims;
- strict pregame features for games whose tipoff preceded the assumed checkpoint;
- treating G League assignment as a physical injury.

### Proposed source grain

`(source_dataset_version, report_date, matchup_text, team_name, reported_player_name)`

After identity resolution, retain both raw and resolved values.

## 2. Historical betting files

### Combined profile

- 14,922 distinct games across any market
- 14,901 games contain moneyline, spread, and total
- Coverage: 2006-07 through 2017-18
- 10 sportsbooks
- Every betting game matches a game in `nba_games_all.csv`
- Every team/opponent pair matches the corresponding game
- No duplicate natural keys at:
  `(game_id, book_id, team_id, opponent_team_id)`

Books include:

- 5Dimes
- Pinnacle Sports
- Bookmaker
- JustBet
- BetOnline
- Sportsbetting
- Intertops
- Bovada
- YouWager
- Heritage

Median books per game:

- Moneyline: 9
- Spread: 10
- Total: 10

This is materially stronger than Yuno Ball's current retained odds coverage because it contains multiple books and approximately 15,000 historical games.

### What the files do not contain

There is no:

- observation timestamp;
- provider update timestamp;
- opening/closing label;
- source URL;
- explicit market phase;
- live/pregame indicator.

Therefore, each row is a **single historical book/game market snapshot of unknown timing**.

Do not call it:

- opening odds;
- closing odds;
- prediction-time odds;
- line movement history

until the Kaggle source documentation proves that semantic.

### Market-specific interpretation

Moneyline:

- `price1` applies to `team_id`
- `price2` applies to `a_team_id`

Spread:

- `spread1` and `price1` apply to `team_id`
- `spread2` and `price2` apply to `a_team_id`

Totals:

- the two line/price pairs should be stored as separate selections;
- do not force one shared total because 82 rows have different `total1` and `total2` values;
- similarly, 71 spread rows are not exact sign inverses.

The canonical observation grain should be selection-specific:

`(source, game_id, book_id, market, selection, source_snapshot_version)`

Suggested normalized selections:

- moneyline/team A
- moneyline/team B
- spread/team A
- spread/team B
- total/over
- total/under

### Data-quality findings

Moneyline:

- 2 rows have both selections at positive American prices and should be quarantined.
- Very large underdog/favorite prices exist. Some are plausible; validate rather than clipping them.
- Calculate and validate implied probability and overround before promotion.

Spread:

- 71 rows have non-inverse team lines.
- This may represent selection-specific offered lines rather than corruption.
- 3 rows contain extreme prices such as `+856/-1056` or `+775/-1100`; quarantine for review.

Totals:

- 82 rows have different over/under line values.
- 168 rows have totals outside the initial 150-260 validation range or extreme prices.
- A group of 2006-07 Bovada totals around 87-104 conflicts with other books near 170-201 for the same games. These are likely malformed, missing a leading digit, or a mixed market type. They must be quarantined, not silently corrected.

### Coverage by season

Core regular-season/playoff game coverage against the accompanying game file:

| Season | Approximate market coverage |
|---|---:|
| 2006-07 | 91.98% |
| 2007-08 | 92.78% |
| 2008-09 | 96.73% |
| 2009-10 | 96.72% |
| 2010-11 | 92.68% |
| 2011-12 | 100.00% |
| 2012-13 | 99.01% |
| 2013-14 | 98.56% |
| 2014-15 | 97.86% |
| 2015-16 | 97.11% |
| 2016-17 | 96.56% |
| 2017-18 | 92.07% |

This is sufficient for historical research after validation.

It is not a substitute for forward collection. The books and betting environment are mostly from the pre-legalization era and end in 2017-18. Current Yuno Ball market evaluation will still require append-only modern observations.

## 3. Team game data

### Profile

- 125,624 team-perspective rows
- 62,812 games
- Exactly two rows per game
- No duplicate `(game_id, team_id)` keys
- No opponent-pair, home/away, season, date, or W/L pairing failures in the paired-row checks
- 69 seasons represented
- 57 team IDs used in games
- Regular season, playoffs, preseason, and All-Star rows

This is structurally strong.

### Important defects

#### Missing dates

`game_date` is blank on 6,248 rows, representing 3,124 games.

However:

- 3,122 of those 3,124 game dates can be repaired from `nba_players_game_stats.csv`.
- Only two blank-date games were not recoverable from the player-game file.

Any repair must be deterministic and recorded as a transformation, not performed manually.

#### Incomplete 2018-19 season

The file contains only one 2018-19 game, with two zero-stat team rows:

- game ID `0021800266`
- date `2018-11-23`
- Memphis at LA Clippers

Exclude 2018-19 from any completeness claim or backfill.

#### Historical missing fields

Older seasons legitimately lack fields that were not tracked historically, including:

- three-point statistics before the rule existed;
- steals and blocks in early eras;
- offensive and defensive rebounds in early eras;
- plus/minus for many seasons.

Do not fill these with zero.

### Recommended scope

Do not import all 69 seasons immediately.

Recommended first eligible range:

**2006-07 through 2017-18**

Reasons:

- aligns with the betting data;
- has strong modern traditional box-score completeness;
- canonical NBA game and team IDs;
- useful for model and historical-market research;
- manageable validation scope.

Later, earlier seasons can be added for historical pages if there is a clear product need.

## 4. Player game data

### Profile

- 1,268,211 player-game rows
- 4,496 players
- 62,893 games
- 57 team IDs
- 68 seasons
- 1950-51 through 2017-18
- No duplicate player-game natural keys detected
- Minutes are numeric in every row

The file is much richer than Yuno Ball's current thin game-log contract. It contains:

- minutes;
- field goals;
- three-point shooting;
- free throws;
- offensive and defensive rebounds;
- assists;
- steals;
- blocks;
- turnovers;
- fouls;
- points;
- plus/minus.

### Modern-range quality

For 2006-07 through 2017-18:

- 352,615 player-game rows
- FGM/FGA and counting statistics are essentially complete
- rebound count missingness is approximately zero
- plus/minus missingness is below 1%
- percentage columns are often blank when the player had no attempts:
  - FG%: 5.16%
  - 3P%: 40.26%
  - FT%: 41.40%

Do not turn an undefined percentage into zero. Recalculate percentages from makes and attempts when needed, returning null for zero attempts.

### Value to Yuno Ball

This can fill historical player-game detail before Yuno Ball's current gamelog coverage.

It does not solve the forward/current problem because it stops after 2017-18. Yuno Ball still needs current traditional and advanced box-score ingestion.

Recommended initial use:

- validate and enrich 2006-07 through 2017-18;
- calculate historical player form and role baselines;
- support old matchup/player pages;
- support historical odds-model experiments;
- retain raw source provenance.

Do not replace current Yuno player-game data with this source.

## 5. Identity files

### `nba_players_all.csv`

- 4,885 unique player IDs
- careers through 2018
- no duplicate IDs
- all 4,496 player IDs used in the player-game file exist in the player master

Weak fields:

- birth date is entirely blank;
- draft number is entirely blank;
- position, height, and weight are missing for roughly 23%;
- only 562 rows are marked active in the old snapshot.

Use it for historical player ID/name mapping only.

Do not overwrite current Yuno player biography fields.

### `nba_teams_all.csv`

- 69 unique NBA historical team IDs
- no duplicate IDs
- spans historical/defunct team identities through 2018

Use it for a historical team-identity mapping table or staging lookup.

Do not append all 69 rows to the current `teams` table without checking application assumptions that expect 30 active teams.

## 6. What Yuno Ball should keep

### Promote after staging and validation

1. Injury daily checkpoint rows
2. Moneyline observations
3. Spread observations
4. Total observations
5. Game identity and final score facts required to validate odds
6. Team game box scores for an approved season range
7. Player game box scores for an approved season range

### Keep only as source-specific mapping

1. Historical player master
2. Historical team master
3. Raw matchup strings
4. Old active/inactive roster flags

### Do not promote directly

1. The incomplete 2018-19 game
2. Malformed Bovada total rows
3. Extreme or impossible market rows before review
4. Missing historical percentages converted to zero
5. G League designations treated as injuries
6. Unresolved player-name matches
7. Rows whose license does not permit the intended use

## 7. Proposed staging design

### Source manifest

`external_dataset_imports`

- dataset ID
- source name
- source URL
- source version
- downloaded at
- file name
- SHA-256
- license identifier
- commercial-use status
- transformation version
- import run ID
- row count
- validation status

### Staging tables

- `stg_kaggle_games`
- `stg_kaggle_player_games`
- `stg_kaggle_moneylines`
- `stg_kaggle_spreads`
- `stg_kaggle_totals`
- `stg_kaggle_players`
- `stg_kaggle_teams`
- `stg_statsurge_availability`

Do not place raw external rows directly into application tables.

### Quarantine tables

- `external_row_rejections`
- `external_identity_conflicts`
- `external_market_anomalies`

Every rejected row should retain:

- source file;
- source row number;
- reason code;
- raw identity fields;
- raw market fields;
- import run ID.

## 8. Promotion rules

### Injury

Promote only after:

- date parsing;
- schedule/game matching;
- team mapping;
- player resolution or explicit unresolved status;
- source checkpoint semantics;
- early-tip leakage check;
- reason classification.

### Odds

Promote only after:

- game match;
- team match;
- market/selection normalization;
- price validation;
- source timing semantics;
- anomaly checks;
- no duplicate natural grain.

### Game and player stats

Promote only after:

- season eligibility;
- paired game rows;
- canonical game date repair;
- score reconciliation;
- field-level missingness rules;
- regular season/playoff separation;
- no special-event contamination in modeling views.

## 9. Licensing gate

The uploaded CSV files do not include a license or source metadata file.

Before public or commercial use, obtain and store:

- Kaggle dataset license;
- Kaggle data-card description;
- original source/provenance for the market data;
- Stat Surge reuse permission or license;
- attribution requirements;
- raw redistribution restrictions;
- model-training and derived-analysis rights.

“Free to download” is not the same as permission to redistribute raw data.

## 10. Final recommendation

### Proceed

- Preserve the files and hashes.
- Add this evaluation to project sources.
- Acquire the Kaggle metadata/license.
- Ask Stat Surge for clear reuse permission if no explicit license is published.
- After the five foundation phases, implement a staging-only import PR.
- Validate the 2006-07 through 2017-18 range first.
- Begin official injury PDF and forward odds collection separately.

### Do not proceed yet

- Do not load these files directly into production tables.
- Do not use the odds as “closing” without source documentation.
- Do not train a betting model from them before time semantics and anomalies are resolved.
- Do not import all 1950-2018 history merely because it is available.
- Do not pay for the Scottfree dataset at this stage.

The free pack already provides enough historical odds and injury data to justify a careful staging/import project. Paying for another historical dataset is unnecessary unless it fills a verified gap such as 2018-2025 market history with explicit opening/closing semantics and acceptable licensing.

## File hashes

| File | SHA-256 |
|---|---|
| Injury Database - Oct 2021 - June 2024.csv | `efa5413c2cb6b6ee952099d19330b81d00747f2a0368e6986e3587bb0e821164` |
| nba_betting_money_line.csv | `a5c6c8adba3c38e4760f1babebca807f4ca147809d90f45d27cfe203664a3662` |
| nba_betting_spread.csv | `2be5d5834a4ecb2a4df5e44dc942679a9b08458d16a03169c193b1e43e77c40b` |
| nba_betting_totals.csv | `6b7a005dfa6c05aa697268c9d46c5ca7a538476c6589daea7f1cb1735e265c85` |
| nba_games_all.csv | `d0c34fafba78b4b6521be2fb11bdd0d9795905c314174e2a5bb6296bb2972b04` |
| nba_players_all.csv | `ca533fdb79d17a97e2e332dbc6213068ac610c2e91ab11cea94bdbf52f901d43` |
| nba_players_game_stats.csv | `c244d320a33019b199d8659561b70637eb6f162885253808b621b07ae46331e5` |
| nba_teams_all.csv | `608771bd1aec5943d43f20582296798c99e17dec3b54e2d0bc02832b72c3e803` |
