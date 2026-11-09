"""In-memory stand-ins for the two process boundaries (terminal, clock)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from PythonMetaTrader5.application.ports import Credentials
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import PendingOrder, Position, Tick, TradeReceipt
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.symbol import SymbolSpec
from PythonMetaTrader5.result import Err, Ok, Result

EURUSD = SymbolSpec(
    name="EURUSD",
    digits=5,
    point=0.00001,
    tick_size=0.00001,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01,
    filling_flags=1,
)
XAUUSD = SymbolSpec(
    name="XAUUSD",
    digits=2,
    point=0.01,
    tick_size=0.01,
    volume_min=0.01,
    volume_max=50.0,
    volume_step=0.01,
    filling_flags=2,
)


def receipt(retcode: int = 10009, price: float = 0.0) -> TradeReceipt:
    return TradeReceipt(
        retcode=retcode,
        deal=1,
        order=1,
        volume=0.1,
        price=price,
        bid=0.0,
        ask=0.0,
        comment="",
        request_id=1,
    )


@dataclass
class FakeTerminal:
    specs: dict[str, SymbolSpec] = field(
        default_factory=lambda: {"EURUSD": EURUSD, "XAUUSD": XAUUSD}
    )
    ticks: dict[str, deque[Tick]] = field(default_factory=dict)
    retcodes: deque[int] = field(default_factory=deque)
    open_positions: list[Position] = field(default_factory=list)
    open_orders: list[PendingOrder] = field(default_factory=list)
    send_failure: TradeError | None = None
    connect_failure: TradeError | None = None
    sent: list[OrderRequest | CancelRequest] = field(default_factory=list)
    connected_with: list[Credentials] = field(default_factory=list)
    shut_down: bool = False

    def quote(self, symbol: str, *ticks: tuple[float, float]) -> None:
        self.ticks[symbol] = deque(Tick(bid, ask) for bid, ask in ticks)

    def connect(self, credentials: Credentials) -> Result[None, TradeError]:
        self.connected_with.append(credentials)
        return Err(self.connect_failure) if self.connect_failure else Ok(None)

    def shutdown(self) -> None:
        self.shut_down = True

    def symbol(self, name: str) -> Result[SymbolSpec, TradeError]:
        if name not in self.specs:
            return Err(TradeError(ErrorKind.SYMBOL_NOT_FOUND, name))
        return Ok(self.specs[name])

    def tick(self, name: str) -> Result[Tick, TradeError]:
        queue = self.ticks.get(name)
        if not queue:
            return Err(TradeError(ErrorKind.NO_PRICE, name))
        # The last quote sticks, earlier ones are consumed one per call.
        return Ok(queue.popleft() if len(queue) > 1 else queue[0])

    def send(self, request: OrderRequest | CancelRequest) -> Result[TradeReceipt, TradeError]:
        self.sent.append(request)
        if self.send_failure:
            return Err(self.send_failure)
        code = self.retcodes.popleft() if self.retcodes else 10009
        price = request.price if isinstance(request, OrderRequest) else 0.0
        return Ok(receipt(code, price))

    def positions(
        self, *, symbol: str | None = None, ticket: int | None = None
    ) -> Result[list[Position], TradeError]:
        return Ok(
            [
                p
                for p in self.open_positions
                if (symbol is None or p.symbol == symbol) and (ticket is None or p.ticket == ticket)
            ]
        )

    def pending_orders(
        self, *, symbol: str | None = None
    ) -> Result[list[PendingOrder], TradeError]:
        return Ok([o for o in self.open_orders if symbol is None or o.symbol == symbol])


@dataclass
class FakeClock:
    sleeps: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
