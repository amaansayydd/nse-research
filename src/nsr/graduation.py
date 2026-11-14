"""Graduation tracker (research_log.md, Phase 4 graduation criteria v1.1).

Graduation is the point at which the owner may consider real capital. This module
only measures the forward record against criteria fixed in advance. It never
ticks the owner's checks (G9), and real capital always needs the owner's decision.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import report
from .costs import CostModel
from .panel import Panel
from .sim import buy_and_hold, simulate
from .tax import TaxModel, buy_and_hold_after_tax

H = 20                                   # decision horizon and holding period
MIN_SESSIONS, MIN_SESSIONS_CALM, MIN_AS_CHAMPION = 500, 750, 250
MARKET_FALL = 0.10                       # the window should contain a fall this deep in NIFTYBEES
MIN_IC, MIN_T = 0.02, 2.0
MARGIN = 0.03                            # after-tax return over the better fund, per year
MOMENTUM_FUND = "MOM30IETF"              # v1.1: G5 is against the better of NIFTYBEES and this fund
DD_FLOOR, DD_MULT, REL_DD = 0.25, 1.5, 0.15
MIN_COVERAGE, VOID_FREE = 0.95, 250
G5 = "G5 against the better fund after costs and taxes"


def max_drawdown(curve) -> float:
    c = np.asarray(curve, dtype=float)
    return float((c / np.maximum.accumulate(c) - 1).min()) if len(c) else 0.0


def _annual(terminal: float, capital: float, sessions: int) -> float:
    return float((terminal / capital) ** (252 / sessions) - 1) if sessions > 0 and terminal > 0 else float("nan")


def book(panel: Panel, preds: pd.DataFrame, model: str) -> dict | None:
    """The model's paper portfolio over its own forward window, with everything G5 to G8 need."""
    days = sorted(set(preds[preds.model == model].asof_date))
    idx = panel.dates.get_indexer(pd.to_datetime(days))
    idx = idx[idx >= 0]
    end = len(panel.dates) - 1
    if len(idx) == 0 or end - idx[0] < 2:
        return None
    start = int(idx[0])
    picks = report.picks_from_preds(panel, preds, model)
    cap = report.CAPITAL
    res = simulate(panel, picks, start, end, H, report.N_NAMES, cap, tax=TaxModel())
    biz = simulate(panel, picks, start, end, H, report.N_NAMES, cap, tax=TaxModel.business())
    hurdle = report.universe_hold(panel, start, end)
    r = panel.bench["NIFTYBEES"].iloc[start + 1: end + 1]
    n = len(r)
    nifty = buy_and_hold_after_tax(r, cap, CostModel(), TaxModel())
    # The momentum fund over the same window. A session without a return is spent in cash, which would
    # lower the hurdle unseen, so the share of sessions that have one is carried along and G5 checks it.
    fund_r = panel.bench[MOMENTUM_FUND].iloc[start + 1: end + 1] if MOMENTUM_FUND in panel.bench else pd.Series(np.nan, index=r.index)
    fund = buy_and_hold_after_tax(fund_r, cap, CostModel(), TaxModel()) if fund_r.notna().any() else float("nan")
    return {
        "sessions": n,
        "coverage": len(idx) / (end - start + 1),
        "after_tax": _annual(cap * (1 + res.stats["after_tax_total_return"]), cap, n),
        "after_tax_if_business_income": _annual(cap * (1 + biz.stats["after_tax_total_return"]), cap, n),
        "nifty_after_tax": _annual(nifty, cap, n),
        "momentum_fund_after_tax": _annual(fund, cap, n), "momentum_fund_coverage": float(fund_r.notna().mean()) if n else 0.0,
        "pre_tax": _annual(float(res.equity.iloc[-1]), cap, n),
        "universe_pre_tax": _annual(float(hurdle.equity.iloc[-1]), cap, n),
        "drawdown": max_drawdown(res.equity), "nifty_drawdown": max_drawdown(buy_and_hold(r, cap)),
        "relative_drawdown": max_drawdown(res.equity.to_numpy() / hurdle.equity.to_numpy()),
    }


def ic_numbers(scores: pd.DataFrame, model: str, since: str | None = None) -> dict:
    s = scores[scores.model == model]
    if since:
        s = s[s.asof_date >= since]
    a, b = s[s.horizon == H].ic.to_numpy(dtype=float), s[s.horizon == 5].ic.to_numpy(dtype=float)
    sd = a.std(ddof=1) if len(a) > 1 else float("nan")
    return {"sessions": int(len(a)), "ic": float(a.mean()) if len(a) else float("nan"),
            "t": float(a.mean() / sd * math.sqrt(len(a) / H)) if len(a) > 1 and sd > 0 else float("nan"),
            "ic_5": float(b.mean()) if len(b) else float("nan")}


def evaluate(model: str, scores: pd.DataFrame, state: dict, bk: dict | None, decay: pd.DataFrame | None,
             void_dates: list[str] | None = None) -> pd.DataFrame:
    """One row per criterion: what is required, where the forward record stands, and whether it is met."""
    ic = ic_numbers(scores, model)
    seat = ic_numbers(scores, model, state.get("champion_since"))["sessions"] if state.get("champion") == model and state.get("champion_since") else 0
    decaying = bool(decay is not None and len(decay) and decay[decay.model == model].state.ne("ok").any())
    ctl = scores[scores.model == "random"]
    control_ok = all(len(g) < 2 or not abs(g.ic.astype(float).mean() / g.ic.astype(float).std(ddof=1) * math.sqrt(len(g) / h)) >= 3
                     for h, g in ctl.groupby("horizon"))
    recent = sorted(set(scores[(scores.model == model) & (scores.horizon == H)].asof_date))[-VOID_FREE:]
    void_recent = bool(void_dates and recent and any(d >= recent[0] for d in void_dates))
    b = bk or {}
    fell = b.get("nifty_drawdown", 0.0) <= -MARKET_FALL
    need = MIN_SESSIONS if fell else MIN_SESSIONS_CALM
    dd_limit = -max(DD_FLOOR, DD_MULT * abs(b.get("nifty_drawdown", 0.0)))
    pct = lambda v: "" if v is None or not np.isfinite(v) else f"{v * 100:.1f}%"
    # G5 (v1.1): the hurdle is the better of the two funds. A momentum fund series with gaps cannot be
    # trusted as a hurdle, and then G5 is not met until the series is repaired.
    fund_cov = b.get("momentum_fund_coverage", 0.0)
    fund_ok = fund_cov >= MIN_COVERAGE and np.isfinite(b.get("momentum_fund_after_tax", float("nan")))
    best_fund = max(b.get("nifty_after_tax", float("nan")), b["momentum_fund_after_tax"]) if fund_ok else float("nan")
    fund_note = "" if fund_ok or not b else f"; {MOMENTUM_FUND} HAS A RETURN ON ONLY {fund_cov:.0%} OF SESSIONS"
    num = lambda v, d=4: "" if v is None or not np.isfinite(v) else f"{v:.{d}f}"
    rows = [
        ("G1 standing", f"champion for {MIN_AS_CHAMPION} scored sessions, not decaying",
         f"{'champion' if state.get('champion') == model else 'not champion'}, {seat} sessions in the seat"
         + (", DECAYING" if decaying else ""), state.get("champion") == model and seat >= MIN_AS_CHAMPION and not decaying),
        ("G2 duration", f"{MIN_SESSIONS} scored sessions with a {MARKET_FALL:.0%} market fall in the window, else {MIN_SESSIONS_CALM}",
         f"{ic['sessions']} sessions; NIFTYBEES worst fall {pct(b.get('nifty_drawdown'))}", ic["sessions"] >= need),
        ("G3 IC", f"20-session IC at least {MIN_IC}, 5-session IC positive",
         f"{num(ic['ic'])} and {num(ic['ic_5'])}", ic["ic"] >= MIN_IC and ic["ic_5"] > 0),
        ("G4 t-stat", f"t of the 20-session IC at least {MIN_T}", num(ic["t"], 2), ic["t"] >= MIN_T),
        (G5, f"at least {MARGIN:.0%} a year over the better of NIFTYBEES and {MOMENTUM_FUND}, all after tax",
         f"{pct(b.get('after_tax'))} against NIFTYBEES {pct(b.get('nifty_after_tax'))} and {MOMENTUM_FUND} "
         f"{pct(b.get('momentum_fund_after_tax'))} (if taxed as business income: {pct(b.get('after_tax_if_business_income'))}){fund_note}",
         b.get("after_tax", float("nan")) >= best_fund + MARGIN),
        ("G6 against the universe", "beats the universe held after costs, before tax",
         f"{pct(b.get('pre_tax'))} against {pct(b.get('universe_pre_tax'))}",
         b.get("pre_tax", float("nan")) > b.get("universe_pre_tax", float("nan"))),
        ("G7 drawdown", f"no deeper than {pct(dd_limit)}; no deeper than {-REL_DD:.0%} against the universe",
         f"{pct(b.get('drawdown'))}; {pct(b.get('relative_drawdown'))} against the universe",
         b.get("drawdown", float("nan")) >= dd_limit and b.get("relative_drawdown", float("nan")) >= -REL_DD),
        ("G8 record integrity", f"predicted on {MIN_COVERAGE:.0%} of sessions, control clean, nothing voided in {VOID_FREE} sessions",
         f"{pct(b.get('coverage'))} of sessions; control {'clean' if control_ok else 'SHOWS SKILL'}; "
         f"{'a void in the window' if void_recent else 'no recent void'}",
         b.get("coverage", 0.0) >= MIN_COVERAGE and control_ok and not void_recent),
        ("G9 owner's checks", "contract note matched, tax treatment confirmed, broker API and static IP ready", "by hand", None),
    ]
    met = lambda m: "by hand" if m is None else ("yes" if bool(m) else "no")
    return pd.DataFrame([{"criterion": c, "required": r, "forward record": v, "met": met(m)} for c, r, v, m in rows])


def section(panel: Panel, preds: pd.DataFrame, scores: pd.DataFrame, state: dict, decay: pd.DataFrame | None,
            challengers: list[str], void_dates: list[str] | None = None) -> str:
    head = """## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

"""
    champ = state.get("champion")
    if champ:
        table = evaluate(champ, scores, state, book(panel, preds, champ), decay, void_dates)
        done = table.met.eq("yes").sum()
        return head + f"Champion `{champ}`: {done} of 8 measured criteria met.\n\n" + report._fmt(table) + "\n"
    rows = []
    for m in challengers:
        ic = ic_numbers(scores, m)
        rows.append({"model": m, "scored_sessions": f"{ic['sessions']} of {MIN_SESSIONS}", "ic_20": ic["ic"],
                     "ic_t": ic["t"], "t_needed": MIN_T, "ic_5": ic["ic_5"]})
    return (head + "There is no champion, so nothing can graduate. Where each challenger stands on the criteria "
            "that can already be measured:\n\n"
            + (report._fmt(pd.DataFrame(rows), dec={"ic_20": 4, "ic_t": 2, "t_needed": 1, "ic_5": 4}) if rows else "_no challengers_\n") + "\n")
