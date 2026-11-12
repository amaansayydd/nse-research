from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from nsr import config, models, predict, score
from nsr.costs import CostModel
from nsr.panel import Panel
from nsr.sim import simulate
from nsr.universe import members_asof


def make_panel(n_days=320, n_stocks=40, seed=1, drift=None):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-01", periods=n_days)
    rows = []
    for s in range(n_stocks):
        r_on = rng.normal(0, 0.005, n_days)
        r_id = rng.normal(0 if drift is None else drift[s], 0.01, n_days)
        rows.append(pd.DataFrame({
            "date": days, "sid": s + 1, "symbol": f"S{s:02d}", "ret_on": r_on, "ret_id": r_id,
            "ret_cc": (1 + r_on) * (1 + r_id) - 1, "band_hit": None, "locked_limit": False, "is_benchmark": False}))
    px = pd.concat(rows, ignore_index=True)
    month_ends = pd.Series(days, index=days).groupby([days.year, days.month]).max()
    uni = pd.concat([pd.DataFrame({"rebalance_date": t, "sid": np.arange(1, n_stocks + 1),
                                   "symbol": [f"S{s:02d}" for s in range(n_stocks)]}) for t in month_ends])
    return Panel.from_frames(px, uni), px, uni


NOW = datetime(2021, 1, 1, 20, 30, tzinfo=config.IST)


def test_universe_membership_waits_for_the_month_to_finish():
    uni = pd.DataFrame({"rebalance_date": pd.to_datetime(["2021-01-29", "2021-02-26"]), "sid": [1, 2]})
    assert members_asof(uni, "2021-02-26").sid.tolist() == [1]   # cannot know yet that Feb has ended
    assert members_asof(uni, "2021-03-01").sid.tolist() == [2]
    assert members_asof(uni, "2021-01-15").empty


def test_predictions_do_not_change_when_the_future_changes():
    panel, _, _ = make_panel()
    i = 280
    a = predict.make_predictions(panel, i, NOW, "r", "c")
    for arr in (panel.ret_cc, panel.ret_on, panel.ret_id):
        arr[i + 1:] = 9.99                                   # poison everything after the as-of session
    panel.traded[i + 1:] = False
    b = predict.make_predictions(panel, i, NOW, "r", "c")
    pd.testing.assert_frame_equal(a, b)
    assert set(a.model) == set(models.MODELS) and a.groupby("model").size().eq(40).all()


def test_view_stops_at_asof():
    panel, _, _ = make_panel()
    v = panel.view(100)
    assert len(v.dates) == 101 and v.ret_cc.shape[0] == 101 and v.asof == panel.dates[100]


def test_log_is_append_only_and_schema_is_frozen(tmp_path):
    panel, _, _ = make_panel()
    path = tmp_path / "predictions.csv"
    d1 = predict.make_predictions(panel, 280, NOW, "r1", "c")
    assert predict.append_predictions(d1, path) == len(d1)
    with pytest.raises(RuntimeError, match="append-only"):
        predict.append_predictions(d1, path)                 # same day again: refused
    d2 = predict.make_predictions(panel, 281, NOW, "r2", "c")
    predict.append_predictions(d2, path)
    back = pd.read_csv(path)
    assert len(back) == len(d1) + len(d2) and list(back.columns) == predict.COLUMNS
    assert back.iloc[: len(d1)].symbol.tolist() == d1.symbol.tolist()   # earlier rows untouched
    path.write_text("wrong,header\n")
    with pytest.raises(RuntimeError, match="schema"):
        predict.append_predictions(d2, path)


def test_no_backfill_after_the_next_open_could_have_happened():
    asof = pd.Timestamp("2026-11-12")
    predict.assert_fresh(asof, datetime(2026, 11, 12, 20, 30, tzinfo=config.IST))
    predict.assert_fresh(asof, datetime(2026, 11, 13, 8, 59, tzinfo=config.IST))
    with pytest.raises(predict.StalePrediction):
        predict.assert_fresh(asof, datetime(2026, 11, 13, 9, 0, tzinfo=config.IST))
    with pytest.raises(predict.StalePrediction):
        predict.assert_fresh(asof, datetime(2026, 11, 16, 20, 30, tzinfo=config.IST))


def test_realized_is_open_to_open_from_the_next_session():
    panel, px, _ = make_panel(n_days=30, n_stocks=3)
    i, h, c = 10, 3, 0
    g = px[px.sid == 1].reset_index(drop=True)
    manual = np.prod([(1 + g.ret_id[s]) * (1 + g.ret_on[s + 1]) for s in range(i + 1, i + 1 + h)]) - 1
    assert panel.realized(i, h)[c] == pytest.approx(manual, rel=1e-5)
    with pytest.raises(IndexError):
        panel.realized(28, 3)                                # window not complete


def test_scorer_sees_skill_when_there_is_some_and_none_when_there_is_not(tmp_path):
    drift = np.linspace(-0.004, 0.004, 40)                   # stock s has a persistent edge
    panel, _, _ = make_panel(drift=drift)
    frames = [predict.make_predictions(panel, i, NOW, "r", "c") for i in range(260, 300)]
    preds = pd.concat(frames)
    s = score.score_matured(panel, preds, set())
    summ = score.summarize(s).set_index(["model", "horizon"])
    assert summ.loc[("mom_12_1", 5), "ic_mean"] > 0.3        # momentum picks up the persistent drift
    assert abs(summ.loc[("random", 5), "ic_mean"]) < 0.1
    # scoring is incremental: nothing new on a second pass
    keys = set(zip(s.asof_date, s.model, s.horizon))
    assert score.score_matured(panel, preds, keys).empty
    # and it respects "as of": on session 262 only the 1-day target of session 260 has matured
    early = score.score_matured(panel, preds, set(), upto=262)
    assert set(zip(early.asof_date, early.horizon)) == {(panel.dates[260].strftime("%Y-%m-%d"), 1)}


def test_cost_model_matches_hand_calculation():
    c = CostModel()
    n = 100_000.0
    buy = n * 0.001 + n * 0.00015 + n * (0.0000307 + 0.000001) * 1.18
    sell = n * 0.001 + n * (0.0000307 + 0.000001) * 1.18 + 16.0
    assert c.buy(n) == pytest.approx(buy) and c.sell(n) == pytest.approx(sell)
    assert 0.0040 < c.round_trip_rate(n) < 0.0046            # ~0.22% charges + 0.2% slippage + DP


def _flat_panel(n_days=30, n_stocks=5):
    days = pd.bdate_range("2021-01-01", periods=n_days)
    px = pd.concat([pd.DataFrame({"date": days, "sid": s + 1, "symbol": f"S{s}", "ret_on": 0.0, "ret_id": 0.0,
                                  "ret_cc": 0.0, "band_hit": None, "locked_limit": False, "is_benchmark": False})
                    for s in range(n_stocks)], ignore_index=True)
    uni = pd.DataFrame({"rebalance_date": days[0], "sid": np.arange(1, n_stocks + 1)})
    return Panel.from_frames(px, uni)


def test_sim_with_flat_prices_loses_exactly_the_costs():
    panel = _flat_panel()
    picks = {i: np.array([0, 1]) for i in range(30)}         # always the same two names
    res = simulate(panel, picks, start=0, end=29, h=5, n_names=2, capital=1_000_000)
    c = CostModel()
    per = 500_000.0
    expected = 2 * ((per - c.buy(per)) * (1 - c.slippage))   # bought once, never sold
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-9)
    assert res.stats["sells"] == 0 and res.stats["buys"] == 2


def test_sim_cannot_buy_at_upper_lock_or_sell_at_lower_lock():
    panel = _flat_panel()
    panel.lock_up[1:, 0] = True                              # name 0 can never be bought
    picks = {i: np.array([0, 1]) for i in range(30)}
    res = simulate(panel, picks, start=0, end=29, h=1, n_names=2)   # h=1: a single start offset
    assert res.stats["buys"] == 1 and res.stats["unfilled_buys"] == 29
    assert res.equity.iloc[-1] > 990_000                     # half the money stayed in cash

    panel = _flat_panel()
    panel.lock_dn[:, 0] = True                               # name 0 can never be sold
    picks = {i: (np.array([0, 1]) if i < 5 else np.array([2, 3])) for i in range(30)}
    res = simulate(panel, picks, start=0, end=29, h=5, n_names=2)
    assert res.stats["blocked_sells"] > 0


def test_sim_pessimistic_bound_writes_off_a_stock_that_stops_trading():
    panel = _flat_panel()
    panel.traded[5:, 0] = False                              # name 0 disappears
    picks = {i: np.array([0, 1]) for i in range(30)}
    kept = simulate(panel, picks, 0, 29, h=1, n_names=2)
    gone = simulate(panel, picks, 0, 29, h=1, n_names=2, writeoff_after=10)
    assert gone.stats["writeoffs"] == 1
    assert gone.equity.iloc[-1] < 0.51 * kept.equity.iloc[-1] + 1


def test_run_log_raises_an_alert_after_three_failures_and_clears_it(tmp_path, monkeypatch):
    from nsr import daily
    log = tmp_path / "run_log.md"
    log.write_text("# Run log\n\n| run at (IST) | outcome | data date | predictions written | notes |\n|---|---|---|---|---|\n")
    monkeypatch.setattr(daily, "RUN_LOG", log)
    monkeypatch.setattr(daily.subprocess, "run", lambda *a, **k: None)   # no desktop notification in tests
    t = datetime(2026, 11, 12, 20, 30, tzinfo=config.IST)
    daily.log_run(t, "OK", "2026-11-12", 1500, "")
    daily.log_run(t, "FAIL", "-", 0, "boom | with a pipe")
    daily.log_run(t, "FAIL", "-", 0, "boom")
    assert "ALERT" not in log.read_text()
    daily.log_run(t, "FAIL", "-", 0, "boom")
    text = log.read_text()
    assert "ALERT: the last 3 runs failed" in text and text.count("| FAIL |") == 3
    assert "boom / with a pipe" in text                       # pipes cannot break the table
    daily.log_run(t, "OK", "2026-11-13", 1500, "")
    assert "ALERT" not in log.read_text() and log.read_text().count("| 2026-11-12 20:30 |") == 5


def test_production_panel_is_refused_outside_production(monkeypatch):
    monkeypatch.delenv(config.PRODUCTION_ENV, raising=False)
    with pytest.raises(config.HoldoutViolation):
        Panel.load(config.PROD_DIR / "clean")
    from nsr import api
    with pytest.raises(config.HoldoutViolation):
        api.refresh_production_register(config.HOLDOUT_END)
    with pytest.raises(config.HoldoutViolation):
        api._guard_window(config.HOLDOUT_START, config.HOLDOUT_END)


def test_random_control_depends_only_on_date_and_ticker():
    panel, px, uni = make_panel(n_days=60, n_stocks=10)
    renumbered = px.assign(sid=px.sid.map(lambda x: 100 - x))        # same tickers, different ids and order
    other = Panel.from_frames(renumbered, uni.assign(sid=100 - uni.sid))
    a = dict(zip(panel.view(40).keys, models.random(panel.view(40))))
    b = dict(zip(other.view(40).keys, models.random(other.view(40))))
    assert a == b and len(set(a.values())) == 10
    assert dict(zip(panel.view(41).keys, models.random(panel.view(41)))) != a   # new draw each day
