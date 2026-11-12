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

## Phase 2 protocol v1 (frozen 2026-11-12, before any trial was scored)

Code: `src/nsr/research/`. Run with `python -m nsr.research.run T-000N`; the runner refuses a trial
that has no row in `trial_ledger.csv`.

| Item | Rule |
|---|---|
| Data | Research window only. Scored sessions: 2012-01-02 to the last session whose 20-session target completes by 2025-11-11 |
| Target and universe | Same as the forward record: open of t+1 to open of t+1+h, liquid top 500, names that traded on t |
| Look-ahead test | Before scoring, the signal is recomputed on the dataset cut off at 5 sessions and must equal the full-history row exactly. A failure means the trial is not scored |
| Dense signal, primary test | Mean daily rank IC at the registered primary horizon, t = mean / sd x sqrt(days / h) |
| Event signal, primary test | Mean excess return per event over the equal-weight universe from the next open, standard error clustered by calendar month |
| Required t | max(3.0, Bonferroni at 5% one-sided over every T- hypothesis registered so far). 3.0 binds until about 37 hypotheses |
| False discovery rate | Benjamini-Hochberg at 10% over the primary p-values of all T- hypotheses. A registered trial that was never run counts as p = 1 |
| Stability | Effect positive in at least 70% of calendar years (events: years with 10 or more events) |
| Known effects | Signal ranks regressed each day on ranks of 12-1 momentum, 5-day reversal, 60-day return, 60-day volatility and traded value. IC of the residual must reach t = 2.0, otherwise it is a known effect in new clothing |
| Tradeable (dense) | Long-only top 20 re-formed every h sessions, all costs, must beat the universe held after costs over the whole window, also when silent holdings are written to zero |
| Tradeable (event) | Mean excess minus one round trip (about 0.44% with slippage) above zero, also when entry is one session later |
| Deflated Sharpe | Reported for the long-only excess return, with the trial count. Not a gate: with 14 years and about 10% tracking error it cannot confirm an information ratio below about 0.7. IC is the powered test; the portfolio only has to not contradict it |
| Too good | IC above 0.06, excess Sharpe above 1.5 or event excess above 5%: frozen as INVESTIGATE until a leak audit is done |
| Robustness | Three sub-periods, three liquidity buckets, and the parameter changes listed in each registration. Reported, never used to pick a better version. Sector splits are not possible yet: there is no point-in-time sector data |
| Walk-forward | None of the first three signals fits a parameter, so every year is out of sample for fitting. A fitted model must use `stats.walk_forward_splits` (expanding window, purge of h+1 sessions, 5-session embargo) |
| Trial count | Each T- registration is one trial. Listed robustness variants are not trials because none can be adopted. Adopting a variant, or any change after seeing results, is a new T- number |
| What a PASS earns | A shadow slot in Phase 3. Nothing more. The forward record decides |

Known gap: the daily bundles carry almost no announcement or board-meeting text from March to
November 2022 (data/README.md F30). Text-based trials have no signal in those months.

## Trials

### T-0001  Delivery-backed moves (deliv_ret_corr_60)      registered: 2026-11-12   status: registered
Mechanism      : NSE publishes how much of each stock's volume was taken for delivery. Intraday
                 traders must square off; delivery buyers and sellers are changing their holdings.
                 A stock that rises on high-delivery days and falls on low-delivery days is being
                 accumulated by holders, and its down-moves are speculative noise. Llorente, Michaely,
                 Saar and Wang (2002): informed-trade moves continue, liquidity-trade moves reverse.
Why it survives: Delivery data arrives after the close, is ignored by most price-only models, and
                 the effect, if any, sits in mid and small caps where institutions cannot deploy size.
Novelty        : Known family (volume-conditioned return continuation). The delivery split is an
                 India-specific measurement. A pass would be "partly new", not a new anomaly.
Data           : `deliv_qty`, `mto_qty`, `ret_cc` from the daily files. available_at D 20:00.
Design         : Score = trailing 60-session Pearson correlation (40 or more valid days) between
                 (delivery share minus that day's median delivery share across all stocks) and
                 (return minus that day's median return, clipped to +/-10%). Higher is better.
                 Dense. Primary horizon 20 sessions. Protocol v1.
Variants       : window 40; window 120; returns not clipped.
Pass criteria  : Protocol v1, all gates.
Falsified if   : IC t below 3 at 20 sessions, or the residual IC t is below 2.
Expected life  : Years if real. Delivery data is public and free, so it would decay if widely used.
Prior          : About 10-15% to pass every gate.
Result         : (pending)

### T-0002  Results-day reaction drift (ear_drift_60)      registered: 2026-11-12   status: registered
Mechanism      : Post-earnings-announcement drift. Investors under-react to results; the price
                 reaction on the results day is a surprise measure that needs no analyst forecasts
                 (Brandt, Kishore, Santa-Clara and Venkatachalam, 2008). Drift should be strongest
                 where coverage is thin.
Why it survives: Limited attention, and funds that cannot trade mid and small caps in size.
Novelty        : Known effect (post-earnings drift). A pass makes it a baseline, not a discovery.
                 It is tested because it is the best-documented effect at a 20-session horizon.
Data           : Board-meeting notices in the daily bundles (`Bm*.txt`) whose purpose mentions
                 results, filed on or before the meeting, at most 60 days ahead. A meeting is
                 dropped if a later notice filed on or before it names another date within 20 days.
                 Returns from the daily files. Usable from the evening the reaction window closes.
Design         : Reaction = sum over the first 2 sessions on or after the meeting date of (stock
                 return minus the universe's mean return). Score = latest reaction, carried for 60
                 sessions. Dense on days with 100 or more scored names. Primary horizon 20. Protocol v1.
Variants       : carried 20 or 40 sessions; 1-session and 3-session reaction.
Pass criteria  : Protocol v1, all gates.
Falsified if   : IC t below 3 at 20 sessions, or the residual IC t is below 2 (it is then just
                 momentum).
Expected life  : Long-lived elsewhere, but shrinking in liquid stocks.
Prior          : About 35% for the IC gates, about 15% to pass every gate.
Result         : (pending)

### T-0003  Order-win announcements (order_win)      registered: 2026-11-12   status: registered
Mechanism      : An order or contract win is hard information about future revenue for project
                 companies. It reaches the market as an unstructured press release. Outside the
                 large caps few analysts update the same day, so the price may adjust over weeks.
Why it survives: Reading and classifying free text is effort; the names are too small for most funds.
Novelty        : Known family (news drift), specific event type, India-specific text source.
Data           : Announcement text in the daily bundles (`An*.txt`). An event is known on the
                 evening of the bundle's date. Classifier v1 is the fixed keyword rule in
                 `signals.py` (ORDER_WIN and not ORDER_EXCLUDE), frozen after reading 45 sampled
                 matches (about 43 genuine) and before any return was looked at.
Design         : Event = a matching announcement for a universe member that traded that day, one
                 per stock per day, skipped if the stock had an event in the previous 5 sessions.
                 Enter at the next open. Primary horizon 20 sessions. Event test, Protocol v1.
                 About 1,700 events in the scored window.
Variants       : no cooldown; cooldown 20 sessions. Horizons 1 and 5 are reported.
Pass criteria  : Protocol v1, all gates.
Falsified if   : Mean excess at 20 sessions has clustered t below 3, or is below one round trip.
Expected life  : Short if real: text is easy to parse now.
Prior          : About 15% to pass every gate. The classifier cannot tell a large order from a
                 routine one, which dilutes any effect.
Result         : (pending)
