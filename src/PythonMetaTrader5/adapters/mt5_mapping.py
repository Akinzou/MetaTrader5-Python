"""Translation between MetaTrader5's raw result objects and domain models.

Split out of mt5_terminal.py (300-line limit). Pure functions: they read fields
of MT5 objects but never call the terminal, so they need no session lock.
"""

from __future__ import annotations

from typing import Any

from PythonMetaTrader5.domain.market import PendingKind, PendingOrder, Position, TradeReceipt
from PythonMetaTrader5.domain.orders import Side

OrderTypes = dict[tuple[Side, PendingKind | None], int]


def order_type_table(mt5: Any) -> OrderTypes:
    return {
        (Side.BUY, None): mt5.ORDER_TYPE_BUY,
        (Side.SELL, None): mt5.ORDER_TYPE_SELL,
        (Side.BUY, PendingKind.LIMIT): mt5.ORDER_TYPE_BUY_LIMIT,
        (Side.SELL, PendingKind.LIMIT): mt5.ORDER_TYPE_SELL_LIMIT,
        (Side.BUY, PendingKind.STOP): mt5.ORDER_TYPE_BUY_STOP,
        (Side.SELL, PendingKind.STOP): mt5.ORDER_TYPE_SELL_STOP,
        (Side.BUY, PendingKind.STOP_LIMIT): mt5.ORDER_TYPE_BUY_STOP_LIMIT,
        (Side.SELL, PendingKind.STOP_LIMIT): mt5.ORDER_TYPE_SELL_STOP_LIMIT,
    }


def receipt(result: Any) -> TradeReceipt:
    return TradeReceipt(
        retcode=int(result.retcode),
        deal=int(result.deal),
        order=int(result.order),
        volume=float(result.volume),
        price=float(result.price),
        bid=float(result.bid),
        ask=float(result.ask),
        comment=str(result.comment),
        request_id=int(result.request_id),
        retcode_external=int(result.retcode_external),
    )


def position(p: Any, position_buy: int) -> Position:
    return Position(
        ticket=int(p.ticket),
        symbol=str(p.symbol),
        side=Side.BUY if p.type == position_buy else Side.SELL,
        volume=float(p.volume),
        price_open=float(p.price_open),
        # MT5 encodes "no stop" as 0.0, which is also a (useless) price.
        sl=float(p.sl) or None,
        tp=float(p.tp) or None,
        price_current=float(p.price_current),
        profit=float(p.profit),
        time=int(p.time),
        magic=int(p.magic),
        comment=str(p.comment),
        swap=float(p.swap),
        identifier=int(p.identifier),
        reason=int(p.reason),
        time_msc=int(p.time_msc),
        time_update=int(p.time_update),
        time_update_msc=int(p.time_update_msc),
        external_id=str(p.external_id),
    )


def pending_orders(
    raw: tuple[Any, ...], by_type: dict[int, tuple[Side, PendingKind]]
) -> list[PendingOrder]:
    orders = []
    for o in raw:
        key = by_type.get(int(o.type))
        # Market orders still being processed and close-by orders are not resting orders.
        if key is None:
            continue
        side, kind = key
        orders.append(
            PendingOrder(
                ticket=int(o.ticket),
                symbol=str(o.symbol),
                side=side,
                kind=kind,
                volume=float(o.volume_current),
                price=float(o.price_open),
                magic=int(o.magic),
                comment=str(o.comment),
            )
        )
    return orders
