"""Instrument specification and the rules that depend only on it."""

from __future__ import annotations

import math
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
    # Required on purpose: a default would quietly treat an exchange symbol as
    # market execution and send limits that cancel instead of resting.
    exchange_execution: bool

    def normalize_price(self, price: float) -> float:
        # A price must sit on the tick grid, not merely have `digits` decimals:
        # index CFDs often have tick 0.25 with 2 digits and reject 5780.13.
        step = self.tick_size if self.tick_size > 0 else self.point
        return round(round(price / step) * step, self.digits)

    def price_on_grid(self, price: float, kind: ErrorKind, what: str) -> Result[float, TradeError]:
        """``price`` on the tick grid, refused if it is not a usable positive level.

        The one place every sent level (entry price, sl, tp) is put on the grid,
        so the two ways a positive finite input still goes wrong are checked
        once: 1e305 / 1e-5 overflows to inf (round(inf) raises), and 1e-6
        snaps to 0.0, which MT5 reads as "no stop" or "fill at the market".
        """
        step = self.tick_size if self.tick_size > 0 else self.point
        if step <= 0:
            # Broken symbol data, refused like a zero volume_step.
            return Err(TradeError(kind, f"{self.name} reports no tick size or point"))
        if not math.isfinite(price / step):
            return Err(TradeError(kind, f"{what} {price} is out of range for {self.name}"))
        level = self.normalize_price(price)
        if level <= 0:
            return Err(TradeError(kind, f"{what} {price} snaps to {level} on {self.name}"))
        return Ok(level)

    def validate_volume(self, volume: float) -> Result[float, TradeError]:
        if self.volume_step <= 0:
            # Broken symbol data: refusing is the only safe answer, guessing a
            # step could send a volume the broker never allowed.
            return Err(self._volume_error(volume, "not checkable against"))
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
