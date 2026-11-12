"""The daily cycle. Run by launchd each evening; safe to run more than once.

  1. download any new NSE files, the corporate-actions register, symbol changes
  2. rebuild the production panel (outside the project: it spans the holdout window)
  3. score predictions whose outcome window has completed -> scores.csv, scoreboard.md
  4. predict for the latest session, if it has not been predicted and it is not too late
  5. commit and push; write one line to run_log.md

Never backfills: a session whose next open may already have happened is logged
as MISSED and skipped for good.

This is the only entry point that sets NSR_PRODUCTION, i.e. the only code
allowed to read holdout-window data, and it does so only to compute features.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import traceback
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from . import api, config, predict, report, score
from .build import build
from .download import HEADERS, daterange, fetch_one, load_manifest, manifest_path, raw_path
from .panel import Panel

RUN_LOG = config.PROJECT / "run_log.md"
SCOREBOARD = config.PROJECT / "scoreboard.md"
TRACKED = ["predictions.csv", "scores.csv", "scoreboard.md", "run_log.md", "data/raw/manifest.csv"]
ALERT_AFTER = 3
ALERT_LINE = "> **ALERT: the last {n} runs failed. Check the notes column below.**"
FORWARD_START = config.HOLDOUT_END + timedelta(days=1)


# ------------------------------------------------------------------ helpers

def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=config.PROJECT, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def log_run(now: datetime, outcome: str, data_date: str, n_pred: int, notes: str) -> None:
    line = f"| {now:%Y-%m-%d %H:%M} | {outcome} | {data_date} | {n_pred} | {notes.replace('|', '/')} |\n"
    text = RUN_LOG.read_text()
    text = "\n".join(l for l in text.splitlines() if not l.startswith("> **ALERT")) + "\n" + line
    outcomes = [l.split("|")[2].strip() for l in text.splitlines() if l.startswith("| 20")]
    streak = 0
    for o in reversed(outcomes):
        if o != "FAIL":
            break
        streak += 1
    if streak >= ALERT_AFTER:
        head, _, rest = text.partition("\n")
        text = head + "\n\n" + ALERT_LINE.format(n=streak) + "\n" + rest
        subprocess.run(["osascript", "-e", f'display notification "{streak} daily runs failed in a row" '
                        'with title "nse-research"'], capture_output=True)
    RUN_LOG.write_text(text)


def download_new(today: date) -> list[str]:
    """Fetch forward-period files that are missing. Recent 404s are retried,
    because 'not published yet' looks the same as 'holiday'."""
    notes = []
    for d in daterange(FORWARD_START, today):
        seen = load_manifest(manifest_path(d))
        for src in ("pr", "mto"):
            if raw_path(src, d).exists():
                continue
            prev = seen.get((d.isoformat(), src))
            if prev and prev["status"] == "404" and (today - d).days > 4:
                continue
            st = fetch_one(src, d)
            if st.startswith("error"):
                notes.append(f"{src} {d}: {st}")
    return notes


def refresh_reference(today: date) -> list[str]:
    notes = []
    try:
        ref = config.PROD_DIR / "reference"
        ref.mkdir(parents=True, exist_ok=True)
        r = requests.get("https://nsearchives.nseindia.com/content/equities/symbolchange.csv", headers=HEADERS, timeout=40)
        if r.status_code == 200 and b"SYMBOL" in r.content[:200].upper():
            (ref / "symbolchange.csv").write_bytes(r.content)
        else:
            notes.append(f"symbolchange http{r.status_code}")
    except requests.RequestException as e:
        notes.append(f"symbolchange {type(e).__name__}")
    try:
        api.refresh_production_register(today)
    except Exception as e:  # the build still works from the daily Bc file; say so and carry on
        notes.append(f"register refresh failed ({type(e).__name__}); using previous copy")
    return notes


def forward_scoreboard(panel: Panel, preds: pd.DataFrame, now: datetime) -> None:
    scores = pd.read_csv(config.SCORES) if config.SCORES.exists() and config.SCORES.stat().st_size else pd.DataFrame(columns=score.SCORE_COLUMNS)
    sims = pd.DataFrame()
    if len(preds):
        first = panel.dates.get_indexer([pd.Timestamp(preds.asof_date.min())])[0]
        if first >= 0:
            sims = report.run_sims(panel, preds, int(first), len(panel.dates) - 1)
    report.write_scoreboard(SCOREBOARD, scores, sims, preds.asof_date.nunique() if len(preds) else 0, f"{now:%Y-%m-%d %H:%M} IST")


# --------------------------------------------------------------------- cycle

def cycle(now: datetime, dry_run: bool = False) -> tuple[str, str, int, str]:
    today, notes = now.date(), []
    notes += download_new(today)
    notes += refresh_reference(today)
    rep = build(end=today)
    if rep["days_unusable_misfiled_or_empty"][-3:]:
        recent = [d for d in rep["days_unusable_misfiled_or_empty"] if d >= FORWARD_START.isoformat()]
        if recent:
            notes.append(f"unusable files: {recent}")
    panel = Panel.load()
    latest = panel.dates[-1]

    preds = pd.read_csv(config.PREDICTIONS)
    new_scores = score.score_matured(panel, preds, score.done_keys(config.SCORES))
    if not dry_run:
        score.append_scores(new_scores, config.SCORES)
    if len(new_scores):
        notes.append(f"scored {len(new_scores)} date-model-horizon results")

    # sessions in the forward period that never got a prediction are gone for good
    logged = set(preds.asof_date)
    missed = [d.strftime("%Y-%m-%d") for d in panel.dates[panel.dates > pd.Timestamp(config.HOLDOUT_END)][:-1]
              if d.strftime("%Y-%m-%d") not in logged]
    known = RUN_LOG.read_text()
    for d in missed:
        if f"MISSED | {d}" not in known and not dry_run:
            log_run(now, "MISSED", d, 0, "no prediction was made in time; not backfilled")

    outcome, n = "OK", 0
    key = latest.strftime("%Y-%m-%d")
    if latest <= pd.Timestamp(config.HOLDOUT_END):
        outcome = "NO_NEW_SESSION"
        notes.append("no forward-period session published yet")
    elif key in logged:
        outcome = "ALREADY_DONE"
    else:
        try:
            predict.assert_fresh(latest, now)
            df = predict.make_predictions(panel, len(panel.dates) - 1, now, f"{now:%Y%m%dT%H%M}", git("rev-parse", "--short", "HEAD"))
            n = len(df)
            if not dry_run:
                predict.append_predictions(df, config.PREDICTIONS)
                preds = pd.concat([preds, df], ignore_index=True)
            else:
                notes.append("dry run: predictions computed but not written")
        except predict.StalePrediction as e:
            outcome = "STALE_SKIPPED"
            notes.append(str(e))
    if not dry_run:
        forward_scoreboard(panel, preds, now)
    return outcome, key, n, "; ".join(notes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="do everything except write predictions, scores or commits")
    a = ap.parse_args(argv)
    os.environ[config.PRODUCTION_ENV] = "1"
    config.PROD_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(config.PROD_DIR / "daily.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0  # another run is in progress
    now = datetime.now(config.IST)
    try:
        outcome, data_date, n, notes = cycle(now, a.dry_run)
        code = 0
    except Exception as e:
        outcome, data_date, n = "FAIL", "-", 0
        notes = f"{type(e).__name__}: {str(e)[:200]}"
        (config.PROD_DIR / "last_error.txt").write_text(traceback.format_exc())
        code = 1
    if a.dry_run:
        print(f"DRY RUN -> {outcome} | data date {data_date} | {n} predictions | {notes}")
        return code
    log_run(now, outcome, data_date, n, notes)
    try:
        git("add", *[f for f in TRACKED if (config.PROJECT / f).exists()])
        if git("status", "--porcelain", "--", *TRACKED):
            git("commit", "-q", "-m", f"daily run {now:%Y-%m-%d %H:%M} IST: {outcome}, data {data_date}, {n} predictions")
        git("push", "-q")
    except RuntimeError as e:
        (config.PROD_DIR / "last_error.txt").write_text(str(e))
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
