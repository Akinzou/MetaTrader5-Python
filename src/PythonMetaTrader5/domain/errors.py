"""Typed failure vocabulary shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PythonMetaTrader5.domain.market import TradeReceipt


class ErrorKind(Enum):
    """Why a call failed. What to do about each kind is in the user guide."""

    INVALID_ARGUMENT = "invalid_argument"
    """An argument MT5 would misread or refuse: checked before sending, or refused by the server."""
    INVALID_VOLUME = "invalid_volume"
    """The volume is outside the symbol's min/max, off its step, or above the position's."""
    INVALID_PRICE = "invalid_price"
    """The price is invalid, e.g. a limit on the wrong side of the market."""
    INVALID_STOPS = "invalid_stops"
    """A stop-loss or take-profit is zero, negative, not finite or refused by the server."""
    INVALID_FILLING = "invalid_filling"
    """The server refused the filling mode chosen from the symbol's flags (10030)."""
    NO_MONEY = "no_money"
    """Not enough margin."""
    MARKET_CLOSED = "market_closed"
    """The market for the symbol is closed."""
    TRADE_DISABLED = "trade_disabled"
    """Trading is not allowed now: on the symbol or account, or in this direction."""
    ALGO_TRADING_DISABLED = "algo_trading_disabled"
    """Algo Trading is off in the terminal (10027) or forbidden by the server (10026)."""
    LIMIT_REACHED = "limit_reached"
    """A broker limit on orders, positions or volume is reached."""
    PARTIAL_FILL = "partial_fill"
    """Only part of the volume was executed; the rest is still open or unfilled."""
    OUTCOME_UNKNOWN = "outcome_unknown"
    """The request may or may not have reached the server: check positions, never auto-retried."""
    RETRIES_EXHAUSTED = "retries_exhausted"
    """Requotes, price changes, no quotes or too many requests outlasted the `RetryPolicy`."""
    REJECTED = "rejected"
    """Any other refusal by the server, unknown retcodes included."""
    SYMBOL_NOT_FOUND = "symbol_not_found"
    """The terminal does not know the symbol."""
    NO_PRICE = "no_price"
    """The symbol has no quote."""
    TERMINAL_ERROR = "terminal_error"
    """A terminal call failed before anything reached the trade server."""
    BROKEN_SYMBOL_DATA = "broken_symbol_data"
    """The terminal's symbol data cannot price an order (point 0, NaN tick size, step 0).

    Unlike TERMINAL_ERROR it does not clear on a resend, so it has its own kind:
    a bot must escalate, not retry.
    """
    CONNECTION_FAILED = "connection_failed"
    """The terminal did not start or the login failed."""


@dataclass(frozen=True, slots=True)
class TradeError:
    """An expected failure: its `ErrorKind`, a message and the broker's answer if any.

    ``receipt`` is the broker's raw answer when there was one; ``ticket`` names
    the position or order when the failure concerns one item of a batch.
    """

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
