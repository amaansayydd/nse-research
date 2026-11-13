"""Exchange filings with exact broadcast times, for research-window trials.

    python -m nsr.research.filings            download insider-trade (PIT) history and build the table

Insider trades (SEBI PIT regulation 7 disclosures) come from NSE's corporates-pit API, one request
per calendar quarter, raw JSON kept gzipped under data/raw/pit_api. The API has data from 2016.
A request that overlaps the locked holdout is refused (api._guard_window).

Timing rule: a filing is usable by the 20:30 run of day D only if it was broadcast by 20:00 on D.
`known` is that day, or the next calendar day for a later broadcast; the event belongs to the
first trading session on or after `known`.
"""
from __future__ import annotations

import gzip
import json
import time
from datetime import date, timedelta

import pandas as pd

from .. import api, config
from ..build import load_symbol_changes

PIT_DIR = config.RAW / "pit_api"
OUT_DIR = config.CLEAN / "research_filings"
PIT_START = date(2016, 1, 1)
CUTOFF_HOUR = 20


def quarters(start: date, end: date):
    q = date(start.year, 3 * ((start.month - 1) // 3) + 1, 1)
    while q <= end:
        nxt = date(q.year + (q.month + 3 > 12), (q.month + 3 - 1) % 12 + 1, 1)
        yield max(q, start), min(nxt - timedelta(days=1), end)
        q = nxt


def fetch_pit(start: date = PIT_START, end: date | None = None, pause: float = 2.0) -> dict[str, int]:
    end = end or config.HOLDOUT_START - timedelta(days=1)
    PIT_DIR.mkdir(parents=True, exist_ok=True)
    s, counts = None, {}
    for lo, hi in quarters(start, end):
        api._guard_window(lo, hi)
        f = PIT_DIR / f"pit_{lo:%Y%m%d}_{hi:%Y%m%d}.json.gz"
        if not f.exists():
            s = s or api.session()
            for attempt in range(4):
                r = s.get(api.SITE + "/api/corporates-pit", timeout=120,
                          params={"index": "equities", "from_date": lo.strftime("%d-%m-%Y"), "to_date": hi.strftime("%d-%m-%Y")})
                if r.status_code == 200 and isinstance(r.json().get("data"), list):
                    break
                time.sleep(10 * (attempt + 1))
                s = api.session()
            else:
                raise RuntimeError(f"PIT API failed for {lo}..{hi}")
            with gzip.open(f, "wt") as fh:
                json.dump(r.json()["data"], fh)
            time.sleep(pause)
        with gzip.open(f, "rt") as fh:
            counts[f.name] = len(json.load(fh))
    return counts


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def build_pit() -> pd.DataFrame:
    rows = []
    for f in sorted(PIT_DIR.glob("pit_*.json.gz")):
        with gzip.open(f, "rt") as fh:
            rows += json.load(fh)
    d = pd.DataFrame(rows)
    b = pd.to_datetime(d["date"], format="%d-%b-%Y %H:%M", errors="coerce")
    out = pd.DataFrame({
        "broadcast": b,
        "known": (b + pd.to_timedelta((b.dt.hour >= CUTOFF_HOUR).astype(int), unit="D")).dt.normalize(),
        "symbol": d.symbol.str.strip(), "person": d.acqName.str.strip(), "category": d.personCategory.str.strip(),
        "mode": d.acqMode.str.strip(), "txn": d.tdpTransactionType.str.strip(), "sec_type": d.secType.str.strip(),
        "qty": _num(d.secAcq), "value": _num(d.secVal),
        "before_pct": _num(d.befAcqSharesPer), "after_pct": _num(d.afterAcqSharesPer),
        "trade_from": pd.to_datetime(d.acqfromDt, format="%d-%b-%Y", errors="coerce"),
        "trade_to": pd.to_datetime(d.acqtoDt, format="%d-%b-%Y", errors="coerce"),
        "filing": d.pid.astype(str), "row_id": d.did.astype(str),      # one filing can list many transactions
    })
    out = out.dropna(subset=["broadcast", "symbol"]).drop_duplicates("row_id").sort_values(["broadcast", "row_id"]).reset_index(drop=True)
    # The API files old disclosures under the company's ticker of today (the same trap as the
    # corporate-actions register, data/README F29). Put each row back on the ticker in use when
    # it was broadcast. Renames dated inside the holdout are not visible to research.
    for r in load_symbol_changes(config.HOLDOUT_START).sort_values("eff", ascending=False).itertuples():
        m = (out.symbol == r.new) & (out.broadcast < r.eff)
        if m.any():
            out.loc[m, "symbol"] = r.old
    assert out.broadcast.max() < pd.Timestamp(config.HOLDOUT_START), "insider table reaches into the holdout"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_DIR / "insider.parquet", index=False)
    return out


if __name__ == "__main__":
    c = fetch_pit()
    t = build_pit()
    print(f"{len(c)} quarters, {sum(c.values())} raw rows, {len(t)} in the table, "
          f"{t.broadcast.min():%Y-%m-%d} .. {t.broadcast.max():%Y-%m-%d}")
    print(t.groupby(t.broadcast.dt.year).size().to_dict())
