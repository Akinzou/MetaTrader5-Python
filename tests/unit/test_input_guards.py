"""Inputs a webhook can deliver malformed must fail loudly before anything is sent."""

from __future__ import annotations

import math
import threading
from dataclasses import replace

import pytest

from PythonMetaTrader5 import Broker, Stop
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, raw_position
from .fakes import EURUSD, FakeClock, FakeTerminal, make_position

NOT_A_STOP = [0, 0.0, -1.1, math.nan, math.inf, True, Stop.points(0), Stop.at_price(0)]
NOT_A_NUMBER = [math.nan, math.inf, -math.inf, True, "0.1", None]


@pytest.mark.parametrize("stop", NOT_A_STOP)
@pytest.mark.parametrize("which", ["sl", "tp"])
def test_a_stop_of_zero_or_garbage_is_refused_not_dropped(
    trader: Trader, terminal: FakeTerminal, stop: object, which: str
) -> None:
    # MT5 reads sl=0 as "no stop": a missing webhook field would open unprotected.
    for result in (
        trader.open_position("EURUSD", "buy", 0.1, **{which: stop}),  # type: ignore[arg-type]
        trader.place_limit_order("EURUSD", "buy", 0.1, 1.09, **{which: stop}),  # type: ignore[arg-type]
    ):
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.INVALID_STOPS
    assert terminal.sent == []


@pytest.mark.parametrize("stop", [0.000001, Stop.points(10_000_000)])
def test_a_stop_that_resolves_to_zero_or_below_is_refused(
    trader: Trader, terminal: FakeTerminal, stop: Stop | float
) -> None:
    # 0.000001 snaps to 0.0 on a 5-digit grid; 10M points below 1.1 is negative.
    result = trader.open_position("EURUSD", "buy", 0.1, sl=stop)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_STOPS
    assert terminal.sent == []


@pytest.mark.parametrize("volume", [*NOT_A_NUMBER, 0, -0.1])
def test_volume_that_is_not_a_positive_finite_number_is_refused(
    trader: Trader, terminal: FakeTerminal, volume: object
) -> None:
    result = trader.open_position("EURUSD", "buy", volume)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_VOLUME
    assert terminal.sent == []


@pytest.mark.parametrize("price", [*NOT_A_NUMBER[:-1], 0, -1.0])
def test_price_that_is_not_a_positive_finite_number_is_refused(
    trader: Trader, terminal: FakeTerminal, price: object
) -> None:
    for result in (
        trader.open_position("EURUSD", "buy", 0.1, price=price),  # type: ignore[arg-type]
        trader.place_limit_order("EURUSD", "buy", 0.1, price),  # type: ignore[arg-type]
    ):
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.INVALID_PRICE
    assert terminal.sent == []


def test_a_symbol_reporting_volume_step_zero_is_an_error_not_a_crash(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.specs["EURUSD"] = replace(EURUSD, volume_step=0.0)
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_VOLUME


@pytest.mark.parametrize("ticket", [0, -5, True, 1.0, "7"])
def test_a_ticket_that_is_not_a_positive_integer_never_reaches_the_terminal(
    trader: Trader, terminal: FakeTerminal, ticket: object
) -> None:
    # positions_get(ticket=0) may mean "no filter" and close the whole account.
    terminal.open_positions = [make_position(1)]
    query = trader.positions(ticket=ticket)  # type: ignore[arg-type]
    assert isinstance(query, Err)
    assert query.error.kind is ErrorKind.INVALID_ARGUMENT
    closed = trader.close_positions(ticket=ticket)  # type: ignore[arg-type]
    assert isinstance(closed, Err)
    assert closed.error.errors[0].kind is ErrorKind.INVALID_ARGUMENT
    assert terminal.sent == []


def test_legacy_calls_refuse_a_zero_stop_and_a_zero_ticket(terminal: FakeTerminal) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    terminal.open_positions = [make_position(1)]
    assert broker.BuySL("EURUSD", 0.1, 0) is None
    assert broker.Close(None, ticket=0) is False
    assert broker.GetPositions(ticket=0) == []
    assert terminal.sent == []


def test_adapter_applies_symbol_and_ticket_together() -> None:
    # MT5's positions_get ignores `symbol` once `ticket` is given.
    mt5 = FakeMT5()
    mt5.positions = (raw_position(ticket=1),)
    adapter = MetaTrader5Terminal(mt5)
    assert adapter.positions(symbol="XAUUSD", ticket=1) == Ok([])
    listed = adapter.positions(symbol="EURUSD", ticket=1)
    assert isinstance(listed, Ok)
    assert [p.ticket for p in listed.value] == [1]


def test_concurrent_calls_cannot_read_each_others_last_error() -> None:
    # last_error() is process-global: a call and its error read must not interleave.
    mt5 = FakeMT5()
    entered, release = threading.Event(), threading.Event()
    mt5.positions = None

    def blocking_positions_get(**_: object) -> None:
        entered.set()
        release.wait(5)

    mt5.positions_get = blocking_positions_get  # type: ignore[method-assign]
    first, second = MetaTrader5Terminal(mt5), MetaTrader5Terminal(mt5)
    worker = threading.Thread(target=first.positions)
    worker.start()
    assert entered.wait(5)
    finished = threading.Event()
    other = threading.Thread(target=lambda: (second.tick("EURUSD"), finished.set()))
    other.start()
    blocked = not finished.wait(0.2)
    release.set()
    worker.join(5)
    other.join(5)
    assert blocked, "a second adapter ran while the first was between call and last_error()"
