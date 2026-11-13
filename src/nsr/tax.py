"""Indian capital-gains tax on listed shares, for after-tax paper results.

Rates checked on 2026-11-13: short-term gains (held 12 months or less) 20% under
section 111A, long-term gains 12.5% above Rs 1.25 lakh a year under section 112A,
plus 4% cess. Surcharge (income above Rs 50 lakh) is not modelled. Dividends are
taxed at slab rate and are ignored here. VERIFY with a chartered accountant
before relying on any after-tax number: frequent trading can be assessed as
business income, taxed at slab rate (`TaxModel.business()` shows that case).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .costs import CostModel


@dataclass(frozen=True)
class TaxModel:
    st_rate: float = 0.20
    lt_rate: float = 0.125
    lt_exempt: float = 125_000.0
    cess: float = 0.04
    long_days: int = 365

    @classmethod
    def business(cls, slab: float = 0.30) -> "TaxModel":
        """Every gain taxed at the top slab rate, no long-term relief."""
        return cls(st_rate=slab, lt_rate=slab, lt_exempt=0.0)


def fin_year(d) -> int:
    """Financial year (April to March), named by the year it starts in."""
    d = pd.Timestamp(d)
    return d.year if d.month >= 4 else d.year - 1


def year_tax(st: float, lt: float, carry_st: float, carry_lt: float, m: TaxModel) -> tuple[float, float, float]:
    """Tax for one financial year from net short-term and long-term gains (losses negative) and
    losses carried in (positive numbers). A short-term loss can absorb either kind of gain; a
    long-term loss only long-term gains. Returns (tax, short-term loss carried out, long-term
    loss carried out). The 8-year limit on carrying losses is not modelled."""
    if st < 0 and lt > 0:
        used = min(-st, lt)
        st, lt = st + used, lt - used
    for which in ("st", "lt"):                      # losses carried in: short-term first
        if carry_st > 0:
            gain = st if which == "st" else lt
            used = min(carry_st, max(gain, 0.0))
            carry_st -= used
            st, lt = (st - used, lt) if which == "st" else (st, lt - used)
    used = min(carry_lt, max(lt, 0.0))
    carry_lt, lt = carry_lt - used, lt - used
    tax = (max(st, 0.0) * m.st_rate + max(lt - m.lt_exempt, 0.0) * m.lt_rate) * (1 + m.cess)
    return tax, carry_st + max(-st, 0.0), carry_lt + max(-lt, 0.0)


def settle(eq: np.ndarray, dates: pd.DatetimeIndex, trades: list[tuple], open_pos: list[tuple],
           cost: CostModel, m: TaxModel) -> dict:
    """After-tax value of a simulated book.

    eq/dates: equity per session. trades: (sell date, buy date, cost, net proceeds) for every
    sale. open_pos: (buy date, cost, current value) for what is still held.
    Tax for each finished financial year is paid at that year's last session by selling a
    pro-rata slice of the book, so everything afterwards shrinks by the same factor. At the end
    the book is liquidated: selling costs and tax on the gains of the unfinished year come off."""
    fy = np.array([fin_year(d) for d in dates])
    years = sorted(set(fy.tolist()))
    gains = {y: [0.0, 0.0] for y in years}
    for sold, bought, basis, proceeds in trades:
        gains[fin_year(sold)][int((sold - bought).days > m.long_days)] += proceeds - basis
    scale, carry_st, carry_lt, paid = 1.0, 0.0, 0.0, 0.0
    curve = np.asarray(eq, dtype=float).copy()
    for y in years[:-1]:
        last = int(np.flatnonzero(fy == y)[-1])
        t, carry_st, carry_lt = year_tax(gains[y][0] * scale, gains[y][1] * scale, carry_st, carry_lt, m)
        f = 1.0 - t / (eq[last] * scale) if eq[last] > 0 else 1.0
        curve[last + 1:] *= f
        scale *= f
        paid += t
    st, lt = gains[years[-1]][0] * scale, gains[years[-1]][1] * scale
    exit_cost = 0.0
    for bought, basis, value in open_pos:
        net = value * (1 - cost.slippage)
        proceeds = net - cost.sell(net)
        exit_cost += (value - proceeds) * scale
        if (dates[-1] - bought).days > m.long_days:
            lt += (proceeds - basis) * scale
        else:
            st += (proceeds - basis) * scale
    t, _, _ = year_tax(st, lt, carry_st, carry_lt, m)
    return {"terminal": float(eq[-1] * scale - exit_cost - t), "tax": float(paid + t), "curve": curve}


def buy_and_hold_after_tax(returns: pd.Series, capital: float, cost: CostModel, m: TaxModel) -> float:
    """Value after buying with `capital` before the first return, holding, selling after the last
    and paying tax on the gain. `returns` is indexed by session date."""
    r = returns.fillna(0.0)
    held = (capital - cost.buy(capital)) * (1 - cost.slippage) * float((1 + r).prod())
    net = held * (1 - cost.slippage)
    proceeds = net - cost.sell(net)
    gain, long_term = proceeds - capital, (r.index[-1] - r.index[0]).days > m.long_days
    t, _, _ = year_tax(0.0 if long_term else gain, gain if long_term else 0.0, 0.0, 0.0, m)
    return float(proceeds - t)
