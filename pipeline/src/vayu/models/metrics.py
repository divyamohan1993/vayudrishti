"""Error metrics and honest skill scoring (spec 5.1/5.2)."""

from __future__ import annotations

import numpy as np


def _clean(y_true, y_pred) -> tuple[np.ndarray, np.ndarray]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mask = ~(np.isnan(yt) | np.isnan(yp))
    return yt[mask], yp[mask]


def rmse(y_true, y_pred) -> float:
    yt, yp = _clean(y_true, y_pred)
    if yt.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def mae(y_true, y_pred) -> float:
    yt, yp = _clean(y_true, y_pred)
    if yt.size == 0:
        return float("nan")
    return float(np.mean(np.abs(yt - yp)))


def skill_pct(model_error: float, baseline_error: float) -> float:
    """Percent improvement in error over a baseline. Positive = better.

    Reported honestly: a worse-than-baseline model yields a NEGATIVE skill, which is a
    valid published number (spec 5.2, acceptance 2). Returns 0.0 if the baseline error
    is zero/undefined.
    """
    if not baseline_error or np.isnan(baseline_error) or np.isnan(model_error):
        return 0.0
    return round(100.0 * (1.0 - model_error / baseline_error), 1)


def pinball_loss(y_true, y_pred, quantile: float) -> float:
    """Quantile (pinball) loss: the proper score for a quantile forecast."""
    yt, yp = _clean(y_true, y_pred)
    if yt.size == 0:
        return float("nan")
    diff = yt - yp
    return float(np.mean(np.maximum(quantile * diff, (quantile - 1.0) * diff)))


__all__ = ["rmse", "mae", "skill_pct", "pinball_loss"]
