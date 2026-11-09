import pytest

from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.retcodes import Outcome, classify, error_for


@pytest.mark.parametrize("retcode", [10008, 10009, 10010])
def test_done_placed_and_partial_are_success(retcode: int) -> None:
    assert classify(retcode) is Outcome.SUCCESS


@pytest.mark.parametrize("retcode", [10004, 10020, 10021, 10024])
def test_price_moves_and_throttling_are_retried(retcode: int) -> None:
    assert classify(retcode) is Outcome.RETRY


@pytest.mark.parametrize("retcode", [10012, 10031])
def test_timeout_and_lost_connection_are_never_retried(retcode: int) -> None:
    # Retrying when the request may already be on the server risks a double fill.
    assert classify(retcode) is Outcome.FAIL
    assert error_for(retcode).kind is ErrorKind.OUTCOME_UNKNOWN


@pytest.mark.parametrize(
    ("retcode", "kind"),
    [
        (10018, ErrorKind.MARKET_CLOSED),
        (10019, ErrorKind.NO_MONEY),
        (10014, ErrorKind.INVALID_VOLUME),
        (10016, ErrorKind.INVALID_STOPS),
        (10015, ErrorKind.INVALID_PRICE),
        (10030, ErrorKind.INVALID_FILLING),
        (10027, ErrorKind.ALGO_TRADING_DISABLED),
        (10017, ErrorKind.TRADE_DISABLED),
        (10040, ErrorKind.LIMIT_REACHED),
        (10006, ErrorKind.REJECTED),
        (99999, ErrorKind.REJECTED),
    ],
)
def test_permanent_failures_map_to_a_kind(retcode: int, kind: ErrorKind) -> None:
    assert classify(retcode) is Outcome.FAIL
    error = error_for(retcode)
    assert error.kind is kind
    assert error.retcode == retcode
    assert error.message
