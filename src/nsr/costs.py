"""Indian cash-equity delivery costs.

Rates checked on 2026-11-12 against NSE's levies page and two discount brokers'
published schedules. VERIFY against your own broker's contract note before
relying on any simulated number: brokerage and DP charges differ by broker.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    brokerage: float = 0.0          # delivery brokerage rate (zero at discount brokers)
    stt: float = 0.001              # 0.1% on buy and on sell (delivery)
    stamp_buy: float = 0.00015      # 0.015% on buy only
    exchange_txn: float = 0.0000307  # NSE 0.00307% each side
    sebi: float = 0.000001          # Rs 10 per crore each side
    gst: float = 0.18               # on brokerage + exchange + SEBI charges
    dp_per_sell: float = 16.0       # rupees per scrip per sell day (broker + depository + GST)
    slippage: float = 0.0010        # 10 bps each side versus the opening price (ASSUMPTION)

    def _levies(self, notional: float) -> float:
        fees = notional * (self.brokerage + self.exchange_txn + self.sebi)
        return fees * (1 + self.gst) + notional * self.stt

    def buy(self, notional: float) -> float:
        """Rupee charges on a buy of `notional` (excluding slippage)."""
        return self._levies(notional) + notional * self.stamp_buy

    def sell(self, notional: float) -> float:
        """Rupee charges on a sell of `notional` (excluding slippage)."""
        return self._levies(notional) + self.dp_per_sell

    def round_trip_rate(self, notional: float) -> float:
        """All-in fraction lost on buying then selling `notional`, slippage included."""
        return (self.buy(notional) + self.sell(notional)) / notional + 2 * self.slippage
