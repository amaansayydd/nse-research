"""Scoreboard and simulation summaries, shared by the daily run and the rehearsal."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .models import ALL_MODELS, ROLES
from .panel import Panel
from .score import summarize
from .costs import CostModel
from .sim import buy_and_hold, performance, simulate
from .tax import TaxModel, buy_and_hold_after_tax

SIM_HORIZONS = (5, 20)   # 1-session holding is a diagnostic only: it cannot pay delivery costs
N_NAMES = 20
CAPITAL = 1_000_000.0


def picks_from_preds(panel: Panel, preds: pd.DataFrame, model: str) -> dict[int, np.ndarray]:
    """session index -> panel columns ranked best-first, matched by (as-of date, symbol)."""
    out = {}
    for asof, g in preds[preds.model == model].groupby("asof_date"):
        i = panel.dates.get_indexer([pd.Timestamp(asof)])[0]
        if i < 0:
            continue
        on = panel.symbols_on(i)
        s2s = pd.Series(on.index, index=on.to_numpy())
        g = g.sort_values("rank_pct", ascending=False)
        sid = s2s.reindex(g.symbol.to_numpy()).dropna().to_numpy().astype(np.int64)
        out[int(i)] = panel.col(sid)
    return out


def universe_hold(panel: Panel, start: int, end: int, tax: TaxModel | None = None):
    """The investable hurdle: buy every universe member in equal weight, re-form about
    monthly, pay the same costs as the models. (A daily-rebalanced, costless equal-weight
    average overstated this by about 10 points over the two rehearsal years.)"""
    picks = {i: panel.members(i) for i in range(start, end + 1)}
    return simulate(panel, picks, start, end, 21, 500, CAPITAL, tax=tax)


def run_sims(panel: Panel, preds: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    rows = []
    if end - start < 2:
        return pd.DataFrame()
    keep = ("total_return", "after_tax_total_return", "cagr", "vol", "max_drawdown", "turnover_per_year",
            "cost_drag_per_year", "unfilled_buys", "blocked_sells")
    tax = TaxModel()
    hurdle = universe_hold(panel, start, end, tax)
    rows.append({"portfolio": "universe, equal weight, all 500 (after costs)", "hold": "21d",
                 **{k: hurdle.stats[k] for k in keep}})
    for name, col in (("NIFTYBEES buy and hold (no trading costs)", "NIFTYBEES"), ("Nifty 50 price index (not investable)", "NIFTY50_PRICE")):
        r = panel.bench.get(col, pd.Series(dtype=float)).iloc[start + 1: end + 1]
        if len(r):
            row = {"portfolio": name, "hold": "-", **performance(buy_and_hold(r, CAPITAL), CAPITAL)}
            if col == "NIFTYBEES":
                row["after_tax_total_return"] = round(buy_and_hold_after_tax(r, CAPITAL, CostModel(), tax) / CAPITAL - 1, 4)
            rows.append(row)
    logged = set(preds.model.unique())
    for model in (m for m in ALL_MODELS if m in logged):
        picks = picks_from_preds(panel, preds, model)
        for h in SIM_HORIZONS:
            res = simulate(panel, picks, start, end, h, N_NAMES, CAPITAL, tax=tax)
            worst = simulate(panel, picks, start, end, h, N_NAMES, CAPITAL, writeoff_after=60)
            rows.append({"portfolio": f"{model} top {N_NAMES}", "hold": f"{h}d",
                         **{k: res.stats[k] for k in keep},
                         "total_return_if_silent_holdings_go_to_zero": worst.stats["total_return"],
                         "writeoffs": worst.stats["writeoffs"]})
    return pd.DataFrame(rows)


def _fmt(df: pd.DataFrame, pct: tuple[str, ...] = (), dec: dict[str, int] | None = None) -> str:
    df = df.copy()
    for c in pct:
        if c in df:
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v * 100:.2f}%")
    for c, n in (dec or {}).items():
        if c in df:
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v:.{n}f}")
    df = df.fillna("")
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in df.to_numpy()) + "\n"


def ic_table(scores: pd.DataFrame) -> str:
    s = summarize(scores)
    if s.empty:
        return "_no matured predictions yet_\n"
    s = s.rename(columns={"days_for_t2_at_this_ic": "days needed for t=2"})
    return _fmt(s, pct=("top_excess_mean", "top_hit"),
                dec={"ic_mean": 4, "ic_sd": 4, "ic_t": 2, "brier": 4, "ic_ex_ref_mean": 4, "days needed for t=2": 0})


def sim_table(sims: pd.DataFrame) -> str:
    if sims.empty:
        return "_not enough sessions to simulate yet_\n"
    pct = ("total_return", "after_tax_total_return", "cagr", "vol", "max_drawdown", "cost_drag_per_year",
           "total_return_if_silent_holdings_go_to_zero")
    return _fmt(sims, pct=pct, dec={"turnover_per_year": 1, "unfilled_buys": 1, "blocked_sells": 1, "writeoffs": 1})


def challenger_section(state: dict | None, comparison: pd.DataFrame | None, weights: dict | None) -> str:
    if state is None:
        return ""
    champ = state["champion"] or "none (seat empty)"
    out = f"""## Champion and challengers

Champion: **{champ}**. Reference to beat: `{state["reference"]}`. Challengers ever started: {len(state["ever_compared"])}.
A challenger is judged only at 250, 375, 500 ... scored sessions at the 20-session horizon. `ic_beyond_reference`
is its rank IC after the reference's ranks are removed; its t-stat must reach `required_t`, which rises
with every challenger ever started. Meeting the rule earns a holdout check by the owner, not a promotion.

"""
    if comparison is None or comparison.empty:
        out += "_no challenger has a matured 20-session score yet_\n"
    else:
        out += _fmt(comparison, pct=("top_decile_excess",),
                    dec={"ic": 4, "ic_t": 2, "reference_ic": 4, "ic_beyond_reference": 4, "beyond_t": 2, "required_t": 2})
    if weights:
        out += "\nEnsemble weights for the latest prediction: " + ", ".join(f"`{k}` {v:.3f}" for k, v in weights.items()) + \
               ". They start equal and move only on matured forward 20-session ICs.\n"
    return out + "\n"


def decay_section(decay: pd.DataFrame | None, retire: dict | None) -> str:
    if decay is None or decay.empty:
        return ""
    d = decay.copy()
    d["retire_rule_met"] = d.model.map(lambda m: "YES" if (retire or {}).get(m) and ROLES.get(m) == "challenger" else "")
    return f"""## Decay monitor

One-sided CUSUM on each model's forward rank IC, sampled every h sessions. `expected_ic` is half the
backtest IC; an alarm means the IC has run below that for long enough to look like a change, and
gives the estimated start. `sessions_to_detect_total_loss` is how long an edge that vanished today
would take to raise the alarm: weak signals decay quietly.

{_fmt(d, dec={"expected_ic": 4, "forward_ic": 4, "cusum": 2, "alarm_at": 2, "sessions_to_detect_total_loss": 0})}
"""


def observed_section(table: pd.DataFrame | None, state: dict | None) -> str:
    if table is None or state is None or not state.get("ever_observed"):
        return ""
    out = f"""## Observed signals

Logged forward without a shadow slot (Phase 3 rules v1.1). An observed signal cannot become champion and
does not change the challengers' margin. Signals ever observed: {len(state["ever_observed"])}, which sets `required_t`.
The label "confirmed forward" is read only at 250, 375, 500 ... evaluated sessions and needs 200 scored events,
`t` at least `required_t`, and a mean excess above one round trip of costs, also when entering a session later.
Running numbers between checkpoints decide nothing.

"""
    if table.empty:
        return out + "_no observed signal is running_\n\n"
    t = table.copy()
    pct = tuple(c for c in t.columns if c.startswith(("mean_", "after_costs", "median_", "hit_rate")))
    main = ["signal", "horizon", "sessions", "judged_on_sessions", "events", "mean_excess", "t", "required_t",
            "after_costs", "after_costs_one_session_later", "status"]
    rest = ["signal"] + [c for c in t.columns if c not in main]
    out += _fmt(t[main], pct=pct, dec={"t": 2, "required_t": 2})
    out += "\nReported, not required:\n\n" + _fmt(t[rest], pct=pct)
    return out + "\n"


def write_scoreboard(path: Path, scores: pd.DataFrame, sims: pd.DataFrame, n_pred_days: int, updated: str,
                     state: dict | None = None, comparison: pd.DataFrame | None = None,
                     decay: pd.DataFrame | None = None, retire: dict | None = None, weights: dict | None = None,
                     graduation: str = "", observed: str = "") -> None:
    text = f"""# Scoreboard (forward-only)

Updated {updated}. Prediction days logged: {n_pred_days}. Days with a matured score: {scores.asof_date.nunique() if len(scores) else 0}.

Only predictions written to `predictions.csv` before their outcome window opened are counted here.
Backtest and dress-rehearsal numbers never appear in this file.

## Rank IC by model and horizon

Target: return from the next session's open to the open h sessions later. `eff_obs` divides the day
count by the horizon because overlapping targets are not independent. An `ic_t` below 2 means nothing
yet. `days needed for t=2` assumes the IC measured so far is the true IC, which early on it is not.

{ic_table(scores)}
`top_excess_mean`: top-decile mean return minus the universe mean, before costs. `top_hit`: share of
top-decile names beating the universe median. `brier`: 0.25 is what a coin flip scores. `ic_ex_ref_mean`:
rank IC left after the reference model's ranks are removed.

## Simulated long-only portfolios after costs

Top {N_NAMES} names, Rs {CAPITAL:,.0f} paper capital, trades at the next open with 10 bps slippage a side,
full delivery charges, no fill at a locked band. Averaged over every possible start day. Pre-tax, except
`after_tax_total_return`: capital-gains tax paid each financial year (20% short-term, 12.5% long-term above
Rs 1.25 lakh, 4% cess) and the book sold at the end. NIFTYBEES is bought once, held and sold the same way.

{sim_table(sims)}
`random` is the control: any model that cannot beat it has shown nothing. The hurdle for a stock-picking
model is the first row (own the whole universe); the hurdle for bothering at all is NIFTYBEES.

"""
    path.write_text(text + challenger_section(state, comparison, weights) + observed + decay_section(decay, retire) + graduation)
