"""Research dataset: the panel plus the extra fields signals need, universe
membership per session, and realised forward returns for scoring.

Signals receive a `ResearchData` and return one row of scores per session.
`truncated(i)` gives the same object as it would have looked on the evening of
session i; the look-ahead test compares a signal computed on that with the same
row of the full-history computation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config
from ..panel import Panel
from ..universe import members_asof

HORIZONS = (1, 5, 20)
FIELDS = ("close", "value", "deliv_qty", "mto_qty")
EVAL_START = pd.Timestamp("2012-01-02")
TEXT_DIR = config.CLEAN / "research_text"
FILINGS_DIR = config.CLEAN / "research_filings"


def _assert_research(dates: pd.DatetimeIndex) -> None:
    if config.is_production():
        raise RuntimeError("research code must not run inside the production process")
    lo, hi = pd.Timestamp(config.HOLDOUT_START), pd.Timestamp(config.HOLDOUT_END)
    if ((dates >= lo) & (dates <= hi)).any():
        raise config.HoldoutViolation("research data contains locked-holdout sessions")


@dataclass
class ResearchData:
    panel: Panel
    fields: dict[str, np.ndarray]          # name -> [session, column]
    member: np.ndarray                     # in the universe for a prediction made that evening
    uni_rank: np.ndarray                   # liquidity rank of members (1 = most traded), NaN otherwise
    fwd: dict[int, np.ndarray]             # horizon -> return open(t+1) to open(t+1+h); NaN if incomplete
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)   # event tables with a `known` date column

    # ------------------------------------------------------------ loading
    @classmethod
    def load(cls, tables: tuple[str, ...] = ("board_meetings", "announcements", "insider")) -> "ResearchData":
        if config.is_production():
            raise RuntimeError("research code must not run inside the production process")
        panel = Panel.load(config.CLEAN)
        px = pd.read_parquet(config.CLEAN / "prices.parquet", columns=["date", "sid", "is_benchmark", *FIELDS])
        found = {t: next((d / f"{t}.parquet" for d in (TEXT_DIR, FILINGS_DIR) if (d / f"{t}.parquet").exists()), None) for t in tables}
        tabs = {t: pd.read_parquet(f) for t, f in found.items() if f is not None}
        return cls.from_panel(panel, px, tabs)

    @classmethod
    def from_panel(cls, panel: Panel, px: pd.DataFrame, tables: dict[str, pd.DataFrame] | None = None) -> "ResearchData":
        _assert_research(panel.dates)
        if "is_benchmark" in px:
            px = px[~px.is_benchmark]
        di, si = panel.dates.get_indexer(px.date), np.searchsorted(panel.sids, px.sid.to_numpy())
        shape = (len(panel.dates), len(panel.sids))
        fields = {}
        for f in FIELDS:
            a = np.full(shape, np.nan)
            if f in px:
                a[di, si] = px[f].to_numpy(float)
            fields[f] = a
        member, rank = _membership(panel)
        fwd = {}
        for h in HORIZONS:
            a = np.full(shape, np.nan)
            for i in range(len(panel.dates) - 1 - h):
                a[i] = panel.realized(i, h)
            fwd[h] = a
        return cls(panel, fields, member, rank, fwd, dict(tables or {}))

    # ------------------------------------------------------------ helpers
    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.panel.dates

    def eval_sessions(self) -> range:
        """Sessions whose 20-session target is complete inside the data."""
        first = int(np.searchsorted(self.dates, EVAL_START))
        return range(first, len(self.dates) - 1 - max(HORIZONS))

    def truncated(self, i: int) -> "ResearchData":
        """The dataset as known on the evening of session i. Forward returns are removed."""
        p, n = self.panel, i + 1
        small = Panel(dates=p.dates[:n], sids=p.sids, ret_cc=p.ret_cc[:n], ret_on=p.ret_on[:n], ret_id=p.ret_id[:n],
                      traded=p.traded[:n], lock_up=p.lock_up[:n], lock_dn=p.lock_dn[:n], symbols=p.symbols,
                      uni=p.uni[p.uni.rebalance_date <= p.dates[i]], bench=p.bench.iloc[:n])
        return ResearchData(small, {k: v[:n] for k, v in self.fields.items()}, self.member[:n], self.uni_rank[:n], {},
                            {k: t[t.known <= p.dates[i]] for k, t in self.tables.items()})

    def symbol_columns(self, dates: pd.Series, symbols: pd.Series, lookback: int = 5) -> np.ndarray:
        """Panel column for each (date, ticker), using the ticker's security on that date or, if it
        did not trade that day, on one of the previous `lookback` sessions. -1 if unknown."""
        sym = self.panel.symbols.reset_index()
        sym["i"] = self.dates.get_indexer(sym.date)
        q = pd.DataFrame({"i": np.searchsorted(self.dates, pd.to_datetime(dates).to_numpy(), side="right") - 1,
                          "symbol": symbols.to_numpy(), "row": np.arange(len(dates))})
        q = q[q.i >= 0].sort_values("i")
        m = pd.merge_asof(q, sym[["i", "symbol", "sid"]].sort_values("i"), on="i", by="symbol",
                          direction="backward", tolerance=lookback)
        out = np.full(len(dates), -1, dtype=np.int64)
        ok = m.sid.notna().to_numpy()
        out[m.row.to_numpy()[ok]] = self.panel.col(m.sid.to_numpy()[ok].astype(np.int64))
        return out


def _membership(panel: Panel) -> tuple[np.ndarray, np.ndarray]:
    member = np.zeros((len(panel.dates), len(panel.sids)), dtype=bool)
    rank = np.full(member.shape, np.nan, dtype=np.float32)
    ym = panel.dates.year * 12 + panel.dates.month
    for key in np.unique(ym):
        rows = np.flatnonzero(ym == key)
        m = members_asof(panel.uni, panel.dates[rows[0]])
        if len(m):
            cols = panel.col(m.sid.to_numpy())
            member[np.ix_(rows, cols)] = True
            rank[np.ix_(rows, cols)] = m["rank"].to_numpy(np.float32)
    return member, rank
