"""Decay monitor: a one-sided CUSUM changepoint test on each model's forward rank IC.

For horizon h the stream is every h-th scored session, so observations do not share
outcome days. The in-control level is HAIRCUT x the backtest IC (backtests flatter
a signal); the test looks for a drop from that level to zero. An alarm marks the
model `decaying` and estimates when the change began. Retirement needs more: see
research_log.md, Phase 3 rules v1.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import config

EXPECTED = config.CODE / "models" / "expected_ic_v1.json"
HAIRCUT = 0.5
FALSE_ALARM_SESSIONS = 5000      # about one false alarm per stream in 20 years of sessions
RETIRE_WINDOW = 250              # sessions of decision-horizon IC that must average <= 0 to retire


def _arl(k: float, b: float, sign: float) -> float:
    """Siegmund's approximation to the average run length of a CUSUM whose increments have
    mean sign*k and unit variance, with corrected threshold b."""
    x = 2 * k * b
    return (math.exp(-sign * x) + sign * x - 1) / (2 * k * k)


def cusum_threshold(k: float, arl0: float) -> float:
    lo, hi = 0.0, 500.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _arl(k, mid + 1.166, -1.0) < arl0 else (lo, mid)
    return hi


def cusum(x: np.ndarray, mu0: float, sd0: float, arl0: float) -> dict:
    """Detect a fall in the mean of x from mu0 to zero. Returns the alarm index (first crossing),
    the estimated start of the change (the observation after the statistic last sat at zero),
    and the expected number of observations to detect a complete loss of the edge."""
    k = mu0 / sd0 / 2
    thr = cusum_threshold(k, arl0)
    s, start, alarm, change = 0.0, 0, None, None
    for t, v in enumerate(x):
        s = max(0.0, s + (mu0 - v) / sd0 - k)
        if s == 0.0:
            start = t + 1
        elif s >= thr and alarm is None:
            alarm, change = t, start
    return {"n": len(x), "stat": s, "threshold": thr, "alarm": alarm, "change": change,
            "detect_obs": _arl(k, thr + 1.166, 1.0)}


def load_expected(path=None) -> dict:
    path = path or EXPECTED
    return json.loads(path.read_text())["models"] if path.exists() else {}


def decay_table(scores: pd.DataFrame, expected: dict | None = None) -> pd.DataFrame:
    """One row per (model, horizon) that has a backtest expectation."""
    expected = load_expected() if expected is None else expected
    rows = []
    for model, by_h in expected.items():
        for h_s, e in by_h.items():
            h = int(h_s)
            g = scores[(scores.model == model) & (scores.horizon == h)].sort_values("asof_date")
            x, dates = g.ic.to_numpy(dtype=float)[::h], g.asof_date.to_numpy()[::h]
            mu0 = HAIRCUT * e["ic"]
            if mu0 <= 0:
                continue
            c = cusum(x, mu0, e["sd"], FALSE_ALARM_SESSIONS / h)
            rows.append({"model": model, "horizon": h, "expected_ic": mu0, "observations": c["n"],
                         "forward_ic": float(np.mean(x)) if len(x) else np.nan,
                         "cusum": c["stat"], "alarm_at": c["threshold"],
                         "state": "ok" if c["alarm"] is None else f"DECAYING since about {dates[min(c['change'], len(dates) - 1)]}",
                         "sessions_to_detect_total_loss": c["detect_obs"] * h})
    return pd.DataFrame(rows)


def retire_flags(scores: pd.DataFrame, table: pd.DataFrame, decision_h: int = 20) -> dict[str, bool]:
    """A model meets the retirement rule when any of its streams is in alarm and its mean IC at
    the decision horizon over the last RETIRE_WINDOW scored sessions is not above zero."""
    out = {}
    for model, g in table.groupby("model"):
        recent = scores[(scores.model == model) & (scores.horizon == decision_h)].sort_values("asof_date").ic.astype(float).tail(RETIRE_WINDOW)
        out[model] = bool(g.state.ne("ok").any() and len(recent) >= RETIRE_WINDOW and recent.mean() <= 0)
    return out
