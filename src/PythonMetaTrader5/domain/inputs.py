"""Checks on raw caller input that MT5 would otherwise misread without an error.

Webhook payloads arrive as loosely typed JSON. Each value below has a reading
in MT5 that is valid but almost never meant: ``sl=0`` is "no stop",
``ticket=0`` may be "no filter", ``volume=True`` is one lot. They are refused
here instead of being passed on.
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from numbers import Integral
from typing import Final

from PythonMetaTrader5.domain.amounts import positive_float
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.stops import Stop, StopKind
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
    parsed = Stop.parse(value, StopKind.PRICE)
    if isinstance(parsed, Err):
        return Err(replace(parsed.error, message=f"{what}: {parsed.error.message}"))
    return Ok(parsed.value)


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


class AnyMagic(Enum):
    """The type of ``ANY_MAGIC``."""

    ANY = "any"


# A named value, not None: close-all and cancel-all default to the trader's own
# magic, and a None read from a missing config key must not widen them to the
# whole account (ADR 0011).
ANY_MAGIC: Final = AnyMagic.ANY
# MT5 stores magic as a ulong; a larger value would overflow in order_send.
_MAX_MAGIC: Final = 2**64 - 1


def magic_filter(magic: object) -> Result[int | AnyMagic | None, TradeError]:
    # "42" or True would match no position and report an empty success with
    # everything still open. 0 is valid: it is what manual trades carry.
    if magic is None or magic is ANY_MAGIC:
        return Ok(magic)
    if (
        isinstance(magic, bool)
        or not isinstance(magic, Integral)
        or not 0 <= int(magic) <= _MAX_MAGIC
    ):
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT,
                f"magic must be an integer from 0 to 2**64-1 or ANY_MAGIC, got {magic!r}",
            )
        )
    return Ok(int(magic))


def own_magic(magic: object) -> Result[int, TradeError]:
    """The magic a trader stamps on its orders and closes by default."""
    checked = magic_filter(magic)
    # None or ANY_MAGIC here would make the own-magic default mean "every magic",
    # and a missing config key would close the whole account (ADR 0011). One
    # message for every refusal: magic_filter's would suggest ANY_MAGIC.
    if isinstance(checked, Err) or not isinstance(checked.value, int):
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT,
                f"the trader's own magic must be an integer from 0 to 2**64-1, got {magic!r}",
            )
        )
    return Ok(checked.value)
