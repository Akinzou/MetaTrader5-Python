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
from PythonMetaTrader5.application.ports import Clock, Credentials, Terminal, parse_login
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.inputs import ANY_MAGIC, positive_number
from PythonMetaTrader5.domain.market import PendingKind, TradeReceipt
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.legacy import views
from PythonMetaTrader5.legacy.arguments import legacy_stop, no_ticket, number
from PythonMetaTrader5.legacy.views import LegacyReceipt
from PythonMetaTrader5.result import Err, Ok, Result

log = logging.getLogger("PythonMetaTrader5.legacy")

_RELOGIN_DELAY_SECONDS = 1.0


class Broker:
    """Deprecated 2.x API, kept so existing bots run; use `connect` instead.

    Read the migration guide before upgrading a bot that trades real money.
    """

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
        account = parse_login(log)
        if account is None:
            # Programming error, raised as 2.x did for non-numeric logins; silently
            # coercing True or 12345678.9 would trade on another account.
            raise ValueError(f"login must be a positive integer, got {log!r}")
        self._credentials = Credentials(account, str(password), self.server)
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
            # The adapter released the session, so nothing may trade until a login works.
            self._connected = False
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
        # 2.x: a ticket selects that position whatever symbol was passed.
        listed = trader.positions(None if ticket is not None else symbol, ticket=ticket)
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
    ) -> LegacyReceipt | None:
        trader = self._ready()
        if trader is None or not no_ticket(ticket):
            return None
        stops = legacy_stop(number(sl), sl_type), legacy_stop(number(tp), tp_type)
        if any(isinstance(stop, Err) for stop in stops):
            return None
        stop_loss, take_profit = (s.value for s in stops if isinstance(s, Ok))
        result = trader.open_position(
            symbol,
            side,
            number(volume),
            sl=stop_loss,
            tp=take_profit,
            price=number(price),
            comment=comment,
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
    ) -> LegacyReceipt | None:
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
    ) -> LegacyReceipt | None:
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
        # 2.x closed every magic; the 3.x own-magic default would skip them.
        result = trader.close_positions(symbol, ticket=ticket, magic=ANY_MAGIC, comment=comment)
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
        result = trader.cancel_pending_orders(symbol, magic=ANY_MAGIC, kind=PendingKind.LIMIT)
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
    ) -> LegacyReceipt | None:
        trader = self._ready()
        if trader is None or self._terminal is None or not no_ticket(ticket):
            return None
        volume = number(volume)
        if price is not None:
            log.error("%s: price has to be None for limit orders", self.log)
            return None
        # Checked before the crossing test below: a level of 0 always "crosses"
        # for a sell and would become a market order.
        level = positive_number(number(stoplimit), ErrorKind.INVALID_PRICE, "stoplimit")
        if isinstance(level, Err):
            log.error("%s: %s", self.log, level.error)
            return None
        stoplimit = level.value
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

    def _receipt(self, result: Result[TradeReceipt, TradeError], what: str) -> LegacyReceipt | None:
        if isinstance(result, Ok):
            log.info("%s: %s done", self.log, what)
            return views.as_receipt(result.value)
        log.error("%s: %s failed: %s", self.log, what, result.error)
        return views.as_receipt(result.error.receipt)


def _load_terminal() -> Terminal | None:
    loaded = MetaTrader5Terminal.load()
    if isinstance(loaded, Err):
        log.error("%s", loaded.error)
        return None
    return loaded.value
