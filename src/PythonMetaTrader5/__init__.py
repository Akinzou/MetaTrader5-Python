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
from PythonMetaTrader5.domain.stops import Stop
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
    "Tick",
    "TradeError",
    "TradeReceipt",
    "Trader",
    "connect",
]
