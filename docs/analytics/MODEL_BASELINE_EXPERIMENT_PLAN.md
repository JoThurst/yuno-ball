# Yuno Ball Baseline Model Experiment Plan

Status: proposed modeling specification  
Prepared: 2026-07-15

## Objective

Establish trustworthy baseline models for:

1. home-team win probability;
2. expected home margin;
3. expected game total.

## Observation grain

One row per game, with home and away features calculated strictly before scheduled tipoff.

## Labels

After final status:

- `home_win`
- `home_margin`
- `game_total`

Exclude:

- unfinished games;
- postponed games without resolved tip semantics;
- special-event teams;
- rows missing a valid home/away pair;
- rows whose features include target-game information.

## Feature families

### Team strength

- season-to-date ratings rebuilt from prior games;
- stable previous-season prior;
- games played;
- home/away splits only after sample threshold.

### Recent form

- last 5/10/20;
- exponentially weighted variants;
- shifted one game;
- opponent adjusted.

### Schedule

- rest days;
- back-to-back;
- 3-in-4;
- 4-in-6;
- rest differential;
- travel proxy.

### Matchup

- pace interaction;
- shooting profile interaction;
- rebound edge;
- turnover edge;
- free-throw edge.

### Availability

Only after source and role history are adequate:

- expected minutes unavailable;
- usage unavailable;
- uncertainty;
- continuity.

## Baselines

### Win

- historical home win rate;
- Elo-style rating;
- logistic regression.

### Margin

- historical home-court mean;
- ridge regression.

### Total

- trailing league mean;
- ridge regression.

## Candidate models

Only after baselines:

- gradient boosting;
- calibrated boosted classifier;
- quantile or conformal intervals where justified.

## Evaluation

Use chronological splits.

### Win metrics

- log loss;
- Brier score;
- ROC AUC;
- calibration error;
- reliability diagram.

### Margin and total metrics

- MAE;
- RMSE;
- residual distribution;
- interval coverage.

Break down by:

- season;
- team;
- month;
- rest bucket;
- missing-input state;
- availability uncertainty;
- early versus mature season.

## Ablation plan

Train/evaluate:

1. strength only;
2. strength + form;
3. + schedule;
4. + matchup;
5. + availability;
6. full model.

Also remove each feature family from the full model.

## Leakage tests

- target game absent from rolling window;
- feature timestamp before tip;
- current endpoint aggregate forbidden for historical rows;
- both team perspectives remain in the same fold;
- preprocessing fitted only on training data;
- market data after prediction time forbidden;
- later games cannot change an old snapshot under the same version.

## Calibration

Test:

- logistic/Platt calibration;
- isotonic calibration when sample supports it;
- calibration by season and confidence bucket;
- degradation under incomplete inputs.

## Prediction storage

Every record includes:

- game ID;
- scheduled tip;
- model version;
- feature version;
- training cutoff;
- prediction timestamp;
- win probability;
- expected margin;
- expected total;
- uncertainty;
- completeness;
- fallback path;
- revision parent.

Never overwrite a published prediction.

## Production gate

- multiple chronological test windows;
- naive baseline beaten;
- acceptable calibration;
- stable feature availability;
- immutable storage;
- monitoring;
- UI limitations written;
- no betting-value language.

## Postgame review

Publish:

- predicted versus actual;
- confidence bucket result;
- major unavailable inputs;
- revision history;
- model version;
- aggregate calibration dashboard.

The review page should include misses, not only wins.
