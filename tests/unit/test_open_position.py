from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import OrderRequest
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.domain.symbol import Filling
from PythonMetaTrader5.result import Err, Ok

from .fakes import FakeClock, FakeTerminal


def only_request(terminal: FakeTerminal) -> OrderRequest:
    (request,) = terminal.sent
    assert isinstance(request, OrderRequest)
    return request


def test_buy_uses_ask_and_resolves_point_stops(trader: Trader, terminal: FakeTerminal) -> None:
    result = trader.open_position(
        "EURUSD", "buy", 0.1, sl=Stop.points(1000), tp=Stop.points(1500), comment="hook"
    )
    assert isinstance(result, Ok)
    request = only_request(terminal)
    assert (request.side, request.price, request.volume) == (Side.BUY, 1.1001, 0.1)
    assert (request.sl, request.tp) == (1.0901, 1.1151)
    assert (request.filling, request.magic, request.comment) == (Filling.FOK, 42, "hook")
    assert request.position is None


def test_sell_uses_bid_and_plain_float_stops_are_prices(
    trader: Trader, terminal: FakeTerminal
) -> None:
    trader.open_position("XAUUSD", Side.SELL, 0.1, sl=2410.123, tp=2390.0)
    request = only_request(terminal)
    assert (request.price, request.sl, request.tp) == (2400.0, 2410.12, 2390.0)
    assert request.filling is Filling.IOC


def test_requote_is_retried_with_a_fresh_quote(
    trader: Trader, terminal: FakeTerminal, clock: FakeClock
) -> None:
    terminal.quote("EURUSD", (1.1, 1.1001), (1.1002, 1.1003))
    terminal.retcodes.extend([10004, 10009])
    assert isinstance(trader.open_position("EURUSD", "buy", 0.1), Ok)
    assert [r.price for r in terminal.sent] == [1.1001, 1.1003]  # type: ignore[union-attr]
    assert clock.sleeps == [0.5]


def test_retries_are_bounded(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.retcodes.extend([10004] * 10)
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.RETRIES_EXHAUSTED
    assert result.error.retcode == 10004
    assert len(terminal.sent) == 3


def test_permanent_failure_is_not_retried(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.retcodes.append(10018)
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.MARKET_CLOSED
    assert result.error.receipt is not None
    assert len(terminal.sent) == 1


def test_transport_failure_is_returned_without_retry(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.send_failure = TradeError(ErrorKind.TERMINAL_ERROR, "IPC broken")
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert result == Err(terminal.send_failure)
    assert len(terminal.sent) == 1


def test_explicit_price_is_normalized_and_sent_once(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.retcodes.append(10004)
    result = trader.open_position("EURUSD", "buy", 0.1, price=1.123456, sl=Stop.points(100))
    assert isinstance(result, Err)
    request = only_request(terminal)
    assert (request.price, request.sl) == (1.12346, 1.12246)


def test_invalid_input_never_reaches_the_terminal(trader: Trader, terminal: FakeTerminal) -> None:
    cases = [
        (trader.open_position("EURUSD", "hold", 0.1), ErrorKind.INVALID_ARGUMENT),
        (trader.open_position("EURUSD", "buy", 0.015), ErrorKind.INVALID_VOLUME),
        (trader.open_position("NOPE", "buy", 0.1), ErrorKind.SYMBOL_NOT_FOUND),
        (
            trader.open_position("EURUSD", "buy", 0.1, comment="c" * 40),
            ErrorKind.INVALID_ARGUMENT,
        ),
    ]
    for result, kind in cases:
        assert isinstance(result, Err)
        assert result.error.kind is kind
    assert terminal.sent == []


def test_missing_quote_is_an_error(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.ticks.clear()
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.NO_PRICE
