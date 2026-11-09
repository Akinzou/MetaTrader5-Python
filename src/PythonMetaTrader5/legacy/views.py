"""Positions and receipts in the exact shapes the 2.x API returned.

2.x handed out raw MetaTrader5 objects (TradePosition, OrderSendResult), so
scripts read any field, index them and call ``_asdict()``. NamedTuples with the
same field names in the same order keep all three working.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from PythonMetaTrader5.domain.market import Position, TradeReceipt
from PythonMetaTrader5.domain.orders import Side

# MT5 POSITION_TYPE_BUY / POSITION_TYPE_SELL: 2.x callers compare `p.type == 0`.
_POSITION_TYPE = {Side.BUY: 0, Side.SELL: 1}

# The keys 2.x `as_dict=True` built by hand. A projection of as_object() rather
# than a second mapping, so the shared fields cannot drift apart; only sl/tp
# differ on purpose (None instead of 0.0, as in 2.x).
_V2_DICT_KEYS = (
    "ticket",
    "symbol",
    "type",
    "volume",
    "price_open",
    "sl",
    "tp",
    "price_current",
    "profit",
    "time",
    "magic",
    "comment",
)


class LegacyPosition(NamedTuple):
    """Field-for-field and in order the same as MetaTrader5.TradePosition."""

    ticket: int
    time: int
    time_msc: int
    time_update: int
    time_update_msc: int
    type: int
    magic: int
    identifier: int
    reason: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str
    external_id: str


class LegacyReceipt(NamedTuple):
    """Field-for-field and in order the same as MetaTrader5.OrderSendResult."""

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
    # The echoed TradeRequest is not kept by 3.x; always None.
    request: None = None


def as_object(p: Position) -> LegacyPosition:
    return LegacyPosition(
        ticket=p.ticket,
        time=p.time,
        time_msc=p.time_msc,
        time_update=p.time_update,
        time_update_msc=p.time_update_msc,
        type=_POSITION_TYPE[p.side],
        magic=p.magic,
        identifier=p.identifier,
        reason=p.reason,
        volume=p.volume,
        price_open=p.price_open,
        # Raw MT5 objects report a missing stop as 0.0; 2.x passed them through as is.
        sl=p.sl or 0.0,
        tp=p.tp or 0.0,
        price_current=p.price_current,
        swap=p.swap,
        profit=p.profit,
        symbol=p.symbol,
        comment=p.comment,
        external_id=p.external_id,
    )


def as_dict(p: Position) -> dict[str, Any]:
    row = as_object(p)._asdict()
    # 2.x `as_dict=True` used None for a missing stop, unlike the raw objects.
    return {key: row[key] for key in _V2_DICT_KEYS} | {"sl": p.sl, "tp": p.tp}


def as_receipt(receipt: TradeReceipt | None) -> LegacyReceipt | None:
    if receipt is None:
        return None
    return LegacyReceipt(
        retcode=receipt.retcode,
        deal=receipt.deal,
        order=receipt.order,
        volume=receipt.volume,
        price=receipt.price,
        bid=receipt.bid,
        ask=receipt.ask,
        comment=receipt.comment,
        request_id=receipt.request_id,
        retcode_external=receipt.retcode_external,
    )
