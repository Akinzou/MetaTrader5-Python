"""Positions in the exact shapes the 2.x API returned."""

from __future__ import annotations

from typing import Any, NamedTuple

from PythonMetaTrader5.domain.market import Position
from PythonMetaTrader5.domain.orders import Side

# MT5 POSITION_TYPE_BUY / POSITION_TYPE_SELL: 2.x callers compare `p.type == 0`.
_POSITION_TYPE = {Side.BUY: 0, Side.SELL: 1}


class LegacyPosition(NamedTuple):
    """Attribute-compatible with MT5's TradePosition for the fields 2.x documented."""

    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    profit: float
    time: int
    magic: int
    comment: str


def as_object(p: Position) -> LegacyPosition:
    # Raw MT5 objects report a missing stop as 0.0; 2.x passed them through as is.
    return LegacyPosition(
        p.ticket,
        p.symbol,
        _POSITION_TYPE[p.side],
        p.volume,
        p.price_open,
        p.sl or 0.0,
        p.tp or 0.0,
        p.price_current,
        p.profit,
        p.time,
        p.magic,
        p.comment,
    )


def as_dict(p: Position) -> dict[str, Any]:
    # 2.x `as_dict=True` used None for a missing stop, unlike the raw objects.
    return {**as_object(p)._asdict(), "sl": p.sl, "tp": p.tp}
