"""Dress rehearsal: replay the daily cycle over the last two years of research
data, one session at a time, exactly as the live run would have behaved.

This is a PIPELINE TEST. Its numbers are not evidence of skill and never go on
the scoreboard. It writes only under rehearsal/, never to predictions.csv.

Also fits the baselines' probability calibration on data that ends before the
rehearsal window (python -m nsr.rehearsal --calibrate).
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import champion, config, ensemble, graduation, monitor, notices, predict, report, score
from .build import build
from .models import ALL_MODELS, HORIZONS, ROLES, VERSION
from .panel import Panel

OUT = config.PROJECT / "rehearsal"
WINDOW_YEARS = 2


def window(panel: Panel) -> tuple[int, int]:
    first = pd.Timestamp(config.HOLDOUT_START) - pd.DateOffset(years=WINDOW_YEARS)
    return int(np.searchsorted(panel.dates, first)), len(panel.dates) - 1


def research_notices() -> pd.DataFrame | None:
    """Board-meeting notices parsed from research-window bundles (python -m nsr.research.text)."""
    f = config.CLEAN / "research_text" / "board_meetings.parquet"
    return pd.read_parquet(f) if f.exists() else None


def set_notices(panel: Panel, bm: pd.DataFrame | None, i: int) -> None:
    """Give the panel what the live run would hold on session i: notices from the last 240 days."""
    if bm is not None:
        panel.tables["board_meetings"] = notices.window(bm, panel.dates[i])


def calibrate(panel: Panel, step: int = 5, challengers: bool = False) -> dict:
    """Slope of P(beat the median) on rank, per model and horizon, from sessions that end well
    before the rehearsal window. Baselines are frozen in models/baselines_v1.json, challengers
    in models/challengers_v1.json (ensemble fitted at equal weights)."""
    start, _ = window(panel)
    last = start - max(HORIZONS) - 5
    first = int(np.searchsorted(panel.dates, pd.Timestamp("2012-01-01")))
    names = [m for m in ALL_MODELS if (ROLES[m] == "challenger") == challengers]
    acc = {m: {h: [0.0, 0.0] for h in HORIZONS} for m in names}
    now = datetime.now(config.IST)
    zero = {m: {str(h): 0.0 for h in HORIZONS} for m in ALL_MODELS}
    bm = research_notices() if challengers else None
    for i in range(first, last, step):
        set_notices(panel, bm, i)
        df = predict.make_predictions(panel, i, now, "calibration", "-", zero, only=set(names))
        for model, g in df.groupby("model"):
            cols = panel.col(g.sid.to_numpy())
            x = g.rank_pct.to_numpy() - 0.5
            for h in HORIZONS:
                r = panel.realized(i, h)[cols]
                ok = np.isfinite(r)
                y = (r[ok] > np.median(r[ok])).astype(float) - 0.5
                acc[model][h][0] += float(x[ok] @ y)
                acc[model][h][1] += float(x[ok] @ x[ok])
    slopes = {m: {str(h): (0.0 if m == "random" or not v[1] else round(v[0] / v[1], 4)) for h, v in d.items()}
              for m, d in acc.items()}
    out = {"version": VERSION, "fit_sessions": [str(panel.dates[first].date()), str(panel.dates[last - 1].date())],
           "every_nth_session": step, "note": "p_beat = 0.5 + slope * (rank_pct - 0.5); random is fixed at 0",
           "slopes": slopes}
    path = predict.CHALLENGER_CALIBRATION if challengers else predict.CALIBRATION
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    return out


def replay(panel: Panel, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = window(panel)
    preds_path, scores_path = out / "predictions.csv", out / "scores.csv"
    for p in (preds_path, scores_path):
        p.unlink(missing_ok=True)
    slopes = predict.load_calibration()
    bm, ref = research_notices(), champion.DEFAULT_STATE["reference"]
    frames, done, scored = {}, set(), [pd.DataFrame(columns=score.SCORE_COLUMNS)]
    weight_rows = []
    for i in range(start, end + 1):
        created = datetime.combine(panel.dates[i].date(), time(20, 30), tzinfo=config.IST)
        predict.assert_fresh(panel.dates[i], created)
        set_notices(panel, bm, i)
        # tonight's scoring step comes first, as in the live run: only what has matured by tonight
        if frames:
            recent = pd.concat([frames[j] for j in range(max(start, i - max(HORIZONS) - 2), i)])
            new = score.score_matured(panel, recent, done, upto=i, ref_model=ref)
            score.append_scores(new, scores_path)
            done |= set(zip(new.asof_date, new.model, new.horizon))
            scored.append(new)
        key = panel.dates[i].strftime("%Y-%m-%d")
        w, ev = ensemble.weights_from_scores(pd.concat(scored, ignore_index=True), key)
        weight_rows.append({"asof_date": key, **w})
        df = predict.make_predictions(panel, i, created, f"rehearsal-{panel.dates[i]:%Y%m%d}", "rehearsal", slopes, weights=w)
        predict.append_predictions(df, preds_path)
        frames[i] = df
    pd.DataFrame(weight_rows).to_csv(out / "ensemble_weights.csv", index=False)
    return pd.read_csv(preds_path), pd.read_csv(scores_path)


def check_truncated_rebuild(panel: Panel, preds: pd.DataFrame, n_dates: int) -> list[dict]:
    """Rebuild the whole dataset from raw files as if the world ended on day D,
    predict from that, and compare with what the replay logged for D."""
    start, end = window(panel)
    picks = np.linspace(start + 20, end - 20, n_dates).astype(int)
    results = []
    for i in picks:
        d = panel.dates[i]
        tmp = Path(tempfile.mkdtemp(prefix="nsr_trunc_"))
        try:
            build(end=d.date(), out_dir=tmp)
            small = Panel.load(tmp)
            assert small.dates[-1] == d
            set_notices(small, research_notices(), len(small.dates) - 1)
            w = pd.read_csv(OUT / "ensemble_weights.csv").set_index("asof_date").loc[d.strftime("%Y-%m-%d")].to_dict()
            a = predict.make_predictions(small, len(small.dates) - 1, datetime.now(config.IST), "x", "x", weights=w)
            b = preds[preds.asof_date == d.strftime("%Y-%m-%d")]
            m = a.merge(b, on=["model", "symbol"], how="outer", suffixes=("_trunc", "_replay"), indicator=True)
            for model, mm in m.groupby("model"):
                both = mm[mm._merge == "both"]
                results.append({
                    "date": str(d.date()), "model": model, "rows_truncated_build": int((a.model == model).sum()),
                    "rows_replay": int((b.model == model).sum()), "only_in_one": int((mm._merge != "both").sum()),
                    "max_abs_score_diff": float((both.score_trunc - both.score_replay).abs().max()),
                    "max_abs_rank_diff": float((both.rank_pct_trunc - both.rank_pct_replay).abs().max()),
                })
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return results


def check_poisoned_future(panel: Panel, preds: pd.DataFrame, n_dates: int = 3) -> bool:
    """Overwrite every row after day D with garbage; predictions for D must not move."""
    start, end = window(panel)
    ok = True
    bm, weights = research_notices(), pd.read_csv(OUT / "ensemble_weights.csv").set_index("asof_date")
    for i in np.linspace(start + 5, end - 30, n_dates).astype(int):
        saved = [a[i + 1:].copy() for a in (panel.ret_cc, panel.ret_on, panel.ret_id, panel.traded)]
        try:
            panel.ret_cc[i + 1:], panel.ret_on[i + 1:], panel.ret_id[i + 1:] = 7.0, 7.0, 7.0
            panel.traded[i + 1:] = False
            if bm is not None:                 # the whole notice table, future rows included: the view must cut it
                panel.tables["board_meetings"] = bm[bm.known > panel.dates[i] - pd.Timedelta(days=notices.LOOKBACK_DAYS)]
            a = predict.make_predictions(panel, i, datetime.now(config.IST), "x", "x",
                                         weights=weights.loc[panel.dates[i].strftime("%Y-%m-%d")].to_dict())
        finally:
            for arr, s in zip((panel.ret_cc, panel.ret_on, panel.ret_id, panel.traded), saved):
                arr[i + 1:] = s
        b = preds[preds.asof_date == panel.dates[i].strftime("%Y-%m-%d")]
        m = a.merge(b, on=["model", "symbol"], suffixes=("_a", "_b"))
        ok &= len(m) == len(a) == len(b) and bool(np.allclose(m.score_a, m.score_b, atol=1e-6))
    return ok


def run(n_rebuild_checks: int = 3) -> dict:
    panel = Panel.load()
    assert panel.dates[-1] < pd.Timestamp(config.HOLDOUT_START), "rehearsal must not see the holdout"
    OUT.mkdir(exist_ok=True)
    start, end = window(panel)
    preds, scores = replay(panel, OUT)
    summ = score.summarize(scores)

    sessions = [d.strftime("%Y-%m-%d") for d in panel.dates[start: end + 1]]
    per_day = preds.groupby(["asof_date", "model"]).size().unstack()
    steady = [m for m in per_day.columns if ROLES[m] != "challenger"]
    shadow = [m for m in per_day.columns if ROLES[m] == "challenger"]
    pos = {d: k for k, d in enumerate(sessions)}
    expected_scores = sum(int(pos[d] + 1 + h <= len(sessions) - 1) for d in preds.drop_duplicates(["asof_date", "model"]).asof_date
                          for h in HORIZONS)
    rnd = summ[summ.model == "random"]
    try:
        predict.append_predictions(preds[preds.asof_date == sessions[0]], OUT / "predictions.csv")
        append_guard = False
    except RuntimeError:
        append_guard = True
    rebuild = check_truncated_rebuild(panel, preds, n_rebuild_checks) if n_rebuild_checks else []

    checks = {
        "every session has predictions from the control and every baseline": bool(per_day[steady].reindex(sessions).notna().all().all()),
        "about 500 names ranked per baseline per day": bool(per_day[steady].min().min() >= 450 and per_day.max().max() <= 500),
        "a challenger never ranks fewer than 100 names": bool(not shadow or per_day[shadow].min().min() >= 100),
        "no duplicate (date, model, symbol) rows": not bool(preds.duplicated(["asof_date", "model", "symbol"]).any()),
        "every matured target was scored, none early": len(scores) == expected_scores,
        "scores never used a session after the run date": bool((scores.scored_through <= sessions[-1]).all()),
        "log refuses a second write for the same day": append_guard,
        "predictions unchanged when the future is overwritten": check_poisoned_future(panel, preds),
        "random model shows no skill (|t| < 3 at every horizon)": bool((rnd.ic_t.abs() < 3).all()),
        "random model Brier is 0.25": bool(((rnd.brier - 0.25).abs() < 1e-6).all()),
        "rebuild from raw as of day D reproduces the logged predictions":
            bool(rebuild) and all(r["only_in_one"] == 0 and r["max_abs_score_diff"] < 1e-5 for r in rebuild),
    }
    sims = report.run_sims(panel, preds, start, end)
    cal = score.calibration_table(panel, preds, 5)
    passed = all(checks.values())
    lines = [
        "# Dress rehearsal report", "",
        f"Replayed {len(sessions)} sessions, {sessions[0]} to {sessions[-1]}, through the same predict, log and score",
        "code the live run uses. **This is a pipeline test. Nothing below is evidence of skill**, and none of it",
        "goes on the scoreboard: the baselines are known effects and this window was not held out from their design.", "",
        f"## Result: {'PASS' if passed else 'FAIL'}", "",
        "| check | ok |", "|---|---|", *[f"| {k} | {'yes' if v else '**NO**'} |" for k, v in checks.items()], "",
        "### Rebuild-from-raw comparison", "",
        report._fmt(pd.DataFrame(rebuild)) if rebuild else "_skipped_", "",
        "## Plumbing numbers (not evidence)", "",
        "### Rank IC", "", report.ic_table(scores), "",
        "### Simulated portfolios after costs", "", report.sim_table(sims), "",
        "### Challenger comparison as the scoreboard would show it", "",
        report.challenger_section({**champion.DEFAULT_STATE, "ever_compared": shadow},
                                  champion.compare(scores, {**champion.DEFAULT_STATE, "ever_compared": shadow}, shadow), None),
        "### Decay monitor as the scoreboard would show it", "",
        report.decay_section(monitor.decay_table(scores), {}), "",
        "### Graduation table as the scoreboard would show it if the ensemble held the seat", "",
        graduation.section(panel, preds, scores, {**champion.DEFAULT_STATE, "champion": ensemble.NAME,
                                                  "champion_since": sessions[len(sessions) // 2]},
                           monitor.decay_table(scores), []) if shadow else "_no challengers_", "",
        "### Sessions on which a challenger was silent", "",
        report._fmt(pd.DataFrame([{"model": m, "silent_sessions": int(per_day[m].reindex(sessions).isna().sum())} for m in shadow])) if shadow else "_none_", "",
        "### Calibration at 5 sessions: predicted vs realised chance of beating the median", "",
        report._fmt(cal, dec={"p_mean": 3, "beat_rate": 3}) if len(cal) else "_none_", "",
        "### IC standard deviation, for forward planning", "",
        report._fmt(summ[["model", "horizon", "ic_sd"]], dec={"ic_sd": 4}),
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    return {"passed": passed, "checks": checks, "sessions": len(sessions)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="fit and freeze the baselines' probability slopes")
    ap.add_argument("--calibrate-challengers", action="store_true", help="fit and freeze the challengers' probability slopes")
    ap.add_argument("--rebuild-checks", type=int, default=3)
    a = ap.parse_args()
    if a.calibrate or a.calibrate_challengers:
        print(json.dumps(calibrate(Panel.load(), challengers=a.calibrate_challengers), indent=2))
    else:
        r = run(a.rebuild_checks)
        print(json.dumps(r, indent=2))
        raise SystemExit(0 if r["passed"] else 1)
