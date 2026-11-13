# What changes if this ever trades real money

Written 2026-11-13, in advance. Nothing here is switched on. The system is paper-only, and real
capital always needs the owner's explicit decision, after the graduation criteria in
`research_log.md` (Phase 4) are met. Nothing in this file is investment advice.

Items marked **VERIFY** were checked on the web on 2026-11-13 but must be confirmed with the broker
or a chartered accountant before any money moves.

## 1. What the paper record does not tell you

| Paper assumption | Reality |
|---|---|
| Fill at the opening price, 10 bps of slippage a side | The open is a call auction (09:00 to 09:08). A market order gets the auction price if it fills; a limit order may not fill at all. Small caps open with wide spreads. Real slippage is unknown until measured |
| Any size fills | True at Rs 50,000 a name in the top 500. Not true at 100 times that in rank 251-500, where the edge is strongest |
| Sells blocked only when a stock is locked at its lower band all session | Real exits also fail in thin books, and a stock under surveillance (ASM, GSM) can need full margin or trade once a week |
| No taxes in the headline numbers | Almost every gain of a 20-session book is short-term (section 3) |
| Sale proceeds are reusable at once | Settlement is T+1. Brokers let most of the sale value be used the same day, not always all. **VERIFY** with the broker |
| The run never fails | One Mac on a home connection. It already had one failed run in its first two days |
| No emotions | A 25% drawdown in real money feels different from a row in a table |

## 2. Rules for placing orders (SEBI retail algo framework, in force since 1 April 2026)

- Orders sent through a broker API are tagged at the exchange as algo orders. **VERIFY**
- A static IP registered with the broker is mandatory for API access, whatever the order rate.
- Under 10 orders a second per exchange no strategy registration is needed. This system would send
  about 20 orders a day.
- Plain market orders are not accepted through the API. Orders need a limit or market protection.
- A self-built algo may be used only for the owner's account and immediate family.
- Placing the same orders by hand in the broker's app needs none of this, and at 20 names every 20
  sessions it is practical. That is the recommended first stage.

Sources: NSE circular NSE/INVG/67858; Zerodha's note on the April 2026 changes.

## 3. Tax (checked 2026-11-13, **VERIFY** with a chartered accountant)

- Short-term capital gains on listed shares (held 12 months or less): 20% under section 111A, plus
  4% cess. No exemption. With cess, 20.8% of net gains.
- Long-term gains: 12.5% above Rs 1.25 lakh a year under section 112A.
- STT on delivery trades is 0.1% a side (unchanged in the 2026 Budget). It is in the cost model.
- Short-term losses can be set off against any capital gain and carried forward 8 years.
- Advance tax is due in instalments during the year if the liability exceeds Rs 10,000.
- Dividends are taxed at slab rate. The paper record ignores this.
- **Business income risk.** Frequent, systematic trading can be assessed as business income, taxed
  at slab rate (up to 30% plus surcharge and cess) and reported on ITR-3 with books of account.
  CBDT circular 6/2016 lets a taxpayer choose capital-gains treatment for listed shares held more
  than 12 months; it does not protect a 20-session book. The scoreboard's graduation table shows the
  result under both treatments. Settle this with an accountant before starting, and stay consistent.

## 4. Other regulation

- Trading your own money on your own research needs no registration.
- Sharing these predictions with anyone, paid or free, in a way that amounts to advice or research
  falls under SEBI's Research Analyst rules. Do not publish the signal list.
- Managing anyone else's money needs registration as a portfolio manager or investment adviser.

## 5. Staged start, if the owner decides to go ahead

Each stage has an exit test set now. Failing it means stepping back a stage, not pushing on.

| Stage | Capital | Length | Pass test |
|---|---|---|---|
| 0. Graduation | none | as long as it takes | Every criterion G1 to G9 met |
| 1. Pilot, orders by hand | 10% of the amount intended, at least Rs 2 lakh so 20 positions are not all fees | 60 sessions | Measured cost per round trip (fill against the official open, plus charges from contract notes) no more than 0.25 points above the model's 0.45%; every order placed as the system said |
| 2. Half | 50% | 120 sessions | Live book within 3 points of the paper book over the stage; no kill rule hit |
| 3. Full | 100% | ongoing | Reviewed every 125 sessions with the Phase 3 checkpoint |

The paper record keeps running in parallel throughout. The gap between the live book and the paper
book is the measure of everything the simulation gets wrong, and it goes on the scoreboard.

## 6. Kill rules for a live book (set now)

| Trigger | Action |
|---|---|
| Decay monitor marks the champion `decaying` | No new buys. Existing holdings run off at their 20-session exits |
| Champion retired or demoted | Same; restart only with a champion that has itself graduated |
| Live book down 25% from its peak, or 1.5 times NIFTYBEES's fall if that is larger | Stop buying, review. Restart needs a written decision |
| Live book 15% behind the universe from a relative peak | Same |
| Live book more than 5 points behind the paper book over 120 sessions | Stop: execution is broken, not the signal |
| Three failed or missed runs in a row | No trading until the run is fixed. A missed evening means no orders the next morning, never a guess |
| `random` control shows skill | Stop everything and audit the scorer |

## 7. Engineering that must exist first (not built)

1. A second machine or a small cloud server for the daily run, with an alert to the phone on
   failure. The Mac stays as the backup.
2. An order list written by the run: buys, sells and quantities for the next open, from the same
   code that writes predictions. Orders are never worked out by hand or in chat.
3. A fills log: what was ordered, what filled, at what price, read from contract notes. This is what
   measures slippage.
4. Corporate-action handling for real holdings (bonus, split, demerger) and a check against the
   demat statement every month.
5. A surveillance filter (ASM, GSM, T2T lists) so the book never buys what it cannot easily sell.
   This is new data and needs its own point-in-time source.
6. The cost model re-fitted to the broker's contract notes, and the tax model to the accountant's
   advice.

## 8. Size

At Rs 10 lakh a position is Rs 50,000: about 0.03% of a day's trading in the 500th most traded
stock (Rs 18 crore a day). Holding each position under 1% of a stock's median daily value caps the
book near Rs 3.6 crore. The paper results say nothing about sizes anywhere near that.
