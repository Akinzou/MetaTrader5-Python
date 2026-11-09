"""The only two process boundaries of the library: the MT5 terminal and time."""

from __future__ import annotations

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
