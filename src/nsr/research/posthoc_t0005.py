"""Attacks on T-0005 after its registered run. Not pre-registered: diagnostics only, they
cannot rescue or improve the trial.

    python -m nsr.research.posthoc_t0005
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import evaluate, signals, stats
from .data import ResearchData
from .run import RESULTS


def _cluster(er: pd.DataFrame, values: np.ndarray | None = None) -> dict:
    d = er[np.isfinite(er.excess)]
    v = d.excess.to_numpy() if values is None else values
    month = (d.date.dt.year * 12 + d.date.dt.month).to_numpy()
    s = stats.cluster_t(v, month)
    return {"n": int(len(v)), "mean": s["mean"], "t": s["t"]}


def other_events(rd: ResearchData, mode: str, txn: str) -> pd.DataFrame:
    """Same filters as the trial, for another kind of transaction (placebo)."""
    t = rd.tables["insider"].copy()
    t.loc[(t["mode"] == mode) & (t.txn == txn), ["mode", "txn"]] = ["Market Purchase", "Buy"]
    t = t[(t["mode"] == "Market Purchase")]
    keep = rd.tables["insider"]
    marker = (keep["mode"] == mode) & (keep.txn == txn)
    saved = rd.tables["insider"]
    rd.tables["insider"] = t[marker.reindex(t.index).fillna(False)]
    try:
        return signals.insider_buys(rd)
    finally:
        rd.tables["insider"] = saved


def run() -> dict:
    rd = ResearchData.load(tables=("insider", "board_meetings"))
    lo, hi = rd.eval_sessions().start, rd.eval_sessions().stop
    ev = signals.insider_buys(rd)
    ev = ev[(ev.i >= lo) & (ev.i < hi)].reset_index(drop=True)
    er = evaluate.event_returns(rd, ev, 20)
    d = er[np.isfinite(er.excess)].reset_index(drop=True)
    x = d.excess.to_numpy()
    out = {"note": "post-hoc diagnostics, not pre-registered"}
    # 1. is the mean a few big winners?
    lo_q, hi_q = np.quantile(x, [0.01, 0.99])
    order = np.argsort(-x)
    out["outliers"] = {
        "mean": float(x.mean()), "median": float(np.median(x)),
        "winsorised_1pct": _cluster(d, np.clip(x, lo_q, hi_q)),
        "mean_without_best_10_events": float(np.delete(x, order[:10]).mean()),
        "mean_without_best_1pct": float(np.delete(x, order[: len(x) // 100]).mean()),
        "share_of_total_from_best_5pct": float(x[order[: len(x) // 20]].sum() / x.sum()),
    }
    # what a random universe stock scores on the same days against the same benchmark
    rng = np.random.default_rng(0)
    rnd = []
    for i in d.i.to_numpy():
        row = rd.fwd[20][i][rd.member[i]]
        row = row[np.isfinite(row)]
        rnd.append(rng.choice(row, 20) - row.mean())
    rnd = np.concatenate(rnd)
    out["random_stock_same_days"] = {"median_excess": float(np.median(rnd)), "hit_rate": float((rnd > 0).mean())}
    out["events_hit_rate"] = float((x > 0).mean())
    # 2. placebos: insider market sales, and share grants (ESOP), through the same filters
    for name, mode, txn in (("insider_market_sales", "Market Sale", "Sell"), ("esop_grants", "ESOP", "Buy")):
        pe = other_events(rd, mode, txn)
        pe = pe[(pe.i >= lo) & (pe.i < hi)].reset_index(drop=True)
        out[name] = _cluster(evaluate.event_returns(rd, pe, 20)) if len(pe) else {"n": 0}
    # 3. is it results drift? Insiders may trade only when the trading window is open, after results
    S = signals.ear_drift(rd)
    pct, has = [], []
    for i, c in zip(d.i.to_numpy(), d.col.to_numpy()):
        m = rd.member[i] & np.isfinite(S[i])
        has.append(bool(np.isfinite(S[i, c])))
        pct.append(float((S[i][m] < S[i, c]).mean()) if has[-1] and m.sum() > 50 else np.nan)
    pct = np.array(pct)
    out["results_drift_overlap"] = {
        "events_with_a_results_reaction_score": float(np.mean(has)),
        "mean_rank_of_that_score": float(np.nanmean(pct)),
        "excess_when_reaction_rank_above_half": _cluster(d[pct >= 0.5]),
        "excess_when_reaction_rank_below_half": _cluster(d[pct < 0.5]),
        "excess_when_no_score": _cluster(d[~np.isfinite(pct)]),
    }
    # 4. how fast does it arrive, and does it last?
    out["by_horizon_from_later_entry"] = {f"enter {k} sessions later": _cluster(evaluate.event_returns(rd, ev, 20, delay=k)) for k in (1, 2, 5)}
    # 5. sessions since the trade: fresh disclosures against slow ones
    t = rd.tables["insider"]
    out["half_years"] = {f"{y}H{h}": _cluster(g) for (y, h), g in d.groupby([d.date.dt.year, (d.date.dt.month > 6) + 1]) if len(g) >= 20}
    (RESULTS / "T-0005_posthoc.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = run()
    for k, v in r.items():
        print(k, json.dumps(v, default=float)[:900] if not isinstance(v, str) else v)
