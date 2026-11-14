import numpy as np
import pandas as pd
import pytest

from nsr import champion, graduation, predict, report, score
from nsr.costs import CostModel
from nsr.sim import simulate
from nsr.tax import TaxModel, buy_and_hold_after_tax, fin_year, settle, year_tax

from test_phase1 import NOW, make_panel
from test_phase3 import fake_scores

M = TaxModel()
FREE = CostModel(stt=0, stamp_buy=0, exchange_txn=0, sebi=0, dp_per_sell=0, slippage=0)


# ------------------------------------------------------------------------ tax
def test_financial_year_runs_april_to_march():
    assert [fin_year(d) for d in ("2027-03-31", "2027-04-01", "2026-11-13")] == [2026, 2027, 2026]


def test_capital_gains_tax_matches_hand_calculation():
    assert year_tax(100_000, 0, 0, 0, M)[0] == pytest.approx(100_000 * 0.20 * 1.04)
    assert year_tax(0, 200_000, 0, 0, M)[0] == pytest.approx((200_000 - 125_000) * 0.125 * 1.04)
    assert year_tax(0, 100_000, 0, 0, M)[0] == 0                       # inside the long-term exemption
    assert year_tax(100_000, 100_000, 0, 0, TaxModel.business())[0] == pytest.approx(200_000 * 0.30 * 1.04)


def test_losses_set_off_and_carry_forward_as_the_law_allows():
    tax, cst, clt = year_tax(-50_000, 300_000, 0, 0, M)                # short-term loss eats long-term gain
    assert tax == pytest.approx((250_000 - 125_000) * 0.125 * 1.04) and (cst, clt) == (0, 0)
    tax, cst, clt = year_tax(100_000, -80_000, 0, 0, M)                # long-term loss cannot touch short-term gain
    assert tax == pytest.approx(20_800) and (cst, clt) == (0, 80_000)
    tax, cst, clt = year_tax(-70_000, 0, 0, 0, M)                      # nothing to absorb it: carried
    assert tax == 0 and cst == 70_000
    tax, cst, clt = year_tax(100_000, 0, 70_000, 0, M)                 # next year it comes off first
    assert tax == pytest.approx(30_000 * 0.20 * 1.04) and cst == 0
    tax, cst, clt = year_tax(0, 200_000, 0, 80_000, M)
    assert tax == 0 and clt == 0                                       # 120,000 left, inside the exemption


def test_settlement_pays_tax_each_year_and_on_liquidation():
    dates = pd.DatetimeIndex(["2027-03-30", "2027-03-31", "2027-04-01", "2027-04-02"])
    eq = np.array([1_000_000.0, 1_100_000.0, 1_100_000.0, 1_210_000.0])
    trades = [(dates[1], dates[0], 500_000.0, 600_000.0)]              # 100,000 short-term gain in FY2026
    held = [(dates[2], 1_079_200.0, 1_210_000.0)]                      # bought after tax day, still held
    out = settle(eq, dates, trades, held, FREE, M)
    paid = 20_800.0
    f = 1 - paid / 1_100_000
    assert out["curve"][1] == 1_100_000 and out["curve"][3] == pytest.approx(1_210_000 * f)
    final = (1_210_000 - 1_079_200) * f * 0.20 * 1.04                  # liquidation gain of the shrunken book
    assert out["tax"] == pytest.approx(paid + final) and out["terminal"] == pytest.approx(1_210_000 * f - final)


def test_buy_and_hold_is_taxed_once_at_the_long_term_rate():
    days = pd.bdate_range("2027-01-01", periods=300)
    r = pd.Series(0.0, index=days)
    r.iloc[10] = 0.5
    assert buy_and_hold_after_tax(r, 1_000_000, FREE, M) == pytest.approx(1_500_000 - (500_000 - 125_000) * 0.125 * 1.04)
    short = r.iloc[:100]
    assert buy_and_hold_after_tax(short, 1_000_000, FREE, M) == pytest.approx(1_500_000 - 500_000 * 0.20 * 1.04)


def test_simulation_after_tax_never_beats_pre_tax_and_leaves_pre_tax_alone():
    drift = np.linspace(-0.002, 0.004, 40)
    panel, _, _ = make_panel(drift=drift)
    picks = {i: np.argsort(-drift) for i in range(len(panel.dates))}
    plain = simulate(panel, picks, 100, 319, 20, 10)
    taxed = simulate(panel, picks, 100, 319, 20, 10, tax=M)
    assert np.array_equal(plain.equity.to_numpy(), taxed.equity.to_numpy())
    assert taxed.stats["tax_paid"] > 0 and taxed.stats["after_tax_total_return"] < taxed.stats["total_return"]
    assert simulate(panel, picks, 100, 319, 20, 10, tax=TaxModel.business()).stats["tax_paid"] > taxed.stats["tax_paid"]


# ----------------------------------------------------------------- graduation
GOOD_BOOK = {"sessions": 760, "coverage": 0.99, "after_tax": 0.22, "after_tax_if_business_income": 0.19,
             "nifty_after_tax": 0.11, "pre_tax": 0.27, "universe_pre_tax": 0.15, "drawdown": -0.22,
             "nifty_drawdown": -0.14, "relative_drawdown": -0.09}


def graduate(book=GOOD_BOOK, days=760, since="2027-06-01", champ="ear_drift_60", **kw):
    state = {**champion.DEFAULT_STATE, "champion": champ, "champion_since": since}
    return graduation.evaluate("ear_drift_60", fake_scores(days, **kw), state, book, None).set_index("criterion").met


def test_a_strong_champion_meets_every_measured_criterion_but_never_the_owners():
    met = graduate()
    assert met.drop("G9 owner's checks").eq("yes").all() and met["G9 owner's checks"] == "by hand"


def test_each_criterion_can_fail_on_its_own():
    assert graduate(champ=None)["G1 standing"] == "no"
    assert graduate(since="2029-10-01")["G1 standing"] == "no"                         # not long enough in the seat
    assert graduate(days=400)["G2 duration"] == "no"
    calm = {**GOOD_BOOK, "nifty_drawdown": -0.04}
    assert graduate(calm, days=600)["G2 duration"] == "no" and graduate(calm, days=760)["G2 duration"] == "yes"
    assert graduate(ic=0.01)["G3 IC"] == "no"
    assert graduate(ic=0.021, sd=0.2)["G4 t-stat"] == "no"
    assert graduate({**GOOD_BOOK, "after_tax": 0.13})["G5 against Nifty after costs and taxes"] == "no"   # only 2 points over
    assert graduate({**GOOD_BOOK, "pre_tax": 0.14})["G6 against the universe"] == "no"
    assert graduate({**GOOD_BOOK, "drawdown": -0.30})["G7 drawdown"] == "no"
    assert graduate({**GOOD_BOOK, "drawdown": -0.30, "nifty_drawdown": -0.25})["G7 drawdown"] == "yes"   # the market fell too
    assert graduate({**GOOD_BOOK, "relative_drawdown": -0.2})["G7 drawdown"] == "no"
    assert graduate({**GOOD_BOOK, "coverage": 0.9})["G8 record integrity"] == "no"
    assert graduate(None)[["G5 against Nifty after costs and taxes", "G6 against the universe", "G7 drawdown"]].eq("no").all()


def test_book_measures_the_models_own_window(tmp_path):
    drift = np.linspace(-0.002, 0.004, 40)
    panel, _, _ = make_panel(drift=drift)
    panel.bench["NIFTYBEES"] = 0.0004
    preds = pd.concat([predict.make_predictions(panel, i, NOW, "r", "c") for i in range(200, 318)])
    b = graduation.book(panel, preds, "mom_12_1")            # momentum's first prediction is session 251
    assert b["sessions"] == 68 and b["coverage"] == pytest.approx(67 / 69)
    assert b["after_tax"] < b["pre_tax"] and b["after_tax_if_business_income"] < b["after_tax"]
    assert b["pre_tax"] > b["universe_pre_tax"]                        # momentum finds the planted drift
    assert graduation.book(panel, preds, "no_such_model") is None


def test_scoreboard_shows_progress_when_there_is_no_champion_and_the_table_when_there_is(tmp_path):
    panel, _, _ = make_panel(drift=np.linspace(-0.002, 0.004, 40))
    panel.bench["NIFTYBEES"] = 0.0004
    preds = pd.concat([predict.make_predictions(panel, i, NOW, "r", "c") for i in range(240, 300)])
    scores = score.score_matured(panel, preds, set(), ref_model="rev_5")
    state = {**champion.DEFAULT_STATE}
    none = graduation.section(panel, preds, scores, state, None, ["mom_12_1"])
    assert "no champion, so nothing can graduate" in none and "of 500" in none
    empty = graduation.section(panel, preds, scores.iloc[0:0], state, None, ["mom_12_1"])
    assert "0 of 500" in empty
    seat = {**state, "champion": "mom_12_1", "champion_since": "2021-01-01"}
    text = graduation.section(panel, preds, scores, seat, None, [])
    assert "Champion `mom_12_1`" in text and "G5 against Nifty after costs and taxes" in text and "by hand" in text
    out = tmp_path / "sb.md"
    sims = report.run_sims(panel, preds, 240, 319)
    report.write_scoreboard(out, scores, sims, 60, "now", graduation=text)
    assert "after_tax_total_return" in out.read_text() and "Graduation (Phase 4)" in out.read_text()


def test_momentum_fund_rows_appear_only_when_the_fund_covers_the_window():
    panel, _, _ = make_panel(drift=np.linspace(-0.002, 0.004, 40))
    panel.bench["NIFTYBEES"] = 0.0004
    preds = pd.concat([predict.make_predictions(panel, i, NOW, "r", "c") for i in range(240, 300)])
    label = lambda sims, sym: sims[sims.portfolio.str.startswith(sym)]
    assert label(report.run_sims(panel, preds, 240, 319), "MOM30IETF").empty        # not in the data: no row, not zeros
    panel.bench["MOM30IETF"] = 0.001
    late = pd.Series(0.001, index=panel.dates)
    late.iloc[:260] = np.nan                                                        # listed inside the window
    panel.bench["MOMENTUM50"] = late
    sims = report.run_sims(panel, preds, 240, 319)
    fund, nifty = label(sims, "MOM30IETF").iloc[0], label(sims, "NIFTYBEES").iloc[0]
    assert fund.total_return == pytest.approx(1.001 ** 79 - 1, abs=1e-4)
    assert 0 < fund.after_tax_total_return < fund.total_return                      # costs and tax on exit
    assert fund.total_return > nifty.total_return and fund.after_tax_total_return > nifty.after_tax_total_return
    assert label(sims, "MOMENTUM50").empty
    assert label(report.run_sims(panel, preds, 265, 319), "MOMENTUM50").shape[0] == 1
    text = report.sim_table(sims)
    assert "Nifty 200 Momentum 30 fund" in text and "Nifty 50 price index" not in text
