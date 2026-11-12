"""Rank-average ensemble whose weights move only on matured rank ICs.

Pure functions, no data access: the backtest (research.signals.combo) and the
daily run call the same code. In live running the ICs come from scores.csv,
which is forward-only, so live weights start equal and shift only as forward
evidence arrives.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NAME = "ens_mom_ear"
COMPONENTS = ("mom_12_1", "ear_drift_60")
WEIGHT_H = 20           # weights use each component's matured 20-session rank IC
IC0, N0 = 0.02, 500     # prior: every component starts as if it had 500 days at IC 0.02
MIN_NAMES = 100         # a component with fewer scored names is treated as absent that day


def rank_pct(score: np.ndarray, eligible: np.ndarray, min_names: int = MIN_NAMES) -> np.ndarray:
    """(rank - 0.5) / n among eligible names with a finite score; NaN elsewhere.
    All NaN if fewer than `min_names` names qualify."""
    out = np.full(score.shape, np.nan)
    ok = eligible & np.isfinite(score)
    n = int(ok.sum())
    if n < min_names:
        return out
    out[ok] = (pd.Series(score[ok]).rank(method="average").to_numpy() - 0.5) / n
    return out


def weights(ic_sum: dict[str, float], ic_n: dict[str, int], components: tuple[str, ...] = COMPONENTS) -> dict[str, float]:
    """w_k proportional to max(0, shrunk mean IC_k); equal weights if every shrunk mean is <= 0."""
    m = {k: max((N0 * IC0 + float(ic_sum.get(k, 0.0))) / (N0 + int(ic_n.get(k, 0))), 0.0) for k in components}
    total = sum(m.values())
    return {k: (m[k] / total if total > 0 else 1.0 / len(components)) for k in components}


def combine(pcts: dict[str, np.ndarray], w: dict[str, float]) -> np.ndarray:
    """Weighted sum of rank percentiles. A missing percentile counts as 0.5 (no view).
    NaN only where every component is missing."""
    names = list(w)
    stack = np.vstack([pcts[k] for k in names])
    have = np.isfinite(stack)
    s = sum(w[k] * np.where(have[j], stack[j], 0.5) for j, k in enumerate(names))
    return np.where(have.any(axis=0), s, np.nan)
