# Yuno Ball Source Evaluation Matrix

Status: research template with current candidates  
Prepared: 2026-07-15

## Evaluation fields

For each source record:

- source name;
- provider;
- endpoint/file;
- business purpose;
- natural grain;
- source timestamp;
- availability timestamp;
- historical range;
- refresh cadence;
- expected latency;
- observed failure rate;
- schema stability;
- identity quality;
- correction behavior;
- raw retention;
- commercial rights;
- redistribution rights;
- model-training rights;
- cost;
- owner;
- current status.

## Status values

- approved_core
- approved_secondary
- staging_only
- experimental
- historical_bridge
- rejected
- needs_license
- needs_semantic_validation

## Current candidates

| Source | Purpose | Grain | Historical range | Current assessment |
|---|---|---|---|---|
| Official NBA injury PDFs | Pregame availability revisions | report document and player status revision | current season; historical retention unknown | approved source spike |
| Stat Surge injury archive | Daily availability checkpoint bridge | date/game/team/player | 2021-22 to 2023-24 | historical bridge; needs permission |
| Kaggle moneyline | Historical book market | game/book/team selection | 2006-07 to 2017-18 | staging only; timing unknown |
| Kaggle spread | Historical book market | game/book/team selection | 2006-07 to 2017-18 | staging only; anomalies quarantined |
| Kaggle totals | Historical over/under market | game/book/selection | 2006-07 to 2017-18 | staging only; malformed rows exist |
| Kaggle games | Historical game facts | game/team perspective | 1950-51 to partial 2018-19 | validation/support; selective import |
| Kaggle player games | Historical player boxes | game/player | 1950-51 to 2017-18 | selective import |
| NBA box-score V3 endpoints | Current detailed game facts | game/player or game/team | endpoint dependent | bake-off required |
| Live timestamped odds provider | Current market observations | event/book/market/selection/time | provider dependent | vendor research required |
| Play-by-play V3 | Possession and substitution facts | event | endpoint dependent | later-stage bake-off |
| pbpstats | Possession/lineup transformation | derived event/possession/stint | source dependent | experimental parser candidate |

## Source score

Score 0-3 on:

- provenance;
- license clarity;
- grain clarity;
- timestamp semantics;
- identity;
- coverage;
- missingness;
- correction handling;
- schema stability;
- cost;
- commercial suitability.

No source can be `approved_core` with a zero in provenance, license, grain, timestamp, or identity.

## Source trial report

Every trial reports:

- sample selection;
- success rate;
- latency;
- empty responses;
- field missingness;
- identity resolution;
- duplicates;
- corrections;
- schema drift;
- storage estimate;
- legal status;
- recommendation.
