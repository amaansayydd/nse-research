"""Checks for the observed tier, on research data only.

    python -m nsr.research.observed_check              parity: live event list against the research one
    python -m nsr.research.observed_check --calibrate  freeze p_beat for event rows (models/observed_v1.json)

Parity replays the live function session by session, giving it only what the daily run would
hold that evening (notices of the last 520 days), and compares the flagged names with
research.signals.results_date_shift over the whole research window.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .. import config, observed, rehearsal
from . import signals
from .data import ResearchData
from .run import RESULTS


def live_events(rd: ResearchData, start: int, stop: int, days: int = observed.NOTICE_DAYS) -> pd.DataFrame:
    bm, rows = rd.tables["board_meetings"], []
    for i in range(start, stop):
        d = rd.dates[i]
        rd.panel.tables[observed.NOTICE_TABLE] = bm[(bm.known <= d) & (bm.known > d - pd.Timedelta(days=days))]
        f = observed.results_advance(rd.panel.view(i))
        rows += [(i, int(c), float(s)) for c, s in zip(f.col, f.score)]
    rd.panel.tables.pop(observed.NOTICE_TABLE, None)
    return pd.DataFrame(rows, columns=["i", "col", "score"])


def parity(rd: ResearchData) -> dict:
    first = int(np.searchsorted(rd.dates, pd.Timestamp("2011-01-03")))
    want = signals.results_date_shift(rd)
    want = want[want.i >= first]
    got = live_events(rd, first, len(rd.dates))
    m = want.merge(got, on=["i", "col"], how="outer", indicator=True)
    both = m[m._merge == "both"]
    short = live_events(rd, len(rd.dates) - 500, len(rd.dates), days=240)
    w2 = want[want.i >= len(rd.dates) - 500]
    out = {"sessions": int(len(rd.dates) - first), "window": [str(rd.dates[first].date()), str(rd.dates[-1].date())],
           "research_events": int(len(want)), "live_events": int(len(got)),
           "only_in_research": int((m._merge == "left_only").sum()), "only_in_live": int((m._merge == "right_only").sum()),
           "max_abs_score_diff": float((both.score + both.abnormal).abs().max()),
           "control: live events found with a 240-day notice window, last 500 sessions": int(len(short)),
           "control: research events in the same sessions": int(len(w2))}
    out["ok"] = out["only_in_research"] == 0 and out["only_in_live"] == 0 and out["max_abs_score_diff"] < 1e-9
    (RESULTS / "parity_results_advance_5d.json").write_text(json.dumps(out, indent=1))
    return out


def calibrate(rd: ResearchData) -> dict:
    """Share of research events that beat the universe median, from sessions that end before the
    rehearsal window. A constant per horizon: an event row carries no rank to scale it by."""
    start, _ = rehearsal.window(rd.panel)
    ev = signals.results_date_shift(rd)
    ev = ev[(ev.i >= rd.eval_sessions().start) & (ev.i < start - 25)]
    p = {}
    for h, fwd in rd.fwd.items():
        beat = []
        for i, g in ev.groupby("i"):
            row = fwd[i][rd.member[i]]
            med = np.nanmedian(row) if np.isfinite(row).any() else np.nan
            r = fwd[i, g.col.to_numpy()]
            beat += list((r[np.isfinite(r)] > med).astype(float)) if np.isfinite(med) else []
        p[str(h)] = round(float(np.mean(beat)), 4)
    out = {"version": "v1", "fit_sessions": [str(rd.dates[rd.eval_sessions().start].date()), str(rd.dates[start - 26].date())],
           "events": int(len(ev)), "note": "p_beat = share of research events that beat the universe median; in sample",
           "p_beat": {observed.NAME: p}}
    observed.CALIBRATION.parent.mkdir(exist_ok=True)
    observed.CALIBRATION.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    data = ResearchData.load(tables=("board_meetings",))
    r = calibrate(data) if a.calibrate else parity(data)
    print(json.dumps(r, indent=1))
    raise SystemExit(0 if a.calibrate or r["ok"] else 1)
