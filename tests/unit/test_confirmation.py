"""Only an answer that proves the requested effect counts as success."""

import operator

import pytest

from PythonMetaTrader5 import Broker, connect
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.application.ports import Credentials
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5, symbol_info
from .fakes import FakeClock, FakeTerminal


@pytest.mark.parametrize(
    ("retcode", "kind"), [(10010, ErrorKind.PARTIAL_FILL), (10008, ErrorKind.OUTCOME_UNKNOWN)]
)
def test_market_entry_succeeds_only_when_done(
    trader: Trader, terminal: FakeTerminal, retcode: int, kind: ErrorKind
) -> None:
    terminal.retcodes.append(retcode)
    result = trader.open_position("EURUSD", "buy", 0.1)
    assert isinstance(result, Err)
    assert result.error.kind is kind
    assert result.error.receipt is not None
    assert len(terminal.sent) == 1  # never re-sent: something may already be open


@pytest.mark.parametrize("retcode", [10008, 10009])
def test_pending_entry_succeeds_when_placed(
    trader: Trader, terminal: FakeTerminal, retcode: int
) -> None:
    terminal.retcodes.append(retcode)
    assert isinstance(trader.place_limit_order("EURUSD", "buy", 0.1, 1.0), Ok)


@pytest.mark.parametrize("login", ["²", "١٢٣", " 12a", ""])
def test_non_ascii_or_malformed_login_is_an_error(login: str) -> None:
    result = connect(login, "pw", "Demo")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT


class IndexLike:
    def __index__(self) -> int:
        return 12345678


def test_integer_like_login_is_accepted(no_real_terminal: FakeMT5) -> None:
    assert operator.index(IndexLike()) == 12345678
    assert isinstance(connect(IndexLike(), "pw", "Demo"), Ok)  # type: ignore[arg-type]
    assert no_real_terminal.calls[0][2]["login"] == 12345678


@pytest.mark.parametrize("login", [True, 12345678.9, "abc"])
def test_legacy_broker_rejects_logins_it_would_coerce(login: object) -> None:
    with (
        pytest.warns(DeprecationWarning, match="connect"),
        pytest.raises(ValueError, match="login"),
    ):
        Broker(login, "pw", "Demo", terminal=FakeTerminal(), clock=FakeClock())  # type: ignore[arg-type]


def test_failed_relogin_releases_the_session_so_a_retry_can_recover() -> None:
    mt5 = FakeMT5()
    adapter = MetaTrader5Terminal(mt5)
    assert adapter.connect(Credentials(1, "pw", "s")) == Ok(None)
    mt5.initialize_ok = False
    assert isinstance(adapter.connect(Credentials(1, "bad", "s")), Err)
    assert [name for name, _, _ in mt5.calls] == ["initialize", "initialize", "shutdown"]


def test_broker_stops_trading_after_a_failed_relogin(terminal: FakeTerminal) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())
    terminal.connect_failure = TradeError(ErrorKind.CONNECTION_FAILED, "down")
    assert broker.login() is False
    assert broker.Buy("EURUSD", 0.1) is None
    assert terminal.sent == []


@pytest.mark.parametrize("login", [True, 1.5, 0])
def test_credentials_refuse_logins_mt5_would_coerce(login: object) -> None:
    with pytest.raises(ValueError, match="login"):
        Credentials(login, "pw", "s")  # type: ignore[arg-type]


def test_exchange_execution_is_read_from_the_symbol() -> None:
    mt5 = FakeMT5()
    mt5.symbols["SBER"] = symbol_info("SBER")
    mt5.symbols["SBER"].trade_exemode = 3
    mt5.symbols["EURUSD"] = symbol_info()
    adapter = MetaTrader5Terminal(mt5)
    sber, eurusd = adapter.symbol("SBER"), adapter.symbol("EURUSD")
    assert isinstance(sber, Ok)
    assert isinstance(eurusd, Ok)
    assert (sber.value.exchange_execution, eurusd.value.exchange_execution) == (True, False)
