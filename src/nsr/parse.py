"""Parse raw NSE daily files into tidy frames. No look-ahead: each function
sees one trade date's file only, and refuses holdout dates outside production.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .download import raw_path

# Listed equity shares only. EQ = normal rolling settlement, BE/BZ = trade-for-trade
# (surveillance / non-compliant). SME, ETFs, bonds, warrants are excluded.
EQUITY_SERIES = ("EQ", "BE", "BZ")
PD_COLS = [
    "mkt", "series", "symbol", "name", "prev_close", "open", "high", "low", "close",
    "value", "volume", "ind_sec", "corp_ind", "trades", "hi_52w", "lo_52w",
]


def _read_member(zf: zipfile.ZipFile, prefix: str) -> bytes | None:
    for n in zf.namelist():
        base = n.rsplit("/", 1)[-1].lower()
        if base.startswith(prefix) and base.endswith((".csv", ".txt")):
            return zf.read(n)
    return None


def _csv(raw: bytes, ncols: int) -> pd.DataFrame:
    """Read a member CSV as strings. Empty or short files yield an empty frame
    with `ncols` columns so callers can treat them as 'nothing published'."""
    empty = pd.DataFrame(columns=range(ncols), dtype=str)
    try:
        df = pd.read_csv(
            io.BytesIO(raw), dtype=str, encoding="latin-1", header=0,
            on_bad_lines="skip", keep_default_na=False, index_col=False,
        )
    except pd.errors.EmptyDataError:
        return empty
    if df.shape[1] < ncols:
        return empty
    return df.iloc[:, :ncols].apply(lambda s: s.str.strip())


def _dates(s: pd.Series) -> pd.Series:
    """Bc files use dd/mm/yyyy until ~2020 and yyyy-mm-dd after."""
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(dmy)


def inner_date_matches(member_name: str, d: date) -> bool:
    """NSE sometimes files another day's bundle under a date (PR020118.zip holds
    02-Jan-2019). The member file names carry the true date; trust those."""
    digits = "".join(ch for ch in member_name.rsplit("/", 1)[-1] if ch.isdigit())
    return digits in (d.strftime("%d%m%y"), d.strftime("%d%m%Y"))


def open_pr(d: date) -> zipfile.ZipFile | None:
    """Open day d's bundle, or None if it is absent or holds another day's data."""
    config.assert_readable(d)
    p = raw_path("pr", d)
    if not p.exists():
        return None
    zf = zipfile.ZipFile(p)
    pd_members = [n for n in zf.namelist() if n.rsplit("/", 1)[-1].lower().startswith("pd")]
    if not pd_members or not inner_date_matches(pd_members[0], d):
        return None
    return zf


def parse_cm(d: date) -> pd.DataFrame:
    """Fallback price source: the classic cm<date>bhav.csv.zip (no indices, no band hits)."""
    config.assert_readable(d)
    p = raw_path("cm", d)
    if not p.exists():
        return pd.DataFrame()
    zf = zipfile.ZipFile(p)
    name = zf.namelist()[0]
    if d.strftime("%d%b%Y").upper() not in name.upper():
        return pd.DataFrame()
    df = _csv(zf.read(name), 12)
    df.columns = ["symbol", "series", "open", "high", "low", "close", "last", "prev_close",
                  "volume", "value", "timestamp", "trades"]
    num = ["prev_close", "open", "high", "low", "close", "value", "volume", "trades"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    eq = df[df.series.isin(EQUITY_SERIES) & (df.close > 0) & (df.prev_close > 0)].copy()
    eq["_o"] = eq.series.map({s: i for i, s in enumerate(EQUITY_SERIES)})
    eq = eq.sort_values(["symbol", "_o"]).drop_duplicates("symbol")
    eq["date"], eq["name"], eq["nifty50"], eq["corp_ind"], eq["is_etf"] = pd.Timestamp(d), "", False, "", False
    return eq[["date", "symbol", "series", "name", "prev_close", "open", "high", "low",
               "close", "value", "volume", "trades", "nifty50", "corp_ind", "is_etf"]].reset_index(drop=True)


def parse_pd(zf: zipfile.ZipFile, d: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (equity price rows, index rows) for one day."""
    raw = _read_member(zf, "pd")
    if raw is None:
        return pd.DataFrame(), pd.DataFrame()
    df = _csv(raw, len(PD_COLS))
    df.columns = PD_COLS
    num = ["prev_close", "open", "high", "low", "close", "value", "volume", "trades"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")

    # section header rows ("EXCHANGE TRADED FUND", ...) have a name but no symbol or price
    header = (df.mkt == "") & (df.symbol == "") & (df.name != "") & df.close.isna()
    df["is_etf"] = df.name.where(header).ffill().fillna("").str.upper().str.contains("EXCHANGE TRADED")
    eq = df[(df.mkt == "N") & df.series.isin(EQUITY_SERIES) & (df.symbol != "")].copy()
    eq = eq[(eq.close > 0) & (eq.prev_close > 0)]
    eq["nifty50"] = eq.ind_sec == "Y"
    eq["date"] = pd.Timestamp(d)
    # one row per symbol: prefer EQ over BE over BZ if a symbol shows in two series
    eq["_o"] = eq.series.map({s: i for i, s in enumerate(EQUITY_SERIES)})
    eq = eq.sort_values(["symbol", "_o"]).drop_duplicates("symbol")
    eq = eq[["date", "symbol", "series", "name", "prev_close", "open", "high", "low",
             "close", "value", "volume", "trades", "nifty50", "corp_ind", "is_etf"]]

    ix = df[(df.symbol == "") & (df.series == "") & (df.name != "") & df.close.notna()].copy()
    ix["date"] = pd.Timestamp(d)
    ix = ix[["date", "name", "prev_close", "open", "high", "low", "close"]]
    return eq.reset_index(drop=True), ix.reset_index(drop=True)


def parse_bc(zf: zipfile.ZipFile, d: date) -> pd.DataFrame:
    """Corporate actions as published in day d's bundle (usually ex-dates >= d)."""
    raw = _read_member(zf, "bc")
    if raw is None:
        return pd.DataFrame()
    df = _csv(raw, 10)
    df.columns = ["series", "symbol", "name", "record_dt", "bc_start", "bc_end",
                  "ex_date", "nd_start", "nd_end", "purpose"]
    df = df[df.series.isin(EQUITY_SERIES)].copy()
    df["ex_date"] = _dates(df.ex_date)
    df["record_dt"] = _dates(df.record_dt)
    df["purpose"] = df.purpose.str.upper().str.replace(r"\s+", " ", regex=True)
    df["file_date"] = pd.Timestamp(d)
    df = df.dropna(subset=["ex_date"]).drop_duplicates(["symbol", "ex_date", "purpose"])
    return df[["file_date", "symbol", "ex_date", "record_dt", "purpose"]].reset_index(drop=True)


def parse_bh(zf: zipfile.ZipFile, d: date) -> pd.DataFrame:
    """Securities that hit their upper (H) or lower (L) price band during the day."""
    raw = _read_member(zf, "bh")
    if raw is None:
        return pd.DataFrame()
    df = _csv(raw, 4)
    df.columns = ["symbol", "series", "name", "band_hit"]
    df = df[df.series.isin(EQUITY_SERIES) & df.band_hit.isin(["H", "L"])].copy()
    df["date"] = pd.Timestamp(d)
    return df[["date", "symbol", "band_hit"]].drop_duplicates(["symbol"]).reset_index(drop=True)


def parse_mcap(zf: zipfile.ZipFile, d: date) -> pd.DataFrame:
    """Face value, shares outstanding and market cap. Only present in recent years."""
    raw = _read_member(zf, "mcap")
    if raw is None:
        return pd.DataFrame()
    df = _csv(raw, 10)
    df.columns = ["trade_date", "symbol", "series", "name", "category", "last_trade",
                  "face_value", "shares_out", "mcap_price", "mcap"]
    df = df[df.series.isin(EQUITY_SERIES)].copy()
    for c in ("face_value", "shares_out", "mcap"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.Timestamp(d)
    return df[["date", "symbol", "face_value", "shares_out", "mcap"]].drop_duplicates("symbol")


def parse_mto(d: date) -> pd.DataFrame:
    """Security-wise delivery position for day d."""
    config.assert_readable(d)
    p: Path = raw_path("mto", d)
    if not p.exists():
        return pd.DataFrame()
    rows = []
    lines = p.read_text(encoding="latin-1").splitlines()
    if len(lines) < 2 or d.strftime("%d%m%Y") not in lines[1]:
        return pd.DataFrame()  # header carries the trade date; reject misfiled days
    for line in lines:
        f = line.split(",")
        if len(f) >= 7 and f[0].strip() == "20" and f[3].strip() in EQUITY_SERIES:
            rows.append((f[2].strip(), f[3].strip(), f[4], f[5]))
    df = pd.DataFrame(rows, columns=["symbol", "series", "mto_qty", "deliv_qty"])
    for c in ("mto_qty", "deliv_qty"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.Timestamp(d)
    return df.drop_duplicates("symbol")[["date", "symbol", "mto_qty", "deliv_qty"]]
