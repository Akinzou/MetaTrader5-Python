"""What a MetaTrader 5 trade-server return code means for the caller.

Codes are integers from the MQL5 "Trade Server Return Codes" table; they are
duplicated here so the domain never imports the MetaTrader5 package.
"""

from __future__ import annotations

from enum import Enum

from PythonMetaTrader5.domain.errors import ErrorKind, TradeError


class Outcome(Enum):
    SUCCESS = "success"
    RETRY = "retry"
    FAIL = "fail"


# PLACED is how the server confirms a pending order; 2.x only accepted DONE and
# therefore re-sent limit orders that had already been placed.
DONE_PARTIAL = 10010
_SUCCESS = frozenset({10008, 10009, DONE_PARTIAL})

# Only codes where the server provably did NOT execute the request. TIMEOUT and
# CONNECTION are deliberately absent: the order may already be live, and an
# automatic retry would open a second position.
_RETRY = frozenset({10004, 10020, 10021, 10024})

_FAILURES: dict[int, tuple[ErrorKind, str]] = {
    10004: (ErrorKind.REJECTED, "requote"),
    10006: (ErrorKind.REJECTED, "request rejected by the server"),
    10007: (ErrorKind.REJECTED, "request cancelled by the trader"),
    10011: (ErrorKind.REJECTED, "request processing error"),
    10012: (ErrorKind.OUTCOME_UNKNOWN, "request timed out; check positions before retrying"),
    10013: (ErrorKind.INVALID_ARGUMENT, "invalid request"),
    10014: (ErrorKind.INVALID_VOLUME, "invalid volume"),
    10015: (ErrorKind.INVALID_PRICE, "invalid price"),
    10016: (ErrorKind.INVALID_STOPS, "invalid stops; check symbol stops_level"),
    10017: (ErrorKind.TRADE_DISABLED, "trading is disabled"),
    10018: (ErrorKind.MARKET_CLOSED, "market is closed"),
    10019: (ErrorKind.NO_MONEY, "not enough money"),
    10020: (ErrorKind.REJECTED, "prices changed"),
    10021: (ErrorKind.NO_PRICE, "no quotes to process the request"),
    10022: (ErrorKind.INVALID_ARGUMENT, "invalid order expiration"),
    10024: (ErrorKind.REJECTED, "too many requests"),
    10026: (ErrorKind.ALGO_TRADING_DISABLED, "autotrading disabled by the server"),
    10027: (ErrorKind.ALGO_TRADING_DISABLED, "enable Algo Trading in the MetaTrader 5 terminal"),
    10028: (ErrorKind.REJECTED, "request locked for processing"),
    10029: (ErrorKind.REJECTED, "order or position frozen"),
    10030: (ErrorKind.INVALID_FILLING, "filling mode not supported by the symbol"),
    10031: (ErrorKind.OUTCOME_UNKNOWN, "no connection to the trade server; check positions"),
    10032: (ErrorKind.TRADE_DISABLED, "operation allowed only on live accounts"),
    10033: (ErrorKind.LIMIT_REACHED, "pending orders limit reached"),
    10034: (ErrorKind.LIMIT_REACHED, "volume limit for the symbol reached"),
    10035: (ErrorKind.INVALID_ARGUMENT, "invalid or prohibited order type"),
    10036: (ErrorKind.REJECTED, "position already closed"),
    10038: (ErrorKind.INVALID_VOLUME, "close volume exceeds position volume"),
    10039: (ErrorKind.REJECTED, "a close order for this position already exists"),
    10040: (ErrorKind.LIMIT_REACHED, "open positions limit reached"),
    10041: (ErrorKind.REJECTED, "pending order activation rejected"),
    10042: (ErrorKind.TRADE_DISABLED, "only long positions are allowed"),
    10043: (ErrorKind.TRADE_DISABLED, "only short positions are allowed"),
    10044: (ErrorKind.TRADE_DISABLED, "only position closing is allowed"),
    10045: (ErrorKind.REJECTED, "FIFO rule: close older positions first"),
}


def classify(retcode: int) -> Outcome:
    if retcode in _SUCCESS:
        return Outcome.SUCCESS
    if retcode in _RETRY:
        return Outcome.RETRY
    return Outcome.FAIL


def error_for(retcode: int) -> TradeError:
    kind, message = _FAILURES.get(retcode, (ErrorKind.REJECTED, "unrecognised server retcode"))
    return TradeError(kind, message, retcode=retcode)
