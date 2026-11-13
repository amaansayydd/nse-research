"""Models in the daily run. Each takes a View (data up to the as-of session only)
and returns one score per security column; higher means "expected to do better".
NaN means "no opinion" and the name is left out of that model's ranking.

Baselines are known effects kept as yardsticks. Challengers passed Phase 2 on
research data and predict in shadow; nothing here is a champion until the forward
record and the owner say so (research_log.md, Phase 3 rules).
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from . import ensemble
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
    """Pure noise. Each score is a hash of (version, date, ticker), so anyone can
    reproduce it from the log alone and it does not depend on how a build numbers
    securities. Its measured skill must be zero; if it is not, the scorer leaks."""
    day = v.asof.date()
    out = np.full(len(v.keys), np.nan)
    for c, k in enumerate(v.keys):
        if k:
            out[c] = int(hashlib.sha256(f"random|{VERSION}|{day}|{k}".encode()).hexdigest()[:13], 16) / 16 ** 13
    return out


# ---------------------------------------------------------------- challengers
RESULTS = re.compile(r"result", re.I)
EAR_HOLD, EAR_DAYS, EAR_MAX_LEAD, EAR_RESCHEDULE = 60, 2, 60, 20


def results_meetings(v: View) -> tuple[np.ndarray, np.ndarray]:
    """Meeting dates and columns of board meetings called to consider results, from notices
    filed on or before the meeting and at most 60 days ahead. A meeting is dropped if a later
    notice, filed on or before it, names another date within 20 days (a reschedule)."""
    bm = v.tables.get("board_meetings")
    if bm is None or bm.empty:
        return np.empty(0, dtype="datetime64[ns]"), np.empty(0, dtype=np.int64)
    lead = (bm.meeting - bm.known).dt.days
    bm = bm[bm.purpose.str.contains(RESULTS) & (lead >= 0) & (lead <= EAR_MAX_LEAD)]
    bm = bm.sort_values("known", kind="stable").drop_duplicates(["symbol", "meeting"])[["known", "symbol", "meeting"]]
    pair = bm.merge(bm, on="symbol", suffixes=("", "_2"))
    gap = (pair.meeting_2 - pair.meeting).dt.days.abs()
    moved = pair[(pair.known_2 > pair.known) & (pair.known_2 <= pair.meeting) & (gap > 0) & (gap <= EAR_RESCHEDULE)]
    bm = bm.merge(moved[["symbol", "meeting"]].drop_duplicates().assign(moved=True), on=["symbol", "meeting"], how="left")
    bm = bm[bm.moved.isna()]
    col = v.symbol_columns(bm.known, bm.symbol)
    return bm.meeting.to_numpy()[col >= 0], col[col >= 0]


def ear_drift_60(v: View) -> np.ndarray:
    """T-0002. Latest results-day reaction: the stock's return minus the universe's mean return,
    summed over the first 2 sessions on or after the results board meeting. Carried for 60
    sessions from the evening the reaction window closes."""
    out = np.full(v.ret_cc.shape[1], np.nan)
    meeting, col = results_meetings(v)
    if len(col) == 0:
        return out
    i = len(v.dates) - 1
    first = np.searchsorted(v.dates, meeting, side="left")
    last = first + EAR_DAYS - 1
    live = (last <= i) & (last > i - EAR_HOLD)          # reaction complete, and still inside its 60 sessions
    mkt: dict[int, float] = {}
    for k in np.flatnonzero(live)[np.argsort(last[live], kind="stable")]:
        rows = np.arange(first[k], last[k] + 1)
        r = v.ret_cc[rows, col[k]].astype(np.float64)
        if not (v.traded[rows, col[k]].all() and np.isfinite(r).all()):
            continue
        for j in rows:
            if j not in mkt:
                rj = v.ret_cc[j].astype(np.float64)
                m = v.member_mask(j) & v.traded[j] & np.isfinite(rj)
                mkt[j] = float(np.nanmean(np.where(m, rj, np.nan))) if m.any() else np.nan
        base = np.array([mkt[j] for j in rows])
        if np.isfinite(base).all():
            out[col[k]] = float((r - base).sum())
    return out


MODELS = {"random": random, "mom_12_1": mom_12_1, "rev_5": rev_5, "ear_drift_60": ear_drift_60}
# Ensembles are built from the rank percentiles of the models above (nsr.ensemble).
ENSEMBLES = {ensemble.NAME: ensemble.COMPONENTS}
ROLES = {"random": "control", "mom_12_1": "baseline", "rev_5": "baseline",
         "ear_drift_60": "challenger", ensemble.NAME: "challenger"}
VERSIONS = {name: "v1" for name in ROLES}
ALL_MODELS = (*MODELS, *ENSEMBLES)
MIN_NAMES = 100          # a challenger that can rank fewer names than this stays silent that day
MAX_CHALLENGERS = 3      # shadow slots (Phase 3 rule)
HORIZONS = (1, 5, 20)

assert sum(r == "challenger" for r in ROLES.values()) <= MAX_CHALLENGERS, "at most 3 challengers in shadow"
assert set(ROLES) == set(ALL_MODELS)
