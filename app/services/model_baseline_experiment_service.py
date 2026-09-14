"""Read-only chronological naive baselines for Program G.

The experiment consumes already-audited, one-row-per-game observations. It
does not persist predictions and never uses the current row's outcome when
forming that row's prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, log, sqrt
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class BaselineGame:
    """A leakage-safe game label used by the historical baseline runner."""

    game_id: str
    scheduled_tipoff: Any
    home_win: int
    home_margin: float
    game_total: float
    home_team_id: int | None = None
    away_team_id: int | None = None
    family_scores: Mapping[str, float | None] | None = None


def _mean(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def _log_loss(actual: list[int], probabilities: list[float]) -> float | None:
    if not actual:
        return None
    losses = []
    for label, probability in zip(actual, probabilities):
        clipped = min(max(probability, 1e-6), 1 - 1e-6)
        losses.append(-(label * log(clipped) + (1 - label) * log(1 - clipped)))
    return _mean(losses)


def _brier(actual: list[int], probabilities: list[float]) -> float | None:
    if not actual:
        return None
    return _mean([(label - probability) ** 2 for label, probability in zip(actual, probabilities)])


def _mae(actual: list[float], predictions: list[float]) -> float | None:
    if not actual:
        return None
    return _mean([abs(label - prediction) for label, prediction in zip(actual, predictions)])


def _rmse(actual: list[float], predictions: list[float]) -> float | None:
    if not actual:
        return None
    return sqrt(_mean([(label - prediction) ** 2 for label, prediction in zip(actual, predictions)]))


def _wilson_interval(successes: int, total: int, *, z: float = 1.96) -> tuple[float, float]:
    """Return a two-sided Wilson interval for a binary observed rate."""
    if total < 1:
        raise ValueError("total must be positive")
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    center = (proportion + (z * z / (2.0 * total))) / denominator
    margin = (
        z
        * sqrt(
            (proportion * (1.0 - proportion) / total)
            + (z * z / (4.0 * total * total))
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _calibration(
    actual: list[int],
    probabilities: list[float],
    bins: int = 10,
    *,
    minimum_bin_count: int = 25,
) -> dict[str, Any]:
    """Return reliability bins plus uncertainty-aware monitoring metadata.

    ECE/MCE retain their existing point estimates. Wilson intervals and the
    minimum-bin flag make small samples visible to reviewers instead of
    allowing a thin bin to look like stable calibration evidence.
    """
    if minimum_bin_count < 1:
        raise ValueError("minimum_bin_count must be positive")
    if not actual:
        return {
            "ece": None,
            "mce": None,
            "bins": [],
            "monitoring": {
                "method": "wilson_95_percent_interval",
                "minimum_bin_count": minimum_bin_count,
                "stable_bin_count": 0,
                "thin_bin_count": 0,
            },
        }
    grouped: list[list[tuple[int, float]]] = [[] for _ in range(bins)]
    for label, probability in zip(actual, probabilities):
        index = min(bins - 1, int(max(0.0, min(0.999999, probability)) * bins))
        grouped[index].append((label, probability))
    reports = []
    weighted_error = 0.0
    maximum_error = 0.0
    total = len(actual)
    for index, group in enumerate(grouped):
        if not group:
            continue
        mean_probability = _mean([probability for _, probability in group])
        observed_rate = _mean([float(label) for label, _ in group])
        gap = abs(observed_rate - mean_probability)
        interval_lower, interval_upper = _wilson_interval(
            sum(label for label, _ in group), len(group)
        )
        weighted_error += len(group) / total * gap
        maximum_error = max(maximum_error, gap)
        reports.append({
            "bin": index,
            "count": len(group),
            "mean_predicted": mean_probability,
            "observed_rate": observed_rate,
            "absolute_gap": gap,
            "observed_rate_interval_95": {
                "lower": interval_lower,
                "upper": interval_upper,
            },
            "meets_minimum_bin_count": len(group) >= minimum_bin_count,
        })
    return {
        "ece": weighted_error,
        "mce": maximum_error,
        "bins": reports,
        "monitoring": {
            "method": "wilson_95_percent_interval",
            "minimum_bin_count": minimum_bin_count,
            "stable_bin_count": sum(
                report["meets_minimum_bin_count"] for report in reports
            ),
            "thin_bin_count": sum(
                not report["meets_minimum_bin_count"] for report in reports
            ),
        },
    }


def _stability(reports: list[dict[str, Any]], metric: str) -> dict[str, float | None]:
    values = [float(report["win"][metric]) for report in reports if report.get("win", {}).get(metric) is not None]
    if not values:
        return {"min": None, "max": None, "range": None}
    return {"min": min(values), "max": max(values), "range": max(values) - min(values)}


def _as_game(row: BaselineGame | Mapping[str, Any]) -> BaselineGame:
    if isinstance(row, BaselineGame):
        return row
    return BaselineGame(
        game_id=str(row["game_id"]),
        scheduled_tipoff=row["scheduled_tipoff"],
        home_win=int(row["home_win"]),
        home_margin=float(row["home_margin"]),
        game_total=float(row["game_total"]),
        home_team_id=row.get("home_team_id"),
        away_team_id=row.get("away_team_id"),
        family_scores=row.get("family_scores"),
    )


def run_naive_baseline_experiment(
    rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    min_train_games: int = 50,
    blocks: int = 3,
) -> dict[str, Any]:
    """Evaluate chronological home-rate, margin-mean, and total-mean baselines.

    Test blocks are contiguous and equal-sized after the warmup period. Every
    prediction is fit from rows strictly before the test row. The returned
    payload is suitable for an audit artifact; it contains aggregate metrics,
    not persisted predictions.
    """
    games = sorted((_as_game(row) for row in rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    if blocks < 1:
        raise ValueError("blocks must be positive")
    if min_train_games < 1:
        raise ValueError("min_train_games must be positive")

    available = len(games)
    if available <= min_train_games:
        return {
            "status": "blocked_insufficient_history",
            "games": available,
            "min_train_games": min_train_games,
            "blocks_requested": blocks,
            "blocks_evaluated": 0,
            "writes_performed": False,
        }

    test_games = games[min_train_games:]
    block_size = max(1, len(test_games) // blocks)
    block_reports: list[dict[str, Any]] = []
    all_win_actual: list[int] = []
    all_win_pred: list[float] = []
    all_margin_actual: list[float] = []
    all_margin_pred: list[float] = []
    all_total_actual: list[float] = []
    all_total_pred: list[float] = []

    for block_index in range(blocks):
        start = block_index * block_size
        end = len(test_games) if block_index == blocks - 1 else min(len(test_games), start + block_size)
        block = test_games[start:end]
        if not block:
            continue
        first_index = min_train_games + start
        history = games[:first_index]
        home_rate = _mean([float(game.home_win) for game in history], 0.5)
        margin_mean = _mean([game.home_margin for game in history])
        total_mean = _mean([game.game_total for game in history])

        win_actual = [game.home_win for game in block]
        win_pred = [home_rate] * len(block)
        margin_actual = [game.home_margin for game in block]
        margin_pred = [margin_mean] * len(block)
        total_actual = [game.game_total for game in block]
        total_pred = [total_mean] * len(block)
        all_win_actual.extend(win_actual)
        all_win_pred.extend(win_pred)
        all_margin_actual.extend(margin_actual)
        all_margin_pred.extend(margin_pred)
        all_total_actual.extend(total_actual)
        all_total_pred.extend(total_pred)

        block_reports.append({
            "block": block_index + 1,
            "train_games": len(history),
            "test_games": len(block),
            "test_start": str(block[0].scheduled_tipoff),
            "test_end": str(block[-1].scheduled_tipoff),
            "win": {
                "home_rate": home_rate,
                "log_loss": _log_loss(win_actual, win_pred),
                "brier": _brier(win_actual, win_pred),
                "calibration": _calibration(win_actual, win_pred),
            },
            "margin": {"mean": margin_mean, "mae": _mae(margin_actual, margin_pred), "rmse": _rmse(margin_actual, margin_pred)},
            "total": {"mean": total_mean, "mae": _mae(total_actual, total_pred), "rmse": _rmse(total_actual, total_pred)},
        })

    return {
        "status": "complete" if block_reports else "blocked_insufficient_history",
        "games": available,
        "min_train_games": min_train_games,
        "blocks_requested": blocks,
        "blocks_evaluated": len(block_reports),
        "aggregate": {
            "test_games": len(all_win_actual),
            "win": {
                "log_loss": _log_loss(all_win_actual, all_win_pred),
                "brier": _brier(all_win_actual, all_win_pred),
                "calibration": _calibration(all_win_actual, all_win_pred),
            },
            "margin": {"mae": _mae(all_margin_actual, all_margin_pred), "rmse": _rmse(all_margin_actual, all_margin_pred)},
            "total": {"mae": _mae(all_total_actual, all_total_pred), "rmse": _rmse(all_total_actual, all_total_pred)},
        },
        "blocks": block_reports,
        "stability": {
            "win_log_loss": _stability(block_reports, "log_loss"),
            "win_brier": _stability(block_reports, "brier"),
            "margin_mae": {
                "min": min((float(report["margin"]["mae"]) for report in block_reports), default=None),
                "max": max((float(report["margin"]["mae"]) for report in block_reports), default=None),
            },
            "total_mae": {
                "min": min((float(report["total"]["mae"]) for report in block_reports), default=None),
                "max": max((float(report["total"]["mae"]) for report in block_reports), default=None),
            },
        },
        "writes_performed": False,
    }


def _elo_probability(home_rating: float, away_rating: float, home_advantage: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-((home_rating + home_advantage - away_rating) / 400.0)))


def _update_elo(
    ratings: dict[int, float],
    game: BaselineGame,
    probability: float,
    *,
    k_factor: float,
) -> None:
    if game.home_team_id is None or game.away_team_id is None:
        return
    actual = float(game.home_win)
    delta = k_factor * (actual - probability)
    ratings[game.home_team_id] = ratings.get(game.home_team_id, 1500.0) + delta
    ratings[game.away_team_id] = ratings.get(game.away_team_id, 1500.0) - delta


def run_elo_baseline_experiment(
    rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    min_train_games: int = 50,
    blocks: int = 3,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
) -> dict[str, Any]:
    """Evaluate an online Elo-style home-win baseline chronologically.

    Ratings are initialized at 1500, fit on the warmup history, and updated
    only after each game result is observed. Missing team identities block the
    experiment rather than collapsing all teams into one rating.
    """
    games = sorted((_as_game(row) for row in rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    if blocks < 1:
        raise ValueError("blocks must be positive")
    if min_train_games < 1:
        raise ValueError("min_train_games must be positive")
    if any(game.home_team_id is None or game.away_team_id is None for game in games):
        return {
            "status": "blocked_missing_team_ids",
            "games": len(games),
            "min_train_games": min_train_games,
            "blocks_requested": blocks,
            "blocks_evaluated": 0,
            "writes_performed": False,
        }
    if len(games) <= min_train_games:
        return {
            "status": "blocked_insufficient_history",
            "games": len(games),
            "min_train_games": min_train_games,
            "blocks_requested": blocks,
            "blocks_evaluated": 0,
            "writes_performed": False,
        }

    ratings: dict[int, float] = {}
    for game in games[:min_train_games]:
        probability = _elo_probability(
            ratings.get(game.home_team_id, 1500.0),
            ratings.get(game.away_team_id, 1500.0),
            home_advantage,
        )
        _update_elo(ratings, game, probability, k_factor=k_factor)

    test_games = games[min_train_games:]
    block_size = max(1, len(test_games) // blocks)
    block_reports: list[dict[str, Any]] = []
    aggregate_actual: list[int] = []
    aggregate_probability: list[float] = []

    for block_index in range(blocks):
        start = block_index * block_size
        end = len(test_games) if block_index == blocks - 1 else min(len(test_games), start + block_size)
        block = test_games[start:end]
        if not block:
            continue
        actual: list[int] = []
        probabilities: list[float] = []
        for game in block:
            probability = _elo_probability(
                ratings.get(game.home_team_id, 1500.0),
                ratings.get(game.away_team_id, 1500.0),
                home_advantage,
            )
            actual.append(game.home_win)
            probabilities.append(probability)
            aggregate_actual.append(game.home_win)
            aggregate_probability.append(probability)
            _update_elo(ratings, game, probability, k_factor=k_factor)
        block_reports.append({
            "block": block_index + 1,
            "train_games": min_train_games + start,
            "test_games": len(block),
            "test_start": str(block[0].scheduled_tipoff),
            "test_end": str(block[-1].scheduled_tipoff),
            "win": {
                "log_loss": _log_loss(actual, probabilities),
                "brier": _brier(actual, probabilities),
                "calibration": _calibration(actual, probabilities),
            },
        })

    return {
        "status": "complete" if block_reports else "blocked_insufficient_history",
        "games": len(games),
        "min_train_games": min_train_games,
        "blocks_requested": blocks,
        "blocks_evaluated": len(block_reports),
        "hyperparameters": {"k_factor": k_factor, "home_advantage": home_advantage},
        "aggregate": {
            "test_games": len(aggregate_actual),
            "win": {
                "log_loss": _log_loss(aggregate_actual, aggregate_probability),
                "brier": _brier(aggregate_actual, aggregate_probability),
                "calibration": _calibration(aggregate_actual, aggregate_probability),
            },
        },
        "blocks": block_reports,
        "stability": {
            "win_log_loss": _stability(block_reports, "log_loss"),
            "win_brier": _stability(block_reports, "brier"),
        },
        "writes_performed": False,
    }


def _logistic(value: float) -> float:
    if value >= 0:
        factor = exp(-value)
        return 1.0 / (1.0 + factor)
    factor = exp(value)
    return factor / (1.0 + factor)


def _fit_platt_calibrator(
    probabilities: list[float],
    actual: list[int],
    *,
    iterations: int = 240,
    learning_rate: float = 0.05,
    l2: float = 0.01,
) -> tuple[float, float]:
    """Fit calibration parameters on historical predictions only."""
    intercept = 0.0
    slope = 1.0
    logits = [log(min(max(probability, 1e-6), 1 - 1e-6) / (1 - min(max(probability, 1e-6), 1 - 1e-6))) for probability in probabilities]
    divisor = float(len(actual))
    for _ in range(iterations):
        intercept_gradient = 0.0
        slope_gradient = 0.0
        for logit, label in zip(logits, actual):
            estimate = _logistic(intercept + slope * logit)
            error = estimate - label
            intercept_gradient += error
            slope_gradient += error * logit
        intercept -= learning_rate * intercept_gradient / divisor
        slope -= learning_rate * (slope_gradient / divisor + l2 * (slope - 1.0))
    return intercept, slope


def run_calibrated_elo_baseline_experiment(
    rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    min_train_games: int = 50,
    blocks: int = 3,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
) -> dict[str, Any]:
    """Evaluate Elo with a train-only Platt calibration repair."""
    games = sorted((_as_game(row) for row in rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    if any(game.home_team_id is None or game.away_team_id is None for game in games):
        return {"status": "blocked_missing_team_ids", "games": len(games), "writes_performed": False}
    if len(games) <= min_train_games:
        return {
            "status": "blocked_insufficient_history",
            "games": len(games),
            "min_train_games": min_train_games,
            "blocks_requested": blocks,
            "blocks_evaluated": 0,
            "writes_performed": False,
        }

    test_games = games[min_train_games:]
    block_size = max(1, len(test_games) // blocks)
    block_reports: list[dict[str, Any]] = []
    raw_actual: list[int] = []
    raw_probability: list[float] = []
    calibrated_probability: list[float] = []

    for block_index in range(blocks):
        start = block_index * block_size
        end = len(test_games) if block_index == blocks - 1 else min(len(test_games), start + block_size)
        block = test_games[start:end]
        if not block:
            continue
        first_index = min_train_games + start
        ratings: dict[int, float] = {}
        training_actual: list[int] = []
        training_probability: list[float] = []
        for game in games[:first_index]:
            probability = _elo_probability(
                ratings.get(game.home_team_id, 1500.0),
                ratings.get(game.away_team_id, 1500.0),
                home_advantage,
            )
            training_actual.append(game.home_win)
            training_probability.append(probability)
            _update_elo(ratings, game, probability, k_factor=k_factor)
        intercept, slope = _fit_platt_calibrator(training_probability, training_actual)

        actual: list[int] = []
        raw: list[float] = []
        calibrated: list[float] = []
        for game in block:
            probability = _elo_probability(
                ratings.get(game.home_team_id, 1500.0),
                ratings.get(game.away_team_id, 1500.0),
                home_advantage,
            )
            logit = log(min(max(probability, 1e-6), 1 - 1e-6) / (1 - min(max(probability, 1e-6), 1 - 1e-6)))
            calibrated_value = _logistic(intercept + slope * logit)
            actual.append(game.home_win)
            raw.append(probability)
            calibrated.append(calibrated_value)
            raw_actual.append(game.home_win)
            raw_probability.append(probability)
            calibrated_probability.append(calibrated_value)
            _update_elo(ratings, game, probability, k_factor=k_factor)
        block_reports.append({
            "block": block_index + 1,
            "train_games": first_index,
            "test_games": len(block),
            "test_start": str(block[0].scheduled_tipoff),
            "test_end": str(block[-1].scheduled_tipoff),
            "calibrator": {"intercept": intercept, "slope": slope},
            "raw": {
                "log_loss": _log_loss(actual, raw),
                "brier": _brier(actual, raw),
                "calibration": _calibration(actual, raw),
            },
            "calibrated": {
                "log_loss": _log_loss(actual, calibrated),
                "brier": _brier(actual, calibrated),
                "calibration": _calibration(actual, calibrated),
            },
        })

    return {
        "status": "complete" if block_reports else "blocked_insufficient_history",
        "games": len(games),
        "min_train_games": min_train_games,
        "blocks_requested": blocks,
        "blocks_evaluated": len(block_reports),
        "hyperparameters": {"k_factor": k_factor, "home_advantage": home_advantage},
        "aggregate": {
            "test_games": len(raw_actual),
            "raw": {
                "log_loss": _log_loss(raw_actual, raw_probability),
                "brier": _brier(raw_actual, raw_probability),
                "calibration": _calibration(raw_actual, raw_probability),
            },
            "calibrated": {
                "log_loss": _log_loss(raw_actual, calibrated_probability),
                "brier": _brier(raw_actual, calibrated_probability),
                "calibration": _calibration(raw_actual, calibrated_probability),
            },
        },
        "blocks": block_reports,
        "writes_performed": False,
    }


def _probability_band_reports(
    actual: list[int], probabilities: list[float]
) -> dict[str, dict[str, Any]]:
    """Report win metrics by broad probability band for stability review."""
    definitions = (
        ("low_confidence", 0.0, 0.35),
        ("competitive", 0.35, 0.65),
        ("high_confidence", 0.65, 1.0),
    )
    reports: dict[str, dict[str, Any]] = {}
    for name, lower, upper in definitions:
        selected = [
            (label, probability)
            for label, probability in zip(actual, probabilities)
            if lower <= probability < upper or (upper == 1.0 and probability == 1.0)
        ]
        band_actual = [label for label, _ in selected]
        band_probability = [probability for _, probability in selected]
        reports[name] = {
            "lower_bound": lower,
            "upper_bound": upper,
            "test_games": len(selected),
            "coverage": len(selected) / len(actual) if actual else 0.0,
            "win": {
                "log_loss": _log_loss(band_actual, band_probability),
                "brier": _brier(band_actual, band_probability),
                "calibration": _calibration(band_actual, band_probability),
            },
        }
    return reports


def _subgroup_acceptance(
    probability_bands: Mapping[str, Mapping[str, Any]],
    *,
    minimum_games: int = 100,
) -> dict[str, Any]:
    """Classify broad probability bands for review, never production use."""
    if minimum_games < 1:
        raise ValueError("minimum_games must be positive")
    bands = {
        name: {
            "test_games": int(report["test_games"]),
            "meets_minimum_games": int(report["test_games"]) >= minimum_games,
        }
        for name, report in probability_bands.items()
    }
    return {
        "minimum_games": minimum_games,
        "bands": bands,
        "all_bands_meet_minimum": bool(bands) and all(
            band["meets_minimum_games"] for band in bands.values()
        ),
        "status": "review_ready" if bands and all(
            band["meets_minimum_games"] for band in bands.values()
        ) else "blocked_thin_subgroup",
    }


def _probability_report(actual: list[int], probabilities: list[float]) -> dict[str, Any]:
    probability_bands = _probability_band_reports(actual, probabilities)
    return {
        "test_games": len(actual),
        "win": {
            "log_loss": _log_loss(actual, probabilities),
            "brier": _brier(actual, probabilities),
            "calibration": _calibration(actual, probabilities),
        },
        "probability_bands": probability_bands,
        "subgroup_acceptance": _subgroup_acceptance(probability_bands),
    }


def _calibrated_probability(probability: float, intercept: float, slope: float) -> float:
    clipped = min(max(probability, 1e-6), 1 - 1e-6)
    logit = log(clipped / (1 - clipped))
    return _logistic(intercept + slope * logit)


def _evaluate_elo_segment(
    games: list[BaselineGame],
    ratings: dict[int, float],
    *,
    intercept: float,
    slope: float,
    k_factor: float,
    home_advantage: float,
) -> dict[str, Any]:
    raw_actual: list[int] = []
    raw_probability: list[float] = []
    calibrated_probability: list[float] = []
    for game in games:
        raw = _elo_probability(
            ratings.get(game.home_team_id, 1500.0),
            ratings.get(game.away_team_id, 1500.0),
            home_advantage,
        )
        calibrated = _calibrated_probability(raw, intercept, slope)
        raw_actual.append(game.home_win)
        raw_probability.append(raw)
        calibrated_probability.append(calibrated)
        # The current row is scored before its outcome changes the ratings.
        _update_elo(ratings, game, raw, k_factor=k_factor)
    return {
        "raw": _probability_report(raw_actual, raw_probability),
        "calibrated": _probability_report(raw_actual, calibrated_probability),
    }


def run_season_heldout_calibration_validation(
    source_rows: Iterable[BaselineGame | Mapping[str, Any]],
    heldout_rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    train_fraction: float = 0.60,
    calibration_fraction: float = 0.20,
    min_train_games: int = 50,
    min_calibration_games: int = 100,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
) -> dict[str, Any]:
    """Fit Elo and Platt calibration chronologically, then test on held-out data.

    The source season is split into train, calibration, and source-test windows.
    Elo is updated through train and calibration, Platt is fit on calibration
    predictions only, and the calibrator is frozen for both source-test and the
    separate held-out season. Held-out outcomes update a private in-memory Elo
    stream only after each prediction; nothing is persisted.
    """
    if not 0 < train_fraction < 1 or not 0 < calibration_fraction < 1:
        raise ValueError("train_fraction and calibration_fraction must be between 0 and 1")
    if train_fraction + calibration_fraction >= 1:
        raise ValueError("train_fraction plus calibration_fraction must be below 1")
    if min_train_games < 1 or min_calibration_games < 1:
        raise ValueError("minimum split sizes must be positive")

    source = sorted((_as_game(row) for row in source_rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    heldout = sorted((_as_game(row) for row in heldout_rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    split_train = int(len(source) * train_fraction)
    split_calibration = int(len(source) * calibration_fraction)
    split_test = len(source) - split_train - split_calibration
    split = {
        "train_games": split_train,
        "calibration_games": split_calibration,
        "source_test_games": split_test,
        "heldout_test_games": len(heldout),
        "train_fraction": train_fraction,
        "calibration_fraction": calibration_fraction,
        "source_test_fraction": 1.0 - train_fraction - calibration_fraction,
    }
    if any(game.home_team_id is None or game.away_team_id is None for game in (*source, *heldout)):
        return {
            "status": "blocked_missing_team_ids",
            "source_games": len(source),
            "heldout_games": len(heldout),
            "split": split,
            "writes_performed": False,
        }
    if (
        split_train < min_train_games
        or split_calibration < min_calibration_games
        or split_test < 1
        or not heldout
    ):
        return {
            "status": "blocked_insufficient_split",
            "source_games": len(source),
            "heldout_games": len(heldout),
            "split": split,
            "min_train_games": min_train_games,
            "min_calibration_games": min_calibration_games,
            "writes_performed": False,
        }

    train_games = source[:split_train]
    calibration_games = source[split_train:split_train + split_calibration]
    source_test_games = source[split_train + split_calibration:]
    ratings_after_train: dict[int, float] = {}
    calibration_actual: list[int] = []
    calibration_probability: list[float] = []
    for game in train_games:
        raw = _elo_probability(
            ratings_after_train.get(game.home_team_id, 1500.0),
            ratings_after_train.get(game.away_team_id, 1500.0),
            home_advantage,
        )
        _update_elo(ratings_after_train, game, raw, k_factor=k_factor)
    for game in calibration_games:
        raw = _elo_probability(
            ratings_after_train.get(game.home_team_id, 1500.0),
            ratings_after_train.get(game.away_team_id, 1500.0),
            home_advantage,
        )
        calibration_actual.append(game.home_win)
        calibration_probability.append(raw)
        _update_elo(ratings_after_train, game, raw, k_factor=k_factor)

    intercept, slope = _fit_platt_calibrator(calibration_probability, calibration_actual)
    source_test_report = _evaluate_elo_segment(
        source_test_games,
        dict(ratings_after_train),
        intercept=intercept,
        slope=slope,
        k_factor=k_factor,
        home_advantage=home_advantage,
    )
    heldout_report = _evaluate_elo_segment(
        heldout,
        dict(ratings_after_train),
        intercept=intercept,
        slope=slope,
        k_factor=k_factor,
        home_advantage=home_advantage,
    )
    return {
        "status": "complete",
        "source_games": len(source),
        "heldout_games": len(heldout),
        "split": split,
        "min_train_games": min_train_games,
        "min_calibration_games": min_calibration_games,
        "hyperparameters": {"k_factor": k_factor, "home_advantage": home_advantage},
        "calibration_fit": {
            "method": "platt_logistic_on_calibration_window",
            "calibration_games": len(calibration_actual),
            "intercept": intercept,
            "slope": slope,
        },
        "source_test": source_test_report,
        "season_heldout": heldout_report,
        "writes_performed": False,
    }


def run_season_heldout_window_sweep(
    source_rows: Iterable[BaselineGame | Mapping[str, Any]],
    heldout_rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    windows: Iterable[tuple[str, float, float]] = (
        ("50_25_25", 0.50, 0.25),
        ("60_20_20", 0.60, 0.20),
        ("70_15_15", 0.70, 0.15),
    ),
    min_train_games: int = 50,
    min_calibration_games: int = 100,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
) -> dict[str, Any]:
    """Run the held-out calibration gate across explicit chronological windows.

    Each window receives the same immutable source/held-out rows and is
    evaluated independently. The sweep is a stability artifact only: it does
    not select a winner, persist forecasts, or relax the single-window gate.
    """
    source = list(source_rows)
    heldout = list(heldout_rows)
    window_reports = []
    for name, train_fraction, calibration_fraction in windows:
        report = run_season_heldout_calibration_validation(
            source,
            heldout,
            train_fraction=train_fraction,
            calibration_fraction=calibration_fraction,
            min_train_games=min_train_games,
            min_calibration_games=min_calibration_games,
            k_factor=k_factor,
            home_advantage=home_advantage,
        )
        window_reports.append({
            "name": name,
            "train_fraction": train_fraction,
            "calibration_fraction": calibration_fraction,
            "source_test_fraction": 1.0 - train_fraction - calibration_fraction,
            "status": report["status"],
            "report": report,
        })
    return {
        "status": "complete" if window_reports and all(
            report["status"] == "complete" for report in window_reports
        ) else "blocked_window",
        "windows": window_reports,
        "writes_performed": False,
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = 10.0 ** (-value)
        return 1.0 / (1.0 + exponent)
    exponent = 10.0 ** value
    return exponent / (1.0 + exponent)


def _complete_family_rows(games: list[BaselineGame], families: tuple[str, ...]) -> list[BaselineGame]:
    return [
        game
        for game in games
        if game.family_scores is not None
        and all(game.family_scores.get(family) is not None for family in families)
    ]


def _fit_logistic_family_model(
    games: list[BaselineGame],
    families: tuple[str, ...],
    *,
    iterations: int = 180,
    learning_rate: float = 0.08,
    l2: float = 0.01,
) -> tuple[list[float], list[float], list[float]]:
    means = [_mean([float(game.family_scores[family]) for game in games]) for family in families]
    scales = []
    for index, mean in enumerate(means):
        variance = _mean([(float(game.family_scores[families[index]]) - mean) ** 2 for game in games])
        scales.append(sqrt(variance) or 1.0)
    weights = [0.0] * (len(families) + 1)
    for _ in range(iterations):
        gradients = [0.0] * len(weights)
        for game in games:
            values = [
                (float(game.family_scores[family]) - means[index]) / scales[index]
                for index, family in enumerate(families)
            ]
            probability = _sigmoid(weights[0] + sum(weight * value for weight, value in zip(weights[1:], values)))
            error = probability - game.home_win
            gradients[0] += error
            for index, value in enumerate(values, start=1):
                gradients[index] += error * value
        divisor = float(len(games))
        weights[0] -= learning_rate * gradients[0] / divisor
        for index in range(1, len(weights)):
            weights[index] -= learning_rate * (gradients[index] / divisor + l2 * weights[index])
    return weights, means, scales


def run_feature_family_ablation(
    rows: Iterable[BaselineGame | Mapping[str, Any]],
    *,
    min_train_games: int = 50,
    blocks: int = 3,
    minimum_test_coverage: float = 0.95,
    minimum_subgroup_games: int = 100,
    variant_definitions: Iterable[tuple[str, tuple[str, ...]]] | None = None,
) -> dict[str, Any]:
    """Evaluate cumulative logistic feature families without future fitting.

    This is a deliberately small research baseline, not a production model.
    Each variant fits its scaler and coefficients only on the historical rows
    before its chronological test block. Rows missing that variant's inputs
    are withheld and counted rather than imputed.
    """
    if not 0 < minimum_test_coverage <= 1:
        raise ValueError("minimum_test_coverage must be between 0 and 1")
    if minimum_subgroup_games < 1:
        raise ValueError("minimum_subgroup_games must be positive")
    games = sorted((_as_game(row) for row in rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    variants = tuple(variant_definitions or (
        ("strength", ("strength",)),
        ("strength_form", ("strength", "form")),
        ("strength_form_schedule", ("strength", "form", "schedule")),
        ("strength_form_schedule_matchup", ("strength", "form", "schedule", "matchup_context")),
    ))
    if len(games) <= min_train_games:
        return {
            "status": "blocked_insufficient_history",
            "games": len(games),
            "min_train_games": min_train_games,
            "blocks_requested": blocks,
            "variants": {},
            "writes_performed": False,
        }

    test_games = games[min_train_games:]
    block_size = max(1, len(test_games) // blocks)
    variant_reports: dict[str, Any] = {}
    for variant_name, families in variants:
        variant_games = _complete_family_rows(games, families)
        reports: list[dict[str, Any]] = []
        aggregate_actual: list[int] = []
        aggregate_probability: list[float] = []
        withheld = 0
        for block_index in range(blocks):
            start = block_index * block_size
            end = len(test_games) if block_index == blocks - 1 else min(len(test_games), start + block_size)
            block = test_games[start:end]
            if not block:
                continue
            first_index = min_train_games + start
            history = _complete_family_rows(games[:first_index], families)
            scored = _complete_family_rows(block, families)
            withheld += len(block) - len(scored)
            if len(history) < min_train_games:
                reports.append({
                    "block": block_index + 1,
                    "train_games": len(history),
                    "test_games": len(block),
                    "scored_test_games": 0,
                    "coverage": 0.0,
                    "status": "blocked_insufficient_complete_history",
                })
                continue
            weights, means, scales = _fit_logistic_family_model(history, families)
            actual: list[int] = []
            probabilities: list[float] = []
            for game in scored:
                values = [
                    (float(game.family_scores[family]) - means[index]) / scales[index]
                    for index, family in enumerate(families)
                ]
                probability = _sigmoid(weights[0] + sum(weight * value for weight, value in zip(weights[1:], values)))
                actual.append(game.home_win)
                probabilities.append(probability)
            aggregate_actual.extend(actual)
            aggregate_probability.extend(probabilities)
            reports.append({
                "block": block_index + 1,
                "train_games": len(history),
                "test_games": len(block),
                "scored_test_games": len(scored),
                "withheld_test_games": len(block) - len(scored),
                "coverage": len(scored) / len(block) if block else 0.0,
                "test_start": str(block[0].scheduled_tipoff),
                "test_end": str(block[-1].scheduled_tipoff),
                "standardized_coefficients": {
                    family: weights[index + 1]
                    for index, family in enumerate(families)
                },
                "win": {
                    "log_loss": _log_loss(actual, probabilities),
                    "brier": _brier(actual, probabilities),
                    "calibration": _calibration(actual, probabilities),
                },
                "status": "complete",
            })
        variant_reports[variant_name] = {
            "families": list(families),
            "status": "complete" if aggregate_actual else "blocked_insufficient_complete_history",
            "available_games": len(variant_games),
            "withheld_test_games": withheld,
            "availability": {
                "effective_test_games": len(test_games),
                "scored_test_games": len(aggregate_actual),
                "coverage": len(aggregate_actual) / len(test_games) if test_games else 0.0,
                "minimum_coverage": minimum_test_coverage,
                "meets_minimum_coverage": (
                    len(aggregate_actual) / len(test_games) >= minimum_test_coverage
                    if test_games else False
                ),
            },
            "aggregate": {
                "test_games": len(aggregate_actual),
                "win": {
                    "log_loss": _log_loss(aggregate_actual, aggregate_probability),
                    "brier": _brier(aggregate_actual, aggregate_probability),
                    "calibration": _calibration(aggregate_actual, aggregate_probability),
                },
            },
            "subgroup_acceptance": _subgroup_acceptance(
                _probability_band_reports(aggregate_actual, aggregate_probability),
                minimum_games=minimum_subgroup_games,
            ),
            "blocks": reports,
            "stability": {
                "win_log_loss": _stability(reports, "log_loss"),
                "win_brier": _stability(reports, "brier"),
            },
        }
    return {
        "status": "complete",
        "games": len(games),
        "min_train_games": min_train_games,
        "blocks_requested": blocks,
        "blocks_evaluated": blocks,
        "variants": variant_reports,
        "writes_performed": False,
    }


def compare_review_ready_feature_variants(
    reports_by_season: Mapping[str, Mapping[str, Any]],
    *,
    minimum_coverage: float = 0.95,
    require_subgroups: bool = True,
) -> dict[str, Any]:
    """Compare ablation variants that pass explicit review gates everywhere.

    The result is a cross-season comparison artifact, not a ranking or model
    selection. A variant is a candidate only when its coverage and subgroup
    review gates pass in every supplied season.
    """
    if not reports_by_season:
        return {
            "status": "blocked_no_seasons",
            "candidate_variants": [],
            "variants": {},
            "writes_performed": False,
        }
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be between 0 and 1")
    variant_sets = [set(report.get("variants", {})) for report in reports_by_season.values()]
    common_variants = sorted(set.intersection(*variant_sets)) if variant_sets else []
    comparisons: dict[str, Any] = {}
    candidates: list[str] = []
    for variant_name in common_variants:
        eligibility = {}
        performance = {}
        eligible_everywhere = True
        for season, report in reports_by_season.items():
            variant = report["variants"][variant_name]
            availability = variant.get("availability", {})
            coverage = float(availability.get("coverage", 0.0))
            coverage_pass = coverage >= minimum_coverage
            subgroup_pass = variant.get("subgroup_acceptance", {}).get(
                "all_bands_meet_minimum", False
            )
            eligible = coverage_pass and (subgroup_pass if require_subgroups else True)
            eligible_everywhere = eligible_everywhere and eligible
            eligibility[season] = {
                "coverage": coverage,
                "minimum_coverage": minimum_coverage,
                "coverage_pass": coverage_pass,
                "subgroup_pass": subgroup_pass,
                "eligible": eligible,
            }
            aggregate = variant.get("aggregate", {})
            win = aggregate.get("win", {})
            performance[season] = {
                "test_games": aggregate.get("test_games", 0),
                "log_loss": win.get("log_loss"),
                "brier": win.get("brier"),
            }
        log_losses = [
            float(metrics["log_loss"])
            for metrics in performance.values()
            if metrics["log_loss"] is not None
        ]
        comparisons[variant_name] = {
            "families": reports_by_season[next(iter(reports_by_season))]["variants"][variant_name].get("families", []),
            "eligible_everywhere": eligible_everywhere,
            "eligibility": eligibility,
            "performance": performance,
            "stability": {
                "log_loss_min": min(log_losses) if log_losses else None,
                "log_loss_max": max(log_losses) if log_losses else None,
                "log_loss_range": max(log_losses) - min(log_losses) if log_losses else None,
            },
        }
        if eligible_everywhere:
            candidates.append(variant_name)
    return {
        "status": "complete" if comparisons else "blocked_no_common_variants",
        "seasons": list(reports_by_season),
        "minimum_coverage": minimum_coverage,
        "require_subgroups": require_subgroups,
        "candidate_variants": candidates,
        "variants": comparisons,
        "writes_performed": False,
    }


def review_feature_family_stability(
    reports_by_season: Mapping[str, Mapping[str, Any]],
    candidate_variants: Iterable[str],
    *,
    minimum_block_coverage: float = 0.95,
) -> dict[str, Any]:
    """Stress-test candidate variants across chronological season segments.

    The input is the output of ``run_feature_family_ablation``. Each block is
    an expanding-history fit followed by a chronological test segment. This
    review summarizes segment performance and standardized feature weights;
    it does not rank, select, persist, or publish a model.
    """
    if not 0 < minimum_block_coverage <= 1:
        raise ValueError("minimum_block_coverage must be between 0 and 1")

    candidates = list(dict.fromkeys(candidate_variants))
    if not reports_by_season or not candidates:
        return {
            "status": "blocked_no_candidates",
            "candidate_variants": candidates,
            "variants": {},
            "writes_performed": False,
        }

    variant_reports: dict[str, Any] = {}
    for variant_name in candidates:
        season_reports: dict[str, Any] = {}
        all_coefficients: dict[str, list[float]] = {}
        eligible_everywhere = True
        for season, report in reports_by_season.items():
            variant = report.get("variants", {}).get(variant_name)
            if not variant:
                eligible_everywhere = False
                season_reports[season] = {
                    "status": "blocked_missing_variant",
                    "eligible": False,
                    "segments": [],
                    "feature_stability": {},
                }
                continue

            segments = []
            block_coefficients: dict[str, list[float]] = {}
            for block in variant.get("blocks", []):
                coverage = float(block.get(
                    "coverage",
                    block.get("scored_test_games", 0) / block["test_games"]
                    if block.get("test_games") else 0.0,
                ))
                win = block.get("win", {})
                segments.append({
                    "block": block.get("block"),
                    "test_start": block.get("test_start"),
                    "test_end": block.get("test_end"),
                    "test_games": block.get("test_games", 0),
                    "scored_test_games": block.get("scored_test_games", 0),
                    "coverage": coverage,
                    "log_loss": win.get("log_loss"),
                    "brier": win.get("brier"),
                    "status": block.get("status", "complete"),
                })
                if block.get("status", "complete") != "complete" or coverage < minimum_block_coverage:
                    eligible_everywhere = False
                for family, coefficient in block.get("standardized_coefficients", {}).items():
                    block_coefficients.setdefault(family, []).append(float(coefficient))
                    all_coefficients.setdefault(family, []).append(float(coefficient))

            feature_stability = {}
            for family, coefficients in block_coefficients.items():
                nonzero_signs = {
                    1 if coefficient > 1e-9 else -1
                    for coefficient in coefficients
                    if abs(coefficient) > 1e-9
                }
                feature_stability[family] = {
                    "block_count": len(coefficients),
                    "coefficient_min": min(coefficients),
                    "coefficient_max": max(coefficients),
                    "coefficient_range": max(coefficients) - min(coefficients),
                    "nonzero_signs": sorted(nonzero_signs),
                    "sign_consistent": len(nonzero_signs) <= 1,
                }
            if not segments or not feature_stability:
                eligible_everywhere = False
            feature_signs_consistent = bool(feature_stability) and all(
                metric["sign_consistent"]
                for metric in feature_stability.values()
            )
            season_reports[season] = {
                "status": "complete" if segments else "blocked_no_segments",
                "eligible": bool(segments) and all(
                    segment["status"] == "complete"
                    and segment["coverage"] >= minimum_block_coverage
                    for segment in segments
                ) and bool(feature_stability),
                "feature_signs_consistent": feature_signs_consistent,
                "segments": segments,
                "feature_stability": feature_stability,
            }

        cross_season_stability = {}
        for family, coefficients in all_coefficients.items():
            nonzero_signs = {
                1 if coefficient > 1e-9 else -1
                for coefficient in coefficients
                if abs(coefficient) > 1e-9
            }
            cross_season_stability[family] = {
                "block_count": len(coefficients),
                "coefficient_min": min(coefficients),
                "coefficient_max": max(coefficients),
                "coefficient_range": max(coefficients) - min(coefficients),
                "nonzero_signs": sorted(nonzero_signs),
                "sign_consistent": len(nonzero_signs) <= 1,
            }
        all_features_sign_consistent = bool(cross_season_stability) and all(
            metric["sign_consistent"]
            for metric in cross_season_stability.values()
        )
        variant_reports[variant_name] = {
            "eligible_everywhere": eligible_everywhere,
            "feature_signs_consistent": all_features_sign_consistent,
            "next_gate_ready": eligible_everywhere and all_features_sign_consistent,
            "seasons": season_reports,
            "cross_season_feature_stability": cross_season_stability,
        }

    return {
        "status": "complete",
        "seasons": list(reports_by_season),
        "candidate_variants": candidates,
        "minimum_block_coverage": minimum_block_coverage,
        "variants": variant_reports,
        "writes_performed": False,
    }


SCHEDULE_DEFINITIONS: dict[str, str] = {
    "rest_edge_raw": "home days-rest minus away days-rest; unbounded control",
    "rest_edge_clipped_1": "home rest edge clipped to [-1, 1]",
    "rest_edge_signed": "home rest edge reduced to -1, 0, or 1",
    "home_rest_deficit": "negative home rest edge only; zero otherwise",
}


SCHEDULE_COMPONENT_VARIANTS: dict[str, tuple[str, ...]] = {
    "strength_form_b2b": ("strength", "form", "b2b_edge"),
    "strength_form_3_in_4": ("strength", "form", "three_in_four_edge"),
    "strength_form_4_in_5": ("strength", "form", "four_in_five_edge"),
    "strength_form_5_in_7": ("strength", "form", "five_in_seven_edge"),
    "strength_form_rest_asymmetry": ("strength", "form", "rest_asymmetry"),
    "strength_form_schedule_components": (
        "strength",
        "form",
        "b2b_edge",
        "three_in_four_edge",
        "four_in_five_edge",
        "five_in_seven_edge",
        "rest_asymmetry",
    ),
}


def _schedule_definition_value(name: str, value: float | None) -> float | None:
    if value is None:
        return None
    if name == "rest_edge_raw":
        return value
    if name == "rest_edge_clipped_1":
        return max(-1.0, min(1.0, value))
    if name == "rest_edge_signed":
        return 1.0 if value > 0 else -1.0 if value < 0 else 0.0
    if name == "home_rest_deficit":
        return min(0.0, value)
    raise ValueError(f"unknown schedule definition: {name}")


def _apply_schedule_definition(
    rows: Iterable[BaselineGame | Mapping[str, Any]],
    definition: str,
) -> list[BaselineGame]:
    if definition not in SCHEDULE_DEFINITIONS:
        raise ValueError(f"unknown schedule definition: {definition}")
    transformed = []
    for game in (_as_game(row) for row in rows):
        family_scores = dict(game.family_scores or {})
        family_scores["schedule"] = _schedule_definition_value(
            definition,
            family_scores.get("schedule"),
        )
        transformed.append(replace(game, family_scores=family_scores))
    return transformed


def run_schedule_definition_sweep(
    games_by_season: Mapping[str, Iterable[BaselineGame | Mapping[str, Any]]],
    *,
    candidate_variants: Iterable[str] = (
        "strength_form_schedule",
        "strength_form_schedule_matchup",
    ),
    definitions: Iterable[str] = tuple(SCHEDULE_DEFINITIONS),
    min_train_games: int = 50,
    blocks: int = 4,
    minimum_block_coverage: float = 0.95,
) -> dict[str, Any]:
    """Rerun candidate stability under explicit schedule feature definitions.

    Each definition is applied in memory to the home-perspective rest edge,
    then evaluated independently by season and reviewed across chronological
    blocks. This is a research sensitivity sweep: it never ranks, selects,
    persists, or publishes a model.
    """
    if not games_by_season:
        return {
            "status": "blocked_no_seasons",
            "definitions": {},
            "writes_performed": False,
        }
    if blocks < 2:
        raise ValueError("blocks must be at least 2 for a segment review")
    definition_names = list(dict.fromkeys(definitions))
    reports: dict[str, Any] = {}
    for definition in definition_names:
        ablations = {
            season: run_feature_family_ablation(
                _apply_schedule_definition(rows, definition),
                min_train_games=min_train_games,
                blocks=blocks,
            )
            for season, rows in games_by_season.items()
        }
        stability = review_feature_family_stability(
            ablations,
            candidate_variants,
            minimum_block_coverage=minimum_block_coverage,
        )
        reports[definition] = {
            "description": SCHEDULE_DEFINITIONS.get(definition, "custom"),
            "stability": stability,
        }
    return {
        "status": "complete" if reports else "blocked_no_definitions",
        "seasons": list(games_by_season),
        "definitions": reports,
        "writes_performed": False,
    }


def run_schedule_component_sweep(
    games_by_season: Mapping[str, Iterable[BaselineGame | Mapping[str, Any]]],
    *,
    definitions: Mapping[str, tuple[str, ...]] = SCHEDULE_COMPONENT_VARIANTS,
    min_train_games: int = 50,
    blocks: int = 4,
    minimum_block_coverage: float = 0.95,
) -> dict[str, Any]:
    """Evaluate schedule-pressure components independently and in combination."""
    if not games_by_season:
        return {
            "status": "blocked_no_seasons",
            "definitions": {},
            "writes_performed": False,
        }
    if blocks < 2:
        raise ValueError("blocks must be at least 2 for a segment review")

    reports: dict[str, Any] = {}
    for name, families in definitions.items():
        variant_definitions = ((name, tuple(families)),)
        ablations = {
            season: run_feature_family_ablation(
                rows,
                min_train_games=min_train_games,
                blocks=blocks,
                variant_definitions=variant_definitions,
            )
            for season, rows in games_by_season.items()
        }
        stability = review_feature_family_stability(
            ablations,
            [name],
            minimum_block_coverage=minimum_block_coverage,
        )
        comparison = compare_review_ready_feature_variants(ablations)
        reports[name] = {
            "families": list(families),
            "stability": stability,
            "comparison": comparison,
        }
    return {
        "status": "complete" if reports else "blocked_no_definitions",
        "seasons": list(games_by_season),
        "definitions": reports,
        "writes_performed": False,
    }


def run_feature_family_season_heldout_validation(
    source_rows: Iterable[BaselineGame | Mapping[str, Any]],
    heldout_rows: Iterable[BaselineGame | Mapping[str, Any]],
    families: tuple[str, ...],
    *,
    min_train_games: int = 50,
    minimum_heldout_coverage: float = 0.95,
) -> dict[str, Any]:
    """Fit one research feature variant on a source season and freeze it.

    The source season supplies all fitting rows. The opposite season is scored
    chronologically with the frozen scaler and coefficients; its labels never
    influence fitting or prediction. This is an out-of-season generalization
    gate, not a production model or forecast publisher.
    """
    if not families:
        raise ValueError("families must not be empty")
    if min_train_games < 1:
        raise ValueError("min_train_games must be positive")
    if not 0 < minimum_heldout_coverage <= 1:
        raise ValueError("minimum_heldout_coverage must be between 0 and 1")
    source = sorted((_as_game(row) for row in source_rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    heldout = sorted((_as_game(row) for row in heldout_rows), key=lambda row: (row.scheduled_tipoff, row.game_id))
    complete_source = _complete_family_rows(source, families)
    complete_heldout = _complete_family_rows(heldout, families)
    heldout_coverage = len(complete_heldout) / len(heldout) if heldout else 0.0
    if len(complete_source) < min_train_games or not heldout:
        return {
            "status": "blocked_insufficient_complete_history",
            "families": list(families),
            "source_games": len(source),
            "source_complete_games": len(complete_source),
            "heldout_games": len(heldout),
            "heldout_complete_games": len(complete_heldout),
            "heldout_coverage": heldout_coverage,
            "minimum_heldout_coverage": minimum_heldout_coverage,
            "writes_performed": False,
        }

    weights, means, scales = _fit_logistic_family_model(complete_source, families)
    actual: list[int] = []
    probabilities: list[float] = []
    for game in complete_heldout:
        values = [
            (float(game.family_scores[family]) - means[index]) / scales[index]
            for index, family in enumerate(families)
        ]
        probabilities.append(_sigmoid(
            weights[0] + sum(weight * value for weight, value in zip(weights[1:], values))
        ))
        actual.append(game.home_win)
    return {
        "status": "complete",
        "families": list(families),
        "source_games": len(source),
        "source_complete_games": len(complete_source),
        "heldout_games": len(heldout),
        "heldout_complete_games": len(complete_heldout),
        "heldout_coverage": heldout_coverage,
        "minimum_heldout_coverage": minimum_heldout_coverage,
        "coverage_pass": heldout_coverage >= minimum_heldout_coverage,
        "training": {
            "games": len(complete_source),
            "standardized_coefficients": {
                family: weights[index + 1]
                for index, family in enumerate(families)
            },
        },
        "heldout": {
            "test_games": len(actual),
            "win": {
                "log_loss": _log_loss(actual, probabilities),
                "brier": _brier(actual, probabilities),
                "calibration": _calibration(actual, probabilities),
            },
            "probability_bands": _probability_band_reports(actual, probabilities),
        },
        "writes_performed": False,
    }


def run_feature_family_season_heldout_sweep(
    games_by_season: Mapping[str, Iterable[BaselineGame | Mapping[str, Any]]],
    definitions: Mapping[str, tuple[str, ...]],
    *,
    min_train_games: int = 50,
    minimum_heldout_coverage: float = 0.95,
) -> dict[str, Any]:
    """Run frozen source-season validation in every supplied season direction."""
    seasons = list(games_by_season)
    if len(seasons) < 2:
        return {
            "status": "blocked_need_two_seasons",
            "definitions": {},
            "writes_performed": False,
        }
    reports: dict[str, Any] = {}
    for name, families in definitions.items():
        directions = {}
        for source_season, heldout_season in ((seasons[0], seasons[1]), (seasons[1], seasons[0])):
            directions[f"{source_season}_to_{heldout_season}"] = run_feature_family_season_heldout_validation(
                games_by_season[source_season],
                games_by_season[heldout_season],
                tuple(families),
                min_train_games=min_train_games,
                minimum_heldout_coverage=minimum_heldout_coverage,
            )
        reports[name] = {
            "families": list(families),
            "directions": directions,
        }
    return {
        "status": "complete" if reports else "blocked_no_definitions",
        "seasons": seasons,
        "definitions": reports,
        "writes_performed": False,
    }
