"""Checks on raw caller input that MT5 would otherwise misread without an error.

Webhook payloads arrive as loosely typed JSON. Each value below has a reading
in MT5 that is valid but almost never meant: ``sl=0`` is "no stop",
``ticket=0`` may be "no filter", ``volume=True`` is one lot. They are refused
here instead of being passed on.
"""

from __future__ import annotations

import math
from numbers import Integral, Real

from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.result import Err, Ok, Result


def positive_number(value: object, kind: ErrorKind, what: str) -> Result[float, TradeError]:
    # numbers.Real rather than float so numpy scalars from pandas-based bots pass;
    # bool is excluded explicitly because it is a Real (True == 1).
    if isinstance(value, bool) or not isinstance(value, Real):
        return Err(TradeError(kind, f"{what} must be a number, got {value!r}"))
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return Err(TradeError(kind, f"{what} must be a positive finite number, got {value!r}"))
    return Ok(number)


def stop_input(value: object, what: str) -> Result[Stop | None, TradeError]:
    """``None`` means no stop; a float is a price; zero is refused, never "no stop"."""
    if value is None:
        return Ok(None)
    raw = value.value if isinstance(value, Stop) else value
    checked = positive_number(raw, ErrorKind.INVALID_STOPS, what)
    if isinstance(checked, Err):
        return checked
    return Ok(value if isinstance(value, Stop) else Stop.at_price(checked.value))


def ticket_filter(ticket: object) -> Result[int | None, TradeError]:
    if ticket is None:
        return Ok(None)
    if isinstance(ticket, bool) or not isinstance(ticket, Integral) or ticket <= 0:
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT, f"ticket must be a positive integer, got {ticket!r}"
            )
        )
    return Ok(int(ticket))


def symbol_filter(symbol: str | None) -> Result[str | None, TradeError]:
    # "" is rejected rather than passed on: a missing webhook field arrives as ""
    # and is easily mistaken for "no filter" (2.x and the first 3.0 draft both
    # dropped falsy filters), which would act on the whole account.
    if symbol == "":
        return Err(TradeError(ErrorKind.INVALID_ARGUMENT, "symbol must not be empty"))
    return Ok(symbol)
