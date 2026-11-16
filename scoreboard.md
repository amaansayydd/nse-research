# Scoreboard (forward-only)

Updated 2026-11-16 20:30 IST. Prediction days logged: 3. Days with a matured score: 1.

Only predictions written to `predictions.csv` before their outcome window opened are counted here.
Backtest and dress-rehearsal numbers never appear in this file.

## Rank IC by model and horizon

Target: return from the next session's open to the open h sessions later. `eff_obs` divides the day
count by the horizon because overlapping targets are not independent. An `ic_t` below 2 means nothing
yet. `days needed for t=2` assumes the IC measured so far is the true IC, which early on it is not.

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | ic_ex_ref_mean | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mom_12_1 | 1 | 1 | 1.0 | 2026-11-12 | 2026-11-12 | 0.1384 |  |  | 0.24% | 55.10% | 0.2489 |  |  |
| random | 1 | 1 | 1.0 | 2026-11-12 | 2026-11-12 | -0.0392 |  |  | 0.06% | 50.00% | 0.2500 | -0.0355 |  |
| rev_5 | 1 | 1 | 1.0 | 2026-11-12 | 2026-11-12 | 0.1170 |  |  | 0.89% | 62.00% | 0.2495 | 0.1158 |  |

`top_excess_mean`: top-decile mean return minus the universe mean, before costs. `top_hit`: share of
top-decile names beating the universe median. `brier`: 0.25 is what a coin flip scores. `ic_ex_ref_mean`:
rank IC left after the reference model's ranks are removed.

## Simulated long-only portfolios after costs

Top 20 names, Rs 1,000,000 paper capital, trades at the next open with 10 bps slippage a side,
full delivery charges, no fill at a locked band. Averaged over every possible start day. Pre-tax, except
`after_tax_total_return`: capital-gains tax paid each financial year (20% short-term, 12.5% long-term above
Rs 1.25 lakh, 4% cess) and the book sold at the end. The funds (NIFTYBEES and the two momentum funds) are
bought once, held and sold the same way, at a stock's charges, which slightly overstates what a fund costs.

| portfolio | hold | total_return | after_tax_total_return | cagr | vol | max_drawdown | turnover_per_year | cost_drag_per_year | unfilled_buys | blocked_sells | total_return_if_silent_holdings_go_to_zero | writeoffs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| universe, equal weight, all 500 (after costs) | 21d | -0.12% | -0.22% | -14.48% | 0.76% | -0.10% | 6.0 | 2.62% | 0.0 | 0.0 |  |  |
| NIFTYBEES buy and hold (no trading costs) | - | -0.21% | -0.63% | -23.43% | 9.95% | 0.00% |  |  |  |  |  |  |
| MOM30IETF buy and hold (Nifty 200 Momentum 30 fund) | - | 0.06% | -0.36% | 8.45% | 7.93% | -0.32% |  |  |  |  |  |  |
| MOMENTUM50 buy and hold (Nifty 500 Momentum 50 fund) | - | -1.52% | -1.94% | -85.49% | 33.53% | -2.25% |  |  |  |  |  |  |
| Nifty 50 price index (not investable) | - | -0.03% |  | -4.03% | 13.43% | 0.00% |  |  |  |  |  |  |
| random top 20 | 5d | -0.53% | -0.62% | -48.67% | 1.47% | -0.33% | 25.2 | 11.02% | 0.0 | 0.0 | -0.53% | 0.0 |
| random top 20 | 20d | -0.13% | -0.16% | -15.33% | 0.37% | -0.08% | 6.3 | 2.75% | 0.0 | 0.0 | -0.13% | 0.0 |
| mom_12_1 top 20 | 5d | -1.04% | -1.13% | -73.07% | 9.10% | -0.92% | 25.2 | 11.02% | 0.0 | 0.0 | -1.04% | 0.0 |
| mom_12_1 top 20 | 20d | -0.26% | -0.28% | -27.87% | 2.27% | -0.23% | 6.3 | 2.75% | 0.0 | 0.0 | -0.26% | 0.0 |
| rev_5 top 20 | 5d | -0.41% | -0.51% | -40.56% | 7.07% | -0.52% | 25.2 | 11.02% | 0.0 | 0.0 | -0.41% | 0.0 |
| rev_5 top 20 | 20d | -0.10% | -0.13% | -12.18% | 1.77% | -0.13% | 6.3 | 2.75% | 0.0 | 0.0 | -0.10% | 0.0 |
| ear_drift_60 top 20 | 5d | -0.34% | -0.39% | -34.94% | 3.82% | -0.34% | 12.6 | 5.51% | 0.0 | 0.0 | -0.34% | 0.0 |
| ear_drift_60 top 20 | 20d | -0.09% | -0.10% | -10.18% | 0.96% | -0.09% | 3.1 | 1.38% | 0.0 | 0.0 | -0.09% | 0.0 |
| ens_mom_ear top 20 | 5d | -0.51% | -0.56% | -47.78% | 5.77% | -0.51% | 12.6 | 5.51% | 0.0 | 0.0 | -0.51% | 0.0 |
| ens_mom_ear top 20 | 20d | -0.13% | -0.14% | -14.96% | 1.44% | -0.13% | 3.1 | 1.38% | 0.0 | 0.0 | -0.13% | 0.0 |

`random` is the control: any model that cannot beat it has shown nothing. The hurdle for a stock-picking
model is the first row (own the whole universe); the hurdle for bothering at all is NIFTYBEES. A model
that leans on momentum must also beat `MOM30IETF`: a fund that follows a published momentum rule and is
taxed only when sold. Fund rows use the fund's own closing price, which can stray from its holdings' value
on a thin day. Graduation criterion G5 is tested against the better of NIFTYBEES and `MOM30IETF` (criteria v1.1).

## Champion and challengers

Champion: **none (seat empty)**. Reference to beat: `mom_12_1`. Challengers ever started: 2.
A challenger is judged only at 250, 375, 500 ... scored sessions at the 20-session horizon. `ic_beyond_reference`
is its rank IC after the reference's ranks are removed; its t-stat must reach `required_t`, which rises
with every challenger ever started. Meeting the rule earns a holdout check by the owner, not a promotion.

| challenger | reference | scored_sessions | judged_on | ic | ic_t | reference_ic | ic_beyond_reference | beyond_t | top_decile_excess | required_t | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | mom_12_1 | 0 | 0 |  |  |  |  |  |  | 2.24 | too early: 0 of 250 sessions |
| ens_mom_ear | mom_12_1 | 0 | 0 |  |  |  |  |  |  | 2.24 | too early: 0 of 250 sessions |

Ensemble weights for the latest prediction: `mom_12_1` 0.500, `ear_drift_60` 0.500. They start equal and move only on matured forward 20-session ICs.

## Observed signals

Logged forward without a shadow slot (Phase 3 rules v1.1). An observed signal cannot become champion and
does not change the challengers' margin. Signals ever observed: 1, which sets `required_t`.
The label "confirmed forward" is read only at 250, 375, 500 ... evaluated sessions and needs 200 scored events,
`t` at least `required_t`, and a mean excess above one round trip of costs, also when entering a session later.
Running numbers between checkpoints decide nothing.

| signal | horizon | sessions | judged_on_sessions | events | mean_excess | t | required_t | after_costs | after_costs_one_session_later | status |
|---|---|---|---|---|---|---|---|---|---|---|
| results_advance_5d | 5 | 0 | 0 | 0 |  |  | 1.96 |  |  | too early: 0 of 250 sessions, 0 of 200 events |

Reported, not required:

| signal | hit_rate | median_excess | mean_minus_momentum_tenth | mean_excess_rank_1-100 | mean_excess_rank_101-250 | mean_excess_rank_251-500 |
|---|---|---|---|---|---|---|
| results_advance_5d |  |  |  |  |  |  |

## Decay monitor

One-sided CUSUM on each model's forward rank IC, sampled every h sessions. `expected_ic` is half the
backtest IC; an alarm means the IC has run below that for long enough to look like a change, and
gives the estimated start. `sessions_to_detect_total_loss` is how long an edge that vanished today
would take to raise the alarm: weak signals decay quietly.

| model | horizon | expected_ic | observations | forward_ic | cusum | alarm_at | state | sessions_to_detect_total_loss | retire_rule_met |
|---|---|---|---|---|---|---|---|---|---|
| mom_12_1 | 1 | 0.0062 | 1 | 0.1384 | 0.00 | 43.57 | ok | 1064 |  |
| mom_12_1 | 5 | 0.0158 | 0 |  | 0.00 | 19.51 | ok | 1175 |  |
| mom_12_1 | 20 | 0.0256 | 0 |  | 0.00 | 10.22 | ok | 1581 |  |
| rev_5 | 1 | 0.0114 | 1 | 0.1170 | 0.00 | 33.22 | ok | 506 |  |
| rev_5 | 5 | 0.0157 | 0 |  | 0.00 | 17.71 | ok | 898 |  |
| rev_5 | 20 | 0.0044 | 0 |  | 0.00 | 13.15 | ok | 3420 |  |
| ear_drift_60 | 1 | 0.0072 | 0 |  | 0.00 | 30.71 | ok | 412 |  |
| ear_drift_60 | 5 | 0.0135 | 0 |  | 0.00 | 15.25 | ok | 605 |  |
| ear_drift_60 | 20 | 0.0205 | 0 |  | 0.00 | 8.25 | ok | 891 |  |
| ens_mom_ear | 1 | 0.0077 | 0 |  | 0.00 | 38.71 | ok | 763 |  |
| ens_mom_ear | 5 | 0.0179 | 0 |  | 0.00 | 18.07 | ok | 949 |  |
| ens_mom_ear | 20 | 0.0285 | 0 |  | 0.00 | 9.65 | ok | 1347 |  |

## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

There is no champion, so nothing can graduate. Where each challenger stands on the criteria that can already be measured:

| model | scored_sessions | ic_20 | ic_t | t_needed | ic_5 |
|---|---|---|---|---|---|
| ear_drift_60 | 0 of 500 |  |  | 2.0 |  |
| ens_mom_ear | 0 of 500 |  |  | 2.0 |  |

