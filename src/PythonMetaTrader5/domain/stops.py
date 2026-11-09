"""Stop-loss / take-profit given either as a price or as a distance in points."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.symbol import SymbolSpec


class StopKind(Enum):
    PRICE = "price"
    POINTS = "points"


@dataclass(frozen=True, slots=True)
class Stop:
    value: float
    kind: StopKind

    # The factories store the value unconverted: float(True) == 1.0 would hide a
    # stray bool from the input checks (domain/inputs.stop_input), which refuse
    # anything that is not a positive finite number.

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
        # The sign is ignored on purpose: direction comes from the trade side, so
        # `-1000` and `1000` both mean "1000 points on the losing side".
        distance = abs(self.value)
        return spec.normalize_price(reference + direction * distance * spec.point)
