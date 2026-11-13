import math
import os
import subprocess
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from nsr import champion, config, ensemble, models, monitor, notices, predict, report, score
from nsr.research import signals

from test_phase1 import make_panel
from test_research import make_rd

NOW = datetime(2021, 1, 1, 20, 30, tzinfo=config.IST)


def notice_table(dates: pd.DatetimeIndex, n_stocks: int = 125) -> pd.DataFrame:
    """Quarterly results meetings for every stock, with the awkward cases mixed in: weekend
    meetings, repeat notices, reschedules, notices filed too early, and non-results meetings."""
    rows = []
    for s in range(n_stocks):
        for q, idx in enumerate(range(70 + s % 17, len(dates) - 3, 63)):
            meeting = dates[idx] - pd.Timedelta(days=2 if s % 11 == 0 and dates[idx].day_of_week == 0 else 0)
            known = meeting - pd.Timedelta(days=5 + s % 20)
            purpose = "Dividend To consider a dividend" if s % 13 == 5 else "Financial Results To consider and approve"
            rows.append((known, f"S{s}", meeting, purpose))
            if s % 7 == 3:                                   # the same meeting printed again later
                rows.append((known + pd.Timedelta(days=2), f"S{s}", meeting, purpose))
            if s % 9 == 4 and q % 2:                         # rescheduled two days later
                rows.append((known + pd.Timedelta(days=3), f"S{s}", meeting + pd.Timedelta(days=2), purpose))
            if s % 10 == 6:                                  # first printed more than 60 days ahead
                rows.append((meeting - pd.Timedelta(days=75), f"S{s}", meeting, purpose))
    return pd.DataFrame(rows, columns=notices.COLUMNS)


# ------------------------------------------------------------------ notices
def test_notice_parser_reads_old_and_new_layout():
    old = "COMPANY NAME    SYMBOL     : BM DATE    : BM PURPOSE \nNTPC Limited    NTPC : 24-OCT-2024 : Financial Results To consider\n"
    new = ("COMPANY NAME    SYMBOL     : BM DATE    : BM PURPOSE\n"
           "Dolat Algotech Limited DOLATALGO : 14-NOV-2026 : Fund Raising With reference to our letter\n\n"
           "Please take the above information on record.\n"
           "Patanjali Foods Limited PATANJALI : 14-NOV-2026 : Financial Results To consider\n")
    assert notices.split_records(old, notices.BM) == [("NTPC", "24-OCT-2024", "Financial Results To consider")]
    recs = notices.split_records(new, notices.BM)
    assert [r[0] for r in recs] == ["DOLATALGO", "PATANJALI"] and recs[0][2].endswith("information on record.")
    bm = notices.frame(notices.bm_records(new, datetime(2026, 11, 12).date()))
    assert list(bm.meeting) == [pd.Timestamp("2026-11-14")] * 2 and list(bm.known) == [pd.Timestamp("2026-11-12")] * 2


def test_notice_window_keeps_240_days_up_to_asof():
    bm = pd.DataFrame({"known": pd.to_datetime(["2020-01-01", "2020-08-01", "2020-12-01"]), "symbol": "A",
                       "meeting": pd.Timestamp("2020-12-10"), "purpose": "x"})
    assert list(notices.window(bm, pd.Timestamp("2020-11-15")).known) == [pd.Timestamp("2020-08-01")]


# ------------------------------------------------------- challenger = backtest
def test_live_results_drift_equals_the_backtested_signal():
    rd = make_rd()
    bm = notice_table(rd.dates)
    rd.tables["board_meetings"] = bm
    S = signals.ear_drift(rd)
    panel = rd.panel
    seen = 0
    for i in range(140, len(rd.dates), 3):
        panel.tables["board_meetings"] = notices.window(bm, rd.dates[i])      # what the live run holds
        live = models.ear_drift_60(panel.view(i))
        assert np.array_equal(np.isfinite(live), np.isfinite(S[i]))
        ok = np.isfinite(live)
        assert np.allclose(live[ok], S[i][ok], atol=1e-9)
        seen += int(ok.sum())
    assert seen > 5000


def test_view_hides_notices_and_universe_from_the_future():
    rd = make_rd()
    panel = rd.panel
    panel.tables["board_meetings"] = notice_table(rd.dates)
    v = panel.view(200)
    assert v.tables["board_meetings"].known.max() <= rd.dates[200]
    assert v.uni.rebalance_date.max() <= rd.dates[200] and v.symbols.index.get_level_values("date").max() <= rd.dates[200]


# ----------------------------------------------------------------- prediction
def test_challengers_join_the_log_without_touching_baselines(tmp_path, monkeypatch):
    rd = make_rd()
    panel = rd.panel
    panel.tables["board_meetings"] = notice_table(rd.dates)
    i = 300
    df = predict.make_predictions(panel, i, NOW, "r", "c")
    n = df.groupby("model").size()
    assert set(n.index) == set(models.ALL_MODELS) and n["ear_drift_60"] >= models.MIN_NAMES
    assert df[df.model == "ear_drift_60"].model_version.eq("v1").all()
    # a model can be added to a day the baselines already logged, but nothing can be written twice
    path = tmp_path / "predictions.csv"
    base = {"random", "mom_12_1", "rev_5"}
    predict.append_predictions(predict.make_predictions(panel, i, NOW, "r", "c", only=base), path)
    predict.append_predictions(predict.make_predictions(panel, i, NOW, "r2", "c", only=set(models.ALL_MODELS) - base), path)
    with pytest.raises(RuntimeError, match="append-only"):
        predict.append_predictions(df[df.model == "ear_drift_60"], path)
    back = pd.read_csv(path)
    pd.testing.assert_frame_equal(back[back.model.isin(base)].reset_index(drop=True)[["model", "symbol", "score"]],
                                  df[df.model.isin(base)].reset_index(drop=True)[["model", "symbol", "score"]])
    # a challenger that breaks is left out with a note; a baseline that breaks stops the run
    monkeypatch.setitem(models.MODELS, "ear_drift_60", lambda v: 1 / 0)
    notes = []
    d2 = predict.make_predictions(panel, i, NOW, "r", "c", notes=notes)
    assert set(d2.model) == base and any("ear_drift_60 failed" in x for x in notes) and any("skipped" in x for x in notes)
    monkeypatch.setitem(models.MODELS, "mom_12_1", lambda v: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        predict.make_predictions(panel, i, NOW, "r", "c")


def test_challenger_with_too_few_names_stays_silent():
    rd = make_rd()
    notes = []
    df = predict.make_predictions(rd.panel, 300, NOW, "r", "c", notes=notes)       # no notices at all
    assert "ear_drift_60" not in set(df.model) and any("ear_drift_60 silent" in x for x in notes)
    assert ensemble.NAME in set(df.model)            # momentum alone still gives the ensemble a view


def test_at_most_three_challengers_and_every_model_has_a_role():
    assert sum(r == "challenger" for r in models.ROLES.values()) <= models.MAX_CHALLENGERS == 3
    assert set(models.ROLES) == set(models.ALL_MODELS) == set(models.VERSIONS)


def test_void_rows_stay_in_the_log_but_are_not_counted(tmp_path):
    preds = pd.DataFrame({"asof_date": ["2026-11-12"] * 3, "model": ["a", "b", "b"], "symbol": list("xyz")})
    void = tmp_path / "void.csv"
    void.write_text("asof_date,model,reason\n2026-11-12,b,written by code that was not deployed\n")
    assert list(predict.drop_void(preds, void).model) == ["a"] and len(preds) == 3
    assert len(predict.drop_void(preds, tmp_path / "missing.csv")) == 3


# ------------------------------------------------------------------- ensemble
def test_ensemble_weights_start_equal_and_move_slowly_on_evidence():
    assert ensemble.weights({}, {}) == {"mom_12_1": 0.5, "ear_drift_60": 0.5}
    w = ensemble.weights({"mom_12_1": 250 * 0.05, "ear_drift_60": 0.0}, {"mom_12_1": 250, "ear_drift_60": 250})
    assert w["mom_12_1"] == pytest.approx((10 + 12.5) / (10 + 12.5 + 10)) and sum(w.values()) == pytest.approx(1)
    lost = ensemble.weights({"mom_12_1": -50.0, "ear_drift_60": -50.0}, {"mom_12_1": 900, "ear_drift_60": 900})
    assert lost == {"mom_12_1": 0.5, "ear_drift_60": 0.5}                   # nothing positive left: back to equal


def test_ensemble_weights_use_only_scores_matured_by_the_prediction_day():
    s = pd.DataFrame({"model": ["mom_12_1", "mom_12_1", "ear_drift_60", "mom_12_1"], "horizon": [20, 20, 20, 5],
                      "ic": [0.5, 0.9, 0.1, 0.99], "scored_through": ["2027-01-10", "2027-02-10", "2027-01-10", "2027-01-05"]})
    w, ev = ensemble.weights_from_scores(s, "2027-01-15")
    assert ev == {"mom_12_1": {"ic_sum": 0.5, "ic_n": 1}, "ear_drift_60": {"ic_sum": 0.1, "ic_n": 1}}
    assert w["mom_12_1"] > w["ear_drift_60"]
    assert ensemble.weights_from_scores(s.iloc[0:0], "2027-01-15")[0] == {"mom_12_1": 0.5, "ear_drift_60": 0.5}


def test_ensemble_treats_a_missing_view_as_neutral():
    a = np.array([0.9, 0.1, np.nan, np.nan])
    b = np.array([0.2, np.nan, 0.8, np.nan])
    out = ensemble.combine({"mom_12_1": a, "ear_drift_60": b}, {"mom_12_1": 0.5, "ear_drift_60": 0.5})
    assert out[:3] == pytest.approx([0.55, 0.30, 0.65]) and np.isnan(out[3])
    few = ensemble.rank_pct(np.arange(50.0), np.ones(50, bool))
    assert np.isnan(few).all()                                           # under 100 names: absent that day
    pct = ensemble.rank_pct(np.arange(200.0), np.arange(200) < 150)
    assert pct[0] == pytest.approx(0.5 / 150) and np.isnan(pct[150:]).all()


def test_backtest_ensemble_matches_fixed_weights_before_any_ic_matures():
    rd = make_rd()
    rd.tables["board_meetings"] = notice_table(rd.dates)
    shifting, fixed = signals.combo(rd), signals.combo(rd, shifting=False)
    first = 21                                      # no 20-session target has closed before session 21
    assert np.allclose(shifting[:first + 1], fixed[:first + 1], equal_nan=True)
    cut = signals.combo(rd.truncated(330))
    assert np.allclose(cut[-1], shifting[330], equal_nan=True)            # no look-ahead in the weights


# --------------------------------------------------------------------- scoring
def test_ic_beyond_reference_isolates_what_the_challenger_adds():
    rng = np.random.default_rng(0)
    ref, own = rng.normal(size=400), rng.normal(size=400)
    r = 0.5 * ref + 0.5 * own + rng.normal(size=400)
    rk = lambda a: pd.Series(a).rank().to_numpy() / len(a)
    assert score.ic_excluding(rk(own), rk(ref), r) > 0.25
    assert abs(score.ic_excluding(rk(ref + 0.05 * rng.normal(size=400)), rk(ref), rng.normal(size=400) + 0.0 * ref)) < 0.15
    assert math.isnan(score.ic_excluding(rk(ref), rk(ref), r))           # the reference adds nothing to itself
    assert math.isnan(score.ic_excluding(rk(own)[:10], rk(ref)[:10], r[:10]))


def test_scores_record_the_reference_and_leave_it_blank_for_the_reference_itself():
    drift = np.linspace(-0.004, 0.004, 40)
    panel, _, _ = make_panel(drift=drift)
    preds = pd.concat([predict.make_predictions(panel, i, NOW, "r", "c") for i in range(260, 290)])
    s = score.score_matured(panel, preds, set(), ref_model="mom_12_1")
    assert list(s.columns) == score.SCORE_COLUMNS and s.ref_model.eq("mom_12_1").all()
    assert s[s.model == "mom_12_1"].ic_ex_ref.isna().all() and s[s.model == "rev_5"].ic_ex_ref.notna().all()


# -------------------------------------------------------------------- champion
def fake_scores(n_days, ic=0.05, beyond=0.03, ref_ic=0.02, sd=0.05, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2027-01-01", periods=n_days).strftime("%Y-%m-%d")
    rows = []
    for d in days:
        for h in (1, 5, 20):
            rows.append({"asof_date": d, "model": "ear_drift_60", "horizon": h, "ic": rng.normal(ic, sd),
                         "ic_ex_ref": rng.normal(beyond, sd), "top_excess": 0.004})
            rows.append({"asof_date": d, "model": "mom_12_1", "horizon": h, "ic": rng.normal(ref_ic, sd),
                         "ic_ex_ref": np.nan, "top_excess": 0.002})
            rows.append({"asof_date": d, "model": "random", "horizon": h, "ic": rng.normal(0, 0.045),
                         "ic_ex_ref": rng.normal(0, 0.045), "top_excess": 0.0})
    return pd.DataFrame(rows)


def test_required_t_rises_with_every_challenger_ever_started():
    t = [champion.threshold(n) for n in (1, 2, 3, 10)]
    assert t[0] == pytest.approx(1.96, abs=0.001) and t == sorted(t) and t[3] > 2.8
    assert [champion.checkpoint(n) for n in (0, 249, 250, 374, 375, 499, 500)] == [0, 0, 250, 250, 375, 375, 500]


def test_comparison_waits_for_the_minimum_period_and_reads_only_checkpoints():
    state = {**champion.DEFAULT_STATE, "ever_compared": ["ear_drift_60"]}
    early = champion.compare(fake_scores(120, ic=0.2, beyond=0.2), state, ["ear_drift_60"]).iloc[0]
    assert early.status.startswith("too early: 120 of 250")
    strong = champion.compare(fake_scores(300, ic=0.08, beyond=0.06), state, ["ear_drift_60"]).iloc[0]
    assert strong.judged_on == 250 and strong.scored_sessions == 300 and strong.status.startswith("ELIGIBLE")
    weak = champion.compare(fake_scores(300, ic=0.01, beyond=0.002), state, ["ear_drift_60"]).iloc[0]
    assert weak.status == "not met at 250; next checkpoint at 375"
    dead = champion.compare(fake_scores(520, ic=0.0, beyond=-0.01), state, ["ear_drift_60"]).iloc[0]
    assert dead.status.startswith("futile")
    crowded = {**state, "ever_compared": [f"c{k}" for k in range(40)]}
    assert champion.compare(fake_scores(300, ic=0.03, beyond=0.03, seed=3), crowded, ["ear_drift_60"]).iloc[0].required_t > 3


def test_comparison_and_scoreboard_work_before_any_score_exists(tmp_path):
    empty = pd.DataFrame(columns=score.SCORE_COLUMNS)                    # the state on the first days of shadow
    state = {**champion.DEFAULT_STATE, "ever_compared": ["ear_drift_60"]}
    cmp_ = champion.compare(empty, state, ["ear_drift_60", ensemble.NAME])
    assert list(cmp_.status) == ["too early: 0 of 250 sessions"] * 2
    decay = monitor.decay_table(empty, {"ear_drift_60": {"1": {"ic": 0.0145, "sd": 0.064}}})
    assert decay.state.tolist() == ["ok"] and monitor.retire_flags(empty, decay) == {"ear_drift_60": False}
    out = tmp_path / "scoreboard.md"
    report.write_scoreboard(out, empty, pd.DataFrame(), 1, "now", state=state, comparison=cmp_, decay=decay,
                            retire={}, weights={"mom_12_1": 0.5, "ear_drift_60": 0.5})
    text = out.read_text()
    assert "Champion: **none (seat empty)**" in text and "Decay monitor" in text and "too early" in text


def test_frozen_when_the_random_control_shows_skill():
    s = fake_scores(300, ic=0.08, beyond=0.06)
    s.loc[s.model == "random", "ic"] += 0.05
    state = {**champion.DEFAULT_STATE, "ever_compared": ["ear_drift_60"]}
    assert champion.compare(s, state, ["ear_drift_60"]).iloc[0].status.startswith("frozen")


# --------------------------------------------------------------------- monitor
def test_cusum_threshold_gives_the_target_false_alarm_rate():
    k = 0.05
    thr = monitor.cusum_threshold(k, 5000)
    assert monitor._arl(k, thr + 1.166, -1.0) == pytest.approx(5000, rel=1e-3)
    assert monitor._arl(k, thr + 1.166, 1.0) < 600                       # a dead signal is caught far sooner


def test_cusum_flags_a_signal_that_died_and_dates_the_change():
    rng = np.random.default_rng(5)
    alive = rng.normal(0.02, 0.06, 2000)
    assert monitor.cusum(alive, 0.02, 0.06, 5000)["alarm"] is None
    died = np.concatenate([alive[:600], rng.normal(0.0, 0.06, 1400)])
    c = monitor.cusum(died, 0.02, 0.06, 5000)
    assert c["alarm"] is not None and c["alarm"] > 600 and 450 <= c["change"] <= 900


def test_retirement_needs_an_alarm_and_a_year_of_non_positive_ic():
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2027-01-01", periods=1500).strftime("%Y-%m-%d")
    ic = np.concatenate([rng.normal(0.02, 0.06, 300), rng.normal(-0.03, 0.06, 1200)])
    s = pd.concat([pd.DataFrame({"asof_date": days, "model": "ear_drift_60", "horizon": h, "ic": ic}) for h in (1, 20)])
    exp = {"ear_drift_60": {"1": {"ic": 0.04, "sd": 0.06}, "20": {"ic": 0.04, "sd": 0.06}}}
    table = monitor.decay_table(s, exp)
    assert table.state.str.startswith("DECAYING").any() and monitor.retire_flags(s, table) == {"ear_drift_60": True}
    healthy = s.assign(ic=rng.normal(0.02, 0.06, len(s)))
    t2 = monitor.decay_table(healthy, exp)
    assert monitor.retire_flags(healthy, t2) == {"ear_drift_60": False}


# ----------------------------------------------------------------- deployment
def test_records_folder_can_differ_from_the_code_folder(tmp_path):
    env = {**os.environ, "NSR_PROJECT": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", "from nsr import config, predict; print(config.PROJECT); "
                          "print(config.CODE); print(predict.CALIBRATION); print(config.PREDICTIONS)"],
                         capture_output=True, text=True, env=env).stdout.split()
    assert out[0] == str(tmp_path) and out[1] == str(config.CODE)
    assert out[2].startswith(str(config.CODE)) and out[3].startswith(str(tmp_path))
