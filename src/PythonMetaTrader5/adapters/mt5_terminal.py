"""Terminal port implemented with the official `MetaTrader5` package.

This is the only module that knows MT5's request dictionaries, numeric order
types and the shape of its result objects.
"""

from __future__ import annotations

import importlib
from typing import Any

from PythonMetaTrader5.application.ports import Credentials
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import (
    PendingKind,
    PendingOrder,
    Position,
    Tick,
    TradeReceipt,
)
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.symbol import Filling, SymbolSpec
from PythonMetaTrader5.result import Err, Ok, Result

# last_error() codes for which order_send provably never left this process
# (bad arguments, no IPC link, terminal refused). Any other failure (send,
# receive, timeout) may have reached the server, so its outcome is unknown.
_NOT_SENT_CODES = (
    "RES_E_INVALID_PARAMS",
    "RES_E_NO_MEMORY",
    "RES_E_NOT_FOUND",
    "RES_E_INVALID_VERSION",
    "RES_E_AUTH_FAILED",
    "RES_E_UNSUPPORTED",
    "RES_E_INTERNAL_FAIL_INIT",
    "RES_E_INTERNAL_FAIL_CONNECT",
)


class MetaTrader5Terminal:
    def __init__(self, mt5: Any) -> None:
        # `Any`: the MetaTrader5 package ships no type information.
        self._mt5 = mt5
        self._order_types = _order_type_table(mt5)
        self._pending_by_type = {
            code: (side, kind)
            for (side, kind), code in self._order_types.items()
            if kind is not None
        }
        self._fillings = {
            Filling.FOK: mt5.ORDER_FILLING_FOK,
            Filling.IOC: mt5.ORDER_FILLING_IOC,
            Filling.RETURN: mt5.ORDER_FILLING_RETURN,
        }
        # Every constant is read here, not at first use, so building the adapter
        # against a new MetaTrader5 release fails at once if one was renamed.
        self._deal = mt5.TRADE_ACTION_DEAL
        self._pending = mt5.TRADE_ACTION_PENDING
        self._remove = mt5.TRADE_ACTION_REMOVE
        self._good_till_cancel = mt5.ORDER_TIME_GTC
        self._position_buy = mt5.POSITION_TYPE_BUY
        self._exchange_execution = mt5.SYMBOL_TRADE_EXECUTION_EXCHANGE
        self._not_sent = frozenset(getattr(mt5, name) for name in _NOT_SENT_CODES)
        self._auto_trading_disabled = mt5.RES_E_AUTO_TRADING_DISABLED
        # MT5 reports "nothing found" and "call failed" both as None; only a
        # last_error() of RES_S_OK tells "nothing found" apart.
        self._ok = mt5.RES_S_OK

    @classmethod
    def load(cls) -> Result[MetaTrader5Terminal, TradeError]:
        try:
            module = importlib.import_module("MetaTrader5")
        except ImportError:
            return Err(
                TradeError(
                    ErrorKind.CONNECTION_FAILED,
                    "the MetaTrader5 package is not installed (it is available on Windows only)",
                )
            )
        return Ok(cls(module))

    def connect(self, credentials: Credentials) -> Result[None, TradeError]:
        args = (credentials.path,) if credentials.path else ()
        if self._mt5.initialize(
            *args,
            login=credentials.login,
            password=credentials.password,
            server=credentials.server,
            timeout=credentials.timeout_ms,
        ):
            return Ok(None)
        error = self._last_error()
        # Always released: MT5 has one session per process, so after a failed login
        # it is unusable for everyone, and a half-open one makes every later
        # initialize() fail (login(ToEffect=True) could never recover). A per-adapter
        # "keep the live session" flag was tried and dropped: connect() builds a
        # new adapter each time, so the flag protected nothing.
        self._mt5.shutdown()
        return Err(
            TradeError(
                ErrorKind.CONNECTION_FAILED,
                f"login {credentials.login}@{credentials.server} failed: {error}",
            )
        )

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def symbol(self, name: str) -> Result[SymbolSpec, TradeError]:
        info = self._mt5.symbol_info(name)
        if info is None:
            return Err(TradeError(ErrorKind.SYMBOL_NOT_FOUND, f"unknown symbol {name!r}"))
        # Hidden symbols have no quotes; 2.x left users to fix Market Watch by hand.
        if not info.visible and not self._mt5.symbol_select(name, True):
            return Err(
                TradeError(
                    ErrorKind.SYMBOL_NOT_FOUND,
                    f"{name!r} cannot be added to Market Watch: {self._last_error()}",
                )
            )
        return Ok(
            SymbolSpec(
                name=info.name,
                digits=int(info.digits),
                point=float(info.point),
                tick_size=float(info.trade_tick_size),
                volume_min=float(info.volume_min),
                volume_max=float(info.volume_max),
                volume_step=float(info.volume_step),
                filling_flags=int(info.filling_mode),
                exchange_execution=int(info.trade_exemode) == self._exchange_execution,
            )
        )

    def tick(self, name: str) -> Result[Tick, TradeError]:
        tick = self._mt5.symbol_info_tick(name)
        # A zero side means no quote yet; trading at price 0 must never be attempted.
        if tick is None or tick.bid <= 0 or tick.ask <= 0:
            return Err(TradeError(ErrorKind.NO_PRICE, f"no quote for {name!r}"))
        return Ok(Tick(bid=float(tick.bid), ask=float(tick.ask)))

    def send(self, request: OrderRequest | CancelRequest) -> Result[TradeReceipt, TradeError]:
        payload = self._payload(request)
        result = self._mt5.order_send(payload)
        if result is None:
            return Err(self._send_failure())
        return Ok(
            TradeReceipt(
                retcode=int(result.retcode),
                deal=int(result.deal),
                order=int(result.order),
                volume=float(result.volume),
                price=float(result.price),
                bid=float(result.bid),
                ask=float(result.ask),
                comment=str(result.comment),
                request_id=int(result.request_id),
            )
        )

    def positions(
        self, *, symbol: str | None = None, ticket: int | None = None
    ) -> Result[list[Position], TradeError]:
        query: dict[str, object] = {}
        if ticket is not None:
            query["ticket"] = ticket
        elif symbol is not None:
            query["symbol"] = symbol
        raw = self._listing(self._mt5.positions_get(**query), "positions_get")
        if isinstance(raw, Err):
            return raw
        return Ok([self._position(p) for p in raw.value])

    def pending_orders(
        self, *, symbol: str | None = None
    ) -> Result[list[PendingOrder], TradeError]:
        query = {"symbol": symbol} if symbol is not None else {}
        raw = self._listing(self._mt5.orders_get(**query), "orders_get")
        if isinstance(raw, Err):
            return raw
        orders = []
        for o in raw.value:
            key = self._pending_by_type.get(int(o.type))
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
        return Ok(orders)

    # ------------------------------------------------------------------ helpers

    def _payload(self, request: OrderRequest | CancelRequest) -> dict[str, Any]:
        if isinstance(request, CancelRequest):
            return {"action": self._remove, "order": request.order}
        payload: dict[str, Any] = {
            "action": self._deal if request.pending is None else self._pending,
            "symbol": request.symbol,
            "volume": request.volume,
            "type": self._order_types[(request.side, request.pending)],
            "price": request.price,
            "deviation": request.deviation,
            "magic": request.magic,
            "comment": request.comment,
            "type_filling": self._fillings[request.filling],
            "type_time": self._good_till_cancel,
        }
        optional = {"sl": request.sl, "tp": request.tp, "position": request.position}
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload

    def _position(self, p: Any) -> Position:
        return Position(
            ticket=int(p.ticket),
            symbol=str(p.symbol),
            side=Side.BUY if p.type == self._position_buy else Side.SELL,
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
        )

    def _listing(self, raw: Any, call: str) -> Result[tuple[Any, ...], TradeError]:
        if raw is not None:
            return Ok(tuple(raw))
        code, _ = self._mt5.last_error()
        if code == self._ok:
            return Ok(())
        return Err(TradeError(ErrorKind.TERMINAL_ERROR, f"{call} failed: {self._last_error()}"))

    def _send_failure(self) -> TradeError:
        code, text = self._error()
        if code == self._auto_trading_disabled:
            kind = ErrorKind.ALGO_TRADING_DISABLED
        elif code in self._not_sent:
            kind = ErrorKind.TERMINAL_ERROR
        else:
            kind = ErrorKind.OUTCOME_UNKNOWN
        return TradeError(kind, f"order_send failed: {text}")

    def _last_error(self) -> str:
        return self._error()[1]

    def _error(self) -> tuple[int, str]:
        code, message = self._mt5.last_error()
        return code, f"[{code}] {message}"


def _order_type_table(mt5: Any) -> dict[tuple[Side, PendingKind | None], int]:
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
