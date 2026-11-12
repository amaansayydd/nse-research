"""NSE website JSON APIs (cookie-protected).

Used for the corporate-actions register, which is more complete than the daily
Bc file (the Bc file omits some splits from ~2022 on). The register has no
publication timestamp, so it is used only for *what happened on an ex-date*,
never as evidence of when something became known.

Requests whose window overlaps the locked holdout are refused outside production.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from . import config

SITE = "https://www.nseindia.com"
WARMUP = SITE + "/companies-listing/corporate-filings-actions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": WARMUP,
}
CA_DIR = config.RAW / "ca_api"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(WARMUP, timeout=30)  # sets the cookies the API insists on
    return s


def _guard_window(start: date, end: date) -> None:
    if not config.is_production() and end >= config.HOLDOUT_START and start <= config.HOLDOUT_END:
        raise config.HoldoutViolation(f"API window {start}..{end} overlaps the locked holdout")


def corporate_actions(s: requests.Session, start: date, end: date, retries: int = 4) -> list[dict]:
    _guard_window(start, end)
    url = f"{SITE}/api/corporates-corporateActions"
    params = {"index": "equities", "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
    for attempt in range(retries):
        try:
            r = s.get(url, params=params, timeout=90)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return data
        except (requests.RequestException, ValueError):
            pass
        time.sleep(3 * (attempt + 1))
        s.get(WARMUP, timeout=30)
    raise RuntimeError(f"corporate actions API failed for {start}..{end}")


def fetch_history(start: date, end: date, out_dir: Path = CA_DIR) -> dict[str, int]:
    """One JSON file per calendar quarter; existing complete quarters are skipped."""
    out_dir.mkdir(parents=True, exist_ok=True)
    s, counts = session(), {}
    q = date(start.year, 3 * ((start.month - 1) // 3) + 1, 1)
    while q <= end:
        nxt = date(q.year + (q.month + 3 > 12), (q.month + 3 - 1) % 12 + 1, 1)
        lo, hi = max(q, start), min(nxt - timedelta(days=1), end)
        f = out_dir / f"ca_{lo:%Y%m%d}_{hi:%Y%m%d}.json"
        if not f.exists():
            rows = corporate_actions(s, lo, hi)
            f.write_text(json.dumps(rows))
            time.sleep(0.7)
        counts[f.name] = len(json.loads(f.read_text()))
        q = nxt
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, default=config.HISTORY_START)
    ap.add_argument("--end", type=date.fromisoformat, default=config.HOLDOUT_START - timedelta(days=1))
    a = ap.parse_args()
    c = fetch_history(a.start, a.end)
    print(f"{len(c)} quarters, {sum(c.values())} rows; smallest {min(c.values())}, largest {max(c.values())}")
