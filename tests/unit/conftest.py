import sys

import pytest

from PythonMetaTrader5.application.trader import Trader

from .fake_mt5 import FakeMT5
from .fakes import FakeClock, FakeTerminal


@pytest.fixture(autouse=True)
def no_real_terminal(monkeypatch: pytest.MonkeyPatch) -> FakeMT5:
    """Unit tests must never reach a real terminal, even where MetaTrader5 is installed."""
    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


@pytest.fixture
def terminal() -> FakeTerminal:
    fake = FakeTerminal()
    fake.quote("EURUSD", (1.10000, 1.10010))
    fake.quote("XAUUSD", (2400.00, 2400.50))
    return fake


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def trader(terminal: FakeTerminal, clock: FakeClock) -> Trader:
    return Trader(terminal, clock, magic=42)
