import pytest

from PythonMetaTrader5.application.trader import Trader

from .fakes import FakeClock, FakeTerminal


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
