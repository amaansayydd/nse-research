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
### T-000N  <short name>            registered: YYYY-MM-DD   status: tested | tested | shadow | retired
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
| Tradeable (event) | Mean excess minus one round trip (0.45% on Rs 50,000 with slippage) above zero, also when entry is one session later |
| Deflated Sharpe | Reported for the long-only excess return, with the trial count. Not a gate: with 14 years and about 10% tracking error it cannot confirm an information ratio below about 0.7. IC is the powered test; the portfolio only has to not contradict it |
| Too good | IC above 0.06, excess Sharpe above 1.5 or event excess above 5%: frozen as INVESTIGATE until a leak audit is done |
| Robustness | Three sub-periods, three liquidity buckets, and the parameter changes listed in each registration. Reported, never used to pick a better version. Sector splits are not possible yet: there is no point-in-time sector data |
| Walk-forward | None of the first three signals fits a parameter, so every year is out of sample for fitting. A fitted model must use `stats.walk_forward_splits` (expanding window, purge of h+1 sessions, 5-session embargo) |
| Trial count | Each T- registration is one trial. Listed robustness variants are not trials because none can be adopted. Adopting a variant, or any change after seeing results, is a new T- number |
| What a PASS earns | A shadow slot in Phase 3. Nothing more. The forward record decides |

Known gap: the daily bundles carry almost no announcement or board-meeting text from March to
November 2022 (data/README.md F30). Text-based trials have no signal in those months.

## Phase 3 rules v1 (frozen 2026-11-13, before any challenger prediction that counts)

Sized with `python -m nsr.research.phase3_plan` (research-window backtests, planning only; output in
`research/results/phase3_plan.json`). Code: `nsr.champion`, `nsr.monitor`, `nsr.ensemble`.

| Item | Rule |
|---|---|
| Champion seat | Empty. Baselines are yardsticks and never hold it. While it is empty the reference to beat is `mom_12_1`, the strongest known effect here. Once there is a champion, it is the reference |
| Shadow | A candidate that passes Phase 2 predicts inside the same scheduled run as the baselines, to the same log. At most 3 challengers at a time (enforced in `nsr.models`). A challenger that fails or can rank fewer than 100 names is silent that day; it can never stop the baselines |
| Every comparison is a trial | Each challenger gets an F- row in `trial_ledger.csv` when it starts. N = challengers ever started, including retired ones. It never goes down |
| Decision horizon | 20 sessions: the horizon every current challenger was registered at, and the shortest one at which a top-20 book pays its costs |
| Minimum period | 250 scored sessions at 20 sessions (about a year, four results seasons, twelve independent windows). Nothing is decided earlier, whatever the numbers |
| Checkpoints | Decisions are read only at 250, 375, 500, ... scored sessions, on the sessions up to that checkpoint. The scoreboard shows the running numbers but they decide nothing between checkpoints |
| Statistic | `ic_ex_ref`: the challenger's daily rank IC after the reference's ranks are regressed out of its ranks. t = mean / sd x sqrt(sessions / 20). Noise the two models share cancels, so this is the sharpest valid test of "does it know something the reference does not" |
| Margin | t of `ic_ex_ref` at least c(N) = the normal quantile at 1 - 0.025/N: 1.96, 2.24, 2.39, 2.58 for N = 1, 2, 3, 5 |
| Also required | Challenger's mean forward IC above zero and above the reference's on the same sessions; top-decile mean excess above zero; simulated top 20 (20-session hold, after costs, up to the checkpoint) at least the reference's and the universe hurdle; `random` shows no skill (abs t below 3 at every horizon), otherwise everything freezes for a scorer audit |
| Two eligible at once | The one with the higher mean forward IC at 20 sessions |
| What eligibility earns | The owner's holdout check (one of the 3 looks) and the owner's decision. Only then is `champion.json` changed and the promotion written in `changelog.md` |
| Reversible | The former champion stays in the daily run for at least 250 sessions. It returns to the seat if the new champion is retired by the decay rule, or if at a checkpoint the champion's mean IC is below the former champion's with a paired t at or below -1.96 |
| Futility | From 500 scored sessions, a challenger whose `ic_ex_ref` t is below 0.5 at a checkpoint is retired and gets a postmortem. Its slot frees; N does not change |
| Decay monitor | One-sided CUSUM on each model's forward IC at 1, 5 and 20 sessions, sampled every h sessions so observations share no outcome days. In-control level: half the backtest IC (`models/expected_ic_v1.json`). It tests for a fall to zero, with about one false alarm per stream in 5,000 sessions. An alarm marks the model `decaying` and dates the change (the point the statistic last sat at zero) |
| Retirement | A challenger or champion is retired when it is `decaying` and its mean IC at 20 sessions over the last 250 scored sessions is at or below zero. A postmortem (POSTMORTEM command) is written to `lessons.md`. Baselines are flagged but never retired |
| Ensemble | `ens_mom_ear` (T-0004). Component weights start equal and move only on matured forward 20-session ICs, shrunk by 500 pseudo-days at IC 0.02. Weights used are logged in `ensemble_weights.csv`. A retired component leaves the ensemble at the next version |
| Voiding | A (date, model) can be struck from scoring only for a process failure and only before any outcome for it is scored. The rows stay in `predictions.csv`; the reason goes in `void_predictions.csv` and `changelog.md` |
| Learning | Every retirement, promotion and failed batch adds to `lessons.md`, including the family scorecard there, which sets the prior for the next hypothesis in that family |
| What counts | Only the forward scoreboard. Backtests size the test and set expectations; they never decide |

### Why this margin, and how long it will take

The obvious test, challenger IC minus reference IC, is close to useless at 20 sessions. In the
backtest the ensemble beats momentum by 0.006 of IC a day with a paired sd of 0.032; reaching
t = 2.24 on that takes about 3,000 sessions (12 years). So the margin is placed on `ic_ex_ref`, and
the head-to-head is required only in direction.

Sessions needed for the `ic_ex_ref` t to reach c(2) = 2.24 at 20 sessions (N = 2 today):

| Challenger | Backtest `ic_ex_ref` (mean, sd) | If the backtest holds in full | If half of it survives |
|---|---|---|---|
| `ear_drift_60` | 0.034, 0.070 | about 420 sessions (first possible checkpoint: 500, two years) | about 1,660 (6.6 years) |
| `ens_mom_ear` | 0.028, 0.063 | about 510 sessions (checkpoint 625, 2.5 years) | about 2,060 (8 years) |

Results drift alone also has to beat momentum's raw IC in direction, which the backtest says it
does not (0.041 against 0.051), so the ensemble is the likelier route to the seat. Checking twice a
year raises the chance of a false "eligible" above the nominal 2.5% (roughly 5 to 8% over eight
checkpoints). That is accepted because eligibility only earns a holdout check, a promotion is
reversible, and no money is involved.

Decay detection is slow for the same reason. An edge that vanished today would take about 410
sessions to raise the alarm on results drift's 1-session stream and about 900 on its 20-session
stream; momentum takes about 1,070 and 1,580.

### Incident, 2026-11-13 07:56: unfinished code ran live

The scheduled job still ran whatever was in the working folder. The 07:56 run picked up Phase 3
code that was half written and not committed. It appended 489 `ens_mom_ear` rows for as-of
2026-11-12 (labelled with commit c4dc8a4, which does not contain that code), then crashed while
writing the scoreboard and logged FAIL. No baseline row was affected and nothing had been scored.
Those 489 rows are void (`void_predictions.csv`): they stay in the log and are never scored. The
same run exposed that `ear_drift_60` was silent because the notice parser read nothing (data/README
F31). Fixes: the job now runs a pinned copy of committed code (`scripts/deploy.sh`), a report
failure can no longer fail a run, and the dry run prints what every model would produce.

### Verification before go-live (2026-11-13)

- 125 tests pass on the deployed copy, including one that the live `ear_drift_60` equals the
  backtested signal on a synthetic panel with reschedules, repeat notices and weekend meetings.
- Real data: over the 496 rehearsal sessions the live code logged 203,620 `ear_drift_60` scores; every
  one equals the backtest's (largest difference 0.0), with the same names every day
  (`research/results/parity_ear_drift_60.json`).
- Dress rehearsal with all five models: PASS on every check, including rebuild-from-raw as of three
  dates and the overwritten-future test (`rehearsal/REPORT.md`).
- Live dry run from the deployed copy: 10,202 notices over 162 sessions, none empty; `ear_drift_60`
  ranks 444 names (backtest average 439), `ens_mom_ear` 498.
- One real run of the scheduled job from the pinned copy: exit 0, scoreboard written, pushed.
- Worth knowing: replayed over the last two research years, which the backtest had already seen,
  neither challenger met the rule at the 375-session checkpoint (t 1.92 and 2.13 against 2.24).
  A year and a half is not enough even in sample.

## Phase 4 graduation criteria v1 (frozen 2026-11-13, before any forward score exists)

Graduation is the point at which the owner may *consider* real capital. It decides nothing by
itself: real capital always needs the owner's explicit decision. Only the forward record counts.
Tax and regulation were checked on 2026-11-13 (sources in `live_trading.md`).

| # | Criterion | Requirement |
|---|---|---|
| G1 | Standing | The model is the champion (Phase 3 rule plus the owner's holdout check), has held the seat for at least 250 scored sessions, and is not `decaying` |
| G2 | Minimum duration | At least 500 scored sessions of its own forward predictions at 20 sessions (two years). The window must contain a fall of 10% or more in NIFTYBEES from a peak; if the market never fell that far, the minimum is 750 sessions |
| G3 | IC | Mean forward rank IC at 20 sessions of at least 0.02, and positive at 5 sessions |
| G4 | t-stat | t of the 20-session IC at least 2.0 (mean / sd x sqrt(sessions / 20)) |
| G5 | Against Nifty after costs and taxes | Paper portfolio (top 20, 20-session hold, Rs 10 lakh, all charges and slippage), with capital-gains tax paid each financial year and the book liquidated at the end, must beat NIFTYBEES bought, held and liquidated the same way by at least 3 percentage points a year |
| G6 | Against the universe | The same portfolio before tax must beat the universe held after costs. Otherwise the result is small-cap exposure, not stock picking |
| G7 | Drawdown | Worst fall of the paper portfolio no deeper than the larger of 25% and 1.5 times NIFTYBEES's worst fall in the window. Worst fall relative to the universe no deeper than 15% |
| G8 | Record integrity | Predictions written on at least 95% of sessions in the window; `random` shows no skill (abs t below 3 at every horizon); nothing voided in the last 250 sessions |
| G9 | Owner's checks (by hand) | Cost schedule matched to a real contract note from the broker to be used; tax treatment confirmed with a chartered accountant; broker API access and static IP in place |

Tracked by `nsr.graduation` and shown on the scoreboard. G9 is never ticked by code.

### Why these numbers

- **IC 0.02 and t 2.0.** 0.02 is half the weakest backtest IC among the current candidates; below it
  the top-20 book cannot be expected to clear costs and tax. t = 2.0 is asked of the model's own IC,
  on top of the Phase 3 margin on what it adds and the holdout check, which are separate evidence.
- **No t-stat on profit.** Confirming an excess Sharpe of 0.5 takes about 16 years, so a significance
  test on the paper P&L could never be met. The P&L has to clear fixed margins instead (G5 to G7);
  the statistical burden sits on IC.
- **3 points over Nifty.** The simulation assumes 10 bps of slippage a side. If the truth is 30 bps,
  a book that turns over about 5 times a year loses another 2 points a year. 3 points leaves that
  and a little more.
- **Tax.** Short-term gains on listed shares are taxed at 20% and long-term gains at 12.5% above
  Rs 1.25 lakh a year, plus 4% cess. A 20-session book is almost all short-term; NIFTYBEES held for
  two years is long-term. The comparison is made after that asymmetry. Dividends (taxed at slab
  rate) are ignored on both sides, which favours the paper portfolio slightly. If the tax office
  treats frequent trading as business income the rate is the slab rate; the scoreboard also shows
  the result at 31.2%.
- **Drawdown.** Limits are relative to the market because a long-only book cannot avoid a crash. The
  backtests fell 41% to 54% at their worst over 14 years; the 25% floor is what a two-year window
  should stay inside unless something is wrong. Tracking error was about 11% a year, so a 15% fall
  against the universe is a rare event for a working model.
- **A bad market in the window.** Two calm years say nothing about how the book behaves when
  everything falls and sells are blocked at lower bands.

### How long, honestly

Sessions for the 20-session IC to reach t = 2.0:

| Model | If the backtest holds in full | If half survives |
|---|---|---|
| `ear_drift_60` | about 280 | about 1,110 |
| `ens_mom_ear` | about 620 | about 2,480 |
| `mom_12_1` (for scale) | about 890 | about 3,550 |

A challenger needs roughly 500 to 625 sessions to be promoted and 250 more in the seat, so the
earliest graduation is about three to three and a half years away if the backtests hold in full. If
half the backtest edge survives, it is closer to ten. Nothing in the design can shorten that except
stronger or more independent signals.

### Pipeline check of the tracker (2026-11-13, not evidence)

The tracker was run on the dress rehearsal (the last two research years, which the backtests had
already seen) as if `ens_mom_ear` held the seat. It met 2 of the 8 measured criteria. Its top 20
returned 19.3% a year before tax against 15.7% for the universe, but 15.1% after tax against 15.1%
for NIFTYBEES after tax, with a 29% drawdown against the 25% limit and an IC t of 0.6. Over those
two years `ear_drift_60`'s top 20 made 40.0% before tax and 30.8% after, against 31.7% for
NIFTYBEES after tax. The bar is real: on recent in-sample data the best candidates do not clear it.
Adding the tax bookkeeping left every pre-tax number in the rehearsal unchanged.

## Trials

### T-0001  Delivery-backed moves (deliv_ret_corr_60)      registered: 2026-11-12   status: tested
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
Result         : FAIL (tested 2026-11-12, 3 hypotheses registered, required t 3.0).
                 For: rank IC at 20 sessions 0.028, t 3.33, positive in 12 of 14 years; residual
                 IC after known effects 0.011, t 2.06; look-ahead test exact.
                 Against: the top decile earned nothing extra (-0.05% per 20 sessions) and the
                 long-only top 20 lagged the universe by 6.1% a year after costs (4 winning years
                 of 14). No IC in the 100 most liquid names (t -0.6); all of it is in ranks
                 251-500 (t 4.4). Window 120 drops to t 2.7, residual t 1.2.
                 Reading: the score correlates -0.30 with volatility. Rank IC rewards a low-volatility
                 tilt because volatile stocks have a lower median return, without the high-ranked
                 names earning more on average. The IC is real as a ranking statistic and useless
                 for a long-only book. Deflated Sharpe of the excess return: 0.00.
                 Not adopted. Inverting it or using it as a filter would be a new trial.

### T-0002  Results-day reaction drift (ear_drift_60)      registered: 2026-11-12   status: tested
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
Result         : PASS (tested 2026-11-12, 3 hypotheses registered, required t 3.0). Known effect:
                 this is a baseline-grade signal, not a discovery.
                 For: rank IC at 20 sessions 0.041, sd 0.076, t 6.84 over 3,235 sessions, positive in
                 13 of 14 years; residual IC after momentum, reversal, 60-day return, volatility and
                 liquidity 0.027, t 5.96, positive in all 14 years; top decile +0.79% per 20 sessions
                 before costs; long-only top 20 beat the universe by 5.3% a year after costs (4.9% if
                 silent holdings go to zero), 9 winning years of 14, excess Sharpe 0.53, deflated
                 Sharpe 0.86 with 3 trials. All four variants positive (t 3.5 to 5.9).
                 Against: 2025 is flat to negative (IC 0.001 in H1, -0.021 in H2; top decile -0.24%),
                 the worst stretch in the sample, about 2 standard errors below the long-run mean.
                 Weak in the 100 most liquid names (IC 0.017, t 1.7); most of it is in ranks 251-500
                 (0.054, t 7.6), where real fills are worst. Maximum drawdown -54%: it is a long-only
                 equity book. 9 winning years of 14 is not a steady edge. No scores from March to
                 November 2022 (missing notices). The one-session reaction variant has residual t 1.9.
                 In the same harness plain 12-1 momentum scored IC 0.051 (t 3.9) and its top 20 beat
                 the universe by 9.5% a year, so this does not beat momentum; it adds to it
                 (correlation with momentum 0.10, with 60-day return 0.31).
                 Post-hoc attacks (not pre-registered, `research/results/T-0002_posthoc.json`):
                 using the score 1 or 2 sessions late leaves IC at 0.040 and 0.039; a placebo that
                 measures the same 2-session return 30 sessions after the meeting gives IC 0.009,
                 t 1.6, residual t 0.8, so the effect belongs to results days; scores 30-59 sessions
                 old still predict (IC 0.040) because the 20-session target then covers the next
                 results date, the known persistence of earnings surprises.
                 Status: candidate for a Phase 3 shadow slot. Holdout look not spent.

### T-0003  Order-win announcements (order_win)      registered: 2026-11-12   status: tested
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
Result         : FAIL (tested 2026-11-12, 3 hypotheses registered, required t 3.0).
                 1,690 scored events. Mean excess over 20 sessions -0.23% (clustered t -0.61), hit
                 rate 43%, positive in 5 of 13 years with 10 or more events. After one round trip
                 -0.68%; entering a session later -0.32%.
                 Against the hypothesis, and significant: the first 5 sessions after an order-win
                 announcement lose 0.67% to the universe (t -4.7), 0.26% on the first day (t -4.0).
                 The news is in the price before the evening file; what follows is give-back.
                 For: 2022-2025 is positive (+0.93%, t 1.3, 497 events). Not significant.
                 Not adopted. "Avoid buying for 5 sessions after an order announcement" is a new
                 hypothesis and would need its own registration.

### T-0004  Momentum plus results-reaction ensemble (ens_mom_ear)      registered: 2026-11-12   status: tested
Mechanism      : No new mechanism. Two known effects whose scores are nearly unrelated (correlation
                 0.10) are averaged, so their errors partly cancel. It should lift IC per unit of
                 noise and soften each part's dead stretches (momentum since late 2023, results
                 drift in 2025).
Why it survives: Same as its parts.
Novelty        : Known effects combined. A pass makes it a baseline-grade challenger, not a discovery.
Data           : As B-002 and T-0002. Nothing new.
Design         : Each evening every component's score becomes a rank percentile among universe
                 members that traded that day. A component with fewer than 100 scored names is
                 absent that day. A missing percentile counts as 0.5. Score = weighted sum.
                 Weight of component k is proportional to max(0, m_k), with
                 m_k = (500 x 0.02 + sum of its matured 20-session rank ICs) / (500 + their count);
                 equal weights if every m_k is zero. Only ICs whose target window has closed by
                 that evening are used. The backtest counts from the first session of the data; the
                 live run counts from the first forward prediction, so live weights start equal.
                 Code: `nsr.ensemble`, shared by the backtest and the daily run. Primary horizon 20.
                 Protocol v1.
Variants       : fixed equal weights; fixed 2/3 momentum; fixed 1/3 momentum.
Pass criteria  : Protocol v1, all gates. Also reported, not a gate: IC and long-only result against
                 momentum alone.
Tripwire       : The parts have ICs of 0.051 and 0.041, so the ensemble may exceed the 0.06 "too
                 good" line. If it does, the audit is: the look-ahead test, the two component
                 results already on file, and whether the ensemble IC is what two signals with those
                 ICs and that correlation imply. It stays INVESTIGATE unless all three are clean.
Falsified if   : IC t below 3, residual IC t below 2, or the top 20 does not beat the universe after
                 costs.
Expected life  : As its parts.
Prior          : About 70% for the IC gates (both parts pass them alone), about 50% for every gate.
Result         : PASS (tested 2026-11-12, 4 hypotheses registered, required t 3.0). Known effects
                 combined: a baseline-grade challenger, not a discovery.
                 For: rank IC at 20 sessions 0.057, sd 0.159, t 4.69 over 3,415 sessions, positive in
                 13 of 14 years; residual IC 0.020, t 4.69; top decile +1.11% per 20 sessions before
                 costs; long-only top 20 beat the universe by 16.3% a year after costs (17.1% if
                 silent holdings go to zero), 12 winning years of 14, excess Sharpe 1.27, deflated
                 Sharpe 0.91 with 4 trials, maximum drawdown -41%, turnover 4.8 times a year.
                 Variants: equal weights 0.056 (t 5.2), 2/3 momentum 0.057 (t 4.6), 1/3 momentum
                 0.050 (t 5.9).
                 Against: it is mostly momentum. Its score correlates 0.90 with 12-1 momentum (the
                 shifting weights settled near 2/3 momentum) and its IC is as noisy as momentum's
                 (sd 0.159). Against momentum alone the IC gain is 0.006 a day (paired t 2.4 over 14
                 years): small. 2025 is negative (-0.017); 2016 and 2020 are near zero; 2022-2025 has
                 IC 0.033, t 1.9. Most of the IC is in ranks 251-500 (0.072, t 6.1; top 100: 0.037,
                 t 2.2). The shifting weights added nothing over equal weights in the backtest.
                 The portfolio result is larger than the IC gain suggests (16.3% a year against 9.5%
                 for momentum and 5.3% for results drift) and sits just under the excess-Sharpe
                 tripwire (1.27 against 1.5). Checked: the look-ahead test is exact, the IC is what
                 two signals with ICs 0.051 and 0.041 and correlation 0.10 imply (about 0.06), and
                 the top-decile return (1.11% per 20 sessions) is in line with a top-20 book. No
                 leak found, but a top-20 backtest in small names flatters; expect less forward.
                 Status: Phase 3 shadow slot. Holdout look not spent.

### Harness validation (2026-11-12, before any trial was scored)

`python -m nsr.research.validate` → `research/results/controls.json`.

| Control | 20-session IC (t) | Top 20 vs universe, after costs | Check |
|---|---|---|---|
| Pure noise | -0.0001 (-0.03); residual t 0.11 | -7.8% a year | no skill at any horizon, loses its costs: pass |
| `mom_12_1` | 0.051 (3.92), 12 of 14 years | +9.5% a year, excess Sharpe 0.71 | rehearsal-window IC 0.002 matches the production scorer (0.002) |
| `rev_5` | 0.009 (1.04); 5-session IC 0.031 (6.98) | -21.4% a year | rehearsal-window 1- and 5-session IC 0.032 and 0.037 match the production scorer (0.032, 0.036) |

These are baselines measured on the research window. They are hurdles, not discoveries. One reporting
fix was made after this validation and before the trials: turnover and cost drag are now scaled by
average equity instead of starting capital (no gate uses them).

### Batch 1 summary (2026-11-12)

3 hypotheses registered, 3 run, 1 pass. Benjamini-Hochberg at 10% keeps T-0001 and T-0002 on the IC
test; T-0001 then fails the tradeable gate. Trials to date: 3. Holdout looks used: 0 of 3.

Queue for batch 2 (ideas only; none is registered and none has been looked at):
1. Promoter and insider open-market purchases (PIT disclosures API, structured, timestamped). Needs ingest.
2. Earnings surprise from reported numbers (financial-results API) to pair with the price reaction in T-0002.
3. Quarterly shareholding changes: promoter, FII and mutual-fund stake changes (shareholding API).
4. Avoid-after-news: the 5-session give-back seen in T-0003, as a filter on other signals' buys.
5. A fitted combination of momentum and results reaction (first use of the walk-forward splitter).
