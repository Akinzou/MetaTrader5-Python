"""Checks on raw caller input that MT5 would otherwise misread without an error.

Webhook payloads arrive as loosely typed JSON. Each value below has a reading
in MT5 that is valid but almost never meant: ``sl=0`` is "no stop",
``ticket=0`` may be "no filter", ``volume=True`` is one lot. They are refused
here instead of being passed on.
"""

from __future__ import annotations

from numbers import Integral

from PythonMetaTrader5.domain.amounts import positive_float
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.result import Err, Ok, Result


def positive_number(value: object, kind: ErrorKind, what: str) -> Result[float, TradeError]:
    number = positive_float(value)
    if number is None:
        return Err(TradeError(kind, f"{what} must be a positive finite number, got {value!r}"))
    return Ok(number)


def stop_input(value: object, what: str) -> Result[Stop | None, TradeError]:
    """``None`` means no stop; a float is a price; zero is refused, never "no stop"."""
    if value is None or isinstance(value, Stop):
        return Ok(value)  # a Stop validated itself when it was built
    number = positive_float(value)
    if number is None:
        return Err(
            TradeError(
                ErrorKind.INVALID_STOPS, f"{what} must be a positive finite price, got {value!r}"
            )
        )
    return Ok(Stop.at_price(number))


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
