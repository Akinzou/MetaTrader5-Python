"""A stand-in for the `MetaTrader5` module with its constants and call log."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

CONSTANTS = {
    "TRADE_ACTION_DEAL": 1,
    "TRADE_ACTION_PENDING": 5,
    "TRADE_ACTION_REMOVE": 8,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "ORDER_TYPE_BUY_LIMIT": 2,
    "ORDER_TYPE_SELL_LIMIT": 3,
    "ORDER_TYPE_BUY_STOP": 4,
    "ORDER_TYPE_SELL_STOP": 5,
    "ORDER_TYPE_BUY_STOP_LIMIT": 6,
    "ORDER_TYPE_SELL_STOP_LIMIT": 7,
    "ORDER_FILLING_FOK": 0,
    "ORDER_FILLING_IOC": 1,
    "ORDER_FILLING_RETURN": 2,
    "ORDER_TIME_GTC": 0,
    "POSITION_TYPE_BUY": 0,
    "POSITION_TYPE_SELL": 1,
    "SYMBOL_TRADE_EXECUTION_EXCHANGE": 3,
    "RES_S_OK": 1,
    "RES_E_INVALID_PARAMS": -2,
    "RES_E_NO_MEMORY": -3,
    "RES_E_NOT_FOUND": -4,
    "RES_E_INVALID_VERSION": -5,
    "RES_E_AUTH_FAILED": -6,
    "RES_E_UNSUPPORTED": -7,
    "RES_E_AUTO_TRADING_DISABLED": -8,
    "RES_E_INTERNAL_FAIL_INIT": -10003,
    "RES_E_INTERNAL_FAIL_CONNECT": -10004,
}


class FakeMT5:
    def __init__(self) -> None:
        for name, value in CONSTANTS.items():
            setattr(self, name, value)
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.initialize_ok = True
        self.error = (1, "Success")
        self.symbols: dict[str, SimpleNamespace] = {}
        self.ticks: dict[str, SimpleNamespace] = {}
        self.send_result: SimpleNamespace | None = SimpleNamespace(
            retcode=10009,
            deal=11,
            order=12,
            volume=0.1,
            price=1.1,
            bid=1.1,
            ask=1.2,
            comment="Request executed",
            request_id=13,
            retcode_external=0,
        )
        self.positions: tuple[SimpleNamespace, ...] | None = ()
        self.orders: tuple[SimpleNamespace, ...] | None = ()

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def initialize(self, *args: Any, **kwargs: Any) -> bool:
        self._record("initialize", *args, **kwargs)
        return self.initialize_ok

    def last_error(self) -> tuple[int, str]:
        return self.error

    def shutdown(self) -> None:
        self._record("shutdown")

    def symbol_info(self, name: str) -> SimpleNamespace | None:
        return self.symbols.get(name)

    def symbol_select(self, name: str, enable: bool) -> bool:
        self._record("symbol_select", name, enable)
        return True

    def symbol_info_tick(self, name: str) -> SimpleNamespace | None:
        return self.ticks.get(name)

    def order_send(self, request: dict[str, Any]) -> SimpleNamespace | None:
        self._record("order_send", request)
        return self.send_result

    def positions_get(self, **kwargs: Any) -> tuple[SimpleNamespace, ...] | None:
        self._record("positions_get", **kwargs)
        return self.positions

    def orders_get(self, **kwargs: Any) -> tuple[SimpleNamespace, ...] | None:
        self._record("orders_get", **kwargs)
        return self.orders


def symbol_info(name: str = "EURUSD", visible: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        visible=visible,
        digits=5,
        point=0.00001,
        trade_tick_size=0.00001,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        filling_mode=1,
        trade_exemode=2,
    )


def raw_position(ticket: int = 1, type_: int = 1, sl: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
        symbol="EURUSD",
        type=type_,
        volume=0.1,
        price_open=1.1,
        sl=sl,
        tp=0.0,
        price_current=1.09,
        profit=5.0,
        time=1700000000,
        magic=42,
        comment="bot",
        swap=-0.5,
        identifier=ticket,
        reason=3,
        time_msc=1700000000123,
        time_update=1700000001,
        time_update_msc=1700000001456,
        external_id="",
    )


def raw_order(ticket: int = 5, type_: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
        symbol="EURUSD",
        type=type_,
        volume_current=0.2,
        price_open=1.2,
        magic=0,
        comment="",
    )
