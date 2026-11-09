"""Instrument specification and the rules that depend only on it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.result import Err, Ok, Result

# Bit flags of SYMBOL_FILLING_MODE as documented in MQL5. The Python package does
# not export them, so they are defined here rather than guessed at call sites.
_FILLING_FOK_FLAG = 1
_FILLING_IOC_FLAG = 2

# Tolerances for float checks: volumes are entered as decimal literals (0.07)
# that are not exactly representable in binary floating point, so an exact
# comparison would reject valid lots.
_EPSILON = 1e-9
_STEP_TOLERANCE = 1e-6
# Volume precision sent to the server; well below any broker's volume_step.
_VOLUME_DECIMALS = 8


class Filling(Enum):
    FOK = "fok"
    IOC = "ioc"
    RETURN = "return"


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    name: str
    digits: int
    point: float
    tick_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    filling_flags: int
    exchange_execution: bool = False

    def normalize_price(self, price: float) -> float:
        # A price must sit on the tick grid, not merely have `digits` decimals:
        # index CFDs often have tick 0.25 with 2 digits and reject 5780.13.
        step = self.tick_size if self.tick_size > 0 else self.point
        return round(round(price / step) * step, self.digits)

    def validate_volume(self, volume: float) -> Result[float, TradeError]:
        if volume < self.volume_min - _EPSILON or volume > self.volume_max + _EPSILON:
            return Err(self._volume_error(volume, "outside"))
        steps = (volume - self.volume_min) / self.volume_step
        if abs(steps - round(steps)) > _STEP_TOLERANCE:
            return Err(self._volume_error(volume, "not a multiple of the step within"))
        snapped = self.volume_min + round(steps) * self.volume_step
        return Ok(round(snapped, _VOLUME_DECIMALS))

    def market_filling(self) -> Filling:
        # FOK first: a webhook bot asking for 1 lot must get 1 lot or nothing.
        # IOC could silently leave it with a partial fill it never asked for.
        if self.filling_flags & _FILLING_FOK_FLAG:
            return Filling.FOK
        if self.filling_flags & _FILLING_IOC_FLAG:
            return Filling.IOC
        return Filling.RETURN

    def pending_filling(self) -> Filling:
        # Exchange-execution symbols (stocks, futures) only let a limit rest in the
        # book with RETURN; FOK/IOC there would cancel it unless instantly fillable.
        # Elsewhere the market rule applies: RETURN is refused by many
        # market-execution brokers (10030) that accepted the IOC sent by 2.x.
        return Filling.RETURN if self.exchange_execution else self.market_filling()

    def _volume_error(self, volume: float, reason: str) -> TradeError:
        return TradeError(
            ErrorKind.INVALID_VOLUME,
            f"{self.name}: volume {volume} is {reason} "
            f"[{self.volume_min}, {self.volume_max}] step {self.volume_step}",
        )
