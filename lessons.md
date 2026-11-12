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
