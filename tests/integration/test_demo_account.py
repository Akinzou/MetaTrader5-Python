"""End-to-end checks against a real MetaTrader 5 terminal on a DEMO account.

Run locally on Windows with a terminal installed:

    set MT5_LOGIN=... & set MT5_PASSWORD=... & set MT5_SERVER=...
    pytest -m integration

Optional: MT5_SYMBOL (default EURUSD), MT5_PATH (terminal64.exe).
These tests place and close real orders, so they refuse to run on anything
but a demo account.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from PythonMetaTrader5 import Err, ErrorKind, Ok, PendingKind, Side, Stop, Trader, connect
from PythonMetaTrader5.domain.orders import MAX_COMMENT_LENGTH

pytestmark = pytest.mark.integration
# Windows-only package: the whole module is skipped where it cannot be installed.
mt5 = pytest.importorskip("MetaTrader5")

REQUIRED = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
# Distinct from any manual trading so cleanup never touches foreign positions.
MAGIC = 930_117
SYMBOL = os.environ.get("MT5_SYMBOL", "EURUSD")


@pytest.fixture(scope="module")
def trader() -> Iterator[Trader]:
    if any(name not in os.environ for name in REQUIRED):
        pytest.skip("MT5_LOGIN / MT5_PASSWORD / MT5_SERVER not set")
    result = connect(
        os.environ["MT5_LOGIN"],
        os.environ["MT5_PASSWORD"],
        os.environ["MT5_SERVER"],
        path=os.environ.get("MT5_PATH"),
        magic=MAGIC,
    )
    if isinstance(result, Err):
        pytest.fail(f"cannot connect: {result.error}")
    account = mt5.account_info()
    if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        result.value.shutdown()
        pytest.fail("refusing to trade: the account is not a demo account")
    yield result.value
    result.value.close_positions(magic=MAGIC)
    result.value.cancel_pending_orders(magic=MAGIC)
    result.value.shutdown()


def minimum_volume() -> float:
    return float(mt5.symbol_info(SYMBOL).volume_min)


def test_open_and_close_a_market_position(trader: Trader) -> None:
    opened = trader.open_position(
        SYMBOL,
        Side.BUY,
        minimum_volume(),
        sl=Stop.points(2000),
        tp=Stop.points(2000),
        # The longest comment we let through must be accepted for real.
        comment="pmt5 integration".ljust(MAX_COMMENT_LENGTH, "."),
    )
    if isinstance(opened, Err) and opened.error.kind is ErrorKind.MARKET_CLOSED:
        pytest.skip("market closed")
    assert isinstance(opened, Ok), opened
    positions = trader.positions(SYMBOL, magic=MAGIC)
    assert isinstance(positions, Ok)
    assert len(positions.value) == 1
    position = positions.value[0]
    assert position.sl is not None
    assert position.tp is not None
    closed = trader.close_positions(ticket=position.ticket)
    assert isinstance(closed, Ok), closed
    assert trader.positions(SYMBOL, magic=MAGIC) == Ok([])


def test_place_and_cancel_a_limit_order_far_from_the_market(trader: Trader) -> None:
    bid = mt5.symbol_info_tick(SYMBOL).bid
    placed = trader.place_limit_order(SYMBOL, Side.BUY, minimum_volume(), bid * 0.9)
    if isinstance(placed, Err) and placed.error.kind is ErrorKind.MARKET_CLOSED:
        pytest.skip("market closed")
    assert isinstance(placed, Ok), placed
    pending = trader.pending_orders(SYMBOL, magic=MAGIC, kind=PendingKind.LIMIT)
    assert isinstance(pending, Ok)
    assert len(pending.value) == 1
    cancelled = trader.cancel_pending_orders(SYMBOL, magic=MAGIC)
    assert isinstance(cancelled, Ok), cancelled
    assert trader.pending_orders(SYMBOL, magic=MAGIC) == Ok([])


def test_oversized_comment_is_rejected_locally(trader: Trader) -> None:
    result = trader.open_position(SYMBOL, Side.BUY, minimum_volume(), comment="x" * 30)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT


@pytest.mark.parametrize(
    ("comment", "accepted"),
    [
        ("x" * MAX_COMMENT_LENGTH, True),
        ("x" * (MAX_COMMENT_LENGTH + 1), False),
        # 15 characters but 30 UTF-16 units: tells unit counting from len().
        ("\U0001f680" * 14 + "x", True),
        ("\U0001f680" * 15, False),
    ],
)
def test_comment_limit_matches_the_installed_package(
    trader: Trader, comment: str, accepted: bool
) -> None:
    # order_check validates without sending. MAX_COMMENT_LENGTH is a measurement
    # of one package build, so a package that moves the boundary fails here.
    tick = mt5.symbol_info_tick(SYMBOL)
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": minimum_volume(),
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "comment": comment,
    }
    checked = mt5.order_check(request)
    code, message = mt5.last_error()
    if accepted:
        assert checked is not None, (code, message)
    else:
        # Refused for the comment, not for a dropped link or a closed market.
        assert checked is None
        assert code == mt5.RES_E_INVALID_PARAMS, (code, message)
        assert "comment" in message, message
