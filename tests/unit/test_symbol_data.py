"""Broken data from the terminal must never price an order, and never block a close."""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

from PythonMetaTrader5 import Stop
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, symbol_info
from .fakes import EURUSD, FakeTerminal, make_position

BROKEN_STEP = [{"point": 0.0, "tick_size": 0.0}, {"point": math.inf, "tick_size": 0.0}]
BROKEN_STEP += [{"tick_size": math.inf}, {"point": math.nan, "tick_size": 0.0}]
BROKEN_STEP += [{"tick_size": math.nan}, {"tick_size": -0.25}, {"digits": -1}]
BROKEN_VOLUME = [{"volume_step": 0.0}, {"volume_min": 0.0}, {"volume_max": 0.001}]
BROKEN_VOLUME += [{"volume_max": math.nan}, {"volume_step": math.inf}]


@pytest.mark.parametrize("broken", BROKEN_STEP)
def test_a_symbol_without_a_usable_step_prices_nothing(
    trader: Trader, terminal: FakeTerminal, broken: dict[str, float]
) -> None:
    terminal.specs["EURUSD"] = replace(EURUSD, **broken)
    for result in (
        trader.place_limit_order("EURUSD", "buy", 0.1, 1.05),
        trader.open_position("EURUSD", "buy", 0.1, sl=1.0),
        trader.open_position("EURUSD", "buy", 0.1),  # no price, no stops
    ):
        assert isinstance(result, Err)
        # The broker's data is at fault, not the caller's input.
        assert result.error.kind is ErrorKind.TERMINAL_ERROR
    assert terminal.sent == []


@pytest.mark.parametrize("point", [0.0, math.inf, math.nan])
def test_points_stops_need_a_usable_point_but_prices_do_not(
    trader: Trader, terminal: FakeTerminal, point: float
) -> None:
    # A tick size alone is enough for absolute prices; only points need `point`.
    terminal.specs["EURUSD"] = replace(EURUSD, point=point)
    refused = trader.open_position("EURUSD", "buy", 0.1, sl=Stop.points(1000))
    assert isinstance(refused, Err)
    assert refused.error.kind is ErrorKind.TERMINAL_ERROR
    assert terminal.sent == []
    assert isinstance(trader.open_position("EURUSD", "buy", 0.1, sl=1.09), Ok)


@pytest.mark.parametrize("broken", BROKEN_VOLUME)
def test_unusable_volume_limits_refuse_every_entry(
    trader: Trader, terminal: FakeTerminal, broken: dict[str, float]
) -> None:
    terminal.specs["EURUSD"] = replace(EURUSD, **broken)
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.TERMINAL_ERROR
    assert terminal.sent == []


@pytest.mark.parametrize("broken", [*BROKEN_STEP, *BROKEN_VOLUME])
def test_a_position_on_a_symbol_with_broken_data_can_still_be_closed(
    trader: Trader, terminal: FakeTerminal, broken: dict[str, float]
) -> None:
    terminal.specs["EURUSD"] = replace(EURUSD, **broken)
    terminal.open_positions = [make_position(1)]
    closed = trader.close_positions("EURUSD")
    assert isinstance(closed, Ok)
    assert len(closed.value) == 1


def test_the_adapter_passes_broken_symbol_data_on_so_closes_still_work() -> None:
    # Refusing it in the adapter would block close_positions (the a0f2aba bug).
    mt5 = FakeMT5()
    info = symbol_info()
    info.point, info.trade_tick_size, info.volume_step = 0.0, 0.0, 0.0
    mt5.symbols["EURUSD"] = info
    spec = MetaTrader5Terminal(mt5).symbol("EURUSD")
    assert isinstance(spec, Ok)
    assert isinstance(spec.value.check_tradable(), Err)


@pytest.mark.parametrize("quote", [math.nan, math.inf])
def test_a_nan_or_infinite_quote_is_no_price(quote: float) -> None:
    mt5 = FakeMT5()
    mt5.ticks["EURUSD"] = SimpleNamespace(bid=1.1, ask=quote)
    result = MetaTrader5Terminal(mt5).tick("EURUSD")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.NO_PRICE


class _OutOfRange(Fraction):
    # Stands in for a numpy longdouble under np.seterr(over="raise").
    def __float__(self) -> float:
        raise FloatingPointError("overflow")


def test_a_number_whose_float_conversion_overflows_is_refused_not_raised(
    trader: Trader, terminal: FakeTerminal
) -> None:
    result = trader.open_position("EURUSD", "buy", _OutOfRange(1, 10))
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_VOLUME
    assert terminal.sent == []


def test_a_bad_price_is_reported_before_a_bad_stop(trader: Trader) -> None:
    result = trader.place_limit_order("EURUSD", "buy", 0.1, 1e-6, sl=1e-6)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_PRICE


def test_absolute_stops_are_checked_before_the_quote_is_fetched(
    trader: Trader, terminal: FakeTerminal
) -> None:
    # No quote: a stop that can never be valid must not wait for retries first.
    terminal.ticks.clear()
    result = trader.open_position("EURUSD", "buy", 0.1, sl=1e-6)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_STOPS


def test_a_points_take_profit_below_zero_is_refused(trader: Trader, terminal: FakeTerminal) -> None:
    result = trader.open_position("EURUSD", "sell", 0.1, tp=Stop.points(10_000_000))
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_STOPS
    assert terminal.sent == []
