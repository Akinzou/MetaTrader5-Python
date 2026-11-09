"""Inputs a webhook can deliver malformed must fail loudly before anything is sent."""

from __future__ import annotations

import math
import threading
from decimal import Decimal

import pytest

from PythonMetaTrader5 import Broker, Stop, StopKind
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.entries import Entry
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, raw_position
from .fakes import EURUSD, FakeClock, FakeTerminal, make_position

NOT_A_STOP = [0, 0.0, -1.1, math.nan, math.inf, True, Decimal("sNaN"), "1.1"]
NOT_A_NUMBER = [math.nan, math.inf, -math.inf, True, "0.1", Decimal("sNaN"), Decimal("NaN"), None]


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


@pytest.mark.parametrize("level", [0, -1.0, math.inf, math.nan, True])
def test_legacy_limit_with_a_bad_level_sends_nothing(terminal: FakeTerminal, level: object) -> None:
    # A bad level used to be compared with the quote first and "crossed" into a market order.
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    assert broker.SellLimit("EURUSD", 0.1, level) is None  # type: ignore[arg-type]
    assert broker.BuyLimit("EURUSD", 0.1, level) is None  # type: ignore[arg-type]
    assert terminal.sent == []


@pytest.mark.parametrize("value", [0, -1.1, True, math.nan, math.inf, Decimal("sNaN"), "1.1"])
@pytest.mark.parametrize("factory", [Stop.at_price, Stop.points])
def test_a_stop_cannot_be_built_from_a_value_mt5_would_misread(
    factory: object, value: object
) -> None:
    if factory == Stop.points and isinstance(value, float) and value < 0:
        pytest.skip("a negative distance is a distance")
    with pytest.raises(ValueError, match="positive finite"):
        factory(value)  # type: ignore[operator]


def test_a_stop_holds_a_float_and_a_distance_has_no_sign() -> None:
    assert Stop.points(-1000) == Stop.points(1000)
    assert Stop.at_price(Decimal("1.1")).value == 1.1
    assert isinstance(Stop.points(Decimal("100")).value, float)


@pytest.mark.parametrize("sl_type", ["absolute", "offset"])
def test_legacy_refuses_a_bool_stop(terminal: FakeTerminal, sl_type: str) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    assert broker.OpenPosition("EURUSD", "buy", 0.1, sl=True, sl_type=sl_type) is None  # type: ignore[arg-type]
    assert broker.OpenPosition("EURUSD", "buy", 0.1, sl=0, sl_type=sl_type) is None
    assert terminal.sent == []


def test_decimal_amounts_are_accepted(trader: Trader, terminal: FakeTerminal) -> None:
    result = trader.open_position("EURUSD", "buy", Decimal("0.1"), price=Decimal("1.1001"))  # type: ignore[arg-type]
    assert isinstance(result, Ok)
    request = terminal.sent[0]
    assert (request.volume, request.price) == (0.1, 1.1001)  # type: ignore[union-attr]


def test_a_bad_price_is_refused_before_any_symbol_lookup(
    trader: Trader, terminal: FakeTerminal
) -> None:
    for result in (
        trader.open_position("EURUSD", "buy", 0.1, price=math.nan),
        trader.place_limit_order("EURUSD", "buy", 0.1, 0),
    ):
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.INVALID_PRICE
    assert terminal.symbol_lookups == []


def test_a_bad_side_is_still_reported_before_a_bad_price(trader: Trader) -> None:
    result = trader.open_position("EURUSD", "hold", 0.1, price=math.nan)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT


def test_an_entry_without_a_price_or_a_quote_sends_nothing() -> None:
    entry = Entry(EURUSD, Side.BUY, 0.1, "", None, None, None)
    result = entry.request(pending=None, deviation=10, magic=0)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.NO_PRICE


def test_a_price_that_snaps_to_zero_is_refused_before_sending(
    trader: Trader, terminal: FakeTerminal
) -> None:
    for result in (
        trader.open_position("EURUSD", "buy", 0.1, price=1e-6),
        trader.place_limit_order("EURUSD", "buy", 0.1, 0.000004),
    ):
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.INVALID_PRICE
    assert terminal.sent == []


def test_numbers_too_large_for_a_float_are_refused_not_raised(
    trader: Trader, terminal: FakeTerminal
) -> None:
    huge = 10**400
    for result, kind in (
        (trader.open_position("EURUSD", "buy", huge), ErrorKind.INVALID_VOLUME),
        (trader.open_position("EURUSD", "buy", 0.1, sl=huge), ErrorKind.INVALID_STOPS),
    ):
        assert isinstance(result, Err)
        assert result.error.kind is kind
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    assert broker.OpenPosition("EURUSD", "buy", 0.1, sl=huge, sl_type="offset") is None
    assert terminal.sent == []


def test_stop_parse_is_the_non_raising_way_to_build_a_stop() -> None:
    assert Stop.parse(-1000, StopKind.POINTS) == Ok(Stop.points(1000))
    for value in (math.nan, 0, True):
        parsed = Stop.parse(value, StopKind.POINTS)
        assert isinstance(parsed, Err)
        assert parsed.error.kind is ErrorKind.INVALID_STOPS


def test_a_stop_kind_must_be_a_stop_kind() -> None:
    with pytest.raises(TypeError, match="StopKind"):
        Stop(1000, "points")  # type: ignore[arg-type]


def test_a_finite_price_too_large_for_the_tick_grid_is_refused_not_raised(
    trader: Trader, terminal: FakeTerminal
) -> None:
    for result, kind in (
        (trader.open_position("EURUSD", "buy", 0.1, price=1e305), ErrorKind.INVALID_PRICE),
        (trader.place_limit_order("EURUSD", "buy", 0.1, 1e305), ErrorKind.INVALID_PRICE),
        (trader.open_position("EURUSD", "buy", 0.1, sl=1e305), ErrorKind.INVALID_STOPS),
        (trader.open_position("EURUSD", "buy", 0.1, tp=1e305), ErrorKind.INVALID_STOPS),
    ):
        assert isinstance(result, Err)
        assert result.error.kind is kind
    assert terminal.sent == []


def test_stop_parse_reports_a_wrong_kind_as_a_type_error_for_any_value() -> None:
    for value in (0, 5):
        with pytest.raises(TypeError, match="StopKind"):
            Stop.parse(value, "points")  # type: ignore[arg-type]
