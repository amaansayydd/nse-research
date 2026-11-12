"""Significance tests that account for how many ideas have been tried."""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329
T_FLOOR = 3.0           # Harvey, Liu and Zhu (2016): a new factor should clear t = 3, not 2
FAMILY_ALPHA = 0.05
FDR_Q = 0.10


def ic_summary(ic: np.ndarray, h: int) -> dict:
    """Mean daily rank IC and its t-stat. Dividing the day count by the horizon is the
    project's (deliberately conservative) allowance for overlapping targets."""
    ic = ic[np.isfinite(ic)]
    if len(ic) < 3 or ic.std(ddof=1) == 0:
        return {"days": int(len(ic)), "ic_mean": float("nan"), "ic_sd": float("nan"), "ic_t": float("nan")}
    mean, sd = float(ic.mean()), float(ic.std(ddof=1))
    return {"days": int(len(ic)), "ic_mean": mean, "ic_sd": sd, "ic_t": mean / sd * math.sqrt(len(ic) / h)}


def required_t(n_trials: int) -> float:
    """t a primary test must reach: Bonferroni at 5% one-sided over every hypothesis
    registered so far, never below 3."""
    return max(T_FLOOR, _N.inv_cdf(1 - FAMILY_ALPHA / max(n_trials, 1)))


def p_one_sided(t: float) -> float:
    return 1.0 if not math.isfinite(t) else 1 - _N.cdf(t)


def bh_survivors(pvalues: dict[str, float], q: float = FDR_Q) -> set[str]:
    """Benjamini-Hochberg: which trials survive at false discovery rate q."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, cut = len(items), 0
    for k, (_, p) in enumerate(items, 1):
        if p <= q * k / m:
            cut = k
    return {name for name, _ in items[:cut]}


def cluster_t(values: np.ndarray, clusters: np.ndarray) -> dict:
    """Mean of `values` with a standard error that lets observations in the same cluster
    (calendar month) be arbitrarily correlated."""
    ok = np.isfinite(values)
    values, clusters = values[ok], clusters[ok]
    n = len(values)
    if n < 3:
        return {"n": n, "clusters": 0, "mean": float("nan"), "t": float("nan")}
    mean = float(values.mean())
    _, inv = np.unique(clusters, return_inverse=True)
    resid_sum = np.bincount(inv, weights=values - mean)
    g = len(resid_sum)
    se = math.sqrt(float((resid_sum ** 2).sum()) * g / max(g - 1, 1)) / n
    return {"n": n, "clusters": g, "mean": mean, "t": mean / se if se > 0 else float("nan")}


def sharpe_tests(x: np.ndarray, n_trials: int, trial_sr_var: float = 0.0) -> dict:
    """Annualised Sharpe of a daily excess-return series, its probabilistic Sharpe ratio
    (chance the true Sharpe is above zero) and the deflated Sharpe ratio of Bailey and
    Lopez de Prado (2014): the same chance after allowing for the best of `n_trials` tries.
    The variance of Sharpe across trials is floored at 1/T, its sampling variance when
    every trial is noise."""
    x = x[np.isfinite(x)]
    t = len(x)
    if t < 30 or x.std(ddof=1) == 0:
        return {"sharpe_ann": float("nan"), "psr": float("nan"), "dsr": float("nan"), "days": t}
    sr = float(x.mean() / x.std(ddof=1))
    z = (x - x.mean()) / x.std(ddof=0)
    skew, kurt = float((z ** 3).mean()), float((z ** 4).mean())
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    sr0 = 0.0
    if n_trials > 1:
        v = max(trial_sr_var, 1.0 / t)
        sr0 = math.sqrt(v) * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
                              + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e)))
    return {"sharpe_ann": sr * math.sqrt(252), "psr": _N.cdf(sr * math.sqrt(t - 1) / denom),
            "dsr": _N.cdf((sr - sr0) * math.sqrt(t - 1) / denom), "days": t,
            "sharpe_daily": sr, "expected_max_sharpe_ann": sr0 * math.sqrt(252)}


def walk_forward_splits(n_sessions: int, first_test: int, test_len: int, horizon: int, embargo: int = 5):
    """Expanding-window splits for models that are fitted. Training rows whose target window
    reaches into the test block are purged (horizon + 1 sessions), plus an embargo. Yields
    (train_index, test_index) arrays of session positions."""
    start = first_test
    while start < n_sessions:
        stop = min(start + test_len, n_sessions)
        train_end = start - (horizon + 1) - embargo
        if train_end > 0:
            yield np.arange(0, train_end), np.arange(start, stop)
        start = stop
