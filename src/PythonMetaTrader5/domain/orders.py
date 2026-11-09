"""Trade direction and the order requests sent through the terminal port."""

from __future__ import annotations

from enum import Enum

from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.result import Err, Ok, Result

_SIDE_ALIASES = {"buy": "BUY", "long": "BUY", "sell": "SELL", "short": "SELL"}


class Side(Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1

    @classmethod
    def parse(cls, value: Side | str) -> Result[Side, TradeError]:
        if isinstance(value, Side):
            return Ok(value)
        name = _SIDE_ALIASES.get(str(value).strip().lower())
        if name is None:
            return Err(
                TradeError(ErrorKind.INVALID_ARGUMENT, f"unknown side {value!r}; use buy/sell")
            )
        return Ok(cls[name])


# The terminal stores at most 31 characters and answers longer comments with an
# "Invalid comment argument" error instead of trimming them.
MAX_COMMENT_LENGTH = 31


def validate_comment(comment: str | None) -> Result[str, TradeError]:
    text = comment or ""
    if len(text) > MAX_COMMENT_LENGTH:
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT,
                f"comment is {len(text)} characters; the terminal accepts {MAX_COMMENT_LENGTH}",
            )
        )
    return Ok(text)
