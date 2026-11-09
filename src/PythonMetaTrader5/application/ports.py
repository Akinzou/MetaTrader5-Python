"""The only two process boundaries of the library: the MT5 terminal and time."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Protocol

from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.market import PendingOrder, Position, Tick, TradeReceipt
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.symbol import SymbolSpec
from PythonMetaTrader5.result import Result


@dataclass(frozen=True, slots=True)
class Credentials:
    login: int
    # repr=False keeps the password out of logs, tracebacks and debugger dumps.
    password: str = field(repr=False)
    server: str
    path: str | None = None
    timeout_ms: int = 60_000

    def __post_init__(self) -> None:
        # The type itself enforces the login rule, so no construction path can
        # hand MT5 True or a float that it would turn into another account.
        if parse_login(self.login) != self.login:
            raise ValueError(f"login must be a positive integer, got {self.login!r}")


def parse_login(login: object) -> int | None:
    """Account number from an int-like value or an ASCII digit string, else None.

    int() is deliberately avoided: int(True) == 1 and int(12345678.9) == 12345678
    would log into another account without any error, and int() accepts
    non-ASCII digits such as "\u0661\u0662\u0663".
    """
    if isinstance(login, bool):
        return None
    if isinstance(login, str):
        text = login.strip()
        number = int(text) if text.isascii() and text.isdecimal() else 0
    else:
        try:
            number = operator.index(login)  # type: ignore[arg-type]
        except TypeError:
            return None
    return number if number > 0 else None


class Terminal(Protocol):
    def connect(self, credentials: Credentials) -> Result[None, TradeError]: ...

    def shutdown(self) -> None: ...

    def symbol(self, name: str) -> Result[SymbolSpec, TradeError]: ...

    def tick(self, name: str) -> Result[Tick, TradeError]: ...

    def send(self, request: OrderRequest | CancelRequest) -> Result[TradeReceipt, TradeError]:
        """Err only when the request could not be delivered; broker refusals are receipts."""
        ...

    def positions(
        self, *, symbol: str | None = None, ticket: int | None = None
    ) -> Result[list[Position], TradeError]: ...

    def pending_orders(
        self, *, symbol: str | None = None
    ) -> Result[list[PendingOrder], TradeError]: ...


class Clock(Protocol):
    def sleep(self, seconds: float) -> None: ...
