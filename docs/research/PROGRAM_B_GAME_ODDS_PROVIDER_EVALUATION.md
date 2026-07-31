# Program B Game-Odds Provider Evaluation

Status: bounded evaluation result; provider not yet approved  
Evaluated: 2026-07-24  
Scope: NBA game markets only; moneyline, spread, and total

## Candidate evaluated

The existing `nba_api.live.nba.endpoints.odds.Odds` integration targets the NBA
live odds document at `cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json`.
The repository already has an approved shared network path for NBA calls. The
new bounded collector now uses that path and converts one response into
append-only market-observation payloads without writing `game_odds`.

## Result

The provider is not approved for collection yet.

- Direct request: CDN returned HTTP 403 with a non-JSON response.
- Configured proxy request: CDN redirected through `www.nba.com` and
  `stats.nba.com` error routes until the client stopped at the redirect limit.
- Dry-run result: zero observations; no database or file writes.
- No conclusion was drawn that today has no games. This is a provider/network
  failure, not an empty-slate result.

## Implementation status

- `nba_live_market_observation_headers` and
  `market_observation_selections` are the durable append-only target.
- `scripts/collect_nba_live_market_observations.py` supports bounded
  `--dry-run` and `--apply` modes, explicit current-Eastern-date scope, US-book
  filtering, observation limits, and ingestion-run lineage on apply.
- `app/services/nba_live_market_observation_adapter.py` supports game
  moneyline, spread, and total payloads. Retrieval time is recorded as the
  observation time when the provider supplies no stronger line timestamp.
- The mutable `game_odds` writer remains untouched.

## Gate before apply

Do not schedule or apply this collector until one of the following is complete:

1. Repair and revalidate the NBA live endpoint/network route, including a
   successful bounded dry-run with game, sportsbook, market, selection, and
   timestamp counts; or
2. Select a replacement provider and document licensing, coverage, timestamp
   precision, cost, schema, and replay behavior.
