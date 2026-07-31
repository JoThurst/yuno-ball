# Yuno Ball Metric Experiment Plan

Status: proposed research specification  
Prepared: 2026-07-15

## Purpose

Define how a Yuno metric moves from an idea to an approved product contract.

## Metric lifecycle

1. Product question
2. Hypothesis
3. Required observation grain
4. Source and coverage audit
5. Formula candidates
6. Leakage and timestamp audit
7. Retrospective experiment
8. Stability and sensitivity analysis
9. User-language prototype
10. Shadow production
11. Approval gate
12. Versioned production
13. Ongoing monitoring

## Approval requirements

Every metric must specify:

- metric ID;
- version;
- formula;
- grain;
- source fields;
- required history;
- feature cutoff;
- interpretation;
- uncertainty;
- completeness;
- prohibited uses;
- validation range;
- update cadence;
- consumers.

## Experiment 1 — Yuno Slate Score

### Product question

Which games deserve a fan's attention today?

### Candidate components

- team strength;
- projected competitiveness;
- standings leverage;
- recent-form divergence;
- schedule disadvantage;
- availability uncertainty;
- style contrast;
- prediction uncertainty;
- market/model disagreement when available.

### Research design

Compare components against:

- close-game rate;
- lead changes;
- standings consequences;
- user clicks;
- time on matchup page;
- social engagement;
- editor selections.

Do not optimize only for close final scores.

### Output contract

- 0-100 score;
- component values;
- top three reasons;
- missing components;
- version;
- as-of;
- confidence tier.

## Experiment 2 — Form Quality Index

### Product question

Is recent team performance genuine or mostly schedule-driven?

### Candidate calculation

- recency-weighted net rating;
- opponent strength known before each game;
- home/away adjustment;
- rest adjustment;
- expected-versus-actual performance;
- sample-size shrinkage.

### Baselines

- raw last-5 net rating;
- raw last-10 net rating;
- season-to-date net rating.

### Evaluation

- future 5-game performance;
- future 10-game performance;
- stability by season;
- behavior after roster changes;
- sensitivity to window and decay.

## Experiment 3 — Schedule Pressure Index

### Product question

How much schedule stress enters the game?

### Components

- rest days;
- back-to-back;
- 3-in-4;
- 4-in-6;
- road trip length;
- travel distance proxy;
- timezone change;
- overtime in previous game;
- rest differential;
- consecutive road games.

### Output

- pressure score;
- component flags;
- opponent-relative edge;
- missing travel semantics.

Do not imply causal certainty.

## Experiment 4 — Style Collision Map

### Product question

Where do team tendencies interact most strongly?

### Candidate edges

- rim frequency versus rim allowance;
- three-point rate versus three-point allowance;
- offensive rebound versus defensive rebound;
- turnover creation versus ball security;
- free-throw pressure versus foul rate;
- transition frequency versus transition defense;
- assisted scoring versus opponent creation denial;
- pace preference interaction.

### Output

For each edge:

- home value;
- away/opponent value;
- league percentile;
- expected direction;
- strength;
- confidence;
- deterministic explanation.

## Experiment 5 — Rotation Shock

### Product question

How much does current availability disrupt expected roles?

### Inputs

- official status;
- expected minutes;
- recent usage;
- starting frequency;
- creation share;
- lineup continuity;
- replacement quality;
- status uncertainty.

### Outputs

- expected minutes unavailable;
- expected usage unavailable;
- creation burden shift;
- role-change count;
- rotation continuity loss;
- replacement uncertainty.

Historical rows without exact report time must be labeled checkpoint quality.

## Experiment 6 — Role Stability

### Product question

How predictable is a player's role entering the game?

### Components

- minutes median and dispersion;
- starting consistency;
- usage dispersion;
- attempt-share dispersion;
- teammate availability;
- games since role change;
- recent substitution pattern.

Do not call production “consistent” when only minutes are stable.

## Experiment 7 — Availability Uncertainty

### Product question

How likely is the available rotation to change before tip?

### Components

- questionable/doubtful players;
- expected minutes attached to uncertain players;
- lateness of latest report;
- team submission status;
- minutes until tip.

No probability should be published until calibrated.

## Experiment 8 — Market Disagreement

### Product question

How much do books disagree at a declared timestamp?

### Inputs

- comparable sportsbook observations;
- same market;
- same selection;
- same pregame window.

### Outputs

- consensus line;
- median price;
- range;
- dispersion;
- missing-book count.

Unknown-time historical odds cannot be used for live disagreement products.

## Experiment record template

Each experiment produces:

- research question;
- dataset versions;
- date range;
- inclusion/exclusion criteria;
- formula candidates;
- baseline;
- evaluation metrics;
- result by season;
- sensitivity;
- failure modes;
- recommended version;
- go/no-go;
- next data requirement.
