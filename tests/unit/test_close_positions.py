from PythonMetaTrader5.application.trader import BatchFailure, Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.market import Position
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import OrderRequest
from PythonMetaTrader5.result import Err, Ok

from .fakes import FakeTerminal


def position(ticket: int, symbol: str, side: Side, magic: int = 42) -> Position:
    return Position(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=0.2,
        price_open=1.0,
        sl=None,
        tp=None,
        price_current=1.0,
        profit=0.0,
        time=0,
        magic=magic,
        comment="",
    )


def sent_orders(terminal: FakeTerminal) -> list[OrderRequest]:
    orders = [r for r in terminal.sent if isinstance(r, OrderRequest)]
    assert len(orders) == len(terminal.sent)
    return orders


def test_each_position_is_closed_on_its_own_symbol(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_positions = [position(1, "EURUSD", Side.BUY), position(2, "XAUUSD", Side.SELL)]
    result = trader.close_positions()
    assert isinstance(result, Ok)
    assert len(result.value) == 2
    first, second = sent_orders(terminal)
    assert (first.symbol, first.side, first.price, first.position) == ("EURUSD", Side.SELL, 1.1, 1)
    assert (second.symbol, second.side, second.price, second.position) == (
        "XAUUSD",
        Side.BUY,
        2400.5,
        2,
    )
    assert first.volume == 0.2


def test_close_by_ticket_ignores_the_symbol_argument(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [position(1, "EURUSD", Side.BUY), position(2, "XAUUSD", Side.SELL)]
    assert isinstance(trader.close_positions("EURUSD", ticket=2), Ok)
    (request,) = sent_orders(terminal)
    assert request.symbol == "XAUUSD"


def test_nothing_to_close_is_success(trader: Trader) -> None:
    assert trader.close_positions("EURUSD") == Ok([])


def test_magic_filter_leaves_foreign_positions_open(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_positions = [
        position(1, "EURUSD", Side.BUY, magic=7),
        position(2, "EURUSD", Side.BUY, magic=42),
    ]
    trader.close_positions("EURUSD", magic=42)
    assert [r.position for r in sent_orders(terminal)] == [2]


def test_partial_failure_reports_what_closed_and_what_did_not(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [position(1, "EURUSD", Side.BUY), position(2, "EURUSD", Side.BUY)]
    terminal.retcodes.extend([10009, 10018])
    result = trader.close_positions("EURUSD")
    assert isinstance(result, Err)
    failure = result.error
    assert isinstance(failure, BatchFailure)
    assert len(failure.succeeded) == 1
    (error,) = failure.errors
    assert (error.kind, error.ticket) == (ErrorKind.MARKET_CLOSED, 2)
