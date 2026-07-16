# Stat Surge Identity Reconciliation Report

Status: apply identity reconciliation evidence

## Technical summary

- Source rows: 35,522
- Fully identity-resolved: 35,234
- Partially resolved: 288
- Conflicts: 0
- Database rows changed: 35,522

All rows retain `cutoff_status = unknown`: the source supplies a methodology-level daily 2 p.m. checkpoint but no exact publication timestamp, and matched schedules are date-only. Identity resolution does not make these strict pregame features.

## Coverage by season

| Season | Rows | Resolved | Partial | Player resolved | Game resolved |
|---|---:|---:|---:|---:|---:|
| 2021-22 | 11,933 | 11,752 | 181 | 11,783 | 11,902 |
| 2022-23 | 11,100 | 11,073 | 27 | 11,073 | 11,100 |
| 2023-24 | 12,489 | 12,409 | 80 | 12,409 | 12,489 |

## Unresolved player names

| Reported player | Rows |
|---|---:|
| Smith, Chris | 74 |
| Poeltl, Jakob | 61 |
| Bediako, Charles | 26 |
| Hommes, Daulton | 25 |
| Bullock, Reggie | 23 |
| Rice, Sir'Jabari | 19 |
| Dowtin, Jeff | 17 |
| Tillman, Justin | 3 |
| Ellison, Malik | 2 |
| Holman, Aric | 2 |
| Martin Jr., Kenyon | 2 |
| Kinsey, Taevion | 1 |
| Tubelis, Azuolas | 1 |
| Williams, Jeenathan | 1 |

## Interpretation

Resolution uses exact team names plus one reviewed franchise alias, strict matchup/date team pairs, and a unique punctuation-insensitive player-name key. No fuzzy or probabilistic player match is accepted. Unresolved names and cancelled/postponed games remain staged and queryable; no canonical availability rows or public behavior are created.
