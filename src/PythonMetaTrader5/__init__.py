"""PythonMetaTrader5: a safe, typed trading layer over the MetaTrader5 package.

from PythonMetaTrader5 import connect, Stop, Ok, Err

match connect(12345678, "password", "MetaQuotes-Demo", magic=1001):
    case Ok(trader):
        trader.open_position("EURUSD", "buy", 0.1, sl=Stop.points(1000))
    case Err(error):
        print(error)
"""

from typing import Any

# `X as X`: explicit re-exports, because __all__ is computed (see __getattr__).
from PythonMetaTrader5.application.batch import BatchFailure as BatchFailure
from PythonMetaTrader5.application.execution import RetryPolicy as RetryPolicy
from PythonMetaTrader5.application.trader import Trader as Trader
from PythonMetaTrader5.connection import connect as connect
from PythonMetaTrader5.domain.errors import ErrorKind as ErrorKind
from PythonMetaTrader5.domain.errors import TradeError as TradeError
from PythonMetaTrader5.domain.inputs import ANY_MAGIC as ANY_MAGIC
from PythonMetaTrader5.domain.inputs import AnyMagic as AnyMagic
from PythonMetaTrader5.domain.market import PendingKind as PendingKind
from PythonMetaTrader5.domain.market import PendingOrder as PendingOrder
from PythonMetaTrader5.domain.market import Position as Position
from PythonMetaTrader5.domain.market import Tick as Tick
from PythonMetaTrader5.domain.market import TradeReceipt as TradeReceipt
from PythonMetaTrader5.domain.orders import Side as Side
from PythonMetaTrader5.domain.stops import Stop as Stop
from PythonMetaTrader5.domain.stops import StopKind as StopKind
from PythonMetaTrader5.legacy import mt5_namespace as _mt5_namespace
from PythonMetaTrader5.legacy.broker import Broker as Broker
from PythonMetaTrader5.result import Err as Err
from PythonMetaTrader5.result import Ok as Ok
from PythonMetaTrader5.result import Result as Result

_OWN_NAMES = (
    "ANY_MAGIC",
    "AnyMagic",
    "BatchFailure",
    "Broker",
    "Err",
    "ErrorKind",
    "Ok",
    "PendingKind",
    "PendingOrder",
    "Position",
    "Result",
    "RetryPolicy",
    "Side",
    "Stop",
    "StopKind",
    "Tick",
    "TradeError",
    "TradeReceipt",
    "Trader",
    "connect",
)


def __getattr__(name: str) -> Any:
    # 2.x re-exported the whole MetaTrader5 namespace and its README relied on it
    # (`symbol_info("EURUSD")` after a star import), so those names resolve here,
    # lazily (ADR 0010). A star import asks for __all__ through this hook too.
    # Names defined in this module always win, e.g. our Tick over MT5's struct.
    if name == "__all__":
        mt5_names = _mt5_namespace.public_names()
        return [*_OWN_NAMES, *(n for n in mt5_names if n not in globals())]
    return _mt5_namespace.resolve(name)


def __dir__() -> list[str]:
    return sorted({*globals(), *__getattr__("__all__")})
