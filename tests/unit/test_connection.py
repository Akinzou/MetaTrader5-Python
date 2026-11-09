import sys

import pytest

from PythonMetaTrader5 import Trader, connect
from PythonMetaTrader5.adapters import system_clock
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.result import Err, Ok

from .fake_mt5 import FakeMT5


@pytest.fixture
def mt5(monkeypatch: pytest.MonkeyPatch) -> FakeMT5:
    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


def test_missing_package_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    result = MetaTrader5Terminal.load()
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.CONNECTION_FAILED


def test_connect_returns_a_configured_trader(mt5: FakeMT5) -> None:
    result = connect("123", "pw", "Demo", magic=7)
    assert isinstance(result, Ok)
    assert isinstance(result.value, Trader)
    assert mt5.calls[0][2]["login"] == 123


def test_connect_failure_is_an_error(mt5: FakeMT5) -> None:
    mt5.initialize_ok = False
    result = connect(123, "pw", "Demo")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.CONNECTION_FAILED


def test_non_numeric_login_is_rejected_before_touching_the_terminal(mt5: FakeMT5) -> None:
    result = connect("abc", "pw", "Demo")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT
    assert mt5.calls == []


def test_trader_is_a_context_manager_that_shuts_down(mt5: FakeMT5) -> None:
    result = connect(1, "pw", "Demo")
    assert isinstance(result, Ok)
    with result.value as trader:
        assert isinstance(trader, Trader)
    assert mt5.calls[-1][0] == "shutdown"


def test_system_clock_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(system_clock.time, "sleep", slept.append)
    system_clock.SystemClock().sleep(0.25)
    assert slept == [0.25]


def test_connect_without_package_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    result = connect(1, "pw", "Demo")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.CONNECTION_FAILED
