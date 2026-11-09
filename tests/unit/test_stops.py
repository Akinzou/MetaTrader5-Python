import pytest

from PythonMetaTrader5.domain.orders import Side
from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.domain.symbol import SymbolSpec

SPEC = SymbolSpec(
    name="EURUSD",
    digits=5,
    point=0.00001,
    tick_size=0.00001,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01,
    filling_flags=1,
    exchange_execution=False,
)


def test_absolute_stop_is_only_normalized() -> None:
    assert Stop.at_price(1.123456).stop_loss(Side.BUY, 1.2, SPEC) == 1.12346
    assert Stop.at_price(1.123456).take_profit(Side.SELL, 1.2, SPEC) == 1.12346


@pytest.mark.parametrize(
    ("side", "stop_loss", "take_profit"),
    [(Side.BUY, 1.09, 1.115), (Side.SELL, 1.11, 1.085)],
)
def test_point_offsets_follow_trade_direction(
    side: Side, stop_loss: float, take_profit: float
) -> None:
    reference = 1.1
    assert Stop.points(1000).stop_loss(side, reference, SPEC) == stop_loss
    assert Stop.points(1500).take_profit(side, reference, SPEC) == take_profit


def test_negative_offset_is_treated_as_distance() -> None:
    assert Stop.points(-1000).stop_loss(Side.BUY, 1.1, SPEC) == 1.09
