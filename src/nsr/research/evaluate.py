"""Evaluators for Phase 2 trials.

Dense signals (a score for most of the universe every evening) are judged on daily
rank IC, on the IC left after known effects are regressed out, and on a long-only
top-20 paper portfolio after costs against the whole universe held after costs.

Event signals (a few flagged names a day) are judged per event: the excess return
over the universe from the next open, with errors clustered by calendar month.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config
from ..costs import CostModel
from ..sim import simulate
from . import stats
from .data import HORIZONS, ResearchData

N_NAMES, CAPITAL = 20, 1_000_000.0
MIN_NAMES = 100
CACHE = config.CLEAN / "research_cache"
PERIODS = (("2012-2016", 2012, 2016), ("2017-2021", 2017, 2021), ("2022-2025", 2022, 2025))
LIQ_BUCKETS = (("rank 1-100", 1, 100), ("rank 101-250", 101, 250), ("rank 251-500", 251, 500))


def _rank(a: np.ndarray) -> np.ndarray:
    return pd.Series(a).rank().to_numpy()


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _rank(a), _rank(b)
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def check_no_lookahead(fn, rd: ResearchData, full: np.ndarray, n_dates: int = 4, seed: int = 0) -> dict:
    """Recompute the signal on the dataset cut off at session D and compare with row D of the
    full-history computation. Any difference means row D used something from after D."""
    rng = np.random.default_rng(seed)
    ev = rd.eval_sessions()
    picks = sorted(set(rng.choice(np.arange(ev.start, ev.stop), n_dates, replace=False).tolist()) | {ev.stop - 1})
    worst = 0.0
    for d in picks:
        cut = fn(rd.truncated(d))[-1]
        a, b = cut[rd.member[d]], full[d][rd.member[d]]
        if (np.isfinite(a) != np.isfinite(b)).any():
            return {"ok": False, "sessions": len(picks), "note": f"different coverage on {rd.dates[d].date()}"}
        both = np.isfinite(a)
        if both.any():
            worst = max(worst, float(np.abs(a[both] - b[both]).max()))
    return {"ok": worst < 1e-9, "sessions": len(picks), "max_abs_diff": worst}


# ---------------------------------------------------------------- dense signals
def daily_metrics(rd: ResearchData, S: np.ndarray, ctrl: dict[str, np.ndarray] | None = None,
                  bucket: tuple[int, int] | None = None, min_names: int = MIN_NAMES) -> pd.DataFrame:
    """One row per (session, horizon): rank IC, IC of the signal with controls regressed out,
    and top-decile return minus the mean of the names scored."""
    rows = []
    p = rd.panel
    for i in rd.eval_sessions():
        m = rd.member[i] & p.traded[i] & np.isfinite(S[i])
        if bucket:
            m &= (rd.uni_rank[i] >= bucket[0]) & (rd.uni_rank[i] <= bucket[1])
        for h in HORIZONS:
            r = rd.fwd[h][i]
            ok = m & np.isfinite(r)
            if ok.sum() < min_names:
                continue
            s, y = S[i, ok], r[ok]
            rs = _rank(s) / ok.sum()
            row = {"date": rd.dates[i], "h": h, "n": int(ok.sum()), "ic": _spearman(s, y),
                   "top_excess": float(y[rs > 0.9].mean() - y.mean())}
            if ctrl:
                X = np.column_stack([np.ones(ok.sum())] + [
                    np.nan_to_num(_rank(c[i, ok]) / ok.sum(), nan=0.5) for c in ctrl.values()])
                beta, *_ = np.linalg.lstsq(X, rs, rcond=None)
                row["ic_neutral"] = _spearman(rs - X @ beta, y)
            rows.append(row)
    return pd.DataFrame(rows)


def ic_table(dm: pd.DataFrame, col: str = "ic") -> pd.DataFrame:
    out = []
    for h, g in dm.groupby("h"):
        out.append({"h": int(h), **stats.ic_summary(g[col].to_numpy(), int(h)),
                    "top_excess_mean": float(g.top_excess.mean()), "avg_names": float(g.n.mean())})
    return pd.DataFrame(out)


def yearly_ic(dm: pd.DataFrame, h: int, col: str = "ic") -> pd.Series:
    g = dm[dm.h == h]
    return g.groupby(g.date.dt.year)[col].mean()


def picks_from_scores(rd: ResearchData, S: np.ndarray, start: int, end: int) -> dict[int, np.ndarray]:
    out = {}
    for i in range(start, end + 1):
        m = np.flatnonzero(rd.member[i] & rd.panel.traded[i] & np.isfinite(S[i]))
        out[i] = m[np.argsort(-S[i, m], kind="stable")]
    return out


def universe_hurdle(rd: ResearchData, start: int, end: int) -> pd.Series:
    """Equity curve of the whole universe held in equal weight, re-formed every 21 sessions,
    paying costs. Slow, so cached by window."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"universe_hold_{rd.dates[start]:%Y%m%d}_{rd.dates[end]:%Y%m%d}.parquet"
    if f.exists():
        return pd.read_parquet(f).equity
    picks = {i: np.flatnonzero(rd.member[i]) for i in range(start, end + 1)}
    eq = simulate(rd.panel, picks, start, end, 21, 500, CAPITAL).equity
    eq.to_frame("equity").to_parquet(f)
    return eq


def portfolio_test(rd: ResearchData, S: np.ndarray, h: int, n_trials: int, trial_sr_var: float = 0.0) -> dict:
    """Long-only top 20 re-formed every h sessions, after costs, against the universe held after costs."""
    ev = rd.eval_sessions()
    start, end = ev.start, len(rd.dates) - 1
    picks = picks_from_scores(rd, S, start, end)
    res = simulate(rd.panel, picks, start, end, h, N_NAMES, CAPITAL)
    worst = simulate(rd.panel, picks, start, end, h, N_NAMES, CAPITAL, writeoff_after=60)
    hurdle = universe_hurdle(rd, start, end)
    x = (res.equity.pct_change() - hurdle.pct_change()).dropna()
    years = len(res.equity) / 252
    cagr = lambda eq: float((eq.iloc[-1] / CAPITAL) ** (1 / years) - 1)
    yr = (1 + res.equity.pct_change().fillna(0)).groupby(res.equity.index.year).prod() - \
         (1 + hurdle.pct_change().fillna(0)).groupby(hurdle.index.year).prod()
    return {
        "hold": h, "cagr": cagr(res.equity), "cagr_if_silent_go_to_zero": cagr(worst.equity),
        "universe_cagr": cagr(hurdle), "excess_cagr": cagr(res.equity) - cagr(hurdle),
        "excess_cagr_if_silent_go_to_zero": cagr(worst.equity) - cagr(hurdle),
        "vol": res.stats["vol"], "max_drawdown": res.stats["max_drawdown"],
        "turnover_per_year": res.stats["turnover_per_year"], "cost_drag_per_year": res.stats["cost_drag_per_year"],
        "unfilled_buys": res.stats["unfilled_buys"], "tracking_error": float(x.std() * np.sqrt(252)),
        "years_beating_universe": int((yr > 0).sum()), "years": int(len(yr)),
        **{f"excess_{k}": v for k, v in stats.sharpe_tests(x.to_numpy(), n_trials, trial_sr_var).items()},
    }


def evaluate_dense(rd: ResearchData, S: np.ndarray, ctrl: dict[str, np.ndarray], primary_h: int,
                   n_trials: int, trial_sr_var: float = 0.0) -> dict:
    dm = daily_metrics(rd, S, ctrl)
    yi, yn = yearly_ic(dm, primary_h), yearly_ic(dm, primary_h, "ic_neutral")
    prim = dm[dm.h == primary_h]
    return {
        "ic": ic_table(dm).to_dict("records"),
        "ic_neutral": ic_table(dm, "ic_neutral").to_dict("records"),
        "primary": stats.ic_summary(prim.ic.to_numpy(), primary_h),
        "primary_neutral": stats.ic_summary(prim.ic_neutral.to_numpy(), primary_h),
        "yearly_ic": {int(k): float(v) for k, v in yi.items()},
        "yearly_ic_neutral": {int(k): float(v) for k, v in yn.items()},
        "years_positive": int((yi > 0).sum()), "years": int(len(yi)),
        "portfolio": portfolio_test(rd, S, primary_h, n_trials, trial_sr_var),
        "by_period": {name: stats.ic_summary(prim[(prim.date.dt.year >= a) & (prim.date.dt.year <= b)].ic.to_numpy(), primary_h)
                      for name, a, b in PERIODS},
        "by_liquidity": {name: stats.ic_summary(
            (lambda d: d[d.h == primary_h].ic.to_numpy())(daily_metrics(rd, S, None, (a, b), 30)), primary_h)
            for name, a, b in LIQ_BUCKETS},
        "signal_correlation_with_controls": control_correlations(rd, S, ctrl),
    }


def control_correlations(rd: ResearchData, S: np.ndarray, ctrl: dict[str, np.ndarray], step: int = 21) -> dict:
    """Average cross-sectional rank correlation between the signal and each control."""
    acc = {k: [] for k in ctrl}
    for i in list(rd.eval_sessions())[::step]:
        m = rd.member[i] & np.isfinite(S[i])
        for k, c in ctrl.items():
            ok = m & np.isfinite(c[i])
            if ok.sum() >= 50:
                acc[k].append(_spearman(S[i, ok], c[i, ok]))
    return {k: float(np.nanmean(v)) if v else float("nan") for k, v in acc.items()}


# ---------------------------------------------------------------- event signals
def event_returns(rd: ResearchData, ev: pd.DataFrame, h: int, delay: int = 0) -> pd.DataFrame:
    """Per event: return from the open of session i+1+delay over h sessions, minus the equal-weight
    mean of universe members over the same window. `ev` has columns i (signal session) and col."""
    i, c = ev.i.to_numpy() + delay, ev.col.to_numpy()
    T = len(rd.dates)
    ok = i < T
    r = np.full(len(ev), np.nan)
    b = np.full(len(ev), np.nan)
    fwd = rd.fwd[h]
    bench = {}
    for k in np.flatnonzero(ok):
        ii = int(i[k])
        if ii not in bench:
            row = fwd[ii][rd.member[ii]]
            bench[ii] = np.nanmean(row) if np.isfinite(row).any() else np.nan
        r[k], b[k] = fwd[ii, c[k]], bench[ii]
    out = ev.copy()
    out["ret"], out["bench"], out["excess"] = r, b, r - b
    out["date"] = rd.dates[np.minimum(ev.i.to_numpy(), T - 1)]
    return out


def event_summary(er: pd.DataFrame) -> dict:
    d = er[np.isfinite(er.excess)]
    month = (d.date.dt.year * 12 + d.date.dt.month).to_numpy()
    s = stats.cluster_t(d.excess.to_numpy(), month)
    s["median"] = float(d.excess.median()) if len(d) else float("nan")
    s["hit_rate"] = float((d.excess > 0).mean()) if len(d) else float("nan")
    return s


def evaluate_events(rd: ResearchData, ev: pd.DataFrame, primary_h: int, cost: CostModel | None = None) -> dict:
    ev = ev[(ev.i >= rd.eval_sessions().start) & (ev.i < rd.eval_sessions().stop)].reset_index(drop=True)
    cost = cost or CostModel()
    rt = cost.round_trip_rate(CAPITAL / N_NAMES)
    er = event_returns(rd, ev, primary_h)
    prim = event_summary(er)
    yearly = er[np.isfinite(er.excess)].groupby(er.date.dt.year).excess.agg(["mean", "size"])
    rank = rd.uni_rank[ev.i.to_numpy(), ev.col.to_numpy()]
    return {
        "events": int(len(ev)), "events_per_year": {int(k): int(v) for k, v in ev.groupby(rd.dates[ev.i].year).size().items()},
        "round_trip_cost": rt,
        "primary": prim, "primary_net_mean": prim["mean"] - rt,
        "by_horizon": {h: event_summary(event_returns(rd, ev, h)) for h in HORIZONS},
        "entry_one_session_later": event_summary(event_returns(rd, ev, primary_h, delay=1)),
        "yearly_mean_excess": {int(k): float(v) for k, v in yearly["mean"].items()},
        "yearly_events_scored": {int(k): int(v) for k, v in yearly["size"].items()},
        "years_positive": int((yearly["mean"] > 0).sum()), "years": int(len(yearly)),
        "by_period": {name: event_summary(er[(er.date.dt.year >= a) & (er.date.dt.year <= b)]) for name, a, b in PERIODS},
        "by_liquidity": {name: event_summary(er[(rank >= a) & (rank <= b)]) for name, a, b in LIQ_BUCKETS},
    }


def to_json(obj) -> str:
    def default(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, (pd.Timestamp,)):
            return str(o.date())
        raise TypeError(type(o))
    return json.dumps(obj, indent=1, default=default)
