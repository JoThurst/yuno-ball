# Daily Intelligence V1 mockup review

These are isolated, static design directions. They use the same representative V1 shapes and observed values from the existing lab/API package: a historical package with 9 games and 58 insights; HOU at IND with pace 102.8, scoring environment 101.4, IND form delta +3.7, and 5 flagged availability records with 0 unresolved. Prediction and market values remain unavailable. The current 2026–27 state is represented as an honest empty/blocked package with zero games and zero insights.

## Directions

- `editorial-magazine.html` — the strongest candidate for the primary fan experience. It makes the explanation itself feel valuable, gives freshness a prominent editorial byline, and avoids dashboard sameness. The hierarchy is calm enough for a daily habit and still supports evidence detail.
- `command-center-telemetry.html` — best for internal QA, analyst workflows, and an eventual operations surface. It makes contract, completeness, freshness, and unresolved inputs scannable, but would feel too clinical as the default fan page.
- `cinematic-game-night.html` — best for an evening or matchup-led mode. It creates emotional pull and a memorable “open this game” moment, but needs the editorial direction’s provenance discipline before production use.

## Recommendation

Use the editorial direction as the base layout. Borrow the command center’s compact audit rail for freshness, completeness, source, and null-state metadata. Borrow the cinematic direction’s single-matchup spotlight, large type, and game-night atmosphere for the top-ranked card or a matchup detail route.

## Integration recommendations

1. Keep the existing V1 payload and production route unchanged; map named fields into presentation components rather than creating a presentation-specific contract.
2. Make the first screen answer “what should I open?” with ranked games, then “why?” with deterministic explanation cards.
3. Keep `freshness.status`, `freshness.explanation`, team/player completeness, source, `as_of`, and prediction/market nulls visible at card or section level.
4. Treat current-season empty data as a designed state: retain the page identity, show the evidence gate, and never reuse historical metrics in the current view.
5. Use permanent dated URLs when the lab graduates: `/daily/YYYY-MM-DD` and `/matchup/YYYY-MM-DD/away-home`.
6. Before production integration, add responsive QA at mobile width, keyboard/focus states, real team marks, and tests for available, stale/unknown, partial, and blocked packages.

## Verification

- Confirmed all three files are static, isolated under `docs/research/design_lab_mockups/`.
- Confirmed no production routes, services, templates, CSS, or the existing Daily V1 lab were modified by this review.
- Confirmed every numeric value in the mockups is labeled as representative V1 package data or a truthful blocked-state count; no prediction or market metric was invented.
