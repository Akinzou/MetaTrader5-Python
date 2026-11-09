import pytest

from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.orders import Side, validate_comment
from PythonMetaTrader5.result import Err, Ok


@pytest.mark.parametrize(
    ("text", "side"),
    [("buy", Side.BUY), ("LONG", Side.BUY), (" sell ", Side.SELL), ("short", Side.SELL)],
)
def test_side_parses_aliases(text: str, side: Side) -> None:
    assert Side.parse(text) == Ok(side)
    assert Side.parse(side) == Ok(side)


def test_unknown_side_is_rejected() -> None:
    result = Side.parse("hold")
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT


def test_side_has_opposite() -> None:
    assert Side.BUY.opposite is Side.SELL
    assert Side.SELL.opposite is Side.BUY


def test_comment_within_terminal_limit_is_kept() -> None:
    assert validate_comment(None) == Ok("")
    assert validate_comment("x" * 31) == Ok("x" * 31)


def test_comment_over_terminal_limit_is_rejected_not_truncated() -> None:
    result = validate_comment("x" * 32)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT
