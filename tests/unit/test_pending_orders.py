from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.market import PendingKind, PendingOrder
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.domain.symbol import Filling
from PythonMetaTrader5.result import Err, Ok

from .fakes import FakeTerminal


def test_limit_order_is_placed_at_its_level(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.retcodes.append(10008)
    result = trader.place_limit_order("EURUSD", "buy", 0.1, 1.0950004, sl=Stop.points(50))
    assert isinstance(result, Ok)
    (request,) = terminal.sent
    assert isinstance(request, OrderRequest)
    assert (request.pending, request.price, request.sl) == (PendingKind.LIMIT, 1.095, 1.0945)
    assert request.filling is Filling.RETURN


def test_limit_order_rejected_by_server_is_an_error(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.retcodes.append(10015)
    result = trader.place_limit_order("EURUSD", "sell", 0.1, 1.0)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_PRICE


def order(ticket: int, symbol: str, magic: int = 42) -> PendingOrder:
    return PendingOrder(
        ticket=ticket,
        symbol=symbol,
        side=Side.BUY,
        kind=PendingKind.LIMIT,
        volume=0.1,
        price=1.0,
        magic=magic,
        comment="",
    )


def test_cancel_removes_every_pending_order_of_the_symbol(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_orders = [order(5, "EURUSD"), order(6, "XAUUSD"), order(7, "EURUSD", magic=1)]
    result = trader.cancel_pending_orders("EURUSD")
    assert isinstance(result, Ok)
    assert terminal.sent == [CancelRequest(order=5), CancelRequest(order=7)]


def test_cancel_with_magic_filter(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_orders = [order(5, "EURUSD"), order(7, "EURUSD", magic=1)]
    trader.cancel_pending_orders("EURUSD", magic=1)
    assert terminal.sent == [CancelRequest(order=7)]


def test_queries_filter_by_magic(trader: Trader, terminal: FakeTerminal) -> None:
    terminal.open_orders = [order(5, "EURUSD"), order(7, "EURUSD", magic=1)]
    pending = trader.pending_orders(magic=1)
    assert isinstance(pending, Ok)
    assert [o.ticket for o in pending.value] == [7]
    assert trader.positions("EURUSD") == Ok([])


def test_shutdown_releases_the_terminal(trader: Trader, terminal: FakeTerminal) -> None:
    trader.shutdown()
    assert terminal.shut_down


def test_invalid_limit_order_never_reaches_the_terminal(
    trader: Trader, terminal: FakeTerminal
) -> None:
    result = trader.place_limit_order("EURUSD", "buy", 1000.0, 1.0)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_VOLUME
    assert terminal.sent == []


def test_cancel_can_be_limited_to_one_order_kind(trader: Trader, terminal: FakeTerminal) -> None:
    stop = PendingOrder(
        ticket=8,
        symbol="EURUSD",
        side=Side.SELL,
        kind=PendingKind.STOP,
        volume=0.1,
        price=1.0,
        magic=42,
        comment="",
    )
    terminal.open_orders = [order(5, "EURUSD"), stop]
    trader.cancel_pending_orders("EURUSD", kind=PendingKind.LIMIT)
    assert terminal.sent == [CancelRequest(order=5)]
