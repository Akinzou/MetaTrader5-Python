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


# Boundaries measured with order_check on MetaTrader5 5.0.6231 (demo account):
# the package counts UTF-16 code units. 29 pass, 30 get [-2] Invalid "comment"
# argument, whether ASCII, Polish, CJK (1 unit each) or emoji (2 units each).
# It also accepts a lone surrogate, so that counts as one unit.
@pytest.mark.parametrize(
    "comment",
    ["x" * 29, "\u0142" * 29, "\u4e2d" * 29, "\U0001f680" * 14 + "x", "\ud83d" * 29],
)
def test_comment_within_package_limit_is_kept(comment: str) -> None:
    assert validate_comment(comment) == Ok(comment)


def test_missing_comment_is_empty() -> None:
    assert validate_comment(None) == Ok("")


@pytest.mark.parametrize(
    "comment",
    ["x" * 30, "\u0142" * 30, "\U0001f680" * 15, "\U0001f680" + "x" * 28],
)
def test_comment_over_package_limit_is_rejected_not_truncated(comment: str) -> None:
    result = validate_comment(comment)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT
    assert "at most 29" in result.error.message


@pytest.mark.parametrize("comment", [12345, 0, False, b"bytes"])
def test_non_text_comment_is_rejected_not_blanked(comment: object) -> None:
    result = validate_comment(comment)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_ARGUMENT
