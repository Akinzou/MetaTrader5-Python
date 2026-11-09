"""PythonMetaTrader5: a safe, typed trading layer over the MetaTrader5 package.

from PythonMetaTrader5 import connect, Stop, Ok, Err

match connect(12345678, "password", "MetaQuotes-Demo", magic=1001):
    case Ok(trader):
        trader.open_position("EURUSD", "buy", 0.1, sl=Stop.points(1000))
    case Err(error):
        print(error)
"""

from PythonMetaTrader5.application.batch import BatchFailure
from PythonMetaTrader5.application.execution import RetryPolicy
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.connection import connect
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import (
    PendingKind,
    PendingOrder,
    Position,
    Tick,
    TradeReceipt,
)
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.stops import Stop, StopKind
from PythonMetaTrader5.legacy import mt5_namespace
from PythonMetaTrader5.legacy.broker import Broker
from PythonMetaTrader5.result import Err, Ok, Result

__all__ = [
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
]

# 2.x re-exported the whole MetaTrader5 namespace, and its README relied on it
# (`symbol_info("EURUSD")` after a star import). Kept for those scripts rather
# than breaking them on upgrade (ADR 0010); our own names win a collision.
_reexported = mt5_namespace.public_names(mt5_namespace.load(), taken=set(globals()))
globals().update(_reexported)
__all__ += sorted(_reexported)  # noqa: PLE0605 - extended at import time on purpose
del _reexported
