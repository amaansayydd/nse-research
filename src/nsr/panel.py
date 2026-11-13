"""Wide (session x security) arrays for features, scoring and simulation.

Look-ahead is prevented structurally: models never get the Panel, only a
`View` whose arrays end at the as-of session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .universe import members_asof

SYMBOL_LOOKBACK = 400   # sessions of ticker history a model may see


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    sids: np.ndarray
    ret_cc: np.ndarray      # close->close total return; NaN if no trade or blanked
    ret_on: np.ndarray      # previous close -> open
    ret_id: np.ndarray      # open -> close
    traded: np.ndarray      # a price row exists
    lock_up: np.ndarray     # locked at the upper band all session: cannot buy
    lock_dn: np.ndarray     # locked at the lower band all session: cannot sell
    symbols: pd.Series      # (date, sid) -> symbol
    uni: pd.DataFrame
    bench: pd.DataFrame     # date-indexed daily returns of benchmarks
    tables: dict = field(default_factory=dict)   # event tables with a `known` date column (e.g. board_meetings)
    _o2o: np.ndarray | None = field(default=None, repr=False)

    # ------------------------------------------------------------ loading
    @classmethod
    def load(cls, clean: Path | None = None) -> "Panel":
        clean = clean or config.clean_dir()
        if clean == config.PROD_DIR / "clean":
            config.assert_production("the production panel")
        cols = ["date", "sid", "symbol", "ret_cc", "ret_on", "ret_id", "band_hit", "locked_limit", "is_benchmark"]
        px = pd.read_parquet(clean / "prices.parquet", columns=cols)
        return cls.from_frames(px, pd.read_parquet(clean / "universe.parquet"),
                               pd.read_parquet(clean / "indices.parquet"))

    @classmethod
    def from_frames(cls, px: pd.DataFrame, uni: pd.DataFrame, ix: pd.DataFrame | None = None) -> "Panel":
        if "is_benchmark" not in px:
            px = px.assign(is_benchmark=False)
        dates = pd.DatetimeIndex(np.sort(px.date.unique()))
        bench = pd.DataFrame(index=dates)
        for sym, g in px[px.is_benchmark].groupby("symbol"):
            bench[sym] = g.set_index("date").ret_cc.reindex(dates)
        if ix is not None and len(ix):
            key = ix.name.str.upper().str.replace(" ", "")
            n50 = ix[key.isin(["S&PCNXNIFTY", "CNXNIFTY", "NIFTY50"])].drop_duplicates("date").set_index("date")
            bench["NIFTY50_PRICE"] = (n50.close / n50.prev_close - 1).reindex(dates)
        px = px[~px.is_benchmark]
        sids = np.sort(px.sid.unique())
        di, si = dates.get_indexer(px.date), np.searchsorted(sids, px.sid.to_numpy())
        shape = (len(dates), len(sids))

        def wide(values, dtype=np.float32, fill=np.nan):
            a = np.full(shape, fill, dtype=dtype)
            a[di, si] = values
            return a

        locked = px.locked_limit.fillna(False).to_numpy(bool)
        band = px.band_hit.to_numpy()
        return cls(
            dates=dates, sids=sids,
            ret_cc=wide(px.ret_cc.to_numpy()), ret_on=wide(px.ret_on.to_numpy()), ret_id=wide(px.ret_id.to_numpy()),
            traded=wide(True, bool, False),
            lock_up=wide(locked & (band == "H"), bool, False), lock_dn=wide(locked & (band == "L"), bool, False),
            symbols=px.set_index(["date", "sid"]).symbol.sort_index(), uni=uni, bench=bench,
        )

    # ------------------------------------------------------------- lookups
    def idx(self, d) -> int:
        i = self.dates.get_indexer([pd.Timestamp(d)])[0]
        if i < 0:
            raise KeyError(f"{d} is not a session in the panel")
        return int(i)

    def col(self, sids) -> np.ndarray:
        return np.searchsorted(self.sids, np.asarray(sids))

    def members(self, i: int) -> np.ndarray:
        """Column positions of universe members for a prediction made on session i."""
        return self.col(members_asof(self.uni, self.dates[i]).sid.to_numpy())

    def symbols_on(self, i: int) -> pd.Series:
        """sid -> symbol for securities that traded on session i."""
        return self.symbols.xs(self.dates[i], level="date")

    def view(self, i: int) -> "View":
        on = self.symbols_on(i)
        keys = np.full(len(self.sids), "", dtype=object)
        keys[self.col(on.index.to_numpy())] = on.to_numpy()
        asof = self.dates[i]
        return View(self.dates[: i + 1], self.ret_cc[: i + 1], self.ret_id[: i + 1], self.traded[: i + 1], keys,
                    sids=self.sids, uni=self.uni[self.uni.rebalance_date <= asof],
                    symbols=self.symbols.loc[self.dates[max(0, i - SYMBOL_LOOKBACK)]: asof],
                    tables={k: t[t.known <= asof] for k, t in self.tables.items()})

    # ------------------------------------------------- realised open-to-open
    @property
    def o2o(self) -> np.ndarray:
        """o2o[s] = return from session s's open to session s+1's open.
        A session with no trade contributes 0; a blanked return gives NaN."""
        if self._o2o is None:
            rid = np.where(self.traded, self.ret_id, 0.0)
            ron = np.where(self.traded, self.ret_on, 0.0)
            self._o2o = (1 + rid[:-1]) * (1 + ron[1:]) - 1
        return self._o2o

    def realized(self, i: int, h: int) -> np.ndarray:
        """Return from the open of session i+1 to the open of session i+1+h, per security.
        Needs sessions up to i+1+h to exist. NaN if the stock did not trade on the entry session."""
        if i + 1 + h >= len(self.dates):
            raise IndexError("target window is not complete yet")
        r = np.prod(1 + self.o2o[i + 1: i + 1 + h], axis=0) - 1
        return np.where(self.traded[i + 1], r, np.nan)


@dataclass(frozen=True)
class View:
    """Everything a model may see: arrays that stop at the as-of session."""
    dates: pd.DatetimeIndex
    ret_cc: np.ndarray
    ret_id: np.ndarray
    traded: np.ndarray
    keys: np.ndarray        # ticker on the as-of session per column ("" if it did not trade)
    sids: np.ndarray | None = None          # security id per column
    uni: pd.DataFrame | None = None         # universe rebalances decided on or before the as-of session
    symbols: pd.Series | None = None        # (date, sid) -> ticker for recent sessions up to the as-of session
    tables: dict = field(default_factory=dict)   # event tables, rows known by the as-of session only

    @property
    def asof(self) -> pd.Timestamp:
        return self.dates[-1]

    def member_mask(self, row: int) -> np.ndarray:
        """Universe membership per column for a prediction made on session `row`."""
        m = np.zeros(self.ret_cc.shape[1], dtype=bool)
        sid = members_asof(self.uni, self.dates[row]).sid.to_numpy()
        m[np.searchsorted(self.sids, sid)] = True
        return m

    def symbol_columns(self, when: pd.Series, tickers: pd.Series, lookback: int = 5) -> np.ndarray:
        """Column for each (date, ticker): the security that carried the ticker on the last session
        at or before the date, or on one of the `lookback` sessions before that. -1 if unknown."""
        sym = self.symbols.reset_index()
        sym["i"] = self.dates.get_indexer(sym.date)
        q = pd.DataFrame({"i": np.searchsorted(self.dates, pd.to_datetime(when).to_numpy(), side="right") - 1,
                          "symbol": np.asarray(tickers), "row": np.arange(len(when))})
        q = q[q.i >= 0].sort_values("i")
        m = pd.merge_asof(q, sym[["i", "symbol", "sid"]].sort_values("i"), on="i", by="symbol",
                          direction="backward", tolerance=lookback)
        out = np.full(len(when), -1, dtype=np.int64)
        ok = m.sid.notna().to_numpy()
        out[m.row.to_numpy()[ok]] = np.searchsorted(self.sids, m.sid.to_numpy()[ok].astype(np.int64))
        return out
