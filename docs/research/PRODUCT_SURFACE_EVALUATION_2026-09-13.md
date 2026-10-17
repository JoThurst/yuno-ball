# Yuno Ball Product Surface Evaluation

Status: review baseline for the public product direction  
Reviewed: 2026-10-10

## Executive read

Yuno Ball has a credible public descriptive product in Daily Intelligence V1,
but the product is not finished if the user still has to translate internal
analytics into an answer. The product question is:

> Which games deserve my attention today, what is changing, why does it matter,
> and how much should I trust the evidence?

Daily and the date-scoped matchup page are the right spine. Players, Teams,
Games, the old matchup flow, and the player dashboard remain useful data and
research surfaces, but they should support that spine rather than compete with
it as separate generic destinations.

## Surface decisions

| Surface | Decision | Product role |
| --- | --- | --- |
| `/daily/` and `/daily/YYYY-MM-DD` | Keep and deepen | Primary editorial answer to “what matters today?” |
| `/matchup/YYYY-MM-DD/AWAY-HOME` | Keep and deepen | Decision workspace for one game; explain the evidence in plain language |
| `/daily/archive` | Keep | Historical index and revisitable content library |
| Players | Keep, reframe | Supporting context linked from Daily and Matchup; emphasize “why this player matters here” |
| Teams | Keep, reframe | Date-aware team context; avoid a generic stats-first profile |
| Games | Keep as archive/lookup | `/games` is the retrieval destination for completed and scheduled game dates; it supports, rather than replaces, Daily |
| Old matchup system | Retire / redirect | Preserve links, but route new product behavior through the date-scoped matchup contract |
| Player dashboard | Rework | `/dashboard/` is now a read-only internal research and data-quality console |
| `/home` and generic dashboards | Reconciled | `/home` redirects to Daily; generic chart, streak, and duplicate matchup paths redirect or are retired |
| Betting | Visible experimental pilot | Keep available to the intended betting/fantasy audience, but label it observation-only until identity, coverage, timestamp, and licensing gates pass |

Do not delete legacy routes during this review. Freeze them behind redirects or
clear internal ownership, and preserve historical links while the replacement
surfaces are proven.

## Availability finding

The 2025–26 data contains official availability evidence. On the April 12,
2025 historical slate, the running Daily API returned 15 games and 28 of 30
team reports complete. The aggregate listed statuses were 131 Out, 14
Doubtful, 27 Questionable, and 5 Probable. The evidence carries a report
timestamp and is selected at the scheduled-tipoff cutoff.

The previous UI obscured this in two ways:

1. Daily displayed only unresolved counts, so a game with several listed Out
   or Questionable players could appear as `0` availability issues.
2. Matchup attempted to count `observations` from a summarized object that did
   not contain the rows, producing a false “0 records attached” impression.

The current contract preserves safe player/status/reason rows in the summary
and adds a human readout for each team: listed counts, report completeness,
unresolved identity, and cutoff language. Missing evidence remains “unknown”;
it is never presented as a clean bill of health.

## Readability standard for Daily and Matchup

Every prominent signal should answer four things in order:

1. **What is it?** Use “Availability,” “Recent form,” “Schedule,” and “Pace,”
   not internal enum names.
2. **What happened?** State the observed value or listed status directly.
3. **Why does it matter?** Use one short descriptive sentence; do not imply a
   causal or predictive conclusion the evidence cannot support.
4. **How sure are we?** Show source, as-of time, completeness, and unresolved
   state adjacent to the claim.

Avoid asking the reader to decode:

- `home availability uncertainty`;
- `three_in_four` or `five_in_seven`;
- raw priority values without the reason;
- `derived_from_slate` as a user-facing source label;
- a missing value that looks like zero.

## Next product slice

The next coherent slice is an editorial layer on top of the stable Daily V1
contract, implemented in the design lab first and then promoted only after
review:

- one sentence explaining the slate’s central story;
- three games first, each with “why this matters”;
- a plain-language availability block;
- evidence cards with source and cutoff;
- an explicit “what could change this read” state;
- a historical follow-up link after the game.

This gives the product a recognizable editorial voice without publishing
unsupported predictions or collapsing descriptive context into betting advice.

## Open gates

- Forward-looking prediction publication remains blocked by timing,
  calibration, immutable model history, and consumer approval.
- Odds remain an observation pilot until canonical identity, complete pairs,
  timestamp precision, coverage, and licensing are approved.
- Preseason is now underway externally, but the repository snapshot contains
  no `Pre Season` schedule rows and the current C7 bridge is Regular Season-only.
  The bridge remains waiting on the first eligible completed Regular Season
  game; preseason should only be added through a separate event-type contract.
- The Daily editorial layer still needs its next content pass; the route-diet
  implementation is now in place and should be verified against live links.
