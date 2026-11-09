from PythonMetaTrader5.domain.market import Tick
from PythonMetaTrader5.domain.orders import Side

from .fakes import make_position


def test_tick_quotes_the_price_a_side_trades_at() -> None:
    tick = Tick(bid=1.1, ask=1.2)
    assert tick.entry_price(Side.BUY) == 1.2
    assert tick.entry_price(Side.SELL) == 1.1
    assert tick.exit_price(Side.BUY) == 1.1
    assert tick.exit_price(Side.SELL) == 1.2


def test_position_without_stops_reports_none() -> None:
    position = make_position(7, side=Side.SELL, price_current=1.09, profit=10.0)
    assert position.to_dict()["sl"] is None
    assert position.to_dict()["side"] == "sell"
