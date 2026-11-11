"""Stop-loss / take-profit given either as a price or as a distance in points."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PythonMetaTrader5.domain.amounts import positive_float
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.symbol import SymbolSpec
from PythonMetaTrader5.result import Err, Ok, Result


class StopKind(Enum):
    """How a `Stop` value is read: an absolute price or a distance in points."""

    PRICE = "price"
    POINTS = "points"


@dataclass(frozen=True, slots=True)
class Stop:
    """A stop-loss or take-profit level, as a price or as a distance in points.

    Build one with `Stop.at_price`, `Stop.points` or, for a value that may be
    bad at runtime, `Stop.parse`. A stop of zero, a negative price or a value
    that is not finite cannot exist: MT5 would read 0 as "no stop".
    """

    value: float
    kind: StopKind

    def __post_init__(self) -> None:
        # The invariant lives here, so every Stop is valid wherever it is built.
        # Raised, not returned: a Stop of 0 cannot exist (MT5 would read it as "no
        # stop"). Code holding a value that may be bad (an ATR that is NaN during
        # warm-up) uses Stop.parse, which returns a Result instead.
        parsed = _checked(self.value, self.kind)
        if isinstance(parsed, Err):
            raise ValueError(parsed.error.message)
        object.__setattr__(self, "value", parsed.value)

    @classmethod
    def parse(cls, value: object, kind: StopKind) -> Result[Stop, TradeError]:
        """Build a stop, or return ``Err(INVALID_STOPS)`` for a bad value instead of raising.

        A ``kind`` that is not a `StopKind` is a programming error and still
        raises ``TypeError``.
        """
        checked = _checked(value, kind)
        if isinstance(checked, Err):
            return checked
        return Ok(cls(checked.value, kind))

    @classmethod
    def at_price(cls, price: float) -> Stop:
        """A stop at an absolute ``price``; raises ``ValueError`` unless positive and finite."""
        return cls(price, StopKind.PRICE)

    @classmethod
    def points(cls, distance: float) -> Stop:
        """A stop ``distance`` points from the entry price; the sign is ignored.

        Raises ``ValueError`` for zero or a value that is not finite; use
        `Stop.parse` for a value that may be bad at runtime.
        """
        return cls(distance, StopKind.POINTS)

    def stop_loss(
        self, side: Side, reference: float, spec: SymbolSpec
    ) -> Result[float, TradeError]:
        """The stop-loss price for a ``side`` trade entered at ``reference``, on the tick grid."""
        return self._resolve(-side.sign, reference, spec, "sl")

    def take_profit(
        self, side: Side, reference: float, spec: SymbolSpec
    ) -> Result[float, TradeError]:
        """The take-profit price for a ``side`` trade entered at ``reference``, on the tick grid."""
        return self._resolve(side.sign, reference, spec, "tp")

    def _resolve(
        self, direction: int, reference: float, spec: SymbolSpec, what: str
    ) -> Result[float, TradeError]:
        # Resolved without a sign check here: price_on_grid is the single place a
        # level below zero (a long points distance) or off the grid is refused.
        level = self.value
        if self.kind is StopKind.POINTS:
            distance = spec.points_to_price(self.value)
            if isinstance(distance, Err):
                return distance
            level = reference + direction * distance.value
        return spec.price_on_grid(level, ErrorKind.INVALID_STOPS, what)


def _checked(value: object, kind: StopKind) -> Result[float, TradeError]:
    # A wrong kind is a programming error, raised for every value alike (also by
    # Stop.parse), rather than read as a price.
    if not isinstance(kind, StopKind):
        raise TypeError(f"kind must be a StopKind, got {kind!r}")
    # A points distance drops its sign: direction comes from the trade side, so
    # `-1000` and `1000` both mean "1000 points on the losing side".
    number = positive_float(value, unsigned=kind is StopKind.POINTS)
    if number is None:
        message = f"{kind.value} stop must be a positive finite number, got {value!r}"
        return Err(TradeError(ErrorKind.INVALID_STOPS, message))
    return Ok(number)
