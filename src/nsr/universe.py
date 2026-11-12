"""Point-in-time liquid universe.

At each month-end trading day t, using only rows dated <= t:
  - the security's most recent trade (within the last 5 sessions) was in series EQ
  - it traded on at least MIN_DAYS of the last LOOKBACK sessions
  - rank by median daily traded value over those sessions; keep the top N

Which membership applies to a prediction made on day D: the latest rebalance in
a calendar month strictly before D's month (`members_asof`). The code cannot know
that today is the last session of a month until the next month starts, so this is
the only rule that gives the same answer live and in replay.
Because it is rebuilt from daily files that include every stock that traded at
the time, later-delisted names are members while they were liquid.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

TOP_N = 500
LOOKBACK = 126
MIN_DAYS = 100


def build_universe(px: pd.DataFrame, top_n: int = TOP_N, lookback: int = LOOKBACK,
                   min_days: int = MIN_DAYS) -> pd.DataFrame:
    value = px.pivot_table(index="date", columns="sid", values="value", aggfunc="sum")
    is_eq = px.assign(e=(px.series == "EQ").astype(float)).pivot_table(
        index="date", columns="sid", values="e", aggfunc="max")
    symbol = px.sort_values("date").groupby(["sid", "date"]).symbol.last()
    days = value.index
    month_ends = pd.Series(days, index=days).groupby([days.year, days.month]).max().to_numpy()
    pos = {d: i for i, d in enumerate(days)}
    out = []
    for t in month_ends:
        i = pos[pd.Timestamp(t)]
        if i + 1 < lookback:
            continue
        win = value.iloc[i + 1 - lookback: i + 1]
        traded = win.notna().sum()
        med = win.median()
        recent_eq = is_eq.iloc[max(0, i - 4): i + 1].ffill().iloc[-1] == 1.0
        ok = (traded >= min_days) & recent_eq
        top = med[ok].sort_values(ascending=False).head(top_n)
        sym_t = px[(px.date <= t) & px.sid.isin(top.index)].sort_values("date").groupby("sid").symbol.last()
        out.append(pd.DataFrame({
            "rebalance_date": pd.Timestamp(t), "sid": top.index.astype("int32"),
            "symbol": sym_t.reindex(top.index).to_numpy(),
            "rank": np.arange(1, len(top) + 1), "median_value": top.to_numpy(),
        }))
    uni = pd.concat(out, ignore_index=True)
    uni["available_at"] = uni.rebalance_date.dt.tz_localize(config.IST) + pd.Timedelta(hours=20)
    return uni


def members_asof(uni: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Universe rows that apply to a prediction made on `asof` (see module docstring)."""
    asof = pd.Timestamp(asof)
    rb = uni.rebalance_date
    done = rb[(rb.dt.year * 12 + rb.dt.month) < (asof.year * 12 + asof.month)]
    if done.empty:
        return uni.iloc[0:0]
    return uni[rb == done.max()]
