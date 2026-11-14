"""Diagnostics on T-0007 after its registered run. Not pre-registered: they explain the result
and cannot rescue or improve the trial. Anything here that looks like a signal is in-sample.

    python -m nsr.research.posthoc_t0007
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import evaluate, signals
from .data import HORIZONS, ResearchData
from .run import RESULTS


def first_notices(rd: ResearchData) -> pd.DataFrame:
    """Every first notice of a results board meeting for a universe member that traded that day,
    with the meeting still ahead. `gap` = sessions from the notice to the meeting."""
    c = signals.results_calendar(rd)
    c["i"] = rd.dates.get_indexer(c.known)
    c = c[(c.i >= 0) & (c.meeting > c.known)]
    c = c[rd.member[c.i.to_numpy(), c.col.to_numpy()] & rd.panel.traded[c.i.to_numpy(), c.col.to_numpy()]]
    c["gap"] = np.searchsorted(rd.dates, c.meeting.to_numpy(), side="left") - c.i
    return c[["i", "col", "gap"]].sort_values(["i", "col"]).drop_duplicates(["i", "col"]).reset_index(drop=True)


def _scored(rd: ResearchData, ev: pd.DataFrame) -> pd.DataFrame:
    s = rd.eval_sessions()
    return ev[(ev.i >= s.start) & (ev.i < s.stop)].reset_index(drop=True)


def horizons(rd: ResearchData, ev: pd.DataFrame, delay: int = 0) -> dict:
    ev = _scored(rd, ev)
    return {h: evaluate.event_summary(evaluate.event_returns(rd, ev, h, delay)) for h in HORIZONS}


def main() -> dict:
    rd = ResearchData.load(tables=("board_meetings",))
    adv = signals.results_date_shift(rd)
    late = signals.results_date_shift(rd, direction="delay")
    every = first_notices(rd)
    key = lambda d: set(zip(d.i, d.col))
    moved = key(adv) | key(late)
    on_time_or_unknown = every[[k not in moved for k in zip(every.i, every.col)]]
    out = {"by_group": {"advance of 7 or more (the trial)": horizons(rd, adv),
                        "delay of 7 or more": horizons(rd, late),
                        "all other first notices": horizons(rd, on_time_or_unknown),
                        "all first notices": horizons(rd, every)}}
    ev = _scored(rd, every)
    er5 = evaluate.event_returns(rd, ev, 5)
    yearly = er5[np.isfinite(er5.excess)].groupby(er5.date.dt.year).excess.agg(["mean", "size"])
    rank = rd.uni_rank[ev.i.to_numpy(), ev.col.to_numpy()]
    out["all_first_notices_h5"] = {
        "yearly_mean": {int(k): float(v) for k, v in yearly["mean"].items()},
        "yearly_events": {int(k): int(v) for k, v in yearly["size"].items()},
        "by_liquidity": {n: evaluate.event_summary(er5[(rank >= a) & (rank <= b)]) for n, a, b in evaluate.LIQ_BUCKETS},
        "meeting within 5 sessions": evaluate.event_summary(er5[(ev.gap <= 5).to_numpy()]),
        "meeting 6 or more sessions away": evaluate.event_summary(er5[(ev.gap >= 6).to_numpy()]),
        "entry one session later": evaluate.event_summary(evaluate.event_returns(rd, ev, 5, delay=1)),
        "entry two sessions later": evaluate.event_summary(evaluate.event_returns(rd, ev, 5, delay=2)),
        "placebo: same stocks, 30 sessions before the notice": evaluate.event_summary(
            evaluate.event_returns(rd, ev[ev.i >= 30].assign(i=lambda d: d.i - 30), 5)),
        "placebo: same stocks, 30 sessions after the notice": evaluate.event_summary(evaluate.event_returns(rd, ev, 5, delay=30)),
        "winsorised at 1% and 99%": (lambda d: {"mean": float(np.clip(d, *np.quantile(d, [0.01, 0.99])).mean()),
                                               "median": float(np.median(d))})(er5.excess[np.isfinite(er5.excess)].to_numpy()),
        "sd_per_event": float(er5.excess.std()),
        "control_ranks": __import__("nsr.research.run", fromlist=["x"]).event_control_ranks(
            rd, ev, __import__("nsr.research.features", fromlist=["x"]).controls(rd)),
    }
    out["advance_h5"] = advance_h5(rd, adv, every)
    (RESULTS / "T-0007_posthoc.json").write_text(evaluate.to_json(out))
    return out


def advance_h5(rd: ResearchData, adv: pd.DataFrame, every: pd.DataFrame) -> dict:
    """The trial's events at 5 sessions instead of the registered 20. In-sample: this horizon was
    looked at because the registered one failed."""
    cost = evaluate.CostModel().round_trip_rate(evaluate.CAPITAL / evaluate.N_NAMES)
    ev = _scored(rd, adv.merge(every, on=["i", "col"], how="left"))
    er = evaluate.event_returns(rd, ev, 5)
    ok = np.isfinite(er.excess)
    yearly = er[ok].groupby(er.date.dt.year).excess.agg(["mean", "size"])
    rank = rd.uni_rank[ev.i.to_numpy(), ev.col.to_numpy()]
    oth = _scored(rd, every)
    eo = evaluate.event_returns(rd, oth, 5)
    # difference from other first notices in the same calendar month, so results seasons cancel
    mo = lambda d: d.date.dt.year * 12 + d.date.dt.month
    in_adv = pd.Series(list(zip(oth.i, oth.col))).isin(set(zip(ev.i, ev.col))).to_numpy()
    base = eo[~in_adv & np.isfinite(eo.excess)].groupby(mo(eo[~in_adv & np.isfinite(eo.excess)])).excess.mean()
    rel = er[ok].assign(rel=lambda d: d.excess - mo(d).map(base))
    rel = rel[np.isfinite(rel.rel)]
    from . import stats
    x = er.excess[ok].to_numpy()
    return {
        "primary": evaluate.event_summary(er), "round_trip_cost": cost, "net_mean": float(er.excess[ok].mean() - cost),
        "yearly_mean": {int(k): float(v) for k, v in yearly["mean"].items()},
        "yearly_events": {int(k): int(v) for k, v in yearly["size"].items()},
        "by_liquidity": {n: evaluate.event_summary(er[(rank >= a) & (rank <= b)]) for n, a, b in evaluate.LIQ_BUCKETS},
        "by_period": {n: evaluate.event_summary(er[(er.date.dt.year >= a) & (er.date.dt.year <= b)]) for n, a, b in evaluate.PERIODS},
        "entry one session later": evaluate.event_summary(evaluate.event_returns(rd, ev, 5, delay=1)),
        "entry two sessions later": evaluate.event_summary(evaluate.event_returns(rd, ev, 5, delay=2)),
        "meeting within 5 sessions": evaluate.event_summary(er[(ev.gap <= 5).to_numpy()]),
        "meeting 6 or more sessions away": evaluate.event_summary(er[(ev.gap >= 6).to_numpy()]),
        "minus other first notices of the same month": stats.cluster_t(rel.rel.to_numpy(), mo(rel).to_numpy()),
        "winsorised mean": float(np.clip(x, *np.quantile(x, [0.01, 0.99])).mean()),
        "mean without the best 1%": float(np.sort(x)[: int(len(x) * 0.99)].mean()),
        "sd_per_event": float(x.std()),
        "sessions 6 to 20 after the notice": evaluate.event_summary(
            evaluate.event_returns(rd, ev, 20).assign(excess=lambda d: d.excess - er.excess.to_numpy())),
        "by_size_of_advance_h5": {name: evaluate.event_summary(evaluate.event_returns(rd, _scored(rd, signals.results_date_shift(rd, **kw)), 5))
                                  for name, kw in {"4 or more": {"min_days": 4}, "7 or more": {}, "14 or more": {"min_days": 14},
                                                   "7 or more, no peer adjustment": {"peers": False},
                                                   "delay of 7 or more": {"direction": "delay"},
                                                   "delay of 14 or more": {"direction": "delay", "min_days": 14}}.items()},
    }


if __name__ == "__main__":
    r = main()
    for g, hs in r["by_group"].items():
        print(g, {h: f"n {s['n']} mean {s['mean']:+.4f} t {s['t']:.2f} med {s['median']:+.4f}" for h, s in hs.items()})
    for block in ("all_first_notices_h5", "advance_h5"):
        print("==", block)
        for k, v in r[block].items():
            print(k, json.dumps(v, default=float)[:700])
