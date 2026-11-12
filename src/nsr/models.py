"""Baseline models. Each takes a View (data up to the as-of session only) and
returns one score per security column; higher means "expected to do better".
NaN means "no opinion" and the name is left out of that model's ranking.

These are known effects, registered as baselines. They are not discoveries.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .panel import View

VERSION = "v1"


def _window_return(v: View, start_back: int, end_back: int, min_frac: float) -> np.ndarray:
    """Compounded close-to-close return over sessions [-start_back, -end_back) from the as-of row."""
    n = len(v.dates)
    lo, hi = n - start_back, n - end_back
    if lo < 0:
        return np.full(v.ret_cc.shape[1], np.nan)
    r = np.nan_to_num(v.ret_cc[lo:hi], nan=0.0)
    out = np.prod(1 + r, axis=0) - 1
    enough = v.traded[lo:hi].mean(axis=0) >= min_frac
    return np.where(enough, out, np.nan)


def mom_12_1(v: View) -> np.ndarray:
    """12-1 momentum: return over the 231 sessions ending 21 sessions ago."""
    return _window_return(v, 252, 21, 0.8)


def rev_5(v: View) -> np.ndarray:
    """Short-term reversal: minus the last 5 sessions' return."""
    return -_window_return(v, 5, 0, 0.8)


def random(v: View) -> np.ndarray:
    """Pure noise, reproducible per date. Its measured skill must be zero; if it is not, the scorer leaks."""
    seed = int(hashlib.sha256(f"random|{VERSION}|{v.asof.date()}".encode()).hexdigest()[:16], 16)
    return np.random.default_rng(seed).standard_normal(v.ret_cc.shape[1])


MODELS = {"random": random, "mom_12_1": mom_12_1, "rev_5": rev_5}
HORIZONS = (1, 5, 20)
