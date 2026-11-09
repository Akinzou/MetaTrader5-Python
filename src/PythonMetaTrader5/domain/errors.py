"""Typed failure vocabulary shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PythonMetaTrader5.domain.market import TradeReceipt


class ErrorKind(Enum):
    INVALID_ARGUMENT = "invalid_argument"
    INVALID_VOLUME = "invalid_volume"
    INVALID_PRICE = "invalid_price"
    INVALID_STOPS = "invalid_stops"
    INVALID_FILLING = "invalid_filling"
    NO_MONEY = "no_money"
    MARKET_CLOSED = "market_closed"
    TRADE_DISABLED = "trade_disabled"
    ALGO_TRADING_DISABLED = "algo_trading_disabled"
    LIMIT_REACHED = "limit_reached"
    # Only part of the volume was executed; the rest is still open/unfilled.
    PARTIAL_FILL = "partial_fill"
    # The request may or may not have reached the trade server: never auto-retried.
    OUTCOME_UNKNOWN = "outcome_unknown"
    RETRIES_EXHAUSTED = "retries_exhausted"
    REJECTED = "rejected"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    NO_PRICE = "no_price"
    TERMINAL_ERROR = "terminal_error"
    # The terminal reports symbol data that cannot price an order (a point of 0,
    # a NaN tick size, a volume step of 0). Unlike TERMINAL_ERROR it does not
    # clear on a resend, so it has its own kind: a bot must escalate, not retry.
    BROKEN_SYMBOL_DATA = "broken_symbol_data"
    CONNECTION_FAILED = "connection_failed"


@dataclass(frozen=True, slots=True)
class TradeError:
    kind: ErrorKind
    message: str
    retcode: int | None = None
    # Kept so callers (and the 2.x facade) can inspect the broker's raw answer.
    receipt: TradeReceipt | None = None
    # Set when the failure concerns one position/order of a batch operation.
    ticket: int | None = None

    def __str__(self) -> str:
        code = f" (retcode {self.retcode})" if self.retcode is not None else ""
        ticket = f" [ticket {self.ticket}]" if self.ticket is not None else ""
        return f"{self.kind.value}: {self.message}{code}{ticket}"
