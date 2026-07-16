# Kaggle Market Reconciliation Report

Status: generated from a read-only PostgreSQL transaction; no market or canonical rows changed
Generated (UTC): 2026-07-16T16:34:48.997087+00:00

## Technical summary

- Eligible staged market rows evaluated: 387,524
- Exact canonical identity matches: 95,516
- Rows whose canonical game is missing: 292,008
- Canonical incomplete rows: 0
- Identity conflicts: 0

Historical snapshots retain `timing_precision = unknown` and `snapshot_type = historical_static`. Identity reconciliation does not make them opening, closing, or prediction-time observations.

## Coverage by market and season type

| Market | Season type | Rows | Games | Matched rows | Missing rows | Conflicts |
|---|---|---:|---:|---:|---:|---:|
| moneyline | Playoffs | 8,569 | 997 | 8,569 | 0 | 0 |
| moneyline | Regular Season | 116,548 | 13,877 | 23,013 | 93,535 | 0 |
| spread | Playoffs | 8,859 | 996 | 8,859 | 0 | 0 |
| spread | Regular Season | 122,572 | 13,886 | 23,078 | 99,494 | 0 |
| total | Playoffs | 8,890 | 995 | 8,890 | 0 | 0 |
| total | Regular Season | 122,086 | 13,891 | 23,107 | 98,979 | 0 |

## Game coverage against the eligible source schedule

| Market | Season type | Eligible source games | Games with market rows | Games without market rows |
|---|---|---:|---:|---:|
| moneyline | Regular Season | 14,519 | 13,877 | 642 |
| moneyline | Playoffs | 999 | 997 | 2 |
| spread | Regular Season | 14,519 | 13,886 | 633 |
| spread | Playoffs | 999 | 996 | 3 |
| total | Regular Season | 14,519 | 13,891 | 628 |
| total | Playoffs | 999 | 995 | 4 |

## Coverage by source season

| Market | Season | Season type | Rows | Games | Matched | Canonical missing | Conflicts |
|---|---|---|---:|---:|---:|---:|---:|
| moneyline | 2006-07 | Playoffs | 439 | 78 | 439 | 0 | 0 |
| moneyline | 2006-07 | Regular Season | 4,376 | 1,126 | 0 | 4,376 | 0 |
| moneyline | 2007-08 | Playoffs | 569 | 86 | 569 | 0 | 0 |
| moneyline | 2007-08 | Regular Season | 7,120 | 1,135 | 0 | 7,120 | 0 |
| moneyline | 2008-09 | Playoffs | 628 | 85 | 628 | 0 | 0 |
| moneyline | 2008-09 | Regular Season | 8,503 | 1,184 | 0 | 8,503 | 0 |
| moneyline | 2009-10 | Playoffs | 583 | 81 | 583 | 0 | 0 |
| moneyline | 2009-10 | Regular Season | 8,667 | 1,188 | 0 | 8,667 | 0 |
| moneyline | 2010-11 | Playoffs | 648 | 81 | 648 | 0 | 0 |
| moneyline | 2010-11 | Regular Season | 9,333 | 1,132 | 0 | 9,333 | 0 |
| moneyline | 2011-12 | Playoffs | 817 | 84 | 817 | 0 | 0 |
| moneyline | 2011-12 | Regular Season | 9,570 | 990 | 0 | 9,570 | 0 |
| moneyline | 2012-13 | Playoffs | 775 | 85 | 775 | 0 | 0 |
| moneyline | 2012-13 | Regular Season | 11,654 | 1,217 | 0 | 11,654 | 0 |
| moneyline | 2013-14 | Playoffs | 877 | 89 | 877 | 0 | 0 |
| moneyline | 2013-14 | Regular Season | 11,431 | 1,201 | 0 | 11,431 | 0 |
| moneyline | 2014-15 | Playoffs | 792 | 81 | 792 | 0 | 0 |
| moneyline | 2014-15 | Regular Season | 11,472 | 1,202 | 0 | 11,472 | 0 |
| moneyline | 2015-16 | Playoffs | 831 | 86 | 831 | 0 | 0 |
| moneyline | 2015-16 | Regular Season | 11,409 | 1,191 | 0 | 11,409 | 0 |
| moneyline | 2016-17 | Playoffs | 790 | 79 | 790 | 0 | 0 |
| moneyline | 2016-17 | Regular Season | 11,780 | 1,185 | 11,780 | 0 | 0 |
| moneyline | 2017-18 | Playoffs | 820 | 82 | 820 | 0 | 0 |
| moneyline | 2017-18 | Regular Season | 11,233 | 1,126 | 11,233 | 0 | 0 |
| spread | 2006-07 | Playoffs | 466 | 77 | 466 | 0 | 0 |
| spread | 2006-07 | Regular Season | 4,681 | 1,126 | 0 | 4,681 | 0 |
| spread | 2007-08 | Playoffs | 597 | 86 | 597 | 0 | 0 |
| spread | 2007-08 | Regular Season | 7,870 | 1,135 | 0 | 7,870 | 0 |
| spread | 2008-09 | Playoffs | 679 | 85 | 679 | 0 | 0 |
| spread | 2008-09 | Regular Season | 9,448 | 1,184 | 0 | 9,448 | 0 |
| spread | 2009-10 | Playoffs | 627 | 81 | 627 | 0 | 0 |
| spread | 2009-10 | Regular Season | 9,489 | 1,188 | 0 | 9,489 | 0 |
| spread | 2010-11 | Playoffs | 668 | 81 | 668 | 0 | 0 |
| spread | 2010-11 | Regular Season | 10,128 | 1,134 | 0 | 10,128 | 0 |
| spread | 2011-12 | Playoffs | 840 | 84 | 840 | 0 | 0 |
| spread | 2011-12 | Regular Season | 9,895 | 990 | 0 | 9,895 | 0 |
| spread | 2012-13 | Playoffs | 812 | 85 | 812 | 0 | 0 |
| spread | 2012-13 | Regular Season | 12,090 | 1,217 | 0 | 12,090 | 0 |
| spread | 2013-14 | Playoffs | 890 | 89 | 890 | 0 | 0 |
| spread | 2013-14 | Regular Season | 12,003 | 1,211 | 0 | 12,003 | 0 |
| spread | 2014-15 | Playoffs | 810 | 81 | 810 | 0 | 0 |
| spread | 2014-15 | Regular Season | 11,981 | 1,202 | 0 | 11,981 | 0 |
| spread | 2015-16 | Playoffs | 860 | 86 | 860 | 0 | 0 |
| spread | 2015-16 | Regular Season | 11,909 | 1,191 | 0 | 11,909 | 0 |
| spread | 2016-17 | Playoffs | 790 | 79 | 790 | 0 | 0 |
| spread | 2016-17 | Regular Season | 11,818 | 1,182 | 11,818 | 0 | 0 |
| spread | 2017-18 | Playoffs | 820 | 82 | 820 | 0 | 0 |
| spread | 2017-18 | Regular Season | 11,260 | 1,126 | 11,260 | 0 | 0 |
| total | 2006-07 | Playoffs | 467 | 77 | 467 | 0 | 0 |
| total | 2006-07 | Regular Season | 4,552 | 1,126 | 0 | 4,552 | 0 |
| total | 2007-08 | Playoffs | 599 | 86 | 599 | 0 | 0 |
| total | 2007-08 | Regular Season | 7,869 | 1,135 | 0 | 7,869 | 0 |
| total | 2008-09 | Playoffs | 671 | 84 | 671 | 0 | 0 |
| total | 2008-09 | Regular Season | 9,469 | 1,187 | 0 | 9,469 | 0 |
| total | 2009-10 | Playoffs | 626 | 81 | 626 | 0 | 0 |
| total | 2009-10 | Regular Season | 9,483 | 1,188 | 0 | 9,483 | 0 |
| total | 2010-11 | Playoffs | 668 | 81 | 668 | 0 | 0 |
| total | 2010-11 | Regular Season | 10,113 | 1,132 | 0 | 10,113 | 0 |
| total | 2011-12 | Playoffs | 840 | 84 | 840 | 0 | 0 |
| total | 2011-12 | Regular Season | 9,625 | 990 | 0 | 9,625 | 0 |
| total | 2012-13 | Playoffs | 849 | 85 | 849 | 0 | 0 |
| total | 2012-13 | Regular Season | 12,079 | 1,217 | 0 | 12,079 | 0 |
| total | 2013-14 | Playoffs | 890 | 89 | 890 | 0 | 0 |
| total | 2013-14 | Regular Season | 12,001 | 1,211 | 0 | 12,001 | 0 |
| total | 2014-15 | Playoffs | 810 | 81 | 810 | 0 | 0 |
| total | 2014-15 | Regular Season | 11,967 | 1,202 | 0 | 11,967 | 0 |
| total | 2015-16 | Playoffs | 860 | 86 | 860 | 0 | 0 |
| total | 2015-16 | Regular Season | 11,821 | 1,192 | 0 | 11,821 | 0 |
| total | 2016-17 | Playoffs | 790 | 79 | 790 | 0 | 0 |
| total | 2016-17 | Regular Season | 11,849 | 1,185 | 11,849 | 0 | 0 |
| total | 2017-18 | Playoffs | 820 | 82 | 820 | 0 | 0 |
| total | 2017-18 | Regular Season | 11,258 | 1,126 | 11,258 | 0 | 0 |

## Interpretation and next gate

Playoff market identity can be promoted independently because the eligible playoff schedule set is now canonical. Regular-season market rows whose games remain absent must stay staged; they are not invalid market observations.

Before promotion, approve a canonical append-only market-observation grain, retain the source manifest/run/row/parser chain, preserve selection-specific spread/total pairs, and define source precedence without overwriting either historical or future observations.
