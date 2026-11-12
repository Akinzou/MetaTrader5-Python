"""Applying one trade action to many positions/orders and reporting per item."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Protocol, TypeVar

from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.inputs import ANY_MAGIC, AnyMagic
from PythonMetaTrader5.domain.market import TradeReceipt
from PythonMetaTrader5.result import Err, Ok, Result


class _Ticketed(Protocol):
    @property
    def ticket(self) -> int: ...

    @property
    def magic(self) -> int: ...


_T = TypeVar("_T", bound=_Ticketed)


@dataclass(frozen=True, slots=True)
class BatchFailure:
    """Some items of a batch (close all / cancel all) failed; others may have succeeded."""

    succeeded: tuple[TradeReceipt, ...]
    errors: tuple[TradeError, ...]

    def __str__(self) -> str:
        return f"{len(self.errors)} failed, {len(self.succeeded)} succeeded: " + "; ".join(
            str(e) for e in self.errors
        )


def run_batch(
    items: Iterable[_T], action: Callable[[_T], Result[TradeReceipt, TradeError]]
) -> Result[list[TradeReceipt], BatchFailure]:
    # Every item is attempted even after a failure: stopping at the first error
    # would leave the remaining positions open while reporting only one problem.
    succeeded: list[TradeReceipt] = []
    errors: list[TradeError] = []
    for item in items:
        # isinstance, not a match without a fallback: an action that broke the
        # Result contract fails loudly on `.value` instead of being skipped,
        # which would end in Ok([]), read as "all closed".
        result = action(item)
        if isinstance(result, Err):
            errors.append(replace(result.error, ticket=item.ticket))
        else:
            succeeded.append(result.value)
    if errors:
        return Err(BatchFailure(tuple(succeeded), tuple(errors)))
    return Ok(succeeded)


def with_magic(items: list[_T], magic: int | AnyMagic | None) -> list[_T]:
    if magic is None or magic is ANY_MAGIC:
        return items
    return [item for item in items if item.magic == magic]
