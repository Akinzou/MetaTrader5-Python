"""Stop-loss / take-profit given either as a price or as a distance in points."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PythonMetaTrader5.domain.amounts import positive_float
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.symbol import SymbolSpec


class StopKind(Enum):
    PRICE = "price"
    POINTS = "points"


@dataclass(frozen=True, slots=True)
class Stop:
    value: float
    kind: StopKind

    def __post_init__(self) -> None:
        # The invariant lives here, so every Stop is valid wherever it is built.
        # A points distance drops its sign: direction comes from the trade side,
        # so `-1000` and `1000` both mean "1000 points on the losing side".
        number = positive_float(self.value, unsigned=self.kind is StopKind.POINTS)
        if number is None:
            # Raised, not returned: a Stop of 0 cannot exist (MT5 would read it as
            # "no stop"), and bool/NaN/str are caller bugs. Plain floats passed as
            # sl/tp are checked without raising, by domain.inputs.stop_input.
            raise ValueError(
                f"{self.kind.value} stop must be a positive finite number, got {self.value!r}"
            )
        object.__setattr__(self, "value", number)

    @classmethod
    def at_price(cls, price: float) -> Stop:
        return cls(price, StopKind.PRICE)

    @classmethod
    def points(cls, distance: float) -> Stop:
        return cls(distance, StopKind.POINTS)

    def stop_loss(self, side: Side, reference: float, spec: SymbolSpec) -> float:
        return self._resolve(-side.sign, reference, spec)

    def take_profit(self, side: Side, reference: float, spec: SymbolSpec) -> float:
        return self._resolve(side.sign, reference, spec)

    def _resolve(self, direction: int, reference: float, spec: SymbolSpec) -> float:
        if self.kind is StopKind.PRICE:
            return spec.normalize_price(self.value)
        return spec.normalize_price(reference + direction * self.value * spec.point)
