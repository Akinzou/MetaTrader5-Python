"""Edge cases where a mistake would close, duplicate or silently lose trades."""

import sys

import pytest

from PythonMetaTrader5 import Broker, connect
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.market import Position
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import CancelRequest
from PythonMetaTrader5.domain.symbol import Filling
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, symbol_info
from .fakes import FakeClock, FakeTerminal


def position(ticket: int, volume: float = 0.5) -> Position:
    return Position(
        ticket=ticket,
        symbol="EURUSD",
        side=Side.BUY,
        volume=volume,
        price_open=1.0,
        sl=None,
        tp=None,
        price_current=1.0,
        profit=0.0,
        time=0,
        magic=0,
        comment="",
    )


def test_empty_symbol_is_rejected_instead_of_meaning_all(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [position(1)]
    for result in (
        trader.close_positions(""),
        trader.cancel_pending_orders(""),
    ):
        assert isinstance(result, Err)
        assert result.error.errors[0].kind is ErrorKind.INVALID_ARGUMENT
    for query in (trader.positions(""), trader.pending_orders("")):
        assert isinstance(query, Err)
        assert query.error.kind is ErrorKind.INVALID_ARGUMENT
    assert terminal.sent == []


def test_adapter_passes_an_empty_symbol_through_as_a_filter() -> None:
    mt5 = FakeMT5()
    adapter = MetaTrader5Terminal(mt5)
    adapter.positions(symbol="")
    adapter.pending_orders(symbol="")
    filters = [kwargs for name, _, kwargs in mt5.calls if name in {"positions_get", "orders_get"}]
    assert filters == [{"symbol": ""}, {"symbol": ""}]


def test_legacy_close_without_symbol_or_ticket_closes_nothing(
    terminal: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    terminal.open_positions = [position(1)]
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    assert broker.Close(None) is False
    assert terminal.sent == []
    assert "symbol or ticket" in caplog.text


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (-10005, ErrorKind.OUTCOME_UNKNOWN),  # IPC timeout: request may be on the server
        (-10001, ErrorKind.OUTCOME_UNKNOWN),
        (-2, ErrorKind.TERMINAL_ERROR),  # invalid arguments: never sent
        (-10004, ErrorKind.TERMINAL_ERROR),  # no IPC connection: never sent
        (-8, ErrorKind.ALGO_TRADING_DISABLED),
    ],
)
def test_undelivered_send_is_unknown_unless_provably_not_sent(code: int, kind: ErrorKind) -> None:
    mt5 = FakeMT5()
    mt5.send_result, mt5.error = None, (code, "x")
    result = MetaTrader5Terminal(mt5).send(CancelRequest(order=1))
    assert isinstance(result, Err)
    assert result.error.kind is kind


def test_symbol_that_cannot_be_selected_is_an_error() -> None:
    mt5 = FakeMT5()
    mt5.symbols["GBPJPY"] = symbol_info("GBPJPY", visible=False)
    mt5.symbol_select = lambda name, enable: False  # type: ignore[method-assign]
    result = MetaTrader5Terminal(mt5).symbol("GBPJPY")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.SYMBOL_NOT_FOUND


def test_first_missing_quote_after_selection_is_waited_for(
    trader: Trader, terminal: FakeTerminal, clock: FakeClock
) -> None:
    terminal.ticks.clear()
    terminal.missing_quotes = 1
    terminal.quote("EURUSD", (1.1, 1.1001))
    assert isinstance(trader.open_position("EURUSD", "buy", 0.1), Ok)
    assert clock.sleeps == [0.5]
    assert len(terminal.sent) == 1


def test_partial_close_is_a_failure_but_partial_open_is_not(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [position(1)]
    terminal.retcodes.append(10010)
    closed = trader.close_positions("EURUSD")
    assert isinstance(closed, Err)
    assert closed.error.errors[0].kind is ErrorKind.PARTIAL_FILL
    terminal.retcodes.append(10010)
    assert isinstance(trader.open_position("EURUSD", "buy", 0.1), Ok)


def test_limit_order_uses_a_filling_mode_the_symbol_allows(
    trader: Trader, terminal: FakeTerminal
) -> None:
    trader.place_limit_order("XAUUSD", "buy", 0.1, 2300.0)
    (request,) = terminal.sent
    assert request.filling is Filling.IOC  # type: ignore[union-attr]


def test_close_all_reads_each_symbol_spec_once(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_positions = [position(1), position(2), position(3)]
    assert isinstance(trader.close_positions("EURUSD"), Ok)
    assert terminal.symbol_lookups == ["EURUSD"]


@pytest.mark.parametrize("login", [None, 1.5e400, "abc", [1]])
def test_unusable_login_is_an_error_not_an_exception(login: object) -> None:
    result = connect(login, "pw", "Demo")  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT


def test_failed_login_releases_the_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    mt5 = FakeMT5()
    mt5.initialize_ok = False
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    assert isinstance(connect(1, "pw", "Demo"), Err)
    assert mt5.calls[-1][0] == "shutdown"
