import math

import numpy as np
import pandas as pd
import pytest

from nsr import config, models
from nsr.panel import Panel
from nsr.research import evaluate, features, signals, stats, text
from nsr.research.data import ResearchData


def make_rd(T=420, N=130, seed=0, tables=None):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2011-06-01", periods=T)
    rows = []
    for s in range(N):
        r = rng.normal(0, 0.02, T)
        o = rng.normal(0, 0.005, T)
        vol = rng.integers(1000, 5000, T).astype(float)
        rows.append(pd.DataFrame({"date": dates, "sid": s, "symbol": f"S{s}", "ret_cc": r, "ret_on": o,
                                  "ret_id": (1 + r) / (1 + o) - 1, "band_hit": None, "locked_limit": False,
                                  "close": 100.0, "value": vol * 100, "mto_qty": vol,
                                  "deliv_qty": vol * rng.uniform(0.2, 0.9, T)}))
    px = pd.concat(rows, ignore_index=True)
    rb = [d for d in dates[dates.is_month_end | (dates == dates[0])]]
    uni = pd.DataFrame([{"rebalance_date": d, "sid": s, "symbol": f"S{s}", "rank": s + 1, "median_value": 1.0}
                        for d in rb for s in range(N - 10)])
    panel = Panel.from_frames(px, uni)
    return ResearchData.from_panel(panel, px, tables)


# ------------------------------------------------------------------ stats
def test_required_t_never_below_three_and_rises_with_trials():
    assert stats.required_t(1) == 3.0 and stats.required_t(30) == 3.0
    assert stats.required_t(200) > stats.required_t(60) > 3.0


def test_bh_keeps_only_strong_results():
    assert stats.bh_survivors({"a": 0.001, "b": 0.5, "c": 0.9}) == {"a"}
    assert stats.bh_survivors({"a": 0.2, "b": 0.5}) == set()


def test_deflated_sharpe_falls_as_trials_grow():
    x = np.random.default_rng(1).normal(0.0004, 0.01, 3000)
    one, many = stats.sharpe_tests(x, 1), stats.sharpe_tests(x, 50)
    assert one["dsr"] == pytest.approx(one["psr"])
    assert many["dsr"] < one["dsr"] and many["expected_max_sharpe_ann"] > 0


def test_cluster_t_is_smaller_when_months_move_together():
    rng = np.random.default_rng(2)
    month = np.repeat(np.arange(40), 25)
    common = rng.normal(0, 0.03, 40)[month]
    v = 0.01 + common + rng.normal(0, 0.01, 1000)
    naive = v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))
    assert 0 < stats.cluster_t(v, month)["t"] < naive


def test_walk_forward_purges_and_embargoes():
    for train, test in stats.walk_forward_splits(1000, 500, 100, horizon=20, embargo=5):
        assert train.max() + 20 + 1 + 5 <= test.min()
    assert len(list(stats.walk_forward_splits(1000, 500, 100, 20))) == 5


# --------------------------------------------------------------- features
def test_roll_corr_matches_pandas():
    rng = np.random.default_rng(3)
    x, y = rng.normal(size=(200, 4)), rng.normal(size=(200, 4))
    x[rng.random(x.shape) < 0.1] = np.nan
    got = features.roll_corr(x, y, 30, 20)
    for c in range(4):
        m = np.isfinite(x[:, c]) & np.isfinite(y[:, c])
        a, b = pd.Series(np.where(m, x[:, c], np.nan)), pd.Series(np.where(m, y[:, c], np.nan))
        want = a.rolling(30, min_periods=20).corr(b).to_numpy()
        both = np.isfinite(got[:, c]) & np.isfinite(want)
        assert both.sum() > 100 and np.allclose(got[both, c], want[both], atol=1e-9)


def test_window_return_matches_production_baselines():
    rd = make_rd()
    mom, rev = features.window_return(rd, 252, 21, 0.8), -features.window_return(rd, 5, 0, 0.8)
    for i in (260, 333, 419):
        v = rd.panel.view(i)
        assert np.allclose(mom[i], models.mom_12_1(v), atol=1e-4, equal_nan=True)
        assert np.allclose(rev[i], models.rev_5(v), atol=1e-4, equal_nan=True)


# --------------------------------------------------------------- evaluate
def test_lookahead_check_passes_honest_signal_and_catches_leak(monkeypatch):
    rd = make_rd()
    monkeypatch.setattr(ResearchData, "eval_sessions", lambda self: range(300, len(self.dates) - 21))
    honest = lambda r: features.window_return(r, 20, 0, 0.5)
    assert evaluate.check_no_lookahead(honest, rd, honest(rd))["ok"]

    def leaky(r):                       # full-sample standardisation uses later rows
        s = features.window_return(r, 20, 0, 0.5)
        return s - np.nanmean(s, axis=0, keepdims=True)
    assert not evaluate.check_no_lookahead(leaky, rd, leaky(rd))["ok"]


def test_truncated_data_has_no_forward_returns():
    rd = make_rd()
    cut = rd.truncated(300)
    assert len(cut.dates) == 301 and cut.fwd == {}
    assert cut.panel.uni.rebalance_date.max() <= cut.dates[-1]


def test_dense_evaluator_finds_planted_signal_and_not_noise(monkeypatch):
    rd = make_rd(seed=4)
    monkeypatch.setattr(ResearchData, "eval_sessions", lambda self: range(260, len(self.dates) - 21))
    rng = np.random.default_rng(5)
    planted = np.nan_to_num(rd.fwd[5]) + rng.normal(0, 0.05, rd.fwd[5].shape)
    noise = rng.normal(size=rd.fwd[5].shape)
    ctrl = features.controls(rd)
    good = evaluate.ic_table(evaluate.daily_metrics(rd, planted, ctrl)).set_index("h")
    bad = evaluate.ic_table(evaluate.daily_metrics(rd, noise, ctrl)).set_index("h")
    assert good.loc[5, "ic_mean"] > 0.3 and good.loc[5, "ic_t"] > 10
    assert abs(bad.loc[5, "ic_t"]) < 3


def test_event_evaluator_measures_excess_over_universe(monkeypatch):
    rd = make_rd(seed=6)
    monkeypatch.setattr(ResearchData, "eval_sessions", lambda self: range(260, len(self.dates) - 21))
    ev = pd.DataFrame({"i": [270, 280, 300, 310, 330, 350], "col": [1, 2, 3, 4, 5, 6]})
    er = evaluate.event_returns(rd, ev, 5)
    k = 0
    want = rd.fwd[5][270, 1] - np.nanmean(rd.fwd[5][270][rd.member[270]])
    assert er.excess.iloc[k] == pytest.approx(want)
    assert evaluate.evaluate_events(rd, ev, 5)["events"] == 6


# ------------------------------------------------------------------- text
def test_announcement_records_join_continuation_lines():
    raw = "COMPANY NAME    SYMBOL    : ANNOUNCEMENTS\nAcme Limited    ACME : Updates Acme has won\n  an order worth Rs 5 crore\n\nBeta Ltd    BETA       : Declaration of NAV x\n"
    recs = text.split_records(raw, text._AN)
    assert recs[0] == ("ACME", "Updates Acme has won an order worth Rs 5 crore") and recs[1][0] == "BETA"


def test_board_meeting_record():
    raw = "COMPANY NAME    SYMBOL     : BM DATE    : BM PURPOSE \nNTPC Limited    NTPC : 24-OCT-2024 : Financial Results/Dividend To consider\n"
    assert text.split_records(raw, text._BM) == [("NTPC", "24-OCT-2024", "Financial Results/Dividend To consider")]


@pytest.mark.parametrize("t", [
    'Press Release titled "L&T Construction Wins Orders Valued Rs 1099 Crores".',
    "has informed the Exchange regarding 'Receipt of LOA for Uttar Pradesh Expressways project'.",
    "the Company has been awarded contracts aggregating to Rs. 106.99 crore by Odisha Power Transmission",
    "Bagging/Receiving of orders/contracts RITES : Major Order secured from Mahanadi Coalfields Limited",
    "has received a work order dated 12 January 2023 from NHAI",
])
def test_order_win_positive(t):
    assert signals.is_order_win(t)


@pytest.mark.parametrize("t", [
    "Hon'ble Supreme Court of India has, vide Order dated February 07, 2011, upheld the Order",
    "the Company has received an order from the Commissioner of Income Tax",
    "Allotment of Securities pursuant to the order",
    "the Company has received approval in order to proceed",
    "Outcome of Board Meeting approved the award of EPC Contract to M/s. Bhimji Velji",
    "Financial Results for the quarter",
])
def test_order_win_negative(t):
    assert not signals.is_order_win(t)


# ---------------------------------------------------------------- signals
def test_ear_drift_uses_reaction_then_carries_it(monkeypatch):
    bm = pd.DataFrame({"known": [pd.Timestamp("2012-06-01")], "symbol": ["S3"],
                       "meeting": [pd.Timestamp("2012-06-12")], "purpose": ["Financial Results To consider"]})
    rd = make_rd(tables={"board_meetings": bm})
    S = signals.ear_drift(rd, hold=10, days=2)
    e1 = int(np.searchsorted(rd.dates, pd.Timestamp("2012-06-12")))
    assert np.isnan(S[e1, 3]) and np.isfinite(S[e1 + 1, 3]) and np.isfinite(S[e1 + 10, 3]) and np.isnan(S[e1 + 11, 3])
    mkt = [np.nanmean(rd.panel.ret_cc[k][rd.member[k]]) for k in (e1, e1 + 1)]
    want = rd.panel.ret_cc[e1, 3] - mkt[0] + rd.panel.ret_cc[e1 + 1, 3] - mkt[1]
    assert S[e1 + 1, 3] == pytest.approx(want, abs=1e-6)
    assert np.isfinite(S).sum() == 10


def test_rescheduled_meeting_is_dropped():
    bm = pd.DataFrame({"known": pd.to_datetime(["2012-06-01", "2012-06-08"]), "symbol": ["S3", "S3"],
                       "meeting": pd.to_datetime(["2012-06-12", "2012-06-15"]),
                       "purpose": ["Results", "Results"]})
    rd = make_rd(tables={"board_meetings": bm})
    assert list(signals.results_meetings(rd).meeting) == [pd.Timestamp("2012-06-15")]


def test_order_events_respect_universe_and_cooldown():
    an = pd.DataFrame({"known": pd.to_datetime(["2012-06-12", "2012-06-13", "2012-07-02", "2012-06-12"]),
                       "symbol": ["S3", "S3", "S3", "S125"],
                       "text": ["Acme bags order worth Rs 5 crore"] * 4})
    rd = make_rd(tables={"announcements": an})
    ev = signals.order_win_events(rd)
    assert list(ev.col) == [3, 3] and len(ev) == 2          # second day inside cooldown; S125 not a member


def test_research_data_refuses_production(monkeypatch):
    monkeypatch.setenv(config.PRODUCTION_ENV, "1")
    with pytest.raises(RuntimeError):
        make_rd(T=300, N=20)


def test_insider_buys_need_size_freshness_membership_and_cooldown():
    def row(known, sym, value, cat="Promoters", mode="Market Purchase", lag=2, hour=10):
        b = pd.Timestamp(known) + pd.Timedelta(hours=hour)
        return {"broadcast": b, "known": (b + pd.Timedelta(days=int(hour >= 20))).normalize(), "symbol": sym, "person": "P",
                "category": cat, "mode": mode, "txn": "Buy", "sec_type": "Equity Shares", "value": value,
                "trade_to": pd.Timestamp(known) - pd.Timedelta(days=lag)}
    ins = pd.DataFrame([
        row("2012-06-12", "S3", 600_000), row("2012-06-12", "S3", 600_000),       # two filings add up to Rs 12 lakh
        row("2012-06-20", "S3", 5_000_000),                                        # inside the 20-session cooldown
        row("2012-06-12", "S4", 500_000),                                          # too small
        row("2012-06-12", "S5", 5_000_000, cat="Employees/Designated Employees"),  # not an insider category
        row("2012-06-12", "S6", 5_000_000, mode="ESOP"),                           # not an open-market purchase
        row("2012-06-12", "S7", 5_000_000, lag=40),                                # stale disclosure
        row("2012-06-12", "S125", 5_000_000),                                      # not in the universe
        row("2012-06-12", "S8", 5_000_000, hour=21),                               # after 20:00: usable next session
    ])
    rd = make_rd(tables={"insider": ins})
    ev = signals.insider_buys(rd)
    d0 = int(np.searchsorted(rd.dates, pd.Timestamp("2012-06-12")))
    assert sorted(zip(ev.i, ev.col)) == [(d0, 3), (d0 + 1, 8)]
    assert len(signals.insider_buys(rd, cooldown=0)) == 3 and len(signals.insider_buys(rd, max_lag_days=None)) == 3
    assert len(signals.insider_buys(rd.truncated(d0))) == 1                        # the late filing is not known yet
