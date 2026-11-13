"""Check that the live results-drift model reproduces the backtested signal on real data.

Compares what the daily-run code logged for `ear_drift_60` during the dress rehearsal
(rehearsal/predictions.csv, two research years) with `signals.ear_drift` computed on the
whole research dataset. Run after `python -m nsr.rehearsal`.

    python -m nsr.research.parity
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config
from . import signals
from .data import ResearchData


def run() -> dict:
    rd = ResearchData.load(tables=("board_meetings",))
    S = signals.ear_drift(rd)
    p = rd.panel
    preds = pd.read_csv(config.PROJECT / "rehearsal" / "predictions.csv")
    preds = preds[preds.model == "ear_drift_60"]
    worst, names, days, coverage_diff, silent_ok = 0.0, 0, 0, 0, 0
    logged = set(preds.asof_date)
    for asof, g in preds.groupby("asof_date"):
        i = p.idx(asof)
        on = p.symbols_on(i)
        col = p.col(pd.Series(on.index, index=on.to_numpy()).reindex(g.symbol).to_numpy().astype(np.int64))
        want = rd.member[i] & p.traded[i] & np.isfinite(S[i])
        coverage_diff += int(set(col) != set(np.flatnonzero(want)))
        worst = max(worst, float(np.abs(g.score.to_numpy() - np.round(S[i, col], 6)).max()))
        names, days = names + len(g), days + 1
    first = p.idx(min(logged))
    for i in range(first, len(p.dates)):                      # days the live model stayed silent
        if p.dates[i].strftime("%Y-%m-%d") not in logged:
            silent_ok += int((rd.member[i] & p.traded[i] & np.isfinite(S[i])).sum() < 100)
    silent = len(p.dates) - first - days
    out = {"days_compared": days, "names_compared": names, "max_abs_score_diff": worst,
           "days_with_different_names": coverage_diff, "silent_days": silent,
           "silent_days_where_backtest_also_has_under_100_names": silent_ok,
           "ok": worst < 1e-6 and coverage_diff == 0 and silent == silent_ok}
    (config.PROJECT / "research" / "results" / "parity_ear_drift_60.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
