"""Intervention-Ledger event-study (spec 13, acceptance 15). Owner: vayu-models.

On the weather-normalized PM2.5 series (deweather.py), estimate the effect of each sharp
GRAP stage transition with:
  - an event-study before/after contrast on the deweathered series (weather removed, so
    the change reflects emissions/policy, not meteorology),
  - a PLACEBO test on matched non-intervention days (defeats the regression-to-mean
    attack: GRAP triggers when pollution is already high), and
  - a block-bootstrap confidence interval (preserves day-to-day autocorrelation).
A CI spanning 0 with a failed placebo is published as a null accountability finding.
Real CAQM calendar from config/interventions/{city}.yaml; zero invented dates.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import yaml

from vayu.publish.sanitize import sanitize_text
from vayu.settings import repo_root
from vayu.timeutils import IST

# Sharp interventions to score (invocations of the higher, biting stages).
SHARP_INTERVENTIONS = [
    ("GRAP-III invoked", "2025-11-11"),
    ("GRAP-IV invoked", "2025-12-13"),
    ("GRAP-IV invoked", "2026-01-17"),
]
WINDOW_DAYS = 10
MIN_PLACEBO_GAP = 21
N_PLACEBO = 300
N_BOOT = 600
BLOCK = 3


def _to_utc(ist_str: str) -> datetime:
    return datetime.strptime(ist_str, "%Y-%m-%d %H:%M").replace(tzinfo=IST).astimezone(UTC)


def load_grap_calendar(city: str = "delhi") -> tuple[dict, list[dict]]:
    """Parse config/interventions/{city}.yaml into (meta, calendar-entries)."""
    path = repo_root() / "config" / "interventions" / f"{city}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = []
    for s in data["stages"]:
        entries.append({
            "stage": s["stage"],
            "start_utc": _to_utc(s["start_ist"]),
            "end_utc": _to_utc(s["end_ist"]) if s.get("end_ist") else None,
            "source_url": s["source_url"],
        })
    return data, entries


def _window_means(series: pd.Series, day: pd.Timestamp, window: int) -> tuple[float, float]:
    pre = series[(series.index >= day - pd.Timedelta(days=window)) & (series.index < day)]
    post = series[(series.index >= day) & (series.index < day + pd.Timedelta(days=window))]
    return (pre.mean(), post.mean())


def event_effect(daily: pd.DataFrame, day: pd.Timestamp, window: int = WINDOW_DAYS) -> float:
    """Post-minus-pre change in weather-normalized PM2.5 (negative = reduction)."""
    s = daily.set_index("date")["pm25_normalized"]
    s.index = pd.to_datetime(s.index)
    pre, post = _window_means(s, day, window)
    return float(post - pre)


def placebo_test(daily: pd.DataFrame, day: pd.Timestamp, intervention_days: list[pd.Timestamp],
                 *, window: int = WINDOW_DAYS, n: int = N_PLACEBO, seed: int = 0) -> tuple[bool, float]:
    """Compare the real effect to effects at random non-intervention days.

    Returns (passed, percentile). Passes when the real reduction is more extreme (more
    negative) than 80% of placebo effects, i.e. it is not a generic high-pollution
    mean-reversion artefact.
    """
    s = daily.set_index("date")["pm25_normalized"]
    s.index = pd.to_datetime(s.index)
    real = event_effect(daily, day, window)
    lo, hi = s.index.min() + pd.Timedelta(days=window), s.index.max() - pd.Timedelta(days=window)
    candidates = pd.date_range(lo, hi, freq="D")
    blocked = set()
    for d in intervention_days:
        for k in range(-MIN_PLACEBO_GAP, MIN_PLACEBO_GAP + 1):
            blocked.add((d + pd.Timedelta(days=k)).normalize())
    pool = [c for c in candidates if c.normalize() not in blocked]
    if not pool:
        return (False, float("nan"))
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    placebo = np.array([event_effect(daily, pool[i], window) for i in picks])
    percentile = float((placebo < real).mean())  # fraction of placebos more negative than real
    passed = bool(real < 0 and percentile <= 0.20)
    return (passed, percentile)


def block_bootstrap_ci(daily: pd.DataFrame, day: pd.Timestamp, *, window: int = WINDOW_DAYS,
                       block: int = BLOCK, n_boot: int = N_BOOT, seed: int = 0) -> tuple[float, float]:
    """Block-bootstrap CI on the effect (resamples pre/post daily values in blocks)."""
    s = daily.set_index("date")["pm25_normalized"]
    s.index = pd.to_datetime(s.index)
    pre = s[(s.index >= day - pd.Timedelta(days=window)) & (s.index < day)].to_numpy()
    post = s[(s.index >= day) & (s.index < day + pd.Timedelta(days=window))].to_numpy()
    if len(pre) < block or len(post) < block:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)

    def resample(arr):
        n_blocks = int(np.ceil(len(arr) / block))
        starts = rng.integers(0, max(1, len(arr) - block + 1), n_blocks)
        return np.concatenate([arr[st:st + block] for st in starts])[: len(arr)]

    effects = np.array([resample(post).mean() - resample(pre).mean() for _ in range(n_boot)])
    return (round(float(np.percentile(effects, 2.5)), 1), round(float(np.percentile(effects, 97.5)), 1))


def build_effects(daily: pd.DataFrame) -> list[dict]:
    """Event-study effect entries for interventions.json (one per sharp intervention)."""
    intervention_days = [pd.Timestamp(d) for _, d in SHARP_INTERVENTIONS]
    effects = []
    for label, dstr in SHARP_INTERVENTIONS:
        day = pd.Timestamp(dstr)
        s = daily.set_index("date")
        s.index = pd.to_datetime(s.index)
        n_days = int(((s.index >= day - pd.Timedelta(days=WINDOW_DAYS)) &
                      (s.index < day + pd.Timedelta(days=WINDOW_DAYS))).sum())
        if n_days < WINDOW_DAYS:  # not enough coverage around this date
            continue
        effect = round(event_effect(daily, day), 1)
        ci_low, ci_high = block_bootstrap_ci(daily, day)
        passed, pct = placebo_test(daily, day, intervention_days)
        if not np.isfinite(ci_low):
            continue
        lo, hi = min(ci_low, effect), max(ci_high, effect)
        note = sanitize_text(
            f"Event-study on deweathered series, {WINDOW_DAYS}d pre/post; block-bootstrap CI "
            f"(block={BLOCK}, {N_BOOT}x); placebo percentile {pct:.2f} "
            f"({'passed' if passed else 'not distinguishable from mean-reversion'})."
        )
        effects.append({
            "stage_transition": f"{label} ({dstr})",
            "effect_ugm3": effect, "ci_low": lo, "ci_high": hi,
            "placebo_pass": passed, "n_days": n_days, "method_notes": note,
        })
    return effects


__all__ = ["load_grap_calendar", "event_effect", "placebo_test", "block_bootstrap_ci",
           "build_effects", "SHARP_INTERVENTIONS"]
