"""The 2.x `Broker` API keeps its names, arguments and return shapes."""

import pytest

from PythonMetaTrader5 import Broker
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import PendingKind, PendingOrder, Position
from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest

from .fakes import FakeClock, FakeTerminal, make_position


@pytest.fixture
def broker(terminal: FakeTerminal, clock: FakeClock) -> Broker:
    with pytest.warns(DeprecationWarning, match="connect"):
        return Broker(123, "pw", "Demo", terminal=terminal, clock=clock)


def orders(terminal: FakeTerminal) -> list[OrderRequest]:
    return [r for r in terminal.sent if isinstance(r, OrderRequest)]


def long_position(ticket: int = 1) -> Position:
    return make_position(ticket, price_open=1.0, tp=1.2, price_current=1.0, profit=3.0, time=5)


def test_constructor_logs_in_with_string_credentials(terminal: FakeTerminal) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        Broker("123", 456, "Demo", terminal=terminal, clock=FakeClock())
    (credentials,) = terminal.connected_with
    assert (credentials.login, credentials.password, credentials.server) == (123, "456", "Demo")


def test_failed_login_is_logged_and_retried_by_login(
    terminal: FakeTerminal, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    terminal.connect_failure = TradeError(ErrorKind.CONNECTION_FAILED, "bad password")
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=clock)
    assert "bad password" in caplog.text
    assert broker.login() is False
    assert broker.OpenPosition("EURUSD", "buy", 0.1) is None
    terminal.connect_failure = None
    assert broker.login(ToEffect=True) is True


def test_open_position_with_offsets_returns_the_receipt(
    broker: Broker, terminal: FakeTerminal
) -> None:
    result = broker.OpenPosition(
        "EURUSD", "long", 0.1, sl=1000, tp=1500, sl_type="offset", tp_type="offset"
    )
    assert result is not None
    assert result.retcode == 10009
    (request,) = orders(terminal)
    assert (request.sl, request.tp) == (1.0901, 1.1151)


def test_wrappers_map_to_sides_and_absolute_stops(broker: Broker, terminal: FakeTerminal) -> None:
    broker.Buy("EURUSD", 0.1)
    broker.Sell("EURUSD", 0.1)
    broker.BuySL("EURUSD", 0.1, 1.05)
    broker.SellSL("EURUSD", 0.1, 100, sl_type="offset")
    sides = [(r.side, r.sl) for r in orders(terminal)]
    assert sides == [(Side.BUY, None), (Side.SELL, None), (Side.BUY, 1.05), (Side.SELL, 1.101)]


def test_broker_refusal_returns_the_receipt_and_logs_it(
    broker: Broker, terminal: FakeTerminal, caplog: pytest.LogCaptureFixture
) -> None:
    terminal.retcodes.append(10027)
    result = broker.OpenPosition("EURUSD", "buy", 0.1)
    assert result is not None
    assert result.retcode == 10027
    assert "Algo Trading" in caplog.text
    assert broker.RetCodes[10027]


@pytest.mark.parametrize(
    "kwargs",
    [{"side": "hold"}, {"sl": 1, "sl_type": "pips"}, {"tp": 1, "tp_type": "pips"}, {"ticket": 5}],
)
def test_unsupported_arguments_return_none(broker: Broker, kwargs: dict[str, object]) -> None:
    arguments: dict[str, object] = {"side": "buy", **kwargs}
    assert broker.OpenPosition("EURUSD", volume=0.1, **arguments) is None  # type: ignore[arg-type]


def test_positions_keep_the_2x_shapes(broker: Broker, terminal: FakeTerminal) -> None:
    terminal.open_positions = [long_position()]
    (raw,) = broker.GetPositions()
    assert (raw.ticket, raw.type, raw.sl, raw.tp) == (1, 0, 0.0, 1.2)
    (as_dict,) = broker.GetPositionsBySymbol("EURUSD", as_dict=True)
    assert (as_dict["type"], as_dict["sl"], as_dict["profit"]) == (0, None, 3.0)
    assert broker.GetPosition(ticket=1, as_dict=True) == as_dict
    assert broker.GetPosition("XAUUSD") is None


def test_close_returns_true_only_when_something_closed(
    broker: Broker, terminal: FakeTerminal
) -> None:
    assert broker.Close("EURUSD") is False
    terminal.open_positions = [long_position()]
    assert broker.Close("EURUSD") is True
    terminal.retcodes.append(10018)
    assert broker.Close("EURUSD", ticket=1) is False


def test_limit_crossing_the_market_executes_immediately(
    broker: Broker, terminal: FakeTerminal
) -> None:
    broker.BuyLimit("EURUSD", 0.1, stoplimit=1.2)  # ask 1.1001 <= 1.2
    broker.SellLimit("EURUSD", 0.1, stoplimit=1.0)  # bid 1.1 >= 1.0
    assert [(r.side, r.pending) for r in orders(terminal)] == [(Side.BUY, None), (Side.SELL, None)]


def test_limit_away_from_the_market_rests(broker: Broker, terminal: FakeTerminal) -> None:
    terminal.retcodes.extend([10008, 10008])
    assert broker.BuyLimit("EURUSD", 0.1, stoplimit=1.05) is not None
    assert broker.SellLimit("EURUSD", 0.1, stoplimit=1.15) is not None
    assert [r.pending for r in orders(terminal)] == [PendingKind.LIMIT, PendingKind.LIMIT]


def test_limit_rejects_price_argument_and_missing_quote(
    broker: Broker, terminal: FakeTerminal
) -> None:
    assert broker.BuyLimit("EURUSD", 0.1, 1.05, price=1.0) is None
    terminal.ticks.clear()
    assert broker.SellLimit("EURUSD", 0.1, 1.15) is None
    assert terminal.sent == []


def test_cancel_orders_removes_only_limit_orders(broker: Broker, terminal: FakeTerminal) -> None:
    def pending(ticket: int, kind: PendingKind) -> PendingOrder:
        return PendingOrder(ticket, "EURUSD", Side.BUY, kind, 0.1, 1.0, 0, "")

    terminal.open_orders = [pending(5, PendingKind.LIMIT), pending(6, PendingKind.STOP)]
    broker.CancelOrders("EURUSD")
    assert terminal.sent == [CancelRequest(order=5)]


def test_disconnect_shuts_the_terminal_down(broker: Broker, terminal: FakeTerminal) -> None:
    broker.Disconnect()
    assert terminal.shut_down
