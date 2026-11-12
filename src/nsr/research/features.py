"""Vectorised building blocks. Every function returns [session, column] arrays whose
row t uses rows <= t only (trailing windows)."""
from __future__ import annotations

import numpy as np

from .data import ResearchData


def roll_sum(a: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Trailing sum over w rows ignoring NaN, and the count of finite values."""
    ok = np.isfinite(a)
    c = np.cumsum(np.where(ok, a, 0.0), axis=0, dtype=np.float64)
    n = np.cumsum(ok, axis=0, dtype=np.int64)
    s, k = c.copy(), n.copy()
    s[w:] -= c[:-w]
    k[w:] -= n[:-w]
    return s, k


def roll_mean(a: np.ndarray, w: int, min_obs: int) -> np.ndarray:
    s, k = roll_sum(a, w)
    return np.where(k >= min_obs, s / np.maximum(k, 1), np.nan)


def roll_std(a: np.ndarray, w: int, min_obs: int) -> np.ndarray:
    s, k = roll_sum(a, w)
    ss, _ = roll_sum(a * a, w)
    kk = np.maximum(k, 2)
    var = (ss - s * s / kk) / (kk - 1)
    return np.where(k >= min_obs, np.sqrt(np.maximum(var, 0.0)), np.nan)


def roll_corr(x: np.ndarray, y: np.ndarray, w: int, min_obs: int) -> np.ndarray:
    """Trailing Pearson correlation over w rows, using rows where both are finite."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = np.where(ok, x, np.nan), np.where(ok, y, np.nan)
    sx, k = roll_sum(x, w)
    sy, _ = roll_sum(y, w)
    sxx, _ = roll_sum(x * x, w)
    syy, _ = roll_sum(y * y, w)
    sxy, _ = roll_sum(x * y, w)
    n = np.maximum(k, 1)
    cov = sxy - sx * sy / n
    vx, vy = sxx - sx * sx / n, syy - sy * sy / n
    with np.errstate(invalid="ignore", divide="ignore"):
        r = cov / np.sqrt(vx * vy)
    return np.where((k >= min_obs) & (vx > 1e-18) & (vy > 1e-18), r, np.nan)


def window_return(rd: ResearchData, start_back: int, end_back: int, min_frac: float) -> np.ndarray:
    """Compounded close-to-close return over the sessions from `start_back` ago up to (not
    including) `end_back` ago, counting from the row after each as-of row. Same definition as
    nsr.models._window_return, for every session at once."""
    p = rd.panel
    lg = np.log1p(np.nan_to_num(p.ret_cc.astype(np.float64), nan=0.0))
    c = np.vstack([np.zeros((1, lg.shape[1])), np.cumsum(lg, axis=0)])        # c[k] = sum of rows < k
    t = np.vstack([np.zeros((1, lg.shape[1])), np.cumsum(p.traded, axis=0, dtype=np.int64)])
    n = len(p.dates)
    out = np.full(lg.shape, np.nan)
    rows = np.arange(start_back - 1, n)                  # as-of row index; window is rows [r+1-start_back, r+1-end_back)
    lo, hi = rows + 1 - start_back, rows + 1 - end_back
    ret = np.expm1(c[hi] - c[lo])
    frac = (t[hi] - t[lo]) / (start_back - end_back)
    out[rows] = np.where(frac >= min_frac, ret, np.nan)
    return out


def controls(rd: ResearchData) -> dict[str, np.ndarray]:
    """Known effects every new signal is measured against."""
    with np.errstate(divide="ignore", invalid="ignore"):
        log_value = np.log(np.where(rd.fields["value"] > 0, rd.fields["value"], np.nan))
    return {
        "mom_12_1": window_return(rd, 252, 21, 0.8),
        "rev_5": -window_return(rd, 5, 0, 0.8),
        "ret_60": window_return(rd, 60, 0, 0.8),
        "vol_60": roll_std(rd.panel.ret_cc.astype(np.float64), 60, 40),
        "liquidity": roll_mean(log_value, 126, 60),
    }
