"""Close-all / cancel-all touch only the trader's own magic unless told otherwise (ADR 0011)."""

import logging
import sys

import pytest

from PythonMetaTrader5 import (
    ANY_MAGIC,
    AnyMagic,
    Broker,
    ErrorKind,
    PendingKind,
    PendingOrder,
    Side,
    connect,
)
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5
from .fakes import FakeClock, FakeTerminal, make_position

OWN = 42  # the conftest trader's magic
MANUAL = 0  # what MT5 stores for trades opened by hand


def closed_tickets(terminal: FakeTerminal) -> list[int | None]:
    return [r.position for r in terminal.sent if isinstance(r, OrderRequest)]


def cancelled_tickets(terminal: FakeTerminal) -> list[int]:
    return [r.order for r in terminal.sent if isinstance(r, CancelRequest)]


def order(ticket: int, magic: int) -> PendingOrder:
    return PendingOrder(
        ticket=ticket,
        symbol="EURUSD",
        side=Side.BUY,
        kind=PendingKind.LIMIT,
        volume=0.1,
        price=1.0,
        magic=magic,
        comment="",
    )


@pytest.fixture
def mt5(monkeypatch: pytest.MonkeyPatch) -> FakeMT5:
    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


@pytest.fixture
def mixed_positions(terminal: FakeTerminal) -> FakeTerminal:
    terminal.open_positions = [
        make_position(1, magic=OWN),
        make_position(2, magic=MANUAL),
        make_position(3, magic=7),
    ]
    return terminal


@pytest.mark.parametrize("call", [(), ("EURUSD",)])
def test_close_without_magic_closes_only_own_positions(
    trader: Trader, mixed_positions: FakeTerminal, call: tuple[str, ...]
) -> None:
    assert isinstance(trader.close_positions(*call), Ok)
    assert closed_tickets(mixed_positions) == [1]


def test_an_explicit_none_is_still_own_not_the_whole_account(
    trader: Trader, mixed_positions: FakeTerminal
) -> None:
    # A None read from a missing config key must not widen the blast radius.
    trader.close_positions(magic=None)
    assert closed_tickets(mixed_positions) == [1]


def test_any_magic_closes_the_whole_account(trader: Trader, mixed_positions: FakeTerminal) -> None:
    trader.close_positions(magic=ANY_MAGIC)
    assert closed_tickets(mixed_positions) == [1, 2, 3]


def test_an_explicit_magic_selects_that_magic(
    trader: Trader, mixed_positions: FakeTerminal
) -> None:
    trader.close_positions(magic=7)
    assert closed_tickets(mixed_positions) == [3]


def test_a_ticket_is_closed_whatever_its_magic(
    trader: Trader, mixed_positions: FakeTerminal
) -> None:
    # Filtering it out would return Ok([]) for a position the caller named.
    result = trader.close_positions(ticket=2)
    assert isinstance(result, Ok)
    assert closed_tickets(mixed_positions) == [2]


def test_cancel_without_magic_cancels_only_own_orders(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_orders = [order(5, OWN), order(6, MANUAL), order(7, 7)]
    trader.cancel_pending_orders()
    assert cancelled_tickets(terminal) == [5]


def test_cancel_with_any_magic_cancels_every_order(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_orders = [order(5, OWN), order(6, MANUAL), order(7, 7)]
    trader.cancel_pending_orders(magic=ANY_MAGIC)
    assert cancelled_tickets(terminal) == [5, 6, 7]


def test_queries_still_list_everything_by_default(
    trader: Trader, mixed_positions: FakeTerminal
) -> None:
    listed = trader.positions()
    assert isinstance(listed, Ok)
    assert [p.ticket for p in listed.value] == [1, 2, 3]
    assert trader.positions(magic=ANY_MAGIC) == listed


@pytest.mark.parametrize("magic", ["42", True, 1.5, -1, 2**64])
def test_a_magic_that_is_not_a_magic_number_is_refused(
    trader: Trader, mixed_positions: FakeTerminal, magic: object
) -> None:
    # "42" != 42 would match nothing and report Ok([]) with every position open.
    closed = trader.close_positions(magic=magic)  # type: ignore[arg-type]
    assert isinstance(closed, Err)
    assert closed.error.errors[0].kind is ErrorKind.INVALID_ARGUMENT
    cancelled = trader.cancel_pending_orders(magic=magic)  # type: ignore[arg-type]
    assert isinstance(cancelled, Err)
    for listed in (
        trader.positions(magic=magic),  # type: ignore[arg-type]
        trader.pending_orders(magic=magic),  # type: ignore[arg-type]
    ):
        assert isinstance(listed, Err)
        assert listed.error.kind is ErrorKind.INVALID_ARGUMENT
    assert mixed_positions.sent == []


def test_legacy_close_and_cancel_keep_acting_on_every_magic(
    terminal: FakeTerminal, clock: FakeClock
) -> None:
    # 2.x Close(symbol) / CancelOrders(symbol) ignored magic numbers.
    terminal.open_positions = [make_position(1, magic=7), make_position(2, magic=MANUAL)]
    terminal.open_orders = [order(5, 7)]
    with pytest.warns(DeprecationWarning, match="Broker is deprecated"):
        broker = Broker(123, "pw", "Demo", terminal=terminal, clock=clock)
    assert broker.Close("EURUSD") is True
    broker.CancelOrders("EURUSD")
    assert closed_tickets(terminal) == [1, 2]
    assert cancelled_tickets(terminal) == [5]


@pytest.mark.parametrize("magic", [None, ANY_MAGIC, "1001", True, -1, 2**64])
def test_connect_refuses_an_own_magic_that_is_not_a_magic_number(
    mt5: FakeMT5, magic: object
) -> None:
    # magic=None from a missing config key made the "own" default mean "all".
    result = connect(123, "pw", "Demo", magic=magic)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT
    assert mt5.calls == []


@pytest.mark.parametrize("magic", [None, ANY_MAGIC, "1001", True, -1, 2**64])
def test_trader_refuses_an_own_magic_that_is_not_a_magic_number(
    terminal: FakeTerminal, clock: FakeClock, magic: object
) -> None:
    with pytest.raises(ValueError, match="magic"):
        Trader(terminal, clock, magic=magic)  # type: ignore[arg-type]


def test_close_all_with_own_magic_zero_warns_that_it_includes_manual_trades(
    terminal: FakeTerminal, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    terminal.open_positions = [make_position(1, magic=MANUAL)]
    terminal.open_orders = [order(5, MANUAL)]
    trader = Trader(terminal, clock)
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        trader.close_positions()
        trader.cancel_pending_orders()
    warnings = [r.getMessage() for r in caplog.records if "manual trades" in r.getMessage()]
    assert len(warnings) == 2
    # ANY_MAGIC would widen the call; an explicit 0 is the way to acknowledge it.
    assert all("magic=0" in w and "ANY_MAGIC" not in w for w in warnings)


def test_magic_zero_warning_only_when_something_is_actually_affected(
    terminal: FakeTerminal, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    trader = Trader(terminal, clock)
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        trader.close_positions()  # nothing open
        trader.close_positions("")  # refused before anything is listed
        terminal.open_positions = [make_position(1, magic=MANUAL)]
        trader.close_positions(magic=0)  # acknowledged explicitly
    assert not [r for r in caplog.records if "manual trades" in r.getMessage()]


def test_no_warning_once_the_trader_has_its_own_magic_or_asks_for_all(
    trader: Trader, mixed_positions: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        trader.close_positions()
        Trader(mixed_positions, FakeClock()).close_positions(magic=ANY_MAGIC)
    assert not [r for r in caplog.records if "manual trades" in r.getMessage()]


def test_any_magic_type_is_public_for_annotations() -> None:
    assert type(ANY_MAGIC) is AnyMagic


def test_the_largest_mt5_magic_is_accepted(terminal: FakeTerminal, clock: FakeClock) -> None:
    # MT5 stores magic as a ulong; anything above would overflow in order_send.
    largest = 2**64 - 1
    terminal.open_positions = [make_position(1, magic=largest)]
    trader = Trader(terminal, clock, magic=largest)
    assert isinstance(trader.close_positions(), Ok)
    assert closed_tickets(terminal) == [1]


def test_a_default_close_that_matches_nothing_says_what_it_left_open(
    trader: Trader, terminal: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    # Netting: the bot's deal merged into a manual position, which kept magic 0.
    terminal.open_positions = [make_position(1, magic=MANUAL)]
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        assert trader.close_positions("EURUSD") == Ok([])
        terminal.open_orders = [order(5, MANUAL)]
        assert trader.cancel_pending_orders("EURUSD") == Ok([])
    left = [r.getMessage() for r in caplog.records if "left open" in r.getMessage()]
    assert len(left) == 2
    assert all("ANY_MAGIC" in m for m in left)
    assert terminal.sent == []


def test_a_failed_check_for_items_left_open_is_logged_not_dropped(
    trader: Trader, terminal: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    # The own listing is empty, then the listing of every magic fails: Ok([])
    # alone would read as "flat" with a merged netting position still open.
    answers = iter([Ok([]), Err(TradeError(ErrorKind.TERMINAL_ERROR, "IPC timeout"))])
    terminal.positions = lambda **_: next(answers)  # type: ignore[method-assign]
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        assert trader.close_positions("EURUSD") == Ok([])
    (message,) = [r.getMessage() for r in caplog.records]
    assert "could not check" in message
    assert "IPC timeout" in message


def test_no_left_open_warning_when_own_items_were_handled(
    trader: Trader, mixed_positions: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="PythonMetaTrader5"):
        trader.close_positions("EURUSD")
        trader.close_positions(magic=7)
    assert not [r for r in caplog.records if "left open" in r.getMessage()]


@pytest.mark.parametrize("magic", ["1001", True, -1, 2**64, None, ANY_MAGIC])
def test_own_magic_error_does_not_suggest_any_magic(mt5: FakeMT5, magic: object) -> None:
    result = connect(123, "pw", "Demo", magic=magic)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert "ANY_MAGIC" not in result.error.message


def test_cancel_with_any_magic_still_keeps_to_the_symbol(
    trader: Trader, terminal: FakeTerminal
) -> None:
    xau = PendingOrder(
        ticket=8,
        symbol="XAUUSD",
        side=Side.BUY,
        kind=PendingKind.LIMIT,
        volume=0.1,
        price=1.0,
        magic=7,
        comment="",
    )
    terminal.open_orders = [order(5, OWN), order(6, MANUAL), xau]
    trader.cancel_pending_orders("EURUSD", magic=ANY_MAGIC)
    assert cancelled_tickets(terminal) == [5, 6]
