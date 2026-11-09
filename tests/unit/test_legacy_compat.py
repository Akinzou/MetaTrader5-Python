"""2.x returned raw MT5 objects; scripts index them, unpack them and call _asdict()."""

from __future__ import annotations

from collections import deque

import pytest

from PythonMetaTrader5 import Broker
from PythonMetaTrader5.domain.requests import OrderRequest

from .fakes import FakeClock, FakeTerminal, make_position

# Field order of MetaTrader5.TradePosition / OrderSendResult (package 5.0.6231).
MT5_POSITION_FIELDS = (
    "ticket",
    "time",
    "time_msc",
    "time_update",
    "time_update_msc",
    "type",
    "magic",
    "identifier",
    "reason",
    "volume",
    "price_open",
    "sl",
    "tp",
    "price_current",
    "swap",
    "profit",
    "symbol",
    "comment",
    "external_id",
)
MT5_RECEIPT_FIELDS = (
    "retcode",
    "deal",
    "order",
    "volume",
    "price",
    "bid",
    "ask",
    "comment",
    "request_id",
    "retcode_external",
    "request",
)
V2_DICT_KEYS = {
    "ticket",
    "symbol",
    "type",
    "volume",
    "price_open",
    "sl",
    "tp",
    "price_current",
    "profit",
    "time",
    "magic",
    "comment",
}


@pytest.fixture
def broker(terminal: FakeTerminal) -> Broker:
    with pytest.warns(DeprecationWarning, match="connect"):
        return Broker(1, "pw", "Demo", terminal=terminal, clock=FakeClock())


def sent_orders(terminal: FakeTerminal) -> list[OrderRequest]:
    return [r for r in terminal.sent if isinstance(r, OrderRequest)]


def test_positions_carry_every_mt5_field_in_mt5_order(
    broker: Broker, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [make_position(7, swap=-1.5, identifier=7, reason=3)]
    (p,) = broker.GetPositions()
    assert p._fields == MT5_POSITION_FIELDS
    assert (p.swap, p.identifier, p.reason) == (-1.5, 7, 3)
    assert p[0] == 7  # 2.x scripts index the raw tuple


def test_as_dict_keeps_exactly_the_2x_keys(broker: Broker, terminal: FakeTerminal) -> None:
    terminal.open_positions = [make_position(7, swap=-1.5)]
    (row,) = broker.GetPositions(as_dict=True)
    assert set(row) == V2_DICT_KEYS


def test_entry_returns_an_order_send_result_shaped_receipt(
    broker: Broker, terminal: FakeTerminal
) -> None:
    receipt = broker.Buy("EURUSD", 0.1)
    assert receipt._fields == MT5_RECEIPT_FIELDS
    assert receipt[0] == receipt.retcode == 10009
    assert receipt._asdict()["retcode_external"] == 0
    # The original request object is not kept; scripts reading it get None.
    assert receipt.request is None


def test_a_rejected_entry_returns_the_same_receipt_shape(
    broker: Broker, terminal: FakeTerminal
) -> None:
    terminal.retcodes = deque([10019])
    receipt = broker.Sell("EURUSD", 0.1)
    assert receipt._fields == MT5_RECEIPT_FIELDS
    assert receipt.retcode == 10019


def test_numeric_strings_are_converted_as_2x_did(broker: Broker, terminal: FakeTerminal) -> None:
    broker.OpenPosition("EURUSD", "buy", "0.1", price="1.10010", sl="1.09", tp="1.2")  # type: ignore[arg-type]
    broker.BuyLimit("EURUSD", "0.2", "1.05")  # type: ignore[arg-type]
    market, limit = sent_orders(terminal)
    assert (market.volume, market.price, market.sl, market.tp) == (0.1, 1.1001, 1.09, 1.2)
    assert (limit.volume, limit.price) == (0.2, 1.05)


def test_a_non_numeric_string_raises_as_2x_did(broker: Broker, terminal: FakeTerminal) -> None:
    with pytest.raises(ValueError, match="could not convert"):
        broker.Buy("EURUSD", "lots")  # type: ignore[arg-type]
    assert terminal.sent == []


def test_ticket_wins_over_symbol_as_in_2x(broker: Broker, terminal: FakeTerminal) -> None:
    terminal.open_positions = [make_position(1)]
    (p,) = broker.GetPositions("XAUUSD", ticket=1)
    assert (p.ticket, p.symbol) == (1, "EURUSD")
