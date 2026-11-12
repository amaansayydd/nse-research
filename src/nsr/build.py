"""Build the cleaned research dataset from raw files.

Outputs (data/clean/):
  prices.parquet        one row per (sid, date): raw OHLCV, repaired returns, flags
  indices.parquet       index OHLC as printed in the daily bundle
  corp_actions.parquet  every equity corporate action with first/last publication date
  universe.parquet      point-in-time liquid universe (see universe.py)
  build_report.json     row counts and data-quality counters

Only research-window dates are read (config.assert_readable enforces it).
"""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config, parse
from .corpactions import parse_purpose, rights_factor
from .api import CA_DIR
from .download import raw_path
from .universe import build_universe

EPISODE_GAP_DAYS = 400      # a symbol silent this long starts a new security
CA_OPEN_TOLERANCE = 0.35    # |log(open / adjusted base)| above this => factor not trusted
ALIGN_TOLERANCE = 0.25      # a factor must fit the open this well to be moved to a neighbouring day
NON_EQUITY_SYMBOL = r"-RE\d*$"                       # rights entitlements trade under <SYMBOL>-RE
FUND_NAME = r"\bETF\b|BEES|MUTUAL FUND|\bMF\b|EXCHANGE TRADED"
REFERENCE = config.RAW / "reference"


def research_dates(end: date | None = None) -> list[date]:
    end = end or (config.HOLDOUT_START - timedelta(days=1))
    out, d = [], config.HISTORY_START
    while d <= end:
        if raw_path("pr", d).exists() or raw_path("cm", d).exists():
            out.append(d)
        d += timedelta(days=1)
    return out


def load_day(d: date) -> dict[str, pd.DataFrame]:
    """Parse one day. `src` is 'pr', 'cm' (fallback) or 'none' (no usable price file)."""
    try:
        return _load_day(d)
    except config.HoldoutViolation:
        raise
    except Exception as exc:  # name the day so a bad file is easy to find
        raise RuntimeError(f"failed to parse raw files for {d}: {exc!r}") from exc


def _load_day(d: date) -> dict[str, pd.DataFrame]:
    e = pd.DataFrame()
    zf = parse.open_pr(d)
    if zf is not None:
        eq, ix = parse.parse_pd(zf, d)
        out = {"eq": eq, "ix": ix, "bc": parse.parse_bc(zf, d), "bh": parse.parse_bh(zf, d),
               "mcap": parse.parse_mcap(zf, d), "src": "pr"}
    else:
        eq = parse.parse_cm(d)
        out = {"eq": eq, "ix": e, "bc": e, "bh": e, "mcap": e, "src": "cm" if len(eq) else "none"}
    out["mto"] = parse.parse_mto(d) if len(out["eq"]) else e
    out["date"] = d
    return out


def _cat(parts: list[dict], key: str) -> pd.DataFrame:
    frames = [p[key] for p in parts if len(p[key])]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------- identity

def load_symbol_changes(before: date) -> pd.DataFrame:
    """NSE's symbol-change list, cut at `before` so later renames are invisible."""
    p = REFERENCE / "symbolchange.csv"
    df = pd.read_csv(p, encoding="latin-1", header=0, names=["name", "old", "new", "eff"],
                     dtype=str, usecols=[0, 1, 2, 3])
    df = df.apply(lambda s: s.str.strip())
    df["eff"] = pd.to_datetime(df.eff, format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["eff"])
    return df[df.eff < pd.Timestamp(before)].sort_values("eff").reset_index(drop=True)


def assign_sid(px: pd.DataFrame, changes: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Stable security id that survives renames and separates reused symbols.

    A symbol's history is cut into episodes at gaps > EPISODE_GAP_DAYS. Two
    episodes are joined only when NSE lists the rename AND the new symbol's
    first prev_close matches the old symbol's last close (price continuity).
    """
    px = px.sort_values(["symbol", "date"])
    gap = px.groupby("symbol").date.diff().dt.days
    ep = (gap > EPISODE_GAP_DAYS).groupby(px.symbol).cumsum()
    key = px.symbol + "#" + ep.astype(str)
    g = px.assign(_k=key).groupby("_k", sort=False)
    eps = pd.DataFrame({
        "symbol": g.symbol.first(), "first": g.date.first(), "last": g.date.last(),
        "first_prev": g.prev_close.first(), "last_close": g.close.last(),
    })
    by_symbol = {s: e for s, e in eps.groupby("symbol")}
    parent = {k: k for k in eps.index}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    stats = {"renames_listed": 0, "renames_linked": 0, "renames_no_data": 0, "renames_price_break": 0}
    slack = pd.Timedelta(days=5)
    for r in changes.itertuples():
        if r.old not in by_symbol and r.new not in by_symbol:
            continue  # not an equity we hold (funds, bonds) or outside our dates
        stats["renames_listed"] += 1
        if r.old not in by_symbol or r.new not in by_symbol:
            stats["renames_no_data"] += 1
            continue
        o, n = by_symbol[r.old], by_symbol[r.new]
        o = o[(o["last"] < r.eff + slack) & (o["last"] > r.eff - pd.Timedelta(days=EPISODE_GAP_DAYS))]
        n = n[(n["first"] > r.eff - slack) & (n["first"] < r.eff + pd.Timedelta(days=EPISODE_GAP_DAYS))]
        if o.empty or n.empty:
            stats["renames_no_data"] += 1
            continue
        oe, ne = o.sort_values("last").iloc[-1], n.sort_values("first").iloc[0]
        if abs(ne.first_prev / oe.last_close - 1) > 0.02:
            stats["renames_price_break"] += 1
            continue
        parent[find(ne.name)] = find(oe.name)
        stats["renames_linked"] += 1

    roots = {k: find(k) for k in eps.index}
    ids = {r: i for i, r in enumerate(sorted(set(roots.values())), start=1)}
    sid = key.map(lambda k: ids[roots[k]]).astype("int32")
    stats["securities"] = len(ids)
    return sid.reindex(px.index), stats


# ---------------------------------------------------------- corporate actions

def load_register(before: date) -> pd.DataFrame:
    """NSE corporate-actions register (api.py), cut at `before`."""
    rows = []
    for f in sorted(CA_DIR.glob("ca_*.json")):
        rows += json.loads(f.read_text())
    df = pd.DataFrame(rows)
    df = df[df.series.isin(parse.EQUITY_SERIES)].copy()
    df["ex_date"] = pd.to_datetime(df.exDate, format="%d-%b-%Y", errors="coerce").astype("datetime64[ns]")
    df = df.dropna(subset=["ex_date"])
    df = df[df.ex_date < pd.Timestamp(before)]
    df["purpose"] = df.subject.str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    df["face_value"] = pd.to_numeric(df.faceVal, errors="coerce")
    return df[["symbol", "ex_date", "purpose", "face_value"]].drop_duplicates(["symbol", "ex_date", "purpose"])


def remap_register_symbols(reg: pd.DataFrame, changes: pd.DataFrame) -> pd.DataFrame:
    """The register files some actions under a company's *later* ticker (AMIORG's
    April 2025 split is listed as ACUTAAS). Put each action back on the ticker
    that was trading on its ex-date. Renames are walked newest-first so chains work."""
    reg = reg.copy()
    for r in changes.sort_values("eff", ascending=False).itertuples():
        m = (reg.symbol == r.new) & (reg.ex_date < r.eff)
        if m.any():
            reg.loc[m, "symbol"] = r.old
    return reg.drop_duplicates(["symbol", "ex_date", "purpose"])


def _bc_latest(bc: pd.DataFrame) -> pd.DataFrame:
    """Daily-file actions: one row per (symbol, ex_date, purpose), latest wording only."""
    bc = bc.assign(ex_date=bc.ex_date.astype("datetime64[ns]"), file_date=bc.file_date.astype("datetime64[ns]"))
    g = bc.groupby(["symbol", "ex_date", "purpose"], as_index=False).agg(
        first_file=("file_date", "min"), last_file=("file_date", "max"))
    latest = g.groupby(["symbol", "ex_date"]).last_file.transform("max")
    g["first_file"] = g.groupby(["symbol", "ex_date"]).first_file.transform("min")
    g = g[g.last_file == latest].copy()
    # an action that vanished from the files well before its ex-date was rescheduled
    g["confirmed"] = g.last_file >= g.ex_date - pd.Timedelta(days=5)
    return g


def consolidate_actions(bc: pd.DataFrame, register: pd.DataFrame | None = None) -> pd.DataFrame:
    """Merge the two corporate-action sources into one parsed table.

    The register is primary: it is complete and its ex-dates are right. The
    daily Bc file adds (a) actions the register lacks and (b) the date an
    action was first published. Rewordings of one event are counted once.
    """
    b = _bc_latest(bc)
    b["source"], b["face_value"] = "bc", np.nan
    if register is not None and len(register):
        a = register.assign(ex_date=register.ex_date.astype("datetime64[ns]"))
        revised = a.purpose.str.contains("REVISED")
        any_rev = revised.groupby([a.symbol, a.ex_date]).transform("any")
        a = a[~any_rev | revised].sort_values("ex_date")
        bkeys = (b.groupby(["symbol", "ex_date"], as_index=False).first_file.min()
                 .sort_values("ex_date").rename(columns={"ex_date": "bc_ex"}))
        a = pd.merge_asof(a, bkeys, left_on="ex_date", right_on="bc_ex", by="symbol",
                          direction="nearest", tolerance=pd.Timedelta(days=3)).drop(columns="bc_ex")
        a["last_file"], a["confirmed"], a["source"] = pd.NaT, True, "register"
        akeys = a[["symbol", "ex_date"]].drop_duplicates().sort_values("ex_date").assign(reg_ex=lambda x: x.ex_date)
        near = pd.merge_asof(b.sort_values("ex_date"), akeys, on="ex_date", by="symbol",
                             direction="nearest", tolerance=pd.Timedelta(days=3))
        g = pd.concat([a, near[near.reg_ex.isna()].drop(columns="reg_ex")], ignore_index=True)
    else:
        g = b
    acts = g.purpose.map(parse_purpose)
    g["factor"] = acts.map(lambda x: x.factor)
    g["dividend"] = acts.map(lambda x: x.dividend)
    # issue price = premium + face value; the register carries face value, the Bc file does not
    g["rights"] = [None if x.rights is None else (x.rights[0], x.rights[1], x.rights[2] + (fv if fv == fv else 0.0))
                   for x, fv in zip(acts, g.face_value)]
    g["div_unknown"] = acts.map(lambda x: x.div_unknown)
    g["unresolved"] = acts.map(lambda x: x.unresolved)
    g["kinds"] = acts.map(lambda x: x.kinds)
    g["_r"] = g.rights.astype(str)
    g = g.sort_values("source", ascending=False).drop_duplicates(
        ["symbol", "ex_date", "factor", "dividend", "_r", "div_unknown", "unresolved"]).drop(columns="_r")
    return g.sort_values(["ex_date", "symbol"]).reset_index(drop=True)


def _align_ex_dates(hit: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """If a split/bonus factor does not fit the open on its nominal ex-date but fits
    a neighbouring session, move it there (published ex-dates were sometimes one
    day off during the T+1 settlement transition)."""
    ratio = hit.factor != 1.0
    if not ratio.any():
        return hit
    by_symbol = {s: g for s, g in px[px.symbol.isin(hit.symbol[ratio].unique())].groupby("symbol")}
    for i in hit.index[ratio]:
        g = by_symbol[hit.at[i, "symbol"]]
        pos = int(np.searchsorted(g.date.to_numpy(), np.datetime64(hit.at[i, "apply_date"])))
        cand = g.iloc[max(0, pos - 2): pos + 3]
        err = np.log(cand.open / (cand.prev_close * hit.at[i, "factor"])).abs()
        nominal = err.get(g.index[pos], np.inf) if pos < len(g) else np.inf
        if not nominal <= ALIGN_TOLERANCE and len(err) and err.min() <= ALIGN_TOLERANCE:
            hit.at[i, "apply_date"] = cand.date.loc[err.idxmin()]
    return hit


def apply_actions(px: pd.DataFrame, ca: pd.DataFrame) -> pd.DataFrame:
    """Attach each confirmed action to the first day the symbol trades on/after ex-date."""
    px = px.assign(date=px.date.astype("datetime64[ns]")).sort_values(["symbol", "date"]).reset_index(drop=True)
    ca = ca[ca.confirmed & (ca.kinds != "")].sort_values("ex_date")
    hit = pd.merge_asof(
        ca, px[["date", "symbol"]].sort_values("date").assign(apply_date=lambda x: x.date),
        left_on="ex_date", right_on="date", by="symbol", direction="forward",
        tolerance=pd.Timedelta(days=60),
    ).dropna(subset=["apply_date"]).reset_index(drop=True)
    hit = _align_ex_dates(hit, px)
    prev = px.set_index(["symbol", "date"]).prev_close
    hit["prev_close"] = prev.reindex(pd.MultiIndex.from_frame(hit[["symbol", "apply_date"]])).to_numpy()
    hit["rf"] = [rights_factor(r, p) if r is not None else 1.0 for r, p in zip(hit.rights, hit.prev_close)]
    agg = hit.groupby(["symbol", "apply_date"]).agg(
        adj=("factor", "prod"), rf=("rf", "prod"), div=("dividend", "sum"),
        div_unknown=("div_unknown", "any"), ca_unresolved=("unresolved", "any"),
        ca_kinds=("kinds", lambda s: "+".join(sorted(set("+".join(s).split("+"))))),
        ca_published=("first_file", "min"),
    ).reset_index().rename(columns={"apply_date": "date"})
    agg["adj"] = agg.adj * agg.rf
    px = px.merge(agg.drop(columns="rf"), on=["symbol", "date"], how="left")
    px["adj"] = px.adj.fillna(1.0)
    px["div"] = px["div"].fillna(0.0)
    for c in ("div_unknown", "ca_unresolved"):
        px[c] = px[c].fillna(False).astype(bool)
    px["ca_kinds"] = px.ca_kinds.fillna("")
    return px


def compute_returns(px: pd.DataFrame) -> pd.DataFrame:
    # A dividend above 40% of the price is usually a parse error, but not always
    # (MAJESCO paid Rs 974 on a Rs 986 share in Dec 2020). Believe it only if the
    # ex-date open agrees with it.
    big = px["div"] > 0.4 * px.prev_close
    ex_base = px.prev_close * px.adj - px["div"]
    fits = big & (ex_base > 0) & (np.log(px.open / ex_base.where(ex_base > 0)).abs() < CA_OPEN_TOLERANCE)
    bad_div = big & ~fits
    px.loc[bad_div, "div"] = 0.0
    px.loc[bad_div, "div_unknown"] = True

    base = px.prev_close * px.adj
    px["ret_cc"] = (px.close + px["div"]) / base - 1      # close -> close, total return
    px["ret_on"] = (px.open + px["div"]) / base - 1       # prev close -> open
    px["ret_id"] = px.close / px.open - 1                 # open -> close
    px.loc[~(px.open > 0), ["ret_on", "ret_id"]] = np.nan

    has_factor = px.adj != 1.0
    px["ca_suspect"] = bad_div | (has_factor & ~big & (np.log(px.open / base).abs() > CA_OPEN_TOLERANCE))
    kill = px.ca_unresolved | px.ca_suspect
    px.loc[kill, ["ret_cc", "ret_on"]] = np.nan
    return px


def quality_flags(px: pd.DataFrame) -> pd.DataFrame:
    px = px.sort_values(["sid", "date"]).reset_index(drop=True)
    g = px.groupby("sid")
    last_close = g.close.shift(1)
    px["first_day"] = last_close.isna()
    # listing-day "return" is measured from the issue price: not a tradeable return
    px.loc[px.first_day, ["ret_cc", "ret_on"]] = np.nan
    # NSE's base price differs from the last traded close: relisting after suspension,
    # or a bad file on one side. Either way the day's return is not well defined.
    px["prevclose_mismatch"] = (~px.first_day) & ((px.prev_close / last_close - 1).abs() > 0.005)
    px.loc[px.prevclose_mismatch, ["ret_cc", "ret_on"]] = np.nan
    px["gap_days"] = g.date.diff().dt.days.fillna(0).astype("int32")
    # big unexplained move in a non-penny stock: possible missed corporate action (kept, flagged)
    px["jump_suspect"] = (px.ret_cc.abs() > 0.40) & (px.adj == 1.0) & (px.prev_close >= 5)
    px["locked_limit"] = px.band_hit.notna() & (px.high == px.low)
    return px


# -------------------------------------------------------------------- driver

def build(end: date | None = None, workers: int = 6) -> dict:
    end = end or (config.HOLDOUT_START - timedelta(days=1))
    dates = research_dates(end)
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(load_day, dates, chunksize=40))
    unusable = [p["date"].isoformat() for p in parts if p["src"] == "none"]
    fallback = [p["date"].isoformat() for p in parts if p["src"] == "cm"]
    parts = [p for p in parts if p["src"] != "none"]
    dates = [p["date"] for p in parts]

    px = _cat(parts, "eq")
    # funds are printed in series EQ: drop every symbol ever listed in the ETF section,
    # anything named like a fund, and rights-entitlement tickers
    funds = set(px.loc[px.is_etf, "symbol"]) | set(px.loc[px.name.str.upper().str.contains(FUND_NAME, regex=True), "symbol"])
    n_all = len(px)
    px = px[~px.symbol.isin(funds) & ~px.symbol.str.contains(NON_EQUITY_SYMBOL, regex=True)].drop(columns="is_etf")
    dropped_non_equity = n_all - len(px)
    for key, cols in (("bh", ["band_hit"]), ("mto", ["mto_qty", "deliv_qty"]),
                      ("mcap", ["face_value", "shares_out", "mcap"])):
        extra = _cat(parts, key)
        if len(extra):
            px = px.merge(extra[["date", "symbol", *cols]], on=["date", "symbol"], how="left")
        else:
            px[cols] = np.nan

    changes = load_symbol_changes(before=end + timedelta(days=1))
    register = remap_register_symbols(load_register(before=end + timedelta(days=1)), changes)
    ca = consolidate_actions(_cat(parts, "bc"), register)
    px = compute_returns(apply_actions(px, ca))

    sid, id_stats = assign_sid(px, changes)
    px["sid"] = sid
    px = quality_flags(px)

    avail = pd.to_datetime(px.date).dt.tz_localize(config.IST) + pd.Timedelta(
        hours=config.ASSUMED_EOD_PUBLISH.hour, minutes=config.ASSUMED_EOD_PUBLISH.minute)
    px["available_at"] = avail
    px["available_at_assumed"] = True

    ix = _cat(parts, "ix")
    ix["available_at"] = pd.to_datetime(ix.date).dt.tz_localize(config.IST) + pd.Timedelta(hours=20)
    # known to the public from the first daily file that printed it; if it never was
    # printed, we only claim it was known on the ex-date itself
    ca["available_at"] = ca.first_file.fillna(ca.ex_date).dt.tz_localize(config.IST) + pd.Timedelta(hours=20)
    uni = build_universe(px)

    config.CLEAN.mkdir(parents=True, exist_ok=True)
    px.to_parquet(config.CLEAN / "prices.parquet", index=False)
    ix.to_parquet(config.CLEAN / "indices.parquet", index=False)
    ca.drop(columns=["rights"]).to_parquet(config.CLEAN / "corp_actions.parquet", index=False)
    uni.to_parquet(config.CLEAN / "universe.parquet", index=False)

    n = len(px)
    priced = ca[ca.confirmed & ca.kinds.str.contains("split|bonus|rights|consolidation|unresolved|dividend")]
    report = {
        "built_through": end.isoformat(),
        "trading_days": len(dates), "first_day": dates[0].isoformat(), "last_day": dates[-1].isoformat(),
        "price_rows": n, "rows_dropped_funds_and_rights_entitlements": dropped_non_equity,
        "fund_symbols_excluded": len(funds), **id_stats,
        "actions_from_register": int((ca.source == "register").sum()),
        "actions_only_in_daily_file": int((ca.source == "bc").sum()),
        "days_from_fallback_source": fallback, "days_unusable_misfiled_or_empty": unusable,
        "days_without_delivery_file": int(sum(1 for p in parts if p["mto"].empty)),
        "days_without_band_hit_file": int(sum(1 for p in parts if p["bh"].empty)),
        "first_day_with_mcap": str(px.loc[px.mcap.notna(), "date"].min())[:10],
        "actions_total": len(ca), "actions_unconfirmed": int((~ca.confirmed).sum()),
        "actions_price_relevant": len(priced),
        "dividends_parsed": int(ca.kinds.str.contains(r"dividend(?!\?)").sum()),
        "dividends_amount_unknown": int(ca.div_unknown.sum()),
        "splits_bonuses_parsed": int(ca.kinds.str.contains("split|bonus|consolidation").sum()),
        "rights_parsed": int(ca.kinds.str.contains("rights").sum()),
        "actions_unresolved": int(ca.unresolved.sum()),
        "rows_ca_unresolved": int(px.ca_unresolved.sum()),
        "rows_ca_suspect": int(px.ca_suspect.sum()),
        "rows_prevclose_mismatch": int(px.prevclose_mismatch.sum()),
        "rows_jump_suspect": int(px.jump_suspect.sum()),
        "rows_ret_missing": int(px.ret_cc.isna().sum()),
        "rows_band_hit": int(px.band_hit.notna().sum()),
        "rows_locked_limit": int(px.locked_limit.sum()),
        "universe_rebalances": int(uni.rebalance_date.nunique()),
    }
    (config.CLEAN / "build_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
