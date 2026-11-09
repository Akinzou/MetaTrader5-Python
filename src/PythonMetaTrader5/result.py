"""Result type used at every port and use-case boundary.

Chosen over exceptions at boundaries because a trading call has many *expected*
failures (market closed, no money, requote); an exception-based API lets callers
forget them, while a Result forces the caller to look at the outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True


# Union (not PEP 604 `|`) because a generic alias built with `|` cannot be
# subscripted at runtime on Python 3.10.
Result = Union[Ok[T], Err[E]]  # noqa: UP007
