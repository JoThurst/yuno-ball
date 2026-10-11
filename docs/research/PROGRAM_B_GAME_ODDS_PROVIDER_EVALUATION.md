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

## Latest transport check — 2026-09-13

A bounded no-write dry-run was rerun for the 2026-27 current-season scope with
a two-game and ten-observation cap. The configured proxy path still returned
HTTP 403 from the NBA CDN and produced no observations. The result remains a
provider/network failure, not evidence that the slate has no games. No
database rows or ingestion artifacts were written.

## SportsGameOdds feasibility slice — 2026-09-13

The user-provided SportsGameOdds Amateur key is configured locally as
`SPORTSGAMEODDS_API_KEY`; it is not stored in the repository and is never sent
in a URL. The new `app/services/sportsgameodds_client.py` provides a
credential-free request plan, a header-authenticated client, and a provider
shape normalizer. It requires an explicit live-probe opt-in, permits one
bounded request of at most 25 events, performs no Yuno Ball writes, and keeps
SportsGameOdds team IDs unresolved until a separate identity gate passes.

The probe script is `scripts/probe_sportsgameodds.py`. With no flags it emits a
plan and performs zero network requests. `--live-probe` is intentionally a
separate operator action and is not scheduled. The normalizer accepts
game-level moneyline, spread, and total markets, retains bookmaker timestamps,
and excludes player props and non-game periods from this first pilot.

### Controlled live probe result — 2026-09-13

The explicitly authorized probe made exactly one read-only `GET /v2/events`
request with `leagueID=NBA`, `finalized=false`, `oddsAvailable=true`, and
`limit=1`. It returned HTTP 200 with one event; one event normalized; both
provider teams and the start time were present; ten game-market rows and 48
bookmaker rows were retained; all 48 bookmaker rows carried a provider update
timestamp. The response included a next cursor, which was not followed. No
database, file, apply, or scheduler writes occurred.

This clears transport and documented response-shape feasibility with high
confidence for the observed event. It does not clear source approval: provider
team IDs still require canonical identity mapping, multi-market pair
completeness needs a broader bounded review, and licensing/coverage/plan
semantics remain open. No Daily market claim should be published from this
probe alone.

The local fixture pair reviewer now counts spread and total pairs as complete
only when both selections have finite lines; spread sides must be reciprocal.
An unlined, non-finite, or same-sign spread remains incomplete in the review
counts. This is a fixture-only validation rule, not provider identity
resolution or approval for collection.

This slice establishes transport and schema feasibility, not source approval.
Before any apply or schedule decision, record one bounded response, map
provider teams to canonical IDs, verify pair completeness and timestamp
precision, and review licensing/coverage. Historical odds remain out of scope.

## Alternate-provider shortlist — research only

Two candidates now have enough documented shape for a bounded forward-only
evaluation. Neither is approved, integrated, or configured with credentials.

| Candidate | Useful fit | Open gate |
| --- | --- | --- |
| [The Odds API NBA docs](https://the-odds-api.com/sports/nba-odds.html) | Current/upcoming NBA moneyline, spread, and total markets; responses expose bookmaker `last_update` timestamps; a free current-data plan is documented | Verify free-plan quota, US-book coverage, licensing, pair completeness, and whether timestamps meet our observation contract |
| [SportsGameOdds docs](https://sportsgameodds.com/docs) | NBA event/odds/bookmaker model, filtered event queries, batching guidance, and official SDK path | Verify plan limits, commercial rights, timestamp precision, US-book coverage, and replay behavior |

The lowest-risk next experiment is a credential-free adapter contract test plus
a single bounded forward dry-run if a user-provided key becomes available. The
historical odds capability documented by The Odds API is paid, so it should not
be treated as a free route to reconstructing old closing lines. Until one
candidate passes the source, licensing, timestamp, and coverage gates, Daily
must continue to show no market claims.
