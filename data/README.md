# Data: sources, timing rules and known flaws

Built 2026-11-12, rebuilt 2026-11-14 to add two benchmark funds (every earlier row unchanged).
Research window 2010-01-04 .. 2025-11-11: 3,935 trading days, 6,264,574 price rows, 2,948 securities
(including three benchmark funds: NIFTYBEES, MOM30IETF, MOMENTUM50). Numbers below come from `data/clean/build_report.json`; rerun
`python -m nsr.build` to refresh them.

## Date regimes

| Regime | Trade dates | Where | Who may read |
|---|---|---|---|
| Research | 2010-01-04 .. 2025-11-11 | `data/raw`, `data/clean` | everything |
| Locked holdout | 2025-11-12 .. 2026-11-11 (248 sessions) | `~/nse_holdout_LOCKED/raw` | scheduled production run only, for live features |
| Forward | 2026-11-12 onward | `data/raw` (collected by the daily run) | everything |

The production panel (`~/nse_production/clean`) is rebuilt by every daily run from all three regimes.
Because it contains holdout-window rows it lives outside the project, and `Panel.load` refuses to
open it unless the caller is the production run.

Holdout files were written to disk without being opened. Only size and SHA-256 were recorded
(`~/nse_holdout_LOCKED/raw/manifest.csv`).

## Sources in use (all free, all verified reachable on 2026-11-12)

| Source | URL pattern | From | What we take |
|---|---|---|---|
| Daily "PR" bundle | `nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PRddmmyy.zip` | 2010 | `pd` prices for all series plus index levels and Nifty 50 flag; `bc` corporate actions; `bh` price-band hits; `mcap` shares and market cap (from 2024-02-01); `bm` board-meeting notices (parsed by `nsr.notices`, used by the results-drift challenger) and `an` announcement text (parsed for research only) |
| Delivery positions | `.../archives/equities/mto/MTO_ddmmyyyy.DAT` | 2010 | deliverable quantity per security |
| Classic bhavcopy | `.../content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip` | 1994–Jul 2024 | fallback prices for days whose PR bundle is misfiled |
| Corporate-actions register | `www.nseindia.com/api/corporates-corporateActions` (cookie session) | 2010 | ex-date, action text, face value. 33,512 rows |
| Symbol changes | `.../content/equities/symbolchange.csv` | all | rename links, cut at the holdout start when loaded |

## Verified available, not ingested yet (build when a hypothesis needs them)

| Data | Endpoint | Timestamp quality |
|---|---|---|
| Announcements | `api/corporate-announcements` | exact (`an_dt`, to the second) |
| Financial results | `api/corporates-financial-results` | exact (`broadCastDate`), but no numbers: one XBRL file per filing. Its date filter does not work; query by symbol. An unfiltered call returns the latest filings, which are inside the holdout window: never call it unfiltered |
| Shareholding patterns | `api/corporate-share-holdings-master` | exact (`broadcastDate`); promoter and public percentages are in the list itself. Full coverage only from the March 2022 quarter (about 2,000 filings a quarter; 18 to 49 before that) |
| Insider trades (PIT) | `api/corporates-pit` | **ingested 2026-11-13** for research (`nsr.research.filings`), 2016 onward, broadcast time to the minute |
| Bulk and block deals | `api/historicalOR/bulk-block-short-deals` | trade date only |
| Pledges | `api/corporate-pledgedata` | returned empty for Oct 2025; needs a second look |
| Trading holidays | `api/holiday-master?type=trading` | current year |
| Index valuation | `content/indices/ind_close_all_ddmmyyyy.csv` | from 2013; P/E, P/B, dividend yield |
| Full bhavcopy with delivery | `products/content/sec_bhavdata_full_ddmmyyyy.csv` | 2020 works, 2016 is 404 |
| UDiFF bhavcopy (has ISIN) | `content/cm/BhavCopy_NSE_CM_0_0_0_yyyymmdd_F_0000.csv.zip` | from mid-2024 |

Not verified this session: FII/DII flow history (NSE only serves the current day; NSDL/SEBI archives
need checking) and total-return index history (the niftyindices.com endpoint refused the request).

## available_at rules

| Data | available_at | Basis |
|---|---|---|
| Prices, delivery, band hits, index levels for trade date D (historical) | D 20:00 IST | **Assumed.** `available_at_assumed = True` |
| The same, collected live | actual fetch time | recorded by the daily run |
| Corporate action | 20:00 IST on the first day a daily file printed it; if never printed, the ex-date | observed for 97% of actions |
| Universe membership decided on month-end t | t 20:00 IST, effective next session | by construction |

A feature may use a row only if its `available_at` is at or before the prediction timestamp.

## How returns are built

NSE's printed previous close is not adjusted on ex-dates, and outside ex-dates it always equals the
last traded close. So each day's return is computed inside that day's row:

    base   = prev_close × adj          adj = product of split / bonus / rights factors on that day
    ret_cc = (close + div) / base − 1  close-to-close total return
    ret_on = (open + div) / base − 1   previous close to open
    ret_id = close / open − 1          open to close

Adjusted price *levels* are deliberately not stored. Build any cumulative series forward from returns.

## Known flaws

Each one says what goes wrong and how the build handles it.

### Timing

- **F1. Publication times are assumed.** NSE never recorded when historical files went up. 20:00 IST
  is conservative for normal days, wrong for the occasional late-night publication. A backtest that
  "runs" at 20:30 may use data that was not actually out yet on those days.
- **F2. The register has no publication time.** It is used for what happened on an ex-date, not for
  when it became known. Using "action announced" as a feature needs the announcements API instead.
- **F3. Holdout files are unvalidated.** They were never opened, so a misfiled day (see F10) inside
  the holdout would only be caught by the production run's date check.

### Corporate actions

- **F4. 415 actions cannot be quantified** (demergers, schemes of arrangement, capital reductions,
  bonus in another share class, rights bundled with warrants). The 236 affected returns are blank.
  A holder is in effect treated as flat that day, which misstates demerger-day P&L.
- **F5. Rights factors are approximate.** Issue price is taken as premium plus the face value the
  register shows today, which may be a post-split face value.
- **F6. 75 dividends have no amount.** That ex-date return is understated by the dividend.
- **F7. Two different dividends of the same amount on one ex-date count once.** Side effect of the
  de-duplication that stops reworded entries being counted twice.
- **F8. 34 rows where a parsed factor contradicts the ex-date open.** Return blanked, not guessed.
  Typical cause: the stock was suspended across the ex-date and NSE had already adjusted the base.
- **F9. The daily Bc file is incomplete from about 2022** (it never printed the 2024 Welspun or 2025
  Shriram Finance splits). Fixed by using the register as primary; 981 actions exist only in the
  daily file. The live run must therefore fetch the register daily, not rely on the bundle alone.
- **F10. Ex-date returns may carry residual error.** In the 2010–11 sample, split and bonus ex-days
  average +2.6%. That may be the documented ex-date effect or leftover factor error. Robustness
  checks should be repeated with ex-days excluded.

### Source errors

- **F11. NSE files the wrong data under some dates.** `PR020118.zip` holds 2 Jan 2019; the build
  detects it from the inner file names and uses the classic bhavcopy for 2018-01-02 (no index rows,
  no band hits, Nifty 50 flag false that day). `PR060424.zip` holds 4 Jun 2024 and is ignored (6 Apr
  2024 was not a session). An MTO file for Saturday 2019-06-22 has no price file and is ignored.
- **F12. 8 sessions have no band-hit file.** `band_hit` is missing on those days.
- **F13. No second vendor cross-check.** Prices are as printed by NSE. Reliance, TCS, Infosys, HDFC
  Bank, ITC and Wipro total-return multiples were reconciled by hand against their known bonus and
  split history. A sample check against BSE or another vendor is an open item.

### Identity and survivorship

- **F14. No delisting returns.** When a stock stops trading, its last return is its last trade.
  Nothing is applied for a suspension that ends at zero, or for a merger payout. 277 of the 1,428
  securities that were ever in the universe no longer trade. The simulator reports two bounds: the
  holding stays at its last price (headline), or it is written to zero after 60 silent sessions.
  The truth for a merger is between the two; for a bankruptcy it is the second.
- **F15. Renames.** 350 renames are linked. 236 could not be (216 predate 2010; the rest lack data
  on one side) and 9 were rejected because the price did not carry over. 11 pairs where both
  tickers exist stay unlinked: such a stock looks like a delisting followed by a new listing, so its
  lookback features restart and the return across the rename is lost.
- **F16. Reused tickers are split by a rule of thumb**: a ticker silent for more than 400 days
  starts a new security.
- **F17. 2,067 rows where NSE's base price is not the last traded close.** 98% follow a gap of more
  than 7 days (relisting after suspension). Return blanked.
- **F18. Fund exclusion is heuristic.** 420 tickers ever printed in the ETF section, or named like a
  fund, are dropped along with rights-entitlement tickers (327,623 rows). An ETF delisted before the
  ETF section existed could remain; a keyword scan of universe names found none.
- **F19. Nifty 50 membership flag is approximate**: exactly 50 names on 3,419 days, 51 on 371,
  49 on 144. There is no free point-in-time Nifty 500 list; the project uses its own universe.

### Coverage

- **F20. Market cap, shares outstanding and face value start 2024-02-01.** Before that, size has to
  be proxied by traded value.
- **F21. Delivery quantity is missing for 6–11% of rows**, all in trade-for-trade series (BE, BZ),
  where delivery is 100% by rule.
- **F22. Index data is price-only.** Names change over time (S&P CNX Nifty, CNX Nifty, Nifty 50).
  The official total-return index endpoint refuses automated requests. The buy-and-hold benchmark
  is therefore the NIFTYBEES ETF (12.0% a year over 2010–2025 against 11.0% for the price index),
  which holds its dividends and is net of fund costs. There is no investable Nifty 500 benchmark.
- **F27. A costless daily-rebalanced equal-weight average is not a fair benchmark.** Over the two
  rehearsal years it returned 44.6% against 33.1% for the same universe bought, held about a month
  and charged costs. The scoreboard uses the second.
- **F28. Three sessions have a bundle but no usable equity rows**: Sundays 2010-05-16 and 2012-11-11
  (mock sessions with near-empty files) and the misfiled 2024-04-06. They are not trading days here.
- **F23. `locked_limit` is a proxy.** The band-hit file says a stock touched its band, not the band
  size or how long it stayed there. `locked_limit` = band hit and high equals low, which misses
  stocks that locked after trading a range. 0.22% of universe rows are locked by this definition.
- **F24. Special sessions are ordinary rows.** Muhurat, budget-day and disaster-recovery Saturday
  sessions (22 in the research window) have thin volume and are not flagged.
- **F25. 25 moves beyond ±40% are kept as real** (Yes Bank, DHFL, Jet Airways, Infibeam and
  similar). The recent ones were checked by eye; older ones were not verified one by one.

- **F29. The corporate-actions register is a snapshot with today's tickers.** It files some old
  actions under a company's later name (Ami Organics' Sept 2024 dividend sits under ACUTAAS). The
  build translates those labels with the rename list. The rehearsal caught this: a rebuild "as of"
  Nov 2024 missed that dividend until the label translation was allowed to use later renames.
  Renames dated inside the locked holdout are still not used by research builds, so an action whose
  company was renamed during the holdout year can be missing if the daily file also lacks it.

- **F30. Announcement and board-meeting text is missing for most of 2022.** The `An` and `Bm` files
  inside the daily bundle are empty or absent from March to November 2022 (announcements: 110
  sessions with none; board meetings: 203), and on 12-22 sessions a year in 2023-2025. Text-based
  signals have nothing to work with on those days. A live text signal would need the announcements
  API as a second source. Parsed tables: `data/clean/research_text/` (1.12 million announcements
  excluding mutual-fund NAV notices, 125,928 board-meeting notices). Some records have the subject
  heading spliced into the first word of the body ("UjaasUpdatess Energy"); keyword rules still match.

- **F31. NSE changed the text layout on 2025-10-13.** In `An` and `Bm` files the company name used
  to be padded from the ticker by several spaces; since then there is one space. The parser read no
  board-meeting notices from that date until it was fixed on 2026-11-13 (`nsr.notices.BM` now accepts
  both; on every bundle up to 2025-10-10 it returns exactly the old records). No registered result
  changed: every scored session ends by 2025-10-09, and a notice filed later cannot enter an earlier
  score (checked by recomputing T-0002's scores with the old and new tables). The announcement parser
  was fixed on 2026-11-14 (`nsr.research.text`). An `An` line carries no date to anchor on, so the
  parser picks the rule per file: a padded file keeps the old two-space rule, a single-space file
  uses 'Name TICKER : text' where the ticker must hold a letter. Checks: all 1,119,583 rows up to
  2025-10-10 are identical after the rebuild; 19,475 rows were added for the 20 sessions from
  2025-10-13 to 2025-11-11 (498 of the 500 universe names have one, against 488 and 495 in the same
  weeks of 2024 and 2023). Squeezing every old file to the new layout and parsing it with the new
  rule gives the old record starts back with 215 false starts in 6.97 million (4 of them on a real
  ticker) and no wrong ticker; the 1,942 it misses are records with a ticker made only of digits,
  which are mutual-fund NAV lines (dropped anyway) except 7. A false start cuts the true record's
  text short at that line. No registered result changed: no row up to 2025-10-10 changed and every
  scored session ends by 2025-10-09. In production the notices come from the last 240 days of bundles,
  holdout window included, and are stored in `~/nse_production/clean/board_meetings.parquet`. The run
  notes flag a window with no notices or more than 30 empty sessions.

- **F32. Insider-trade disclosures (PIT), ingested 2026-11-13.** 327,803 rows, 2016-01-01 to
  2025-11-11, raw JSON in `data/raw/pit_api`, table in `data/clean/research_filings/insider.parquet`.
  Flaws: (a) the API files old records under the company's ticker of today; they are put back on
  the ticker of the day with the rename list, which lifts the share that maps to a security from
  91-95% to 97-99% for 2016-2022; (b) renames dated inside the holdout are invisible to research,
  so those companies' records are lost (mapped share 92% in 2024, 87% in 2025, which also counts SME
  tickers that are not in the panel); (c) one filing lists many transactions, so rows are keyed by
  `did`, not `pid`; (d) coverage thins after 2021 as promoter trades moved to system-driven
  disclosure at the depositories: raw rows fall from 58,542 in 2018 to 16,991 in 2024; pledge
  releases by promoters of universe stocks fall to 11 in 2025; (e) nothing before 2016.

- **F33. Benchmark funds are priced at their traded close, not at the value of their holdings**
  (added 2026-11-14). `MOM30IETF` (from 2022-08-10, earlier ticker ICICIMOM30) and `MOMENTUM50` (from
  2024-09-30) are kept as benchmark series, numbered after every stock so that adding them changed no
  other row. `MOM30IETF` traded under 100 times a day until 2024: its daily correlation with its index
  is 0.89 and the worst one-day gap 8.9%, though yearly returns agree within 1 point. Its 10-for-1
  unit split of 2022-08-12 is not in the register; a benchmark fund's return is blanked on any
  session where it moves more than 40% with no recorded action. Use the series from 2022-08-16.

### Settlement

- **F26. T+1 settlement (phased in 2022–23) is not modelled.** Paper predictions do not need it.
  A live system would: sale proceeds and buying power depend on it.

## Universe

Top 500 by 126-session median traded value, EQ series, at least 100 traded days in the window,
rebuilt each month-end (185 rebalances, median 16 names replaced). Latest: rank 1 trades about
Rs 1,640 crore a day, rank 500 about Rs 18 crore. Equal-weighted, it returned 11.9% a year
(total return) against 11.7% for the Nifty 500 price index, with a daily correlation of 0.90 and the
small-cap tilt you would expect. That is a plumbing check, not a result.
