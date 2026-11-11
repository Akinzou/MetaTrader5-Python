"""Read models returned by the terminal: quotes, positions, orders, receipts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from PythonMetaTrader5.domain.orders import Side


@dataclass(frozen=True, slots=True)
class Tick:
    """The current quote of a symbol."""

    bid: float
    ask: float

    def entry_price(self, side: Side) -> float:
        """The price a market order on ``side`` fills at: ask to buy, bid to sell."""
        return self.ask if side is Side.BUY else self.bid

    def exit_price(self, side: Side) -> float:
        """The price that closes a ``side`` position: bid for a long, ask for a short."""
        # Closing a long sells at bid, closing a short buys at ask.
        return self.entry_price(side.opposite)


@dataclass(frozen=True, slots=True)
class Position:
    """An open position. ``sl`` and ``tp`` are ``None`` when not set."""

    ticket: int
    symbol: str
    side: Side
    volume: float
    price_open: float
    sl: float | None
    tp: float | None
    price_current: float
    profit: float
    time: int
    magic: int
    comment: str
    # Kept although the 3.x API does not use them: 2.x returned the raw MT5
    # object, so its users may read any of them (swap for P&L, identifier on
    # netting accounts).
    swap: float
    identifier: int
    reason: int
    time_msc: int
    time_update: int
    time_update_msc: int
    external_id: str

    def to_dict(self) -> dict[str, Any]:
        """The fields as a dict, with ``side`` as its string value."""
        data = asdict(self)
        data["side"] = self.side.value
        return data


class PendingKind(Enum):
    """The type of a pending order."""

    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """A pending order waiting on the server."""

    ticket: int
    symbol: str
    side: Side
    kind: PendingKind
    volume: float
    price: float
    magic: int
    comment: str


@dataclass(frozen=True, slots=True)
class TradeReceipt:
    """Broker answer to a trade request.

    Field names mirror MetaTrader5's ``OrderSendResult`` on purpose, so 2.x code
    reading ``result.retcode`` / ``result.comment`` keeps working unchanged.
    """

    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request_id: int
    retcode_external: int
