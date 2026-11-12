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
        return View(self.dates[: i + 1], self.ret_cc[: i + 1], self.ret_id[: i + 1], self.traded[: i + 1])

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

    @property
    def asof(self) -> pd.Timestamp:
        return self.dates[-1]
