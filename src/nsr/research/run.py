"""Run a registered trial and write its result file.

    python -m nsr.research.run T-0001          run one trial
    python -m nsr.research.run --verdicts      apply the pass rules across all results so far

A trial must have a row in trial_ledger.csv (written when it was pre-registered in
research_log.md) before it will run. Results go to research/results/<trial>.json.
"""
from __future__ import annotations

import argparse
import json
from functools import partial

import numpy as np
import pandas as pd

from .. import config
from . import evaluate, signals, stats
from .data import ResearchData
from .features import controls

RESULTS = config.PROJECT / "research" / "results"
LEDGER = config.PROJECT / "trial_ledger.csv"
NEUTRAL_T = 2.0
YEAR_SHARE = 0.70
MIN_EVENTS_YEAR = 10
TRIPWIRE = {"ic": 0.06, "excess_sharpe": 1.5, "event_excess": 0.05}

TRIALS = {
    "T-0001": {"kind": "dense", "name": "deliv_ret_corr_60", "primary_h": 20, "fn": signals.deliv_ret_corr,
               "variants": {"window 40": partial(signals.deliv_ret_corr, window=40, min_obs=27),
                            "window 120": partial(signals.deliv_ret_corr, window=120, min_obs=80),
                            "returns not clipped": partial(signals.deliv_ret_corr, clip=10.0)}},
    "T-0002": {"kind": "dense", "name": "ear_drift_60", "primary_h": 20, "fn": signals.ear_drift,
               "variants": {"carried 20 sessions": partial(signals.ear_drift, hold=20),
                            "carried 40 sessions": partial(signals.ear_drift, hold=40),
                            "one-session reaction": partial(signals.ear_drift, days=1),
                            "three-session reaction": partial(signals.ear_drift, days=3)}},
    "T-0003": {"kind": "event", "name": "order_win", "primary_h": 20, "fn": signals.order_win_events,
               "variants": {"no cooldown": partial(signals.order_win_events, cooldown=0),
                            "cooldown 20 sessions": partial(signals.order_win_events, cooldown=20)}},
}


def result_files() -> list:
    """One file per trial (T-0001.json); diagnostics such as T-0002_posthoc.json are not results."""
    return sorted(f for f in RESULTS.glob("T-*.json") if f.stem[2:].isdigit())


def registered_trials() -> list[str]:
    led = pd.read_csv(LEDGER)
    return [t for t in led.trial_id if str(t).startswith("T-")]


def prior_sharpe_var() -> float:
    srs = [json.loads(f.read_text()).get("portfolio", {}).get("excess_sharpe_daily") for f in result_files()]
    srs = [s for s in srs if s is not None and np.isfinite(s)]
    return float(np.var(srs, ddof=1)) if len(srs) >= 2 else 0.0


def run_trial(trial: str, rd: ResearchData | None = None) -> dict:
    reg = registered_trials()
    if trial not in reg:
        raise SystemExit(f"{trial} is not in trial_ledger.csv: pre-register it in research_log.md first")
    spec, n = TRIALS[trial], len(reg)
    rd = rd or ResearchData.load()
    ctrl = controls(rd)
    out = {"trial": trial, "name": spec["name"], "kind": spec["kind"], "primary_h": spec["primary_h"],
           "trials_registered_when_run": n, "required_t": stats.required_t(n),
           "window": [str(rd.dates[rd.eval_sessions().start].date()), str(rd.dates[rd.eval_sessions().stop - 1].date())]}
    if spec["kind"] == "dense":
        S = spec["fn"](rd)
        out["lookahead_check"] = evaluate.check_no_lookahead(spec["fn"], rd, S)
        if not out["lookahead_check"]["ok"]:
            raise SystemExit(f"{trial}: look-ahead check failed, not scored: {out['lookahead_check']}")
        out.update(evaluate.evaluate_dense(rd, S, ctrl, spec["primary_h"], n, prior_sharpe_var()))
        out["variants"] = {}
        for name, fn in spec["variants"].items():
            dm = evaluate.daily_metrics(rd, fn(rd), ctrl)
            g = dm[dm.h == spec["primary_h"]]
            out["variants"][name] = {"ic": stats.ic_summary(g.ic.to_numpy(), spec["primary_h"]),
                                     "ic_neutral": stats.ic_summary(g.ic_neutral.to_numpy(), spec["primary_h"])}
    else:
        ev = spec["fn"](rd)
        fn_m = lambda r: signals.events_matrix(r, spec["fn"](r))
        out["lookahead_check"] = evaluate.check_no_lookahead(fn_m, rd, signals.events_matrix(rd, ev))
        if not out["lookahead_check"]["ok"]:
            raise SystemExit(f"{trial}: look-ahead check failed, not scored: {out['lookahead_check']}")
        out.update(evaluate.evaluate_events(rd, ev, spec["primary_h"]))
        out["event_control_ranks"] = event_control_ranks(rd, ev, ctrl)
        out["variants"] = {name: evaluate.evaluate_events(rd, fn(rd), spec["primary_h"])["primary"]
                           for name, fn in spec["variants"].items()}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{trial}.json").write_text(evaluate.to_json(out))
    return out


def event_control_ranks(rd: ResearchData, ev: pd.DataFrame, ctrl: dict) -> dict:
    """Where flagged names sit on each known effect (0.5 = typical universe member)."""
    acc = {k: [] for k in ctrl}
    for i, g in ev.groupby("i"):
        m = rd.member[i]
        for k, c in ctrl.items():
            ref = c[i][m & np.isfinite(c[i])]
            for col in g.col:
                if len(ref) and np.isfinite(c[i, col]):
                    acc[k].append(float((ref < c[i, col]).mean()))
    return {k: float(np.mean(v)) if v else float("nan") for k, v in acc.items()}


def primary_t(r: dict) -> float:
    return r["primary"]["ic_t"] if r["kind"] == "dense" else r["primary"]["t"]


def verdicts() -> pd.DataFrame:
    """Apply the pre-registered pass rules to every result on file. The t threshold and the
    false-discovery test use the number of hypotheses registered to date, so an old pass can
    be withdrawn as the trial count grows."""
    res = {f.stem: json.loads(f.read_text()) for f in result_files()}
    n = len(registered_trials())
    need = stats.required_t(n)
    p = {k: stats.p_one_sided(primary_t(r)) for k, r in res.items()}
    p.update({t: 1.0 for t in registered_trials() if t not in p})          # registered but not run counts against
    alive = stats.bh_survivors(p)
    rows = []
    for k, r in res.items():
        t = primary_t(r)
        g = {"t_reaches_required": bool(t >= need), "survives_fdr_10pct": k in alive}
        if r["kind"] == "dense":
            pf = r["portfolio"]
            g["positive_in_70pct_of_years"] = r["years_positive"] >= YEAR_SHARE * r["years"]
            g["adds_to_known_effects"] = bool(r["primary_neutral"]["ic_t"] >= NEUTRAL_T)
            g["beats_universe_after_costs"] = bool(pf["excess_cagr"] > 0 and pf["excess_cagr_if_silent_go_to_zero"] > 0)
            trip = abs(r["primary"]["ic_mean"]) > TRIPWIRE["ic"] or pf["excess_sharpe_ann"] > TRIPWIRE["excess_sharpe"]
            effect = r["primary"]["ic_mean"]
        else:
            yrs = {y: m for y, m in r["yearly_mean_excess"].items() if r["yearly_events_scored"][y] >= MIN_EVENTS_YEAR}
            g["positive_in_70pct_of_years"] = sum(m > 0 for m in yrs.values()) >= YEAR_SHARE * len(yrs)
            g["positive_after_costs"] = bool(r["primary_net_mean"] > 0)
            g["positive_after_costs_entering_a_session_later"] = bool(
                r["entry_one_session_later"]["mean"] - r["round_trip_cost"] > 0)
            trip = abs(r["primary"]["mean"]) > TRIPWIRE["event_excess"]
            effect = r["primary"]["mean"]
        rows.append({"trial": k, "name": r["name"], "effect": effect, "t": t, "required_t": need, "p": p[k], **g,
                     "verdict": "INVESTIGATE (too good)" if trip else ("PASS" if all(g.values()) else "FAIL")})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trials", nargs="*")
    ap.add_argument("--verdicts", action="store_true")
    a = ap.parse_args()
    if a.trials:
        rd = ResearchData.load()
        for t in a.trials:
            r = run_trial(t, rd)
            print(t, r["name"], "primary:", r["primary"])
    if a.verdicts:
        print(verdicts().T.to_string())
