"""Broken symbol data from the terminal must be refused before anything is priced."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from PythonMetaTrader5 import Stop
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.result import Err

from .fake_mt5 import FakeMT5, symbol_info
from .fakes import EURUSD, FakeTerminal

BROKEN = [
    {"point": 0.0},
    {"point": math.inf},
    {"point": math.nan},
    {"trade_tick_size": math.inf},
    {"trade_tick_size": -0.1},
    {"volume_step": 0.0},
    {"volume_min": 0.0},
    {"volume_max": 0.001},
    {"digits": -1},
]
SPEC_FIELD = {"trade_tick_size": "tick_size"}


@pytest.mark.parametrize("broken", BROKEN)
def test_the_adapter_refuses_symbol_data_that_cannot_price_an_order(
    broken: dict[str, float],
) -> None:
    mt5 = FakeMT5()
    info = symbol_info()
    for key, value in broken.items():
        setattr(info, key, value)
    mt5.symbols["EURUSD"] = info
    result = MetaTrader5Terminal(mt5).symbol("EURUSD")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.TERMINAL_ERROR


@pytest.mark.parametrize("broken", BROKEN)
def test_a_symbol_spec_with_broken_data_cannot_exist(broken: dict[str, float]) -> None:
    fields = {SPEC_FIELD.get(key, key): value for key, value in broken.items()}
    with pytest.raises(ValueError, match="EURUSD"):
        replace(EURUSD, **fields)  # type: ignore[arg-type]


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
