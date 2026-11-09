"""2.x `Broker` facade over the 3.x Trader.

Names, arguments and return shapes follow 2.x so old scripts keep running. The
behaviour that made 2.x dangerous is NOT preserved: no endless retry loops and
no Ctrl+E keystrokes into whichever window has focus. See MIGRATION.md.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, ClassVar

from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.adapters.system_clock import SystemClock
from PythonMetaTrader5.application.ports import Clock, Credentials, Terminal
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.market import PendingKind, TradeReceipt
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.legacy import views
from PythonMetaTrader5.result import Err, Ok, Result

log = logging.getLogger("PythonMetaTrader5.legacy")

_RELOGIN_DELAY_SECONDS = 1.0


class Broker:
    RetCodes: ClassVar[dict[int, str]] = {
        10027: "Enable Algo Trading in MetaTrader5 app",
        10018: "Market closed",
        10016: "Wrong SL",
    }

    def __init__(
        self,
        log: int | str,
        password: Any,
        server: Any,
        *,
        terminal: Terminal | None = None,
        clock: Clock | None = None,
    ) -> None:
        warnings.warn(
            "Broker is deprecated; use PythonMetaTrader5.connect() (see MIGRATION.md)",
            DeprecationWarning,
            stacklevel=2,
        )
        self.log = log
        self.server = str(server)
        self._credentials = Credentials(int(log), str(password), self.server)
        self._clock = clock or SystemClock()
        self._terminal = terminal or _load_terminal()
        self._trader = Trader(self._terminal, self._clock) if self._terminal else None
        self._connected = self.login()

    def login(self, ToEffect: bool = False) -> bool:
        """Log in once, or keep trying every second until it works when ``ToEffect``."""
        if self._terminal is None:
            return False
        while True:
            result = self._terminal.connect(self._credentials)
            if isinstance(result, Ok):
                log.info("%s: logged in to %s", self.log, self.server)
                self._connected = True
                return True
            log.error("%s: %s", self.log, result.error)
            if not ToEffect:
                return False
            self._clock.sleep(_RELOGIN_DELAY_SECONDS)

    # ---------------------------------------------------------------- queries

    def GetPositionsBySymbol(self, symbol: str, as_dict: bool = False) -> list[Any]:
        return self.GetPositions(symbol, as_dict=as_dict)

    def GetPositions(
        self, symbol: str | None = None, *, ticket: int | None = None, as_dict: bool = False
    ) -> list[Any]:
        trader = self._ready()
        if trader is None:
            return []
        listed = trader.positions(symbol, ticket=ticket)
        if isinstance(listed, Err):
            log.error("%s: %s", self.log, listed.error)
            return []
        convert = views.as_dict if as_dict else views.as_object
        return [convert(p) for p in listed.value]

    def GetPosition(
        self, symbol: str | None = None, *, ticket: int | None = None, as_dict: bool = False
    ) -> Any:
        found = self.GetPositions(symbol, ticket=ticket, as_dict=as_dict)
        return found[0] if found else None

    # ---------------------------------------------------------------- entries

    def OpenPosition(
        self,
        symbol: str,
        side: str,
        volume: float,
        *,
        sl: float | None = None,
        tp: float | None = None,
        price: float | None = None,
        comment: str | None = None,
        ticket: int | None = None,
        sl_type: str = "absolute",
        tp_type: str = "absolute",
    ) -> TradeReceipt | None:
        trader = self._ready()
        if trader is None or not _no_ticket(ticket):
            return None
        stops = _legacy_stop(sl, sl_type), _legacy_stop(tp, tp_type)
        if any(isinstance(stop, Err) for stop in stops):
            return None
        stop_loss, take_profit = (s.value for s in stops if isinstance(s, Ok))
        result = trader.open_position(
            symbol, side, volume, sl=stop_loss, tp=take_profit, price=price, comment=comment
        )
        return self._receipt(result, f"{side} {symbol}")

    def Buy(self, symbol: str, volume: float, price: float | None = None, **kw: Any) -> Any:
        return self.OpenPosition(symbol, "buy", volume, price=price, **kw)

    def BuySL(
        self, symbol: str, volume: float, sl: float, price: float | None = None, **kw: Any
    ) -> Any:
        return self.OpenPosition(symbol, "buy", volume, sl=sl, price=price, **kw)

    def Sell(self, symbol: str, volume: float, price: float | None = None, **kw: Any) -> Any:
        return self.OpenPosition(symbol, "sell", volume, price=price, **kw)

    def SellSL(
        self, symbol: str, volume: float, sl: float, price: float | None = None, **kw: Any
    ) -> Any:
        return self.OpenPosition(symbol, "sell", volume, sl=sl, price=price, **kw)

    def BuyLimit(
        self,
        symbol: str,
        volume: float,
        stoplimit: float,
        price: float | None = None,
        comment: str | None = None,
        ticket: int | None = None,
    ) -> TradeReceipt | None:
        return self._limit(
            Side.BUY, symbol, volume, stoplimit, price=price, comment=comment, ticket=ticket
        )

    def SellLimit(
        self,
        symbol: str,
        volume: float,
        stoplimit: float,
        price: float | None = None,
        comment: str | None = None,
        ticket: int | None = None,
    ) -> TradeReceipt | None:
        return self._limit(
            Side.SELL, symbol, volume, stoplimit, price=price, comment=comment, ticket=ticket
        )

    # ------------------------------------------------------------------ exits

    def Close(
        self, symbol: str | None, *, comment: str | None = None, ticket: int | None = None
    ) -> bool:
        """True when at least one position closed and none failed."""
        trader = self._ready()
        if trader is None:
            return False
        if symbol is None and ticket is None:
            # 2.x crashed here without closing anything; 3.x would close the account.
            log.error("%s: Close needs a symbol or ticket", self.log)
            return False
        result = trader.close_positions(symbol, ticket=ticket, comment=comment)
        if isinstance(result, Err):
            log.error("%s: closing %s: %s", self.log, symbol, result.error)
            return False
        if not result.value:
            log.info("%s: there are no positions to close on %s", self.log, symbol)
        return bool(result.value)

    def CancelOrders(self, symbol: str) -> None:
        trader = self._ready()
        if trader is None:
            return
        if not symbol:
            # 2.x matched orders against the symbol and so cancelled nothing here.
            log.error("%s: CancelOrders needs a symbol", self.log)
            return
        # 2.x only ever cancelled limit orders; stop orders stay untouched.
        result = trader.cancel_pending_orders(symbol, kind=PendingKind.LIMIT)
        if isinstance(result, Err):
            log.error("%s: cancelling orders on %s: %s", self.log, symbol, result.error)

    def Disconnect(self) -> None:
        if self._trader is not None:
            self._trader.shutdown()
        self._connected = False
        log.info("Disconnected from MT5")

    # ---------------------------------------------------------------- helpers

    def _limit(
        self,
        side: Side,
        symbol: str,
        volume: float,
        stoplimit: float,
        *,
        price: float | None,
        comment: str | None,
        ticket: int | None,
    ) -> TradeReceipt | None:
        trader = self._ready()
        if trader is None or self._terminal is None or not _no_ticket(ticket):
            return None
        if price is not None:
            log.error("%s: price has to be None for limit orders", self.log)
            return None
        tick = self._terminal.tick(symbol)
        if isinstance(tick, Err):
            log.error("%s: %s", self.log, tick.error)
            return None
        quote = tick.value.entry_price(side)
        # 2.x semantics: a limit already reached by the market is filled at market.
        crossed = quote <= stoplimit if side is Side.BUY else quote >= stoplimit
        if crossed:
            result = trader.open_position(symbol, side, volume, comment=comment)
        else:
            result = trader.place_limit_order(symbol, side, volume, stoplimit, comment=comment)
        return self._receipt(result, f"{side.value} limit {symbol} @ {stoplimit}")

    def _ready(self) -> Trader | None:
        if self._trader is None or not self._connected:
            log.error("%s: not connected to MetaTrader 5; call login()", self.log)
            return None
        return self._trader

    def _receipt(self, result: Result[TradeReceipt, TradeError], what: str) -> TradeReceipt | None:
        if isinstance(result, Ok):
            log.info("%s: %s done", self.log, what)
            return result.value
        log.error("%s: %s failed: %s", self.log, what, result.error)
        return result.error.receipt


def _legacy_stop(value: float | None, kind: str) -> Result[Stop | None, str]:
    if value is None:
        return Ok(None)
    match (kind or "absolute").lower():
        case "absolute":
            return Ok(Stop.at_price(value))
        case "offset":
            return Ok(Stop.points(value))
        case other:
            log.error("invalid stop type %r (use 'absolute' or 'offset')", other)
            return Err(other)


def _no_ticket(ticket: int | None) -> bool:
    if ticket is None:
        return True
    # 2.x forwarded it as `position` on an opening deal, which on hedging
    # accounts turns an opposite-side entry into a close of that position.
    log.error("the ticket argument is not supported for entries; use Close(ticket=...)")
    return False


def _load_terminal() -> Terminal | None:
    loaded = MetaTrader5Terminal.load()
    if isinstance(loaded, Err):
        log.error("%s", loaded.error)
        return None
    return loaded.value
