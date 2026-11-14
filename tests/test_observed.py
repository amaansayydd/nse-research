"""Observation tier (Phase 3 rules v1.1): the event model, its log, scoring and the checkpoint rule."""
from datetime import datetime, time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nsr import champion, config, daily, models, notices, observed, predict, score
from nsr.panel import Panel
from nsr.research import signals, stats
from nsr.research.data import ResearchData


def make_px(T=420, N=130, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2011-06-01", periods=T)
    rows = []
    for s in range(N):
        r, o = rng.normal(0, 0.02, T), rng.normal(0, 0.005, T)
        rows.append(pd.DataFrame({"date": dates, "sid": s, "symbol": f"S{s}", "ret_cc": r, "ret_on": o,
                                  "ret_id": (1 + r) / (1 + o) - 1, "band_hit": None, "locked_limit": False}))
    px = pd.concat(rows, ignore_index=True)
    rb = [d for d in dates[dates.is_month_end | (dates == dates[0])]]
    uni = pd.DataFrame([{"rebalance_date": d, "sid": s, "symbol": f"S{s}", "rank": s + 1, "median_value": 1.0}
                        for d in rb for s in range(N - 10)])
    return dates, px, uni


def notice_table(dates, rows):
    return pd.DataFrame([{"known": dates[k], "symbol": s, "meeting": pd.Timestamp(m), "purpose": "Financial Results"}
                         for s, k, m in rows])


@pytest.fixture
def world():
    dates, px, uni = make_px()
    k1, k2 = dates.get_loc(pd.Timestamp("2011-07-20")), dates.get_loc(pd.Timestamp("2012-07-05"))
    last = [(f"S{j}", k1, "2011-08-10") for j in range(1, 8)]
    now = [(f"S{j}", k2, "2012-08-10") for j in range(3, 8)] + [("S1", k2, "2012-07-31"), ("S2", k2, "2012-07-25")]
    bm = notice_table(dates, last + now)
    panel = Panel.from_frames(px, uni)
    panel.tables[observed.NOTICE_TABLE] = bm
    return panel, bm, px, k2


def test_live_event_list_equals_the_research_definition(world, monkeypatch):
    panel, bm, px, k2 = world
    monkeypatch.setattr(observed, "MIN_PEERS", 5)
    rd = ResearchData.from_panel(panel, px, {"board_meetings": bm})
    want = signals.results_date_shift(rd, min_peers=5)
    assert len(want) == 2 and set(want.i) == {k2}
    for i in (k2 - 1, k2, k2 + 1):
        got = observed.results_advance(panel.view(i))
        w = want[want.i == i].sort_values("col")
        assert got.col.tolist() == w.col.tolist()
        assert np.allclose(got.score, -w.abnormal)
    assert observed.results_advance(panel.view(k2)).score.tolist() == [10.0, 16.0]     # days early, S1 and S2


def test_event_model_needs_peers_base_year_and_a_long_enough_window(world, monkeypatch):
    panel, bm, px, k2 = world
    assert observed.results_advance(panel.view(k2)).empty                     # 7 peers known, 30 needed
    monkeypatch.setattr(observed, "MIN_PEERS", 5)
    panel.tables[observed.NOTICE_TABLE] = notices.window(bm, panel.dates[k2], 240)
    assert observed.results_advance(panel.view(k2)).empty                     # last year's notices fell out of 240 days
    panel.tables[observed.NOTICE_TABLE] = notices.window(bm, panel.dates[k2], observed.NOTICE_DAYS)
    assert len(observed.results_advance(panel.view(k2))) == 2
    panel.tables.pop(observed.NOTICE_TABLE)
    assert observed.results_advance(panel.view(k2)).empty                     # no table: silent, not an error


def test_step_logs_every_evaluation_once_and_never_twice(world, monkeypatch, tmp_path):
    panel, bm, px, k2 = world
    monkeypatch.setattr(observed, "MIN_PEERS", 5)
    preds, runs = tmp_path / "predictions.csv", tmp_path / "observed_runs.csv"
    state = {"ever_observed": [observed.NAME], "dropped": []}
    small = Panel.from_frames(px[px.date <= panel.dates[k2]], panel.uni)
    small.tables[observed.NOTICE_TABLE] = bm
    now = datetime.combine(small.dates[-1].date(), time(20, 30), tzinfo=config.IST)
    notes = []
    assert observed.step(small, now, "r1", "abc", notes, predictions=preds, runs=runs, state=state) == 2
    assert observed.step(small, now, "r2", "abc", notes, predictions=preds, runs=runs, state=state) == 0
    p, r = pd.read_csv(preds), pd.read_csv(runs)
    assert list(p.columns) == predict.COLUMNS and list(p.symbol) == ["S1", "S2"] and (p.model == observed.NAME).all()
    assert list(p.score) == [10.0, 16.0] and (p.rank_pct == 1.0).all()
    assert len(r) == 1 and r.flagged[0] == 2 and r.run_id[0] == "r1"
    # a quiet evening is still an evaluated session
    quiet = Panel.from_frames(px[px.date <= panel.dates[k2 + 1]], panel.uni)
    quiet.tables[observed.NOTICE_TABLE] = bm
    later = datetime.combine(quiet.dates[-1].date(), time(20, 30), tzinfo=config.IST)
    assert observed.step(quiet, later, "r3", "abc", notes, predictions=preds, runs=runs, state=state) == 0
    assert list(pd.read_csv(runs).flagged) == [2, 0] and len(pd.read_csv(preds)) == 2
    # too late for that session: nothing is written, nothing is backfilled
    stale = datetime.combine(quiet.dates[-1].date() + pd.Timedelta(days=1), time(9, 30), tzinfo=config.IST)
    (tmp_path / "x.csv").write_text("")
    assert observed.step(quiet, stale, "r4", "abc", notes, predictions=preds, runs=tmp_path / "x.csv", state=state) == 0
    assert (tmp_path / "x.csv").read_text() == ""
    # dropped signals are not evaluated; a dry run writes nothing
    assert observed.step(small, now, "r5", "abc", notes, predictions=preds, runs=tmp_path / "y.csv",
                         state={"ever_observed": [observed.NAME], "dropped": [observed.NAME]}) == 0
    assert not (tmp_path / "y.csv").exists()
    dry = []
    assert observed.step(small, now, "r6", "abc", dry, dry_run=True, predictions=preds, runs=tmp_path / "y.csv", state=state) == 0
    assert dry == [f"observed {observed.NAME}: would flag 2 names"] and not (tmp_path / "y.csv").exists()


def test_a_broken_observed_signal_is_noted_and_swallowed(world, monkeypatch, tmp_path):
    panel, *_ = world

    def boom(v):
        raise ValueError("bad notice file")
    monkeypatch.setitem(observed.SIGNALS[observed.NAME], "fn", boom)
    notes = []
    now = datetime.combine(panel.dates[-1].date(), time(20, 30), tzinfo=config.IST)
    assert observed.step(panel, now, "r", "abc", notes, predictions=tmp_path / "p.csv", runs=tmp_path / "r.csv",
                         state={"ever_observed": [observed.NAME], "dropped": []}) == 0
    assert "failed (ValueError" in notes[0] and not (tmp_path / "r.csv").exists()


def test_event_scores_match_the_research_event_returns(world, monkeypatch):
    panel, bm, px, k2 = world
    monkeypatch.setattr(observed, "MIN_PEERS", 5)
    rd = ResearchData.from_panel(panel, px, {"board_meetings": bm})
    from nsr.research import evaluate
    flags = observed.results_advance(panel.view(k2))
    now = datetime.combine(panel.dates[k2].date(), time(20, 30), tzinfo=config.IST)
    rows = observed.event_rows(panel, k2, observed.NAME, flags, now, "r", "abc", {observed.NAME: {"5": 0.52}})
    assert (rows.p_beat_5d == 0.52).all() and (rows.p_beat_1d == 0.5).all()
    dense = predict.make_predictions(panel, k2, now, "r", "abc", only={"mom_12_1"})
    s = observed.score_events(panel, pd.concat([rows, dense], ignore_index=True), set())
    assert sorted(s.horizon.unique()) == [1, 5, 20] and len(s) == 6
    ev = signals.results_date_shift(rd, min_peers=5)
    for h in (1, 5, 20):
        want = evaluate.event_returns(rd, ev, h).excess.to_numpy()
        late = evaluate.event_returns(rd, ev, h, delay=1).excess.to_numpy()
        got = s[s.horizon == h].sort_values("symbol")
        assert np.allclose(got.excess, want) and np.allclose(got.excess_late, late)
    five = s[s.horizon == 5]
    assert (five.scored_through == panel.dates[k2 + 7].strftime("%Y-%m-%d")).all()       # t+2+h
    assert list(five.uni_rank) == [2.0, 3.0] and five.mom_tenth_ret.notna().all()
    # nothing is scored before session t+2+h exists, and nothing twice
    assert observed.score_events(panel, rows, set(), upto=k2 + 6).query("horizon == 5").empty
    assert observed.score_events(panel, rows, {(rows.asof_date[0], observed.NAME, h) for h in (1, 5, 20)}).empty
    # the dense scorer never sees these rows in the daily run; alone they are too few for it anyway
    assert score.score_matured(panel, rows, set()).empty


def test_cluster_t_is_the_research_formula():
    rng = np.random.default_rng(1)
    x, m = rng.normal(0.01, 0.06, 400), rng.integers(0, 24, 400)
    a, b = observed.cluster_t(x, m), stats.cluster_t(x, m)
    assert a["n"] == b["n"] and a["t"] == pytest.approx(b["t"]) and a["mean"] == pytest.approx(b["mean"])


def _history(n_sessions, events_per_session, mean, sd=0.06, seed=0, late_gap=0.002):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-11-16", periods=n_sessions).strftime("%Y-%m-%d")
    runs = pd.DataFrame({"asof_date": dates, "model": observed.NAME})
    rows = []
    for d in dates:
        for k in range(events_per_session):
            x = rng.normal(mean, sd)
            rows.append({"asof_date": d, "model": observed.NAME, "symbol": f"S{k}", "horizon": 5, "ret": x + 0.001,
                         "universe_ret": 0.001, "excess": x, "excess_late": x - late_gap, "mom_tenth_ret": 0.002,
                         "uni_rank": 50 + 200 * k})
    ctl = pd.DataFrame({"asof_date": np.repeat(dates, 3), "model": "random", "horizon": np.tile([1, 5, 20], n_sessions),
                        "ic": np.where(np.arange(3 * n_sessions) // 3 % 2 == 0, 0.05, -0.05)})   # a control with no skill
    return pd.DataFrame(rows), runs, ctl, dates


def test_status_follows_the_frozen_rule():
    ev, runs, ctl, dates = _history(300, 1, 0.012)
    early = observed.status(observed.NAME, ev, runs, ctl, 1, dates[119])
    assert early["status"] == "too early: 120 of 250 sessions, 120 of 200 events" and early["sessions"] == 120
    ok = observed.status(observed.NAME, ev, runs, ctl, 1, dates[-1])
    assert ok["judged_on_sessions"] == 250 and ok["events"] == 250 and ok["required_t"] == pytest.approx(1.96, abs=0.001)
    assert ok["t"] >= 1.96 and ok["status"].startswith("CONFIRMED FORWARD")
    assert ok["after_costs"] == pytest.approx(ok["mean_excess"] - observed.COST)
    assert ok["mean_minus_momentum_tenth"] == pytest.approx(ok["mean_excess"] - 0.001)
    # a higher M raises the bar for the same record
    assert observed.status(observed.NAME, ev, runs, ctl, 10, dates[-1])["required_t"] == pytest.approx(2.807, abs=0.001)
    # the same record with too few events is not confirmed, whatever its t
    thin = ev[ev.asof_date.isin(dates[::2])]
    s = observed.status(observed.NAME, thin, runs, ctl, 1, dates[-1])
    assert s["events"] == 125 and s["status"] == "not met at 250: 125 of 200 events; next checkpoint at 375"
    # clears zero but not costs: not confirmed
    weak, r2, c2, d2 = _history(300, 1, 0.004, sd=0.01)
    s = observed.status(observed.NAME, weak, r2, c2, 1, d2[-1])
    assert s["t"] > 1.96 and s["after_costs"] < 0 and s["status"] == "not met at 250; next checkpoint at 375"
    # clears costs at once but not a session later: not confirmed
    slip, r3, c3, d3 = _history(300, 1, 0.006, sd=0.01, late_gap=0.003)
    s = observed.status(observed.NAME, slip, r3, c3, 1, d3[-1])
    assert s["after_costs"] > 0 and s["after_costs_one_session_later"] < 0 and s["status"].startswith("not met")
    # futility from 500 sessions; a frozen scorer beats everything
    dead, r4, c4, d4 = _history(520, 1, -0.002)
    assert observed.status(observed.NAME, dead, r4, c4, 1, d4[-1])["status"].startswith("futile")
    c4 = c4.assign(ic=c4.ic * 0.1 + 0.05)             # a control that scores: the scorer leaks
    assert observed.status(observed.NAME, dead, r4, c4, 1, d4[-1])["status"].startswith("frozen")


def test_status_reads_only_events_up_to_the_checkpoint():
    ev, runs, ctl, dates = _history(300, 1, 0.012)
    poisoned = ev.copy()
    poisoned.loc[poisoned.asof_date > dates[249], "excess"] = -0.5
    a, b = (observed.status(observed.NAME, e, runs, ctl, 1, dates[-1]) for e in (ev, poisoned))
    assert a["mean_excess"] == b["mean_excess"] and a["status"] == b["status"]


def test_the_observed_tier_changes_nothing_for_challengers():
    assert observed.NAME not in models.ALL_MODELS and observed.NAME not in models.ROLES
    assert sum(r == "challenger" for r in models.ROLES.values()) == 2
    assert len(observed.SIGNALS) <= observed.MAX_OBSERVED
    assert observed.load_state(Path("/nonexistent/observed.json")) == {"ever_observed": [], "dropped": []}
    if champion.STATE.exists() and observed.STATE.exists():       # the project's own state (absent in a release copy)
        assert champion.threshold(len(champion.load_state()["ever_compared"])) == pytest.approx(2.2414, abs=1e-3)
        st = observed.load_state()
        assert st["ever_observed"] == [observed.NAME] and st["dropped"] == []
    assert set(daily.TRACKED) >= {"observed_runs.csv", "event_scores.csv", "predictions.csv"}
    cal = observed.load_calibration()[observed.NAME]
    assert set(cal) == {"1", "5", "20"} and all(0.3 < v < 0.7 for v in cal.values())


def test_short_notice_window_is_cut_from_the_long_one_unchanged():
    dates = pd.bdate_range("2024-01-01", periods=400)
    bm = notice_table(dates, [("S1", k, "2030-01-01") for k in range(0, 400, 3)])
    asof = dates[-1]
    short = notices.window(bm, asof)
    long = notices.window(bm, asof, observed.NOTICE_DAYS)
    assert notices.window(long, asof).equals(short) and len(long) > len(short)
    cov = notices.coverage(short, dates)
    assert cov["notices"] == len(short) and cov["sessions"] - cov["sessions_without_notices"] == short.known.nunique()
