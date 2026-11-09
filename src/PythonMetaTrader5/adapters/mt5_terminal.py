"""Terminal port implemented with the official `MetaTrader5` package.

This is the only module that knows MT5's request dictionaries, numeric order
types and the shape of its result objects.
"""

from __future__ import annotations

import functools
import importlib
import threading
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from PythonMetaTrader5.adapters import mt5_mapping
from PythonMetaTrader5.application.ports import Credentials
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import PendingOrder, Position, Tick, TradeReceipt
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

# last_error() is process-global, so a call and the error read that explains it
# must not interleave with another thread's call. The lock is module-level, not
# per adapter: connect() builds a new adapter each time, and two Traders in one
# process share the one MT5 session. Direct MetaTrader5 calls made by user code
# are outside this lock.
_SESSION = threading.RLock()
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _serialized(method: Callable[_P, _R]) -> Callable[_P, _R]:
    @functools.wraps(method)
    def locked(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with _SESSION:
            return method(*args, **kwargs)

    return locked


class MetaTrader5Terminal:
    def __init__(self, mt5: Any) -> None:
        # `Any`: the MetaTrader5 package ships no type information.
        self._mt5 = mt5
        self._order_types = mt5_mapping.order_type_table(mt5)
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

    @_serialized
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

    @_serialized
    def shutdown(self) -> None:
        self._mt5.shutdown()

    @_serialized
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
        return SymbolSpec.check(
            {
                "name": info.name,
                "digits": int(info.digits),
                "point": float(info.point),
                "tick_size": float(info.trade_tick_size),
                "volume_min": float(info.volume_min),
                "volume_max": float(info.volume_max),
                "volume_step": float(info.volume_step),
                "filling_flags": int(info.filling_mode),
                "exchange_execution": int(info.trade_exemode) == self._exchange_execution,
            }
        )

    @_serialized
    def tick(self, name: str) -> Result[Tick, TradeError]:
        tick = self._mt5.symbol_info_tick(name)
        # A zero side means no quote yet; trading at price 0 must never be attempted.
        if tick is None or tick.bid <= 0 or tick.ask <= 0:
            return Err(TradeError(ErrorKind.NO_PRICE, f"no quote for {name!r}"))
        return Ok(Tick(bid=float(tick.bid), ask=float(tick.ask)))

    @_serialized
    def send(self, request: OrderRequest | CancelRequest) -> Result[TradeReceipt, TradeError]:
        payload = self._payload(request)
        result = self._mt5.order_send(payload)
        if result is None:
            return Err(self._send_failure())
        return Ok(mt5_mapping.receipt(result))

    @_serialized
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
        found = [mt5_mapping.position(p, self._position_buy) for p in raw.value]
        # MT5 ignores `symbol` once `ticket` is given; the port promises both apply.
        return Ok([p for p in found if symbol is None or p.symbol == symbol])

    @_serialized
    def pending_orders(
        self, *, symbol: str | None = None
    ) -> Result[list[PendingOrder], TradeError]:
        query = {"symbol": symbol} if symbol is not None else {}
        raw = self._listing(self._mt5.orders_get(**query), "orders_get")
        if isinstance(raw, Err):
            return raw
        return Ok(mt5_mapping.pending_orders(raw.value, self._pending_by_type))

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
