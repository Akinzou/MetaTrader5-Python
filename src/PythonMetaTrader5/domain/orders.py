"""Trade direction and the order requests sent through the terminal port."""

from __future__ import annotations

from enum import Enum

from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.result import Err, Ok, Result

_SIDE_ALIASES = {"buy": "BUY", "long": "BUY", "sell": "SELL", "short": "SELL"}


class Side(Enum):
    """Trade direction. Calls also accept ``"buy"``, ``"sell"``, ``"long"``, ``"short"``."""

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> Side:
        """The side that closes a position of this side."""
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        """``1`` for BUY, ``-1`` for SELL: the direction in which profit grows."""
        return 1 if self is Side.BUY else -1

    @classmethod
    def parse(cls, value: Side | str) -> Result[Side, TradeError]:
        """A `Side`, or ``Err(INVALID_ARGUMENT)`` for an unknown name."""
        if isinstance(value, Side):
            return Ok(value)
        name = _SIDE_ALIASES.get(str(value).strip().lower())
        if name is None:
            return Err(
                TradeError(ErrorKind.INVALID_ARGUMENT, f"unknown side {value!r}; use buy/sell")
            )
        return Ok(cls[name])


# Measured with order_check, not taken from the docs: MetaTrader5 5.0.6231
# accepts 29 UTF-16 code units and refuses 30 with [-2] Invalid "comment"
# argument before sending. The documented 31 would let 30-31 through to a
# TERMINAL_ERROR that hides the cause, and trimming would change what the user
# asked to store. tests/integration re-measures it when the package changes.
MAX_COMMENT_LENGTH = 29


def validate_comment(comment: object) -> Result[str, TradeError]:
    if comment is None:
        return Ok("")
    # `comment or ""` would store 0 or False as an empty comment without a word.
    if not isinstance(comment, str):
        return Err(TradeError(ErrorKind.INVALID_ARGUMENT, f"comment must be text, not {comment!r}"))
    # The package counts UTF-16 units, not len(): "\U0001f680" * 15 is refused.
    # surrogatepass: the package accepts a lone surrogate (measured), so it is
    # one unit here, not a UnicodeEncodeError.
    units = len(comment.encode("utf-16-le", "surrogatepass")) // 2
    if units > MAX_COMMENT_LENGTH:
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT,
                f"comment is {units} UTF-16 units (characters outside the BMP, such as "
                f"most emoji, count as 2; combined emoji more); "
                f"the MetaTrader5 package accepts at most {MAX_COMMENT_LENGTH}",
            )
        )
    return Ok(comment)
