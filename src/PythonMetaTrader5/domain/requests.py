"""Trade requests in domain terms; the terminal adapter translates them to MT5."""

from __future__ import annotations

from dataclasses import dataclass

from PythonMetaTrader5.domain.market import PendingKind
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.symbol import Filling


@dataclass(frozen=True, slots=True)
class OrderRequest:
    symbol: str
    side: Side
    volume: float
    price: float
    filling: Filling
    deviation: int
    magic: int
    comment: str = ""
    sl: float | None = None
    tp: float | None = None
    # Ticket of the position being closed; None opens a new position.
    position: int | None = None
    # None means a market deal; a kind means a pending order at `price`.
    pending: PendingKind | None = None


@dataclass(frozen=True, slots=True)
class CancelRequest:
    order: int
