"""Champion and challengers: the forward comparison (research_log.md, Phase 3 rules v1).

Nothing here promotes anything. The code works out, at fixed checkpoints, whether a
challenger has met the statistical part of the rule. A promotion also needs a
portfolio sanity check, the owner's holdout check and the owner's decision, and is
recorded by hand in champion.json and changelog.md.
"""
from __future__ import annotations

import json
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config

STATE = config.PROJECT / "champion.json"
DECISION_H = 20          # horizon every current challenger was registered at, and the one costs allow
MIN_SESSIONS = 250       # about a year: four results seasons, twelve independent 20-session windows
CHECK_EVERY = 125        # decisions are read only at 250, 375, 500 ... scored sessions
ALPHA = 0.025            # one-sided, shared across every challenger ever started
FUTILITY_SESSIONS = 500
FUTILITY_T = 0.5
DEFAULT_STATE = {"champion": None, "champion_since": None, "reference": "mom_12_1", "ever_compared": [],
                 "former_champions": [], "retired": []}


def load_state(path=None) -> dict:
    path = path or STATE
    return {**DEFAULT_STATE, **(json.loads(path.read_text()) if path.exists() else {})}


def threshold(n_ever: int) -> float:
    """Required t. Rises with the number of challengers ever compared (Bonferroni)."""
    return NormalDist().inv_cdf(1 - ALPHA / max(int(n_ever), 1))


def checkpoint(n_days: int) -> int:
    """Largest checkpoint at or below n_days; 0 before the minimum period."""
    return 0 if n_days < MIN_SESSIONS else MIN_SESSIONS + (n_days - MIN_SESSIONS) // CHECK_EVERY * CHECK_EVERY


def _t(x, h: int) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x) / h))


def compare(scores: pd.DataFrame, state: dict, challengers: list[str]) -> pd.DataFrame:
    """One row per challenger, using the scored sessions up to its latest checkpoint
    (or everything so far, marked as too early, before the first checkpoint)."""
    ref, need = state["reference"], threshold(len(state["ever_compared"]))
    scores = scores.astype({c: float for c in ("ic", "ic_ex_ref", "top_excess") if c in scores})
    s = scores[scores.horizon == DECISION_H]
    r = s[s.model == ref].set_index("asof_date")
    ctl = scores[scores.model == "random"]
    rows = []
    for name in challengers:
        c = s[s.model == name].set_index("asof_date").sort_index()
        c = c[c.index.isin(r.index)]
        n, cp = len(c), checkpoint(len(c))
        used = c.iloc[:cp] if cp else c
        rr = r.ic.reindex(used.index)
        row = {"challenger": name, "reference": ref, "scored_sessions": n, "judged_on": len(used),
               "ic": used.ic.mean() if n else np.nan, "ic_t": _t(used.ic.to_numpy(), DECISION_H),
               "reference_ic": rr.mean() if n else np.nan,
               "ic_beyond_reference": used.ic_ex_ref.mean() if n else np.nan,
               "beyond_t": _t(used.ic_ex_ref.to_numpy(), DECISION_H),
               "top_decile_excess": used.top_excess.mean() if n else np.nan, "required_t": need}
        if not cp:
            row["status"] = f"too early: {n} of {MIN_SESSIONS} sessions"
        else:
            last = used.index.max()
            ct = ctl[ctl.asof_date <= last]
            control_ok = all(not (abs(_t(g.ic.to_numpy(), h)) >= 3) for h, g in ct.groupby("horizon"))
            met = (row["beyond_t"] >= need and row["ic"] > max(row["reference_ic"], 0.0)
                   and row["top_decile_excess"] > 0)
            if not control_ok:
                row["status"] = "frozen: the random control shows skill, audit the scorer"
            elif met:
                row["status"] = "ELIGIBLE at this checkpoint: portfolio check, owner's holdout check and decision needed"
            elif cp >= FUTILITY_SESSIONS and not row["beyond_t"] >= FUTILITY_T:
                row["status"] = "futile: retire and write a postmortem"
            else:
                row["status"] = f"not met at {cp}; next checkpoint at {cp + CHECK_EVERY}"
        rows.append(row)
    return pd.DataFrame(rows)
