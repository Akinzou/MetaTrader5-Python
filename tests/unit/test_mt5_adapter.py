from types import SimpleNamespace

import pytest

from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.ports import Credentials
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.market import PendingKind, Tick
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.symbol import Filling
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, raw_order, raw_position, symbol_info

CREDENTIALS = Credentials(login=123, password="secret", server="Demo", timeout_ms=5000)


@pytest.fixture
def mt5() -> FakeMT5:
    return FakeMT5()


@pytest.fixture
def adapter(mt5: FakeMT5) -> MetaTrader5Terminal:
    return MetaTrader5Terminal(mt5)


def last_sent(mt5: FakeMT5) -> dict[str, object]:
    name, (request,), _ = mt5.calls[-1]
    assert name == "order_send"
    return request  # type: ignore[no-any-return]


def test_connect_passes_credentials_and_reports_failure(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    assert adapter.connect(CREDENTIALS) == Ok(None)
    assert mt5.calls[0] == (
        "initialize",
        (),
        {"login": 123, "password": "secret", "server": "Demo", "timeout": 5000},
    )
    mt5.initialize_ok, mt5.error = False, (-6, "Authorization failed")
    result = adapter.connect(Credentials(1, "p", "s", path="C:/mt5/terminal64.exe"))
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.CONNECTION_FAILED
    assert "Authorization failed" in result.error.message
    assert "p" not in result.error.message.split()
    assert mt5.calls[-2][1] == ("C:/mt5/terminal64.exe",)
    assert mt5.calls[-1][0] == "shutdown"


def test_password_never_appears_in_repr() -> None:
    assert "secret" not in repr(CREDENTIALS)


def test_symbol_is_mapped_and_hidden_symbols_are_selected(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    mt5.symbols["EURUSD"] = symbol_info(visible=False)
    result = adapter.symbol("EURUSD")
    assert isinstance(result, Ok)
    assert (result.value.digits, result.value.tick_size) == (5, 1e-5)
    assert ("symbol_select", ("EURUSD", True), {}) in mt5.calls
    missing = adapter.symbol("NOPE")
    assert isinstance(missing, Err)
    assert missing.error.kind is ErrorKind.SYMBOL_NOT_FOUND


def test_tick_requires_a_two_sided_quote(adapter: MetaTrader5Terminal, mt5: FakeMT5) -> None:
    mt5.ticks["EURUSD"] = SimpleNamespace(bid=1.1, ask=1.2)
    assert adapter.tick("EURUSD") == Ok(Tick(1.1, 1.2))
    mt5.ticks["EURUSD"] = SimpleNamespace(bid=0.0, ask=0.0)
    for name in ("EURUSD", "NOPE"):
        result = adapter.tick(name)
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.NO_PRICE


def test_market_close_request_is_translated(adapter: MetaTrader5Terminal, mt5: FakeMT5) -> None:
    request = OrderRequest(
        symbol="EURUSD",
        side=Side.SELL,
        volume=0.1,
        price=1.1,
        filling=Filling.FOK,
        deviation=10,
        magic=42,
        comment="x",
        sl=1.2,
        position=7,
    )
    result = adapter.send(request)
    assert isinstance(result, Ok)
    assert (result.value.retcode, result.value.deal, result.value.request_id) == (10009, 11, 13)
    assert last_sent(mt5) == {
        "action": 1,
        "symbol": "EURUSD",
        "volume": 0.1,
        "type": 1,
        "price": 1.1,
        "deviation": 10,
        "magic": 42,
        "comment": "x",
        "type_filling": 0,
        "type_time": 0,
        "sl": 1.2,
        "position": 7,
    }


def test_pending_and_cancel_requests_are_translated(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    adapter.send(
        OrderRequest(
            symbol="EURUSD",
            side=Side.BUY,
            volume=0.1,
            price=1.0,
            filling=Filling.RETURN,
            deviation=10,
            magic=0,
            tp=1.1,
            pending=PendingKind.LIMIT,
        )
    )
    sent = last_sent(mt5)
    assert (sent["action"], sent["type"], sent["type_filling"], sent["tp"]) == (5, 2, 2, 1.1)
    assert "sl" not in sent
    adapter.send(CancelRequest(order=99))
    assert last_sent(mt5) == {"action": 8, "order": 99}


def test_undeliverable_request_is_a_terminal_error(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    mt5.send_result, mt5.error = None, (-2, 'Invalid "comment" argument')
    result = adapter.send(CancelRequest(order=1))
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.TERMINAL_ERROR
    assert "comment" in result.error.message


def test_positions_are_mapped_with_zero_stops_as_none(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    mt5.positions = (raw_position(sl=1.2),)
    result = adapter.positions(symbol="EURUSD")
    assert isinstance(result, Ok)
    (position,) = result.value
    assert (position.side, position.sl, position.tp, position.magic) == (Side.SELL, 1.2, None, 42)
    adapter.positions(ticket=1)
    adapter.positions()
    filters = [kwargs for name, _, kwargs in mt5.calls if name == "positions_get"]
    assert filters == [{"symbol": "EURUSD"}, {"ticket": 1}, {}]


def test_pending_orders_skip_non_pending_types(adapter: MetaTrader5Terminal, mt5: FakeMT5) -> None:
    mt5.orders = (raw_order(5, type_=3), raw_order(6, type_=0), raw_order(7, type_=4))
    result = adapter.pending_orders(symbol="EURUSD")
    assert isinstance(result, Ok)
    kinds = [(o.ticket, o.side, o.kind, o.volume) for o in result.value]
    assert kinds == [(5, Side.SELL, PendingKind.LIMIT, 0.2), (7, Side.BUY, PendingKind.STOP, 0.2)]


def test_listing_distinguishes_empty_from_failure(
    adapter: MetaTrader5Terminal, mt5: FakeMT5
) -> None:
    mt5.positions = mt5.orders = None
    assert adapter.positions() == Ok([])
    assert adapter.pending_orders() == Ok([])
    mt5.error = (-10004, "No IPC connection")
    for result in (adapter.positions(), adapter.pending_orders()):
        assert isinstance(result, Err)
        assert result.error.kind is ErrorKind.TERMINAL_ERROR


def test_shutdown_is_forwarded(adapter: MetaTrader5Terminal, mt5: FakeMT5) -> None:
    adapter.shutdown()
    assert mt5.calls[-1][0] == "shutdown"
