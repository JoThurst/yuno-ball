# Release 1 External Data Coverage Report

Status: Release 1 — External Data Staging complete in the local branch and local PostgreSQL database; not yet committed, merged, or deployed
Generated (UTC): 2026-07-16T16:46:30.715862+00:00

## Technical summary

Release 1 now has immutable manifests, source-specific staging, quarantine partitions, deterministic identity reconciliation, documented source precedence, provenance-preserving bounded promotion, and no public consumer. Historical market timing and Stat Surge cutoff timing remain explicitly unknown rather than being inferred.

## Registered source artifacts

| Dataset | Source | Inspected rows | License | Commercial use | Validation |
|---|---|---:|---|---|---|
| nba-injury-daily-checkpoints | stat-surge | 35,522 | approved_public | permitted | registered |
| nba-moneyline-observations | kaggle-uploaded-pack | 125,286 | approved_public | permitted | registered |
| nba-player-game-facts | kaggle-uploaded-pack | 1,268,211 | approved_public | permitted | registered |
| nba-player-identities | kaggle-uploaded-pack | 4,885 | approved_public | permitted | registered |
| nba-spread-observations | kaggle-uploaded-pack | 131,690 | approved_public | permitted | registered |
| nba-team-game-facts | kaggle-uploaded-pack | 125,624 | approved_public | permitted | registered |
| nba-team-identities | kaggle-uploaded-pack | 69 | approved_public | permitted | registered |
| nba-total-observations | kaggle-uploaded-pack | 131,386 | approved_public | permitted | registered |

## Staging coverage

| Dataset | Staged rows | Distinct dates or games |
|---|---:|---:|
| Kaggle moneylines | 125,284 | 14,906 |
| Kaggle spreads | 131,687 | 14,914 |
| Kaggle team games | 125,624 | 62,812 |
| Kaggle totals | 131,218 | 14,918 |
| Stat Surge checkpoints | 35,522 | 628 |

## Stat Surge identity coverage

| Season | Rows | Fully identity-resolved | Partial | Player unresolved | Game unresolved | Cutoff unknown |
|---|---:|---:|---:|---:|---:|---:|
| 2021-22 | 11,933 | 11,752 | 181 | 150 | 31 | 11,933 |
| 2022-23 | 11,100 | 11,073 | 27 | 27 | 0 | 11,100 |
| 2023-24 | 12,489 | 12,409 | 80 | 80 | 0 | 12,489 |

## Eligible game coverage

| Season type | Source games | Canonical games | Canonical missing |
|---|---:|---:|---:|
| Playoffs | 999 | 999 | 0 |
| Regular Season | 14,519 | 2,460 | 12,059 |

The bounded playoff promotion inserted 838 previously missing games / 1,676 reciprocal rows with manifest, run, row, hash, and parser lineage. Missing regular-season games remain staged and are not a Release 1 blocker.

## Eligible market identity coverage

| Market | Season type | Rows | Games | Exact canonical matches | Canonical missing | Conflicts |
|---|---|---:|---:|---:|---:|---:|
| moneyline | Playoffs | 8,569 | 997 | 8,569 | 0 | 0 |
| moneyline | Regular Season | 116,548 | 13,877 | 23,013 | 93,535 | 0 |
| spread | Playoffs | 8,859 | 996 | 8,859 | 0 | 0 |
| spread | Regular Season | 122,572 | 13,886 | 23,078 | 99,494 | 0 |
| total | Playoffs | 8,890 | 995 | 8,890 | 0 | 0 |
| total | Regular Season | 122,086 | 13,891 | 23,107 | 98,979 | 0 |

## Quarantine and partition results

- Market semantic anomalies: 173
- Parser row rejections: 0
- Selection-specific spread and total pairs remain source-shaped; they were not normalized away.

## Release 1 exit gate

| Gate | Local status | Evidence |
|---|---|---|
| Import manifests | Complete | Eight immutable artifact registrations with hashes and permissions |
| Staging tables | Complete | Injury, team-game, moneyline, spread, total, rejection, and anomaly tables |
| Injury and odds profiles | Complete | Source semantics, season coverage, missingness, and timing limitations are reported |
| Identity reconciliation | Complete for Release 1 | Exact game/market audit plus versioned Stat Surge staging identity outcomes |
| Quarantine rules | Complete | Malformed and declared semantic anomaly partitions are queryable |
| Source precedence | Complete | Field-specific non-destructive rules in `ANALYTICS_ARCHITECTURE_CONTRACT.md` |
| No public behavior change | Complete | No route, cache, model, or serving consumer was added |

## Intentional deferrals

- Canonical market-observation promotion waits for a separate append-only header/selection contract. `game_odds` is not a safe target.
- Stat Surge canonical availability promotion waits for stronger cutoff semantics; all rows remain staging-only and cutoff-unknown.
- Fourteen unresolved player names and two missing/cancelled source games remain queryable rather than fuzzily matched.
- Promotion of 12,059 missing eligible regular-season games and 363 audited date repairs is a separate high-volume phase.
- Full player-game and identity-file relational staging is deferred to broader Program A work; it is not required for Release 1's no-public-behavior staging boundary.
- Official injury PDF collection, forward timestamped odds, and box-score endpoint bake-offs begin later roadmap milestones.
