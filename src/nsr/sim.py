"""Long-only paper portfolio.

Every h sessions the portfolio is re-formed into the model's top N names.
Decisions use the evening's ranking; trades happen at the next session's open.

  - buy  : open * (1 + slippage) plus charges. No fill if the stock does not
           trade or is locked at its upper band; the cash stays idle.
  - sell : open * (1 - slippage) minus charges. If the stock does not trade or
           is locked at its lower band, the sell is retried every session.
  - a holding that stops trading stays marked at its last price. That is the
    optimistic case. With `writeoff_after` set, a holding silent for that many
    sessions is written down to zero instead (the pessimistic bound).

To remove the luck of which day the cycle starts, h portfolios are run, one per
start offset, and their equity curves are averaged.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import tax as taxes
from .costs import CostModel
from .panel import Panel


@dataclass
class SimResult:
    equity: pd.Series          # average equity across start offsets, indexed by session
    stats: dict


def _one_phase(panel: Panel, picks: dict[int, np.ndarray], sessions: range, rebal: set[int], n_names: int,
               capital: float, cost: CostModel, writeoff_after: int | None) -> tuple[np.ndarray, dict, list, list]:
    """Returns equity per session, counters, every sale as (sell session, buy session, cost,
    net proceeds), and what is still held as (buy session, cost, value)."""
    cash, pos, last_trade, pending = capital, {}, {}, set()
    basis, bought, trades = {}, {}, []
    eq = np.empty(len(sessions))
    st = {"buys": 0, "sells": 0, "unfilled_buys": 0, "blocked_sells": 0, "charges": 0.0,
          "slippage": 0.0, "traded_notional": 0.0, "writeoffs": 0}
    nz = lambda x: 0.0 if not np.isfinite(x) else float(x)
    for k, s in enumerate(sessions):
        tr = panel.traded[s]
        for c in pos:                                     # overnight move to the open
            if tr[c]:
                pos[c] *= 1 + nz(panel.ret_on[s, c])
        target = picks.get(s - 1) if (s - 1) in rebal else None
        if target is not None:
            keep = set(target[:n_names].tolist())
            pending = {c for c in pos if c not in keep}
        for c in sorted(pending):                         # sells first: they fund the buys
            if tr[c] and not panel.lock_dn[s, c]:
                gross = pos.pop(c)
                net = gross * (1 - cost.slippage)
                fee = cost.sell(net)
                cash += net - fee
                trades.append((s, bought.pop(c), basis.pop(c), net - fee))
                st["sells"] += 1; st["charges"] += fee; st["slippage"] += gross - net; st["traded_notional"] += gross
                pending.discard(c)
            else:
                st["blocked_sells"] += 1
        if target is not None:
            want = [c for c in target[:n_names].tolist() if c not in pos][: max(n_names - len(pos), 0)]
            if want:
                per = min((cash + sum(pos.values())) / n_names, cash / len(want))
                for c in want:
                    if per <= 0:
                        break
                    if tr[c] and not panel.lock_up[s, c]:
                        fee = cost.buy(per)
                        pos[c] = (per - fee) * (1 - cost.slippage)
                        basis[c], bought[c] = per, s
                        cash -= per
                        st["buys"] += 1; st["charges"] += fee; st["slippage"] += (per - fee) * cost.slippage
                        st["traded_notional"] += per
                    else:
                        st["unfilled_buys"] += 1
        for c in list(pos):                               # intraday move, and silent holdings
            if tr[c]:
                pos[c] *= 1 + nz(panel.ret_id[s, c])
                last_trade[c] = s
            elif writeoff_after is not None and s - last_trade.get(c, s) >= writeoff_after:
                pos.pop(c); pending.discard(c); st["writeoffs"] += 1
                basis.pop(c); bought.pop(c)               # no loss is claimed on a write-off
        for c in pos:
            last_trade.setdefault(c, s)
        eq[k] = cash + sum(pos.values())
    return eq, st, trades, [(bought[c], basis[c], v) for c, v in pos.items()]


def simulate(panel: Panel, picks: dict[int, np.ndarray], start: int, end: int, h: int, n_names: int = 20,
             capital: float = 1_000_000.0, cost: CostModel | None = None, writeoff_after: int | None = None,
             tax: "taxes.TaxModel | None" = None) -> SimResult:
    """`picks[i]` = panel column positions ranked best-first for the decision made on session i.
    Trading runs over sessions start+1 .. end. With `tax`, the stats also carry the after-tax
    result: tax paid each financial year, book liquidated at the end (nsr.tax.settle)."""
    cost = cost or CostModel()
    sessions = range(start + 1, end + 1)
    dates = panel.dates[start + 1: end + 1]
    curves, agg, settled = [], {}, []
    for p in range(h):
        rebal = set(range(start + p, end, h))
        eq, st, trades, held = _one_phase(panel, picks, sessions, rebal, n_names, capital, cost, writeoff_after)
        curves.append(eq)
        for k, v in st.items():
            agg[k] = agg.get(k, 0) + v / h
        if tax is not None:
            settled.append(taxes.settle(
                eq, dates, [(panel.dates[a], panel.dates[b], c, d) for a, b, c, d in trades],
                [(panel.dates[b], c, v) for b, c, v in held], cost, tax))
    equity = pd.Series(np.mean(curves, axis=0), index=dates)
    stats = performance(equity, capital)
    years = len(equity) / 252
    stats.update({k: round(v, 2) for k, v in agg.items()})
    if settled:
        terminal = float(np.mean([x["terminal"] for x in settled]))
        stats["after_tax_total_return"] = round(terminal / capital - 1, 4)
        stats["after_tax_cagr"] = round(float((terminal / capital) ** (1 / years) - 1), 4) if years > 0 and terminal > 0 else np.nan
        stats["tax_paid"] = round(float(np.mean([x["tax"] for x in settled])), 2)
    stats["turnover_per_year"] = round(agg["traded_notional"] / 2 / capital / years, 2) if years else np.nan
    stats["cost_drag_per_year"] = round((agg["charges"] + agg["slippage"]) / capital / years, 4) if years else np.nan
    return SimResult(equity, stats)


def performance(equity: pd.Series, start_value: float | None = None) -> dict:
    start_value = start_value if start_value is not None else equity.iloc[0]
    r = equity.pct_change().fillna(equity.iloc[0] / start_value - 1)
    years = len(equity) / 252
    dd = (equity / equity.cummax() - 1).min()
    return {
        "total_return": round(float(equity.iloc[-1] / start_value - 1), 4),
        "cagr": round(float((equity.iloc[-1] / start_value) ** (1 / years) - 1), 4) if years > 0 else np.nan,
        "vol": round(float(r.std() * np.sqrt(252)), 4),
        "max_drawdown": round(float(dd), 4),
    }


def buy_and_hold(returns: pd.Series, capital: float = 1_000_000.0) -> pd.Series:
    """Equity curve of a costless holding with the given daily returns (benchmarks)."""
    return capital * (1 + returns.fillna(0)).cumprod()
