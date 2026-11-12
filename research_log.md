# Research log

Pre-registered hypotheses and their results. A hypothesis is written here **before** it is tested.
Any change made after seeing results is a new trial with a new number.

## Standing design decisions (owner-approved 2026-11-12)

| Decision | Choice |
|---|---|
| Universe | Top 500 NSE EQ-series stocks by trailing 126-session median traded value, rebuilt each month-end. A month-end list applies from the first prediction made in the next calendar month (the code cannot know a month has ended until the next one starts) |
| Holdout | 2025-11-12 .. 2026-11-11, stored outside the project in `~/nse_holdout_LOCKED` |
| Holdout access | Production daily run only, and only to compute features for live predictions. Research code is blocked by `config.assert_readable` |
| Tamper evidence | Git commit after every run, pushed to a private GitHub repo |
| Scheduler | launchd on this Mac, ~20:30 IST on trading days. Missed days are skipped, never backfilled |
| Money | None. Paper only until the owner explicitly decides otherwise |

## Evaluation rules that apply to every trial

1. **Long-only.** Overnight short selling is not available to retail in cash equities. The tradeable
   test is a long-only top-bucket portfolio against the equal-weight universe. Long-short spreads may be
   reported as a diagnostic but never decide anything.
2. **Investable total-return benchmark.** "Nifty 50 buy and hold" is the NIFTYBEES ETF: dividends are
   inside it and it is net of fund costs, which is what a retail holder earns. (The official TRI
   endpoint refuses automated requests.) The stock-picking hurdle is the whole universe held in equal
   weight, re-formed monthly, paying the same costs as the models. A costless daily-rebalanced
   average is not used: it overstated that by about 10 points over the two rehearsal years.
3. **1-day horizon is a diagnostic.** It gives the fastest statistical feedback but cannot pay for
   delivery costs. Tradeable claims are made only at 5 and 20 sessions.
4. **Entry at the next session's open** with slippage; no fill if the stock is locked at a price band.
5. **Holdout budget.** Each look at the locked holdout is a trial. Budget: 3 looks in total. After
   that, the forward record is the only untouched test.
6. **available_at.** A feature may use a data point only if its `available_at` is at or before the
   prediction timestamp.

## Phase 0 — reality check (2026-11-12)

### What a solo, zero-budget researcher can expect in NSE cash equities

The most likely outcome is that nothing beats the known factor premia after costs and tax. That is
a legitimate result, and the system is built to reach it cheaply.

A realistic success looks like this:
- Forward rank IC of 0.02–0.04 at 5–20 sessions on the liquid 500.
- A long-only tilt beating the equal-weight universe by a few percent a year before tax, with
  tracking error around 8–12%. That is an information ratio of roughly 0.3–0.6.
- Edge concentrated outside the top 100 names, where institutions cannot deploy size.

What is not realistic: reliable daily direction calls, Sharpe above 2, or anything that survives
at a 1-day holding period.

### Why costs decide the horizon (rates verified 2026-11-12, re-verify before Phase 1 freezes them)

Delivery round trip, per rupee traded: STT 0.1% buy + 0.1% sell, stamp duty 0.015% on buy, NSE
transaction charge 0.00307% a side, SEBI fee 0.0001% a side, 18% GST on the charges, DP charge about
Rs 16 per sell. That is about 0.22% before slippage, and 0.35–0.6% after realistic slippage on a
top-500 name.

| Holding period | Round trips a year | Cost drag if fully turned over |
|---|---|---|
| 1 session | ~250 | far above any plausible gross edge |
| 5 sessions | ~50 | ~18–30% a year |
| 20 sessions | ~12 | ~4–7% a year |

Short-term capital gains are taxed at 20%, which takes another fifth of any gross profit.

### How long until forward results mean anything

t-stat of the mean IC = mean IC / sd of IC × sqrt(independent periods). The Phase 0 planning value
for the sd was 0.10. The rehearsal measured 0.10–0.14 for momentum and reversal, so the table uses
0.13 (revised 2026-11-12).

| Horizon | Independent periods a year | True IC needed for t = 2 in 1 year | Time to t = 2 if true IC is 0.02 |
|---|---|---|---|
| 1 session | ~250 | 0.016 | ~8 months |
| 5 sessions | ~50 | 0.037 | ~3.4 years |
| 20 sessions | ~12 | 0.074 | ~13 years |

Portfolio P&L is weaker still: confirming an excess Sharpe of 0.5 at t = 2 takes about 16 years.
So skill will be judged on IC, with the simulated portfolio as a sanity check on tradeability.

Planning conclusion: about 8 months before the 1-day diagnostic can say anything about a weak signal,
2–3 years before a 5-day claim is credible, and 20-day results stay provisional for many years. A
candidate signal has to be considerably stronger than IC 0.02, or be an event signal judged per event
instead of per day, to be confirmed in a useful time.

### Regulatory flags (SEBI)

- Personal research and trading your own account: no registration.
- Sharing signals or recommendations with others, paid or free, in a way that amounts to investment
  advice or research: SEBI (Research Analysts) Regulations. Registration is required before doing it.
- Managing other people's money: Portfolio Manager or Investment Adviser registration.
- Automating orders later: the retail algo framework has applied in full since 1 April 2026. Orders go
  through the broker's API with an exchange algo ID. A self-built algo below the exchange's order-rate
  threshold (10 orders a second on NSE) needs no separate registration, and may be used only for your
  own and immediate family's accounts.

## Phase 1 — definitions frozen before the forward record (2026-11-12)

| Item | Definition |
|---|---|
| Prediction time | Evening run after the session's files are public (scheduled 20:30 IST). A prediction for as-of session t must be written before 09:00 IST on the next calendar day, or it is never written |
| Target | Total return from the open of session t+1 to the open of session t+1+h, for h = 1, 5, 20 |
| Rank IC | Spearman correlation across ranked universe members between the model's rank and that return |
| IC t-stat | mean IC / sd of IC × sqrt(days / h). Dividing by h is a deliberately conservative allowance for overlapping targets |
| Hit rate | Share of top-decile names that beat the universe median |
| p_beat | Model's probability that a stock beats the universe median. Baselines: 0.5 + slope × (rank − 0.5), slope fitted on 2012 to Oct 2023 and frozen in `models/baselines_v1.json` |
| Paper portfolio | Long-only top 20, re-formed every h sessions (h = 5, 20), Rs 10 lakh, trades at next open, 10 bps slippage a side, full delivery charges, no buy at an upper lock, sells retried at a lower lock, averaged over all start days, pre-tax |
| Stocks that stop trading | Headline: held at last price. Also reported: written to zero after 60 silent sessions |
| Baselines | `random` (control), `mom_12_1`, `rev_5`. Benchmarks: NIFTYBEES, the universe held in equal weight after costs, Nifty 50 price |

## Hypothesis template

```
### T-000N  <short name>            registered: YYYY-MM-DD   status: registered | tested | shadow | retired
Mechanism      : who behaves suboptimally or bears risk, and why
Why it survives: what stops arbitrage
Novelty        : new / known family (name it)
Data           : sources and available_at rule
Design         : universe, horizon, feature definition, walk-forward splits, purge/embargo, costs
Pass criteria  : fixed numbers, set before testing
Falsified if   : ...
Expected life  : ...
Result         : (filled after) evidence for and against, deflated Sharpe, trials to date
```

## Trials

None yet. Phase 2 starts after Phase 1 is approved.
