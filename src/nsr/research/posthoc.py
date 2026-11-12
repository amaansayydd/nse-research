"""Post-hoc diagnostics for trials that passed. These were NOT pre-registered: they exist
to attack a pass (leak audit, placebo, decay), and nothing here can be adopted as a signal.

    python -m nsr.research.posthoc T-0002
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import evaluate, signals, stats
from .data import ResearchData
from .features import controls
from .run import RESULTS


def t0002(rd: ResearchData) -> dict:
    ctrl = controls(rd)
    S = signals.ear_drift(rd)
    h = 20

    def summary(M):
        dm = evaluate.daily_metrics(rd, M, ctrl)
        g = dm[dm.h == h]
        return {"ic": stats.ic_summary(g.ic.to_numpy(), h), "ic_neutral": stats.ic_summary(g.ic_neutral.to_numpy(), h),
                "top_excess_mean": float(g.top_excess.mean())}, dm

    out = {}
    base, dm = summary(S)
    out["registered"] = base
    # 1. entry delayed: use the score one and two sessions late (guards the 20:00 publication assumption)
    for lag in (1, 2):
        L = np.full(S.shape, np.nan)
        L[lag:] = S[:-lag]
        out[f"score used {lag} session(s) late"], _ = summary(L)
    # 2. placebo: the same two-session abnormal return measured 30 sessions after each meeting (no results that day)
    tab = rd.tables["board_meetings"].copy()
    shifted = rd.dates[np.minimum(np.searchsorted(rd.dates, tab.meeting.to_numpy()) + 30, len(rd.dates) - 1)]
    fake = ResearchData(rd.panel, rd.fields, rd.member, rd.uni_rank, rd.fwd,
                        {"board_meetings": tab.assign(meeting=shifted, known=np.minimum(tab.known.to_numpy(), shifted.to_numpy()))})
    out["placebo: reaction measured 30 sessions after the meeting"], _ = summary(signals.ear_drift(fake))
    # 3. decay: IC by half-year for the last four years, and top-decile excess by year
    g = dm[dm.h == h].copy()
    recent = g[g.date >= "2022-01-01"]
    half = recent.groupby([recent.date.dt.year, (recent.date.dt.month > 6).map({False: "H1", True: "H2"})])
    out["ic_by_half_year_since_2022"] = {f"{y}{k}": [round(float(v.ic.mean()), 4), int(len(v))] for (y, k), v in half}
    out["top_decile_excess_by_year"] = {int(y): round(float(v), 4) for y, v in g.groupby(g.date.dt.year).top_excess.mean().items()}
    # 4. is it only the first sessions after results? IC by age of the score
    age = np.full(S.shape, np.nan)
    fresh = np.isfinite(S) & ~np.isfinite(np.vstack([np.full((1, S.shape[1]), np.nan), S[:-1]]))
    changed = np.isfinite(S) & (np.vstack([np.full((1, S.shape[1]), np.nan), S[:-1]]) != S)
    last = np.where(fresh | changed, np.arange(S.shape[0])[:, None], -1)
    last = np.maximum.accumulate(last, axis=0)
    age = np.where(np.isfinite(S), np.arange(S.shape[0])[:, None] - last, np.nan)
    for name, lo, hi in (("score 0-9 sessions old", 0, 9), ("score 10-29 sessions old", 10, 29), ("score 30-59 sessions old", 30, 59)):
        M = np.where((age >= lo) & (age <= hi), S, np.nan)
        dmb = evaluate.daily_metrics(rd, M, None, min_names=40)
        gb = dmb[dmb.h == h]
        out[name] = {"ic": stats.ic_summary(gb.ic.to_numpy(), h), "avg_names": float(gb.n.mean())}
    return out


if __name__ == "__main__":
    trial = sys.argv[1]
    res = {"T-0002": t0002}[trial](ResearchData.load())
    (RESULTS / f"{trial}_posthoc.json").write_text(evaluate.to_json(res))
    for k, v in res.items():
        print(k, "|", v)
