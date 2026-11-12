"""Download NSE daily archive files.

Sources (verified reachable 2026-11-12):
  pr  : PRddmmyy.zip   daily bundle: prices (all series + indices), corporate
                       actions, price-band hits, announcements text, board
                       meetings, market cap (recent years). Available 2010+.
  mto : MTO_ddmmyyyy.DAT  security-wise delivery position. Available 2010+.

Holdout-dated files are written straight to the locked directory outside the
project. Their contents are never parsed here: we only check the first bytes
(file-type magic) and record size + sha256.

A 404 means "no file for that date" (weekend/holiday). Missed days are never
synthesised. Run with --retry-404 to re-check weekday 404s once.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config

BASE = "https://nsearchives.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}


@dataclass(frozen=True)
class Source:
    name: str
    url: str  # strftime template
    filename: str  # strftime template, ISO-dated
    magic: bytes


SOURCES = {
    "pr": Source("pr", "/archives/equities/bhavcopy/pr/PR%d%m%y.zip", "PR_%Y%m%d.zip", b"PK"),
    "mto": Source("mto", "/archives/equities/mto/MTO_%d%m%Y.DAT", "MTO_%Y%m%d.DAT", b"Security"),
    # classic bhavcopy (ends July 2024): fallback for days whose PR bundle is missing or misfiled
    "cm": Source("cm", "/content/historical/EQUITIES/%Y/{MON}/cm%d{MON}%Ybhav.csv.zip", "CM_%Y%m%d.zip", b"PK"),
}
DEFAULT_SOURCES = ["pr", "mto"]

MANIFEST_FIELDS = ["date", "source", "status", "bytes", "sha256", "fetched_at_utc"]
_lock = threading.Lock()
_local = threading.local()


def raw_path(source: str, d: date) -> Path:
    s = SOURCES[source]
    return config.raw_root(d) / source / f"{d.year}" / d.strftime(s.filename)


def manifest_path(d: date) -> Path:
    return config.raw_root(d) / "manifest.csv"


def load_manifest(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {(r["date"], r["source"]): r for r in csv.DictReader(f)}


def _append_manifest(path: Path, row: dict) -> None:
    with _lock:
        new = not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)


def _session() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update(HEADERS)
    return _local.s


def fetch_one(source: str, d: date, retries: int = 5) -> str:
    """Fetch one file. Returns status: 'ok', '404' or 'error:<detail>'."""
    s = SOURCES[source]
    url = BASE + d.strftime(s.url.replace("{MON}", d.strftime("%b").upper()))
    status, body = "error:unknown", b""
    for attempt in range(retries):
        try:
            r = _session().get(url, timeout=40)
            if r.status_code == 200 and r.content[: len(s.magic)] == s.magic:
                status, body = "ok", r.content
                break
            if r.status_code == 404:
                status = "404"
                break
            status = f"error:http{r.status_code}"
        except requests.RequestException as e:  # network trouble: retry
            status = f"error:{type(e).__name__}"
        time.sleep(1.5 * (attempt + 1))
    row = {
        "date": d.isoformat(),
        "source": source,
        "status": status,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest() if body else "",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if status == "ok":
        p = raw_path(source, d)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(body)
        tmp.rename(p)
    _append_manifest(manifest_path(d), row)
    return status


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def plan(start: date, end: date, sources: list[str], retry_404: bool) -> list[tuple[str, date]]:
    manifests: dict[Path, dict] = {}
    todo = []
    for d in daterange(start, end):
        mp = manifest_path(d)
        if mp not in manifests:
            manifests[mp] = load_manifest(mp)
        for src in sources:
            if raw_path(src, d).exists():
                continue
            prev = manifests[mp].get((d.isoformat(), src))
            if prev and prev["status"] == "404" and not (retry_404 and d.weekday() < 5):
                continue
            todo.append((src, d))
    return todo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=date.fromisoformat, default=config.HISTORY_START)
    ap.add_argument("--end", type=date.fromisoformat, default=config.HOLDOUT_END)
    ap.add_argument("--sources", nargs="+", default=DEFAULT_SOURCES, choices=list(SOURCES))
    ap.add_argument("--dates", nargs="+", type=date.fromisoformat, help="fetch only these dates")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retry-404", action="store_true")
    a = ap.parse_args(argv)

    if a.dates:
        todo = [(src, d) for d in a.dates for src in a.sources if not raw_path(src, d).exists()]
    else:
        todo = plan(a.start, a.end, a.sources, a.retry_404)
    print(f"{len(todo)} files to fetch", flush=True)
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for i, st in enumerate(ex.map(lambda t: fetch_one(*t), todo), 1):
            key = st.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if i % 500 == 0:
                print(f"  {i}/{len(todo)} {counts}", flush=True)
    print(f"done {counts}", flush=True)
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
