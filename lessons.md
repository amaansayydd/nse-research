# Lessons

What has been learned about this market and this pipeline. Each entry says whether it is a
**finding** (measured here) or a **prior** (believed, not yet tested here). Priors steer which
hypotheses get proposed; they are not evidence.

## Findings — data (Phase 0, 2026-11-12)

- NSE's printed previous close is **not** adjusted on ex-dates. A split shows up as a -80% or -90%
  "return" unless repaired. Checked on LITL 04-Jan-2010 (576.70 prev close, 59.40 open).
- Corporate-action text is free-form and misspelt ("FV-SPTLRS10TORS2"). A parser alone is not
  enough; every parsed factor is checked against the ex-date open, and the return is blanked when
  they disagree.
- About 10% of dividends are first published without an amount ("INTERIM DIVIDEND") and get the
  amount in a later file. Always use the latest text for an ex-date.
- Outside ex-dates the printed previous close always equals the prior traded close (zero mismatches
  in 2010–2011), so daily returns can be computed inside a single day's row.
- Actions appear in the daily file a median of 17 days before the ex-date, so ex-dates are known in
  advance and are point-in-time safe.
- NSE's CORP_IND flag is unreliable across years (absent in the 2016 sample). Do not depend on it.
- A list of current symbols (EQUITY_L.csv, index constituent lists) is a survivorship trap. The
  universe is rebuilt from daily files instead.

## Findings — pipeline and measurement (Phase 1 rehearsal, 2026-11-12)

These come from the two-year replay. They are facts about costs and measurement, not evidence that
any signal works.

- A costless, daily-rebalanced equal-weight average is a flattering benchmark: 44.6% over the two
  rehearsal years against 33.1% for the same stocks bought, held a month and charged costs.
- Measured cost drag for a 20-name portfolio on Rs 10 lakh: about 22–24% a year when names rotate
  every 5 sessions, about 6% a year at 20 sessions. Momentum turns over far less on its own
  (5–11 times a year), costing 2.4–4.9% a year.
- 5-day reversal had a rank IC near 0.03 at 1 and 5 sessions in the replay and still lost about 5% a
  year after costs at a 5-session hold. A positive gross IC is not a tradeable edge.
- The day-to-day standard deviation of rank IC is about 0.045 for pure noise (close to 1/sqrt(500))
  but 0.10–0.14 for momentum and reversal, because real signals load on common factors. Forward
  confirmation therefore takes roughly 3 times longer than a noise calculation suggests.
- Security ids are only stable inside one build. Anything stored across days (the prediction log)
  must be matched by date and ticker.
- The code cannot know a month has ended until the next one starts. Any "month-end" rule has to be
  written so that live and replay agree.

- A "current snapshot" source hides look-ahead in its labels, not just its values. NSE's
  corporate-actions register files old actions under today's ticker. The replay looked fine; only
  rebuilding the whole dataset as of a past date exposed it (one stock, one Rs 3 dividend). Every
  new non-point-in-time source needs that rebuild-as-of test before it is trusted.
- A random control must be reproducible from the log alone. Seeding it by array position made it
  change whenever a rebuild renumbered securities; it is now a hash of date and ticker.

## Priors — market (untested here)

- Delivery costs of ~0.22% a round trip before slippage make 1-day holding periods unviable.
- Long-short backtests overstate what a retail cash account can do; the short leg is not tradeable.
- Much of the apparent small-cap edge in India sits in stocks locked at price bands.
- Known factor effects (momentum, low volatility, quality) probably exist in India but are baselines,
  not discoveries.
- India-specific disclosures with exact timestamps (insider trades, pledges, bulk deals, results,
  shareholding) are less crowded than price-only signals.

## Process lessons

- State a design conflict before building around it. The 12-month holdout collides with live
  features that need 12 months of history; it was resolved by owner decision (production-only read).
