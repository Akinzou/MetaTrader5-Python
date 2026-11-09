import pytest

from PythonMetaTrader5.application.batch import BatchFailure
from PythonMetaTrader5.application.execution import RetryPolicy
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import Position
from PythonMetaTrader5.result import Err

from .fakes import FakeTerminal, make_position, receipt


def btc_position() -> Position:
    return make_position(9, symbol="BTCUSD", price_open=1.0, price_current=1.0, magic=42)


@pytest.mark.parametrize("policy", [{"attempts": 0}, {"delay_seconds": -1.0}])
def test_nonsensical_retry_policy_fails_at_construction(policy: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="invalid retry policy"):
        RetryPolicy(**policy)  # type: ignore[arg-type]


def test_errors_render_kind_retcode_and_ticket() -> None:
    error = TradeError(ErrorKind.MARKET_CLOSED, "market is closed", retcode=10018, ticket=3)
    assert str(error) == "market_closed: market is closed (retcode 10018) [ticket 3]"
    failure = BatchFailure((receipt(),), (error,))
    assert str(failure).startswith("1 failed, 1 succeeded: market_closed")


def test_close_reports_unknown_symbol_and_missing_quote(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [btc_position()]
    result = trader.close_positions()
    assert isinstance(result, Err)
    assert result.error.errors[0].kind is ErrorKind.SYMBOL_NOT_FOUND
    terminal.specs["BTCUSD"] = terminal.specs["EURUSD"]
    result = trader.close_positions()
    assert isinstance(result, Err)
    assert result.error.errors[0].kind is ErrorKind.NO_PRICE


def test_close_rejects_overlong_comment_before_touching_positions(
    trader: Trader, terminal: FakeTerminal
) -> None:
    terminal.open_positions = [btc_position()]
    result = trader.close_positions(comment="c" * 30)
    assert isinstance(result, Err)
    assert result.error.errors[0].kind is ErrorKind.INVALID_ARGUMENT
    assert terminal.sent == []


class BrokenListing(FakeTerminal):
    def positions(self, **_: object) -> Err[TradeError]:  # type: ignore[override]
        return Err(TradeError(ErrorKind.TERMINAL_ERROR, "positions_get failed"))

    def pending_orders(self, **_: object) -> Err[TradeError]:  # type: ignore[override]
        return Err(TradeError(ErrorKind.TERMINAL_ERROR, "orders_get failed"))


def test_listing_failures_surface_as_batch_failures(clock: object) -> None:
    trader = Trader(BrokenListing(), clock)  # type: ignore[arg-type]
    for result in (trader.close_positions(), trader.cancel_pending_orders()):
        assert isinstance(result, Err)
        assert result.error.errors[0].kind is ErrorKind.TERMINAL_ERROR
    assert isinstance(trader.positions(), Err)
    assert isinstance(trader.pending_orders(), Err)
