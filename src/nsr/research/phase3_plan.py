"""Planning numbers for the Phase 3 forward test, from research-window backtests.

Not a trial: no signal is changed or chosen here. It measures, for each challenger,
how noisy the forward statistics will be, so the promotion rule and the decay
monitor can be sized before any forward score exists. Writes
research/results/phase3_plan.json and models/expected_ic_v1.json.

    python -m nsr.research.phase3_plan
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .. import champion, config, ensemble
from ..score import ic_excluding
from . import signals
from .data import HORIZONS, ResearchData
from .features import window_return
from .run import RESULTS

REF = "mom_12_1"


def _summ(x: np.ndarray, h: int) -> dict:
    x = x[np.isfinite(x)]
    m, sd = float(x.mean()), float(x.std(ddof=1))
    return {"days": int(len(x)), "mean": m, "sd": sd, "t": m / sd * math.sqrt(len(x) / h)}


def _sessions_needed(mean: float, sd: float, h: int, t: float) -> float:
    return float("inf") if mean <= 0 else h * (t * sd / mean) ** 2


def run() -> dict:
    rd = ResearchData.load()
    p = rd.panel
    S = {"mom_12_1": window_return(rd, 252, 21, 0.8), "rev_5": -window_return(rd, 5, 0, 0.8),
         "ear_drift_60": signals.ear_drift(rd), ensemble.NAME: signals.combo(rd)}
    elig = rd.member & p.traded
    acc = {m: {h: {"ic": [], "ex": [], "d": []} for h in HORIZONS} for m in S}
    for i in rd.eval_sessions():
        pct = {m: ensemble.rank_pct(S[m][i], elig[i], 100 if m in ("ear_drift_60", ensemble.NAME) else 1) for m in S}
        for h in HORIZONS:
            r = rd.fwd[h][i]
            ic = {}
            for m in S:
                ok = np.isfinite(pct[m]) & np.isfinite(r)
                if ok.sum() >= 20:
                    a, b = pd.Series(pct[m][ok]).rank().to_numpy(), pd.Series(r[ok]).rank().to_numpy()
                    ic[m] = float(np.corrcoef(a, b)[0, 1])
            for m in S:
                if m not in ic:
                    continue
                acc[m][h]["ic"].append(ic[m])
                if m != REF and REF in ic:
                    ok = np.isfinite(pct[m]) & np.isfinite(r)
                    acc[m][h]["ex"].append(ic_excluding(pct[m][ok], pct[REF][ok], r[ok]))
                    acc[m][h]["d"].append(ic[m] - ic[REF])
    out = {"note": "research-window backtest, 2012 to 2025; planning only", "reference": REF, "models": {}}
    expected = {}
    for m in S:
        out["models"][m], expected[m] = {}, {}
        for h in HORIZONS:
            a = acc[m][h]
            row = {"ic": _summ(np.array(a["ic"]), h)}
            expected[m][str(h)] = {"ic": row["ic"]["mean"], "sd": row["ic"]["sd"]}
            if a["ex"]:
                row["ic_beyond_reference"] = _summ(np.array(a["ex"], dtype=float), h)
                row["paired_difference"] = _summ(np.array(a["d"]), h)
                for n in (1, 2, 3):
                    t = champion.threshold(n)
                    e, d = row["ic_beyond_reference"], row["paired_difference"]
                    row[f"sessions_needed_N{n}"] = {
                        "beyond_reference_full_strength": _sessions_needed(e["mean"], e["sd"], h, t),
                        "beyond_reference_half_strength": _sessions_needed(e["mean"] / 2, e["sd"], h, t),
                        "own_ic_full_strength": _sessions_needed(row["ic"]["mean"], row["ic"]["sd"], h, t),
                        "own_ic_half_strength": _sessions_needed(row["ic"]["mean"] / 2, row["ic"]["sd"], h, t),
                        "paired_difference_full_strength": _sessions_needed(d["mean"], d["sd"], h, t)}
            out["models"][m][str(h)] = row
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "phase3_plan.json").write_text(json.dumps(out, indent=1))
    (config.CODE / "models" / "expected_ic_v1.json").write_text(json.dumps({
        "note": "Backtest rank IC mean and day-to-day sd per model and horizon, research window 2012-2025 "
                "(python -m nsr.research.phase3_plan). The decay monitor halves the mean before using it.",
        "models": expected}, indent=1))
    return out


if __name__ == "__main__":
    r = run()
    for m, by_h in r["models"].items():
        for h, row in by_h.items():
            print(m, h, {k: ({a: round(b, 4) if isinstance(b, float) else b for a, b in v.items()}) for k, v in row.items()})
