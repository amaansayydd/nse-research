import numpy as np
import pandas as pd
import pytest

from nsr.build import apply_actions, assign_sid, compute_returns, consolidate_actions, quality_flags
from nsr.universe import build_universe


def _px(symbol, dates, closes, series="EQ", value=1e7):
    closes = np.asarray(closes, dtype=float)
    prev = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({
        "date": pd.to_datetime(dates), "symbol": symbol, "series": series,
        "prev_close": prev, "open": closes, "high": closes, "low": closes, "close": closes,
        "value": value, "volume": 1000.0, "band_hit": None,
    })


def _bc(symbol, ex_date, purpose, files):
    return pd.DataFrame({"file_date": pd.to_datetime(files), "symbol": symbol,
                         "ex_date": pd.Timestamp(ex_date), "record_dt": pd.NaT, "purpose": purpose})


def test_split_day_return_is_repaired():
    # 1000 -> 10-for-1 split -> trades at 101 next day: true return is +1%
    px = _px("AAA", ["2020-01-01", "2020-01-02", "2020-01-03"], [1000, 1000, 101])
    px.loc[2, "prev_close"] = 1000  # NSE leaves prev close unadjusted
    ca = consolidate_actions(_bc("AAA", "2020-01-03", "FV SPLIT RS.10 TO RE.1", ["2020-01-01", "2020-01-03"]))
    out = compute_returns(apply_actions(px, ca))
    r = out.set_index("date").ret_cc
    assert r["2020-01-03"] == pytest.approx(0.01)
    assert r["2020-01-02"] == pytest.approx(0.0)


def test_dividend_is_added_back_and_rewording_is_not_double_counted():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 98])
    bc = pd.concat([
        _bc("AAA", "2020-01-02", "INTERIM DIVIDEND", ["2019-12-20"]),
        _bc("AAA", "2020-01-02", "INT DIV-RS.2/- PER SHARE", ["2019-12-27", "2020-01-02"]),
    ])
    out = compute_returns(apply_actions(px, consolidate_actions(bc)))
    row = out[out.date == "2020-01-02"].iloc[0]
    assert row["div"] == pytest.approx(2.0) and not row.div_unknown
    assert row.ret_cc == pytest.approx(0.0)


def test_action_on_a_non_trading_day_applies_at_next_trade():
    px = _px("AAA", ["2020-01-01", "2020-01-06"], [200, 100])
    ca = consolidate_actions(_bc("AAA", "2020-01-03", "BONUS 1:1", ["2020-01-01", "2020-01-02"]))
    out = compute_returns(apply_actions(px, ca))
    assert out[out.date == "2020-01-06"].ret_cc.iloc[0] == pytest.approx(0.0)


def test_rescheduled_action_is_ignored():
    px = _px("AAA", ["2020-01-01", "2020-03-02"], [100, 100])
    # listed once two months before the ex-date, then dropped from the files
    ca = consolidate_actions(_bc("AAA", "2020-03-02", "BONUS 1:1", ["2020-01-01"]))
    out = compute_returns(apply_actions(px, ca))
    assert (out.adj == 1.0).all()


def test_wrong_factor_is_caught_and_return_blanked():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 99])
    ca = consolidate_actions(_bc("AAA", "2020-01-02", "BONUS 1:1", ["2020-01-01", "2020-01-02"]))
    out = compute_returns(apply_actions(px, ca))
    row = out[out.date == "2020-01-02"].iloc[0]
    assert row.ca_suspect and np.isnan(row.ret_cc)


def test_unresolved_event_blanks_the_return():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 60])
    ca = consolidate_actions(_bc("AAA", "2020-01-02", "SCHEME OF ARRANGEMENT", ["2020-01-01", "2020-01-02"]))
    out = compute_returns(apply_actions(px, ca))
    assert np.isnan(out[out.date == "2020-01-02"].ret_cc.iloc[0])


def test_rename_keeps_one_id_and_reused_symbol_gets_a_new_one():
    old = _px("OLDCO", ["2020-01-01", "2020-01-02"], [100, 102])
    new = _px("NEWCO", ["2020-01-03", "2020-01-06"], [103, 104])
    new.loc[0, "prev_close"] = 102
    reuse = _px("OLDCO", ["2023-06-01", "2023-06-02"], [15, 16])  # different company, years later
    px = pd.concat([old, new, reuse], ignore_index=True)
    changes = pd.DataFrame({"name": ["x"], "old": ["OLDCO"], "new": ["NEWCO"], "eff": [pd.Timestamp("2020-01-03")]})
    sid, stats = assign_sid(px, changes)
    px["sid"] = sid
    a = px[(px.symbol == "OLDCO") & (px.date < "2021-01-01")].sid.unique()
    b = px[px.symbol == "NEWCO"].sid.unique()
    c = px[(px.symbol == "OLDCO") & (px.date > "2021-01-01")].sid.unique()
    assert len(a) == len(b) == len(c) == 1
    assert a[0] == b[0] and c[0] != a[0]
    assert stats["renames_linked"] == 1


def test_extra_benchmark_funds_take_ids_after_every_stock():
    from nsr.build import EXTRA_BENCHMARKS, number_securities
    funds = list(EXTRA_BENCHMARKS)
    stocks = pd.concat([_px("AAA", ["2020-01-01", "2020-01-02"], [100, 102]), _px("NNN", ["2020-01-01", "2020-01-02"], [50, 51]),
                        _px("ZZZ", ["2020-01-01", "2020-01-02"], [10, 11])], ignore_index=True)
    none = pd.DataFrame({"name": [], "old": [], "new": [], "eff": pd.to_datetime([])})
    alone, _ = assign_sid(stocks, none)
    px = pd.concat([_px(funds[-1], ["2020-01-01", "2020-01-02"], [20, 21]), stocks,
                    _px(funds[0], ["2020-01-02"], [30])], ignore_index=True)
    sid, stats = number_securities(px, none)
    px["sid"] = sid
    assert px[~px.symbol.isin(funds)].sid.tolist() == alone.tolist()         # funds between A and Z renumber nothing
    assert stats["securities"] == 3 and str(sid.dtype) == "int32"
    assert [px[px.symbol == f].sid.unique().tolist() for f in funds] == [[4 + k] for k in range(len(funds))]


def test_rename_without_price_continuity_is_not_linked():
    old = _px("OLDCO", ["2020-01-01", "2020-01-02"], [100, 102])
    new = _px("NEWCO", ["2020-01-03", "2020-01-06"], [500, 510])  # prev_close 500, no continuity
    px = pd.concat([old, new], ignore_index=True)
    changes = pd.DataFrame({"name": ["x"], "old": ["OLDCO"], "new": ["NEWCO"], "eff": [pd.Timestamp("2020-01-03")]})
    sid, stats = assign_sid(px, changes)
    assert sid.nunique() == 2 and stats["renames_price_break"] == 1


def test_listing_day_return_is_not_counted():
    px = _px("IPO", ["2020-01-01", "2020-01-02"], [150, 153])
    px.loc[0, "prev_close"] = 100  # issue price
    px = compute_returns(apply_actions(px, consolidate_actions(_bc("ZZZ", "2020-01-02", "EGM", ["2020-01-01"]))))
    px["sid"] = 1
    out = quality_flags(px)
    assert np.isnan(out.ret_cc.iloc[0]) and out.first_day.iloc[0]
    assert out.ret_cc.iloc[1] == pytest.approx(0.02)


def _synthetic_market(n_days=200, n_stocks=30, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2020-01-01", periods=n_days)
    frames = []
    for s in range(n_stocks):
        f = _px(f"S{s:02d}", days, 100 + rng.normal(0, 1, n_days).cumsum())
        f["value"] = rng.lognormal(10 + s * 0.1, 0.5, n_days)
        f["sid"] = s + 1
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def test_universe_is_point_in_time():
    px = _synthetic_market()
    full = build_universe(px, top_n=10, lookback=60, min_days=50)
    cut = px.date.sort_values().unique()[150]
    part = build_universe(px[px.date <= cut], top_n=10, lookback=60, min_days=50)
    common = part.rebalance_date.unique()[:-1]  # last partial month-end differs by construction
    assert len(common) >= 2
    a = full[full.rebalance_date.isin(common)].set_index(["rebalance_date", "rank"]).sid
    b = part[part.rebalance_date.isin(common)].set_index(["rebalance_date", "rank"]).sid
    pd.testing.assert_series_equal(a, b)


def test_universe_requires_trading_history_and_eq_series():
    px = _synthetic_market()
    px.loc[px.symbol == "S29", "series"] = "BE"          # most liquid name, but trade-for-trade
    px = px[~((px.symbol == "S28") & (px.date > "2020-03-01"))]  # stopped trading
    uni = build_universe(px, top_n=10, lookback=60, min_days=50)
    last = uni[uni.rebalance_date == uni.rebalance_date.max()]
    assert not last.symbol.isin(["S29", "S28"]).any()
    assert len(last) == 10


def _reg(symbol, ex_date, purpose, fv=10.0):
    return pd.DataFrame({"symbol": [symbol], "ex_date": [pd.Timestamp(ex_date)], "purpose": [purpose], "face_value": [fv]})


def test_register_supplies_actions_missing_from_daily_file():
    px = _px("AAA", ["2020-01-01", "2020-01-02", "2020-01-03"], [1000, 1000, 101])
    px.loc[2, "prev_close"] = 1000
    bc = _bc("ZZZ", "2020-01-03", "EGM", ["2020-01-01"])  # daily file never mentions AAA
    ca = consolidate_actions(bc, _reg("AAA", "2020-01-03", "FACE VALUE SPLIT (SUB-DIVISION) - FROM RS 10/- PER SHARE TO RE 1/- PER SHARE"))
    out = compute_returns(apply_actions(px, ca))
    assert out[out.date == "2020-01-03"].ret_cc.iloc[0] == pytest.approx(0.01)


def test_same_event_in_both_sources_is_applied_once():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 98])
    bc = _bc("AAA", "2020-01-02", "INT DIV-RS.2/- PER SHARE", ["2019-12-27", "2020-01-02"])
    ca = consolidate_actions(bc, _reg("AAA", "2020-01-02", "INTERIM DIVIDEND - RS 2 PER SHARE"))
    out = compute_returns(apply_actions(px, ca))
    row = out[out.date == "2020-01-02"].iloc[0]
    assert row["div"] == pytest.approx(2.0)
    assert row.ca_published == pd.Timestamp("2019-12-27")  # publication date still comes from the daily file


def test_ex_date_one_day_early_is_moved_to_where_the_price_adjusts():
    # daily file says ex 02-Jan, but the price actually splits on 03-Jan (T+1 transition case)
    px = _px("AAA", ["2020-01-01", "2020-01-02", "2020-01-03"], [500, 505, 101])
    ca = consolidate_actions(_bc("AAA", "2020-01-02", "FVSPLT FRM RS 10 TO RS 2", ["2020-01-01", "2020-01-02"]))
    out = compute_returns(apply_actions(px, ca)).set_index("date")
    assert out.adj["2020-01-02"] == 1.0 and out.adj["2020-01-03"] == pytest.approx(0.2)
    assert out.ret_cc["2020-01-03"] == pytest.approx(101 / (505 * 0.2) - 1)
    assert not out.ca_suspect.any()


def test_revised_register_entry_replaces_the_original():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 97.5])
    reg = pd.concat([_reg("AAA", "2020-01-02", "INTERIM DIVIDEND - RS 2 PER SHARE"),
                     _reg("AAA", "2020-01-02", "INTERIM DIVIDEND - RS 2.50/- PER SHARE (PURPOSE REVISED)")])
    ca = consolidate_actions(_bc("ZZZ", "2020-01-02", "EGM", ["2020-01-01"]), reg)
    out = compute_returns(apply_actions(px, ca))
    assert out[out.date == "2020-01-02"]["div"].iloc[0] == pytest.approx(2.5)


def test_huge_real_dividend_is_kept_when_the_open_confirms_it():
    # MAJESCO, 23-Dec-2020: Rs 974 dividend on a Rs 985.65 share, opened at 12.20
    px = _px("MAJ", ["2020-12-22", "2020-12-23"], [985.65, 12.20])
    ca = consolidate_actions(_bc("MAJ", "2020-12-23", "INTDIV - RS 974 PER SH", ["2020-12-18", "2020-12-23"]))
    row = compute_returns(apply_actions(px, ca)).iloc[-1]
    assert row["div"] == pytest.approx(974.0) and not row.ca_suspect
    assert row.ret_cc == pytest.approx((12.20 + 974) / 985.65 - 1)


def test_huge_dividend_that_the_open_contradicts_is_rejected():
    px = _px("AAA", ["2020-01-01", "2020-01-02"], [100, 99])
    ca = consolidate_actions(_bc("AAA", "2020-01-02", "DIVIDEND-RS.60 PER SHARE", ["2020-01-01", "2020-01-02"]))
    row = compute_returns(apply_actions(px, ca)).iloc[-1]
    assert row["div"] == 0 and row.ca_suspect and np.isnan(row.ret_cc)


def test_register_action_filed_under_later_ticker_is_put_back():
    from nsr.build import remap_register_symbols
    reg = pd.concat([_reg("NEWCO", "2020-01-02", "BONUS 1:1"), _reg("NEWCO", "2021-06-01", "BONUS 1:1")])
    changes = pd.DataFrame({"name": ["x"], "old": ["OLDCO"], "new": ["NEWCO"], "eff": [pd.Timestamp("2020-06-01")]})
    out = remap_register_symbols(reg, changes).sort_values("ex_date")
    assert out.symbol.tolist() == ["OLDCO", "NEWCO"]
