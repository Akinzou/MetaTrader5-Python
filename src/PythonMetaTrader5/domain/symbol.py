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

    # Broken terminal data (a point of 0 or inf, a NaN tick size, a volume step
    # of 0) is reported as TERMINAL_ERROR: it is the broker's fault, and a bot
    # must not file it as a bad signal. It is checked on use rather than refused
    # for the whole spec, because closing a position needs only filling_flags
    # and must keep working on such a symbol (a constructor invariant was tried
    # and dropped for exactly that). Entries call check_tradable() first.

    def check_tradable(self) -> Result[None, TradeError]:
        problem = self._pricing_problem() or self._volume_problem()
        return Ok(None) if problem is None else Err(self._data_error(problem))

    def price_on_grid(self, price: float, kind: ErrorKind, what: str) -> Result[float, TradeError]:
        """``price`` on the tick grid, refused if it is not a usable positive level.

        Every caller-supplied level (an explicit entry price, sl, tp) goes through
        here; quote prices come from the terminal already on the grid. The two
        ways a positive finite input still goes wrong are checked once: 1e305 /
        1e-5 overflows to inf (round(inf) raises), and 1e-6 snaps to 0.0, which
        MT5 reads as "no stop" or "fill at the market".
        """
        problem = self._pricing_problem()
        if problem is not None:
            return Err(self._data_error(problem))
        # A price must sit on the tick grid, not merely have `digits` decimals:
        # index CFDs often have tick 0.25 with 2 digits and reject 5780.13.
        step = self._step
        if not math.isfinite(price / step):
            return Err(TradeError(kind, f"{what} {price} is out of range for {self.name}"))
        level = round(round(price / step) * step, self.digits)
        if level <= 0:
            return Err(TradeError(kind, f"{what} {price} snaps to {level} on {self.name}"))
        return Ok(level)

    def points_to_price(self, points: float) -> Result[float, TradeError]:
        # Only points stops need `point`: a symbol with a valid tick size and a
        # point of 0 still trades absolute prices.
        if not _usable(self.point):
            return Err(self._data_error(f"point {self.point!r} cannot measure a points stop"))
        return Ok(points * self.point)

    def validate_volume(self, volume: float) -> Result[float, TradeError]:
        problem = self._volume_problem()
        if problem is not None:
            return Err(self._data_error(problem))
        if volume < self.volume_min - _EPSILON or volume > self.volume_max + _EPSILON:
            return Err(self._volume_error(volume, "outside"))
        steps = (volume - self.volume_min) / self.volume_step
        if abs(steps - round(steps)) > _STEP_TOLERANCE:
            return Err(self._volume_error(volume, "not a multiple of the step within"))
        snapped = self.volume_min + round(steps) * self.volume_step
        return Ok(round(snapped, _VOLUME_DECIMALS))

    @property
    def _step(self) -> float:
        # A tick size of 0 means the terminal did not report one; point is used.
        return self.tick_size if self.tick_size > 0 else self.point

    def _pricing_problem(self) -> str | None:
        # Checked before _step is used: a NaN or negative tick size would
        # otherwise fall back to point without anyone noticing.
        if not (self.tick_size == 0 or _usable(self.tick_size)):
            return f"tick size {self.tick_size!r} is neither 0 nor positive and finite"
        if not _usable(self._step):
            return f"no usable tick size or point (point {self.point!r})"
        if self.digits < 0:
            return f"digits {self.digits} is negative"
        return None

    def _volume_problem(self) -> str | None:
        limits = (self.volume_min, self.volume_max, self.volume_step)
        if not all(_usable(x) for x in limits):
            return f"volume min/max/step {limits} are not all positive and finite"
        if self.volume_max < self.volume_min:
            return f"volume_max {self.volume_max} is below volume_min {self.volume_min}"
        return None

    def _data_error(self, problem: str) -> TradeError:
        return TradeError(ErrorKind.TERMINAL_ERROR, f"{self.name}: broken symbol data: {problem}")

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


def _usable(value: float) -> bool:
    return math.isfinite(value) and value > 0
