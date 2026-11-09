"""The 2.x facade degrades loudly: every failure is logged and returns 2.x's 'nothing'."""

import sys

import pytest

from PythonMetaTrader5 import Broker

from .fakes import FakeClock
from .test_failure_paths import BrokenListing


def test_without_metatrader5_package_every_call_is_a_logged_no_op(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", clock=FakeClock())
    assert "not installed" in caplog.text
    assert broker.login() is False
    assert broker.GetPositions() == []
    assert broker.Close("EURUSD") is False
    assert broker.BuyLimit("EURUSD", 0.1, 1.0) is None
    assert broker.CancelOrders("EURUSD") is None
    broker.Disconnect()
    assert "not connected" in caplog.text


def test_listing_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=BrokenListing(), clock=FakeClock())
    assert broker.GetPositions() == []
    assert broker.Close("EURUSD") is False
    broker.CancelOrders("EURUSD")
    assert caplog.text.count("orders_get failed") == 1
    assert caplog.text.count("positions_get failed") == 2


def test_limit_with_ticket_is_refused(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.warns(DeprecationWarning, match="connect"):
        broker = Broker(1, "pw", "Demo", terminal=BrokenListing(), clock=FakeClock())
    assert broker.SellLimit("EURUSD", 0.1, 1.0, ticket=3) is None
    assert "Close(ticket=...)" in caplog.text
